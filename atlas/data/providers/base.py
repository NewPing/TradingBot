"""Base data provider interface with rate limiting, retry backoff, and caching."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from atlas.core.errors import DataError
from atlas.core.types import Symbol

logger = logging.getLogger("atlas.data.providers")


class ProviderError(DataError):
    """Base error raised when a data provider fails."""

    pass


class RateLimitError(ProviderError):
    """Raised when rate limit is exceeded and all retries exhausted."""

    pass


class AuthenticationError(ProviderError):
    """Raised on invalid API credentials."""

    pass


class ResourceNotFoundError(ProviderError):
    """Raised when symbol or dataset is not found."""

    pass


class TokenBucketLimiter:
    """Async token-bucket rate limiter for API requests."""

    def __init__(self, rate_per_sec: float, capacity: float | None = None) -> None:
        self.rate = float(rate_per_sec)
        self.capacity = float(capacity if capacity is not None else rate_per_sec)
        self.tokens = self.capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.last_update = now

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return

                # Sleep until enough tokens are replenished
                needed = tokens - self.tokens
                wait_time = needed / self.rate
                await asyncio.sleep(wait_time)


class BaseDataProvider(ABC):
    """Abstract base class for all market data providers."""

    def __init__(
        self,
        name: str,
        rate_limit_per_sec: float = 5.0,
        max_retries: int = 4,
        backoff_factor: float = 1.5,
        cache_dir: Path | str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.name = name
        self.rate_limiter = TokenBucketLimiter(rate_limit_per_sec)
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.timeout = timeout
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, key: str) -> Path | None:
        if not self.cache_dir:
            return None
        safe_key = "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in key)
        return self.cache_dir / f"{safe_key}.json"

    def _read_cache(self, key: str) -> Any | None:
        path = self._get_cache_path(key)
        if path and path.is_file():
            try:
                with path.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Failed to read cache at %s: %s", path, e)
        return None

    def _write_cache(self, key: str, data: Any) -> None:
        path = self._get_cache_path(key)
        if path:
            try:
                with path.open("w", encoding="utf-8") as f:
                    json.dump(data, f)
            except Exception as e:
                logger.warning("Failed to write cache at %s: %s", path, e)

    async def _request_with_retry(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        use_cache: bool = False,
        cache_key: str | None = None,
    ) -> Any:
        if use_cache and cache_key:
            cached = self._read_cache(cache_key)
            if cached is not None:
                return cached

        retries = 0
        while True:
            await self.rate_limiter.acquire()
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    data = response.json()
                    if use_cache and cache_key:
                        self._write_cache(cache_key, data)
                    return data
                elif response.status_code == 404:
                    raise ResourceNotFoundError(f"Resource not found: {url}")
                elif response.status_code in (401, 403):
                    raise AuthenticationError(
                        f"Authentication failed for {self.name}: {response.text}"
                    )
                elif response.status_code == 429:
                    retries += 1
                    if retries > self.max_retries:
                        raise RateLimitError(
                            f"Rate limit exceeded for {self.name} after {retries} retries"
                        )
                    # Check Retry-After header if present
                    retry_after = response.headers.get("Retry-After")
                    sleep_time = (
                        float(retry_after)
                        if retry_after and retry_after.isdigit()
                        else (self.backoff_factor**retries) + random.uniform(0.1, 0.5)
                    )
                    logger.warning(
                        "Rate limit hit for %s, backing off %.2fs", self.name, sleep_time
                    )
                    await asyncio.sleep(sleep_time)
                elif response.status_code >= 500:
                    retries += 1
                    if retries > self.max_retries:
                        raise ProviderError(
                            f"Server error {response.status_code} for {self.name} after {retries} retries"
                        )
                    sleep_time = (self.backoff_factor**retries) + random.uniform(0.1, 0.5)
                    logger.warning(
                        "Server error %d for %s, retrying in %.2fs",
                        response.status_code,
                        self.name,
                        sleep_time,
                    )
                    await asyncio.sleep(sleep_time)
                else:
                    response.raise_for_status()

            except (httpx.RequestError, httpx.TimeoutException) as exc:
                retries += 1
                if retries > self.max_retries:
                    raise ProviderError(
                        f"Network error communicating with {self.name}: {exc}"
                    ) from exc
                sleep_time = (self.backoff_factor**retries) + random.uniform(0.1, 0.5)
                logger.warning(
                    "Network failure for %s (%s), retrying in %.2fs", self.name, exc, sleep_time
                )
                await asyncio.sleep(sleep_time)

    @abstractmethod
    async def fetch_daily_bars(
        self,
        symbol: Symbol,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch raw daily bars between start_date and end_date (inclusive)."""
        pass

    @abstractmethod
    async def fetch_corporate_actions(
        self,
        symbol: Symbol,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch stock splits and dividend actions."""
        pass

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Ping provider API to verify connectivity and credentials."""
        pass
