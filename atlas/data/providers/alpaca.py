"""Alpaca market data provider client."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from atlas.core.config import get_settings
from atlas.core.types import Symbol
from atlas.data.providers.base import BaseDataProvider, ProviderError

logger = logging.getLogger("atlas.data.providers.alpaca")


class AlpacaMarketDataProvider(BaseDataProvider):
    """Alpaca Market Data API v2 client for historical and daily bars."""

    DATA_BASE_URL = "https://data.alpaca.markets/v2"

    def __init__(
        self,
        api_key_id: str | None = None,
        api_secret: str | None = None,
        rate_limit_per_sec: float = 3.0,
        max_retries: int = 4,
        backoff_factor: float = 1.5,
        cache_dir: Path | str | None = None,
        timeout: float = 30.0,
        feed: str = "iex",
    ) -> None:
        super().__init__(
            name="alpaca",
            rate_limit_per_sec=rate_limit_per_sec,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            cache_dir=cache_dir,
            timeout=timeout,
        )
        settings = get_settings()
        self.api_key_id = api_key_id or settings.alpaca_api_key_id
        self.api_secret = api_secret or settings.alpaca_api_secret
        self.feed = feed

    def _get_headers(self) -> dict[str, str]:
        if not self.api_key_id or not self.api_secret:
            raise ProviderError(
                "Alpaca API credentials missing. Set ALPACA_API_KEY_ID and ALPACA_API_SECRET."
            )
        return {
            "APCA-API-KEY-ID": self.api_key_id,
            "APCA-API-SECRET-KEY": self.api_secret,
        }

    async def is_healthy(self) -> bool:
        """Check Alpaca API health with a simple bars query."""
        if not self.api_key_id or not self.api_secret:
            return False
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.DATA_BASE_URL}/stocks/SPY/bars"
                params = {"timeframe": "1Day", "limit": 1, "feed": self.feed}
                data = await self._request_with_retry(
                    client=client,
                    method="GET",
                    url=url,
                    params=params,
                    headers=self._get_headers(),
                )
                return isinstance(data, dict) and "bars" in data
        except Exception as e:
            logger.warning("Alpaca health check failed: %s", e)
            return False

    async def fetch_daily_bars(
        self,
        symbol: Symbol,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch daily raw bars for a symbol from Alpaca."""
        url = f"{self.DATA_BASE_URL}/stocks/{symbol}/bars"
        all_bars: list[dict[str, Any]] = []
        page_token: str | None = None

        cache_key = f"alpaca_bars_{symbol}_{start_date.isoformat()}_{end_date.isoformat()}"
        cached = self._read_cache(cache_key)
        if cached is not None and isinstance(cached, list):
            return cached

        async with httpx.AsyncClient() as client:
            while True:
                params: dict[str, Any] = {
                    "timeframe": "1Day",
                    "start": f"{start_date.isoformat()}T00:00:00Z",
                    "end": f"{end_date.isoformat()}T23:59:59Z",
                    "limit": 1000,
                    "adjustment": "raw",
                    "feed": self.feed,
                }
                if page_token:
                    params["page_token"] = page_token

                data = await self._request_with_retry(
                    client=client,
                    method="GET",
                    url=url,
                    params=params,
                    headers=self._get_headers(),
                )

                bars = data.get("bars") or []
                all_bars.extend(bars)

                page_token = data.get("next_page_token")
                if not page_token:
                    break

        if all_bars:
            self._write_cache(cache_key, all_bars)

        return all_bars

    async def fetch_corporate_actions(
        self,
        symbol: Symbol,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch corporate actions announcements from Alpaca."""
        url = f"{self.DATA_BASE_URL}/corporate_actions/announcements"
        params = {
            "ca_types": "dividend,split",
            "since": start_date.isoformat(),
            "until": end_date.isoformat(),
            "symbols": symbol,
        }
        cache_key = f"alpaca_ca_{symbol}_{start_date.isoformat()}_{end_date.isoformat()}"
        async with httpx.AsyncClient() as client:
            data = await self._request_with_retry(
                client=client,
                method="GET",
                url=url,
                params=params,
                headers=self._get_headers(),
                use_cache=True,
                cache_key=cache_key,
            )
            return data if isinstance(data, list) else []
