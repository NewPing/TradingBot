"""Tiingo market data provider client."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any, cast

import httpx

from atlas.core.config import get_settings
from atlas.core.types import Symbol
from atlas.data.providers.base import BaseDataProvider, ProviderError

logger = logging.getLogger("atlas.data.providers.tiingo")


class TiingoProvider(BaseDataProvider):
    """Tiingo REST API client for daily bars and corporate actions."""

    BASE_URL = "https://api.tiingo.com/tiingo"

    def __init__(
        self,
        api_key: str | None = None,
        rate_limit_per_sec: float = 5.0,
        max_retries: int = 4,
        backoff_factor: float = 1.5,
        cache_dir: Path | str | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(
            name="tiingo",
            rate_limit_per_sec=rate_limit_per_sec,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            cache_dir=cache_dir,
            timeout=timeout,
        )
        self.api_key = api_key or get_settings().tiingo_api_key

    def _get_headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ProviderError(
                "Tiingo API key is missing. Set TIINGO_API_KEY environment variable."
            )
        return {
            "Content-Type": "application/json",
            "Authorization": f"Token {self.api_key}",
        }

    async def is_healthy(self) -> bool:
        """Verify API key and connectivity with SPY metadata request."""
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.BASE_URL}/daily/SPY"
                data = await self._request_with_retry(
                    client=client,
                    method="GET",
                    url=url,
                    headers=self._get_headers(),
                )
                return isinstance(data, dict) and "ticker" in data
        except Exception as e:
            logger.warning("Tiingo healthcheck failed: %s", e)
            return False

    async def fetch_ticker_metadata(self, symbol: Symbol) -> dict[str, Any]:
        """Fetch metadata for a given symbol."""
        url = f"{self.BASE_URL}/daily/{symbol}"
        cache_key = f"tiingo_meta_{symbol}"
        async with httpx.AsyncClient() as client:
            return cast(
                dict[str, Any],
                await self._request_with_retry(
                    client=client,
                    method="GET",
                    url=url,
                    headers=self._get_headers(),
                    use_cache=True,
                    cache_key=cache_key,
                ),
            )

    async def fetch_daily_bars(
        self,
        symbol: Symbol,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch daily OHLCV bars from Tiingo."""
        url = f"{self.BASE_URL}/daily/{symbol}/prices"
        params = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "format": "json",
            "resampleFreq": "daily",
        }
        cache_key = f"tiingo_bars_{symbol}_{start_date.isoformat()}_{end_date.isoformat()}"
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
            if not isinstance(data, list):
                raise ProviderError(f"Unexpected response format from Tiingo for {symbol}: {data}")
            return data

    async def fetch_corporate_actions(
        self,
        symbol: Symbol,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Extract dividend and split corporate actions from Tiingo daily price bars."""
        bars = await self.fetch_daily_bars(symbol, start_date, end_date)
        actions: list[dict[str, Any]] = []

        for bar in bars:
            bar_date = bar.get("date", "").split("T")[0]
            div_cash = float(bar.get("divCash", 0.0) or 0.0)
            split_factor = float(bar.get("splitFactor", 1.0) or 1.0)

            if div_cash > 0.0:
                actions.append(
                    {
                        "symbol": symbol,
                        "ex_date": bar_date,
                        "action_type": "DIVIDEND",
                        "amount": div_cash,
                        "ratio": None,
                    }
                )

            if split_factor != 1.0 and split_factor > 0.0:
                actions.append(
                    {
                        "symbol": symbol,
                        "ex_date": bar_date,
                        "action_type": "SPLIT",
                        "amount": None,
                        "ratio": split_factor,
                    }
                )

        return actions
