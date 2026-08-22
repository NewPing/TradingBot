"""Yahoo Finance provider client (fallback & benchmark data)."""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from pathlib import Path
from typing import Any, cast

from atlas.core.types import Symbol
from atlas.data.providers.base import BaseDataProvider, ProviderError

logger = logging.getLogger("atlas.data.providers.yfinance")


class YFinanceProvider(BaseDataProvider):
    """yfinance market data wrapper for fallback and benchmark index data."""

    def __init__(
        self,
        rate_limit_per_sec: float = 2.0,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        cache_dir: Path | str | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(
            name="yfinance",
            rate_limit_per_sec=rate_limit_per_sec,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            cache_dir=cache_dir,
            timeout=timeout,
        )

    async def is_healthy(self) -> bool:
        """Check yfinance connectivity with a small SPY request."""
        try:
            bars = await self.fetch_daily_bars(Symbol("SPY"), date.today(), date.today())
            return isinstance(bars, list)
        except Exception as e:
            logger.warning("yfinance healthcheck failed: %s", e)
            return False

    def _sync_fetch_bars(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        try:
            import yfinance as yf  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ProviderError("yfinance is not installed in the environment.") from exc

        ticker = yf.Ticker(symbol)
        df = ticker.history(
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            interval="1d",
            auto_adjust=False,
            actions=True,
        )
        if df.empty:
            return []

        results: list[dict[str, Any]] = []
        for index_ts, row in df.iterrows():
            ts_str = index_ts.isoformat() if hasattr(index_ts, "isoformat") else str(index_ts)
            results.append(
                {
                    "date": ts_str,
                    "open": float(row.get("Open", 0.0)),
                    "high": float(row.get("High", 0.0)),
                    "low": float(row.get("Low", 0.0)),
                    "close": float(row.get("Close", 0.0)),
                    "volume": int(row.get("Volume", 0)),
                    "adj_close": float(row.get("Adj Close", row.get("Close", 0.0))),
                    "dividends": float(row.get("Dividends", 0.0)),
                    "stock_splits": float(row.get("Stock Splits", 0.0)),
                }
            )
        return results

    async def fetch_daily_bars(
        self,
        symbol: Symbol,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch daily bars from yfinance."""
        await self.rate_limiter.acquire()
        cache_key = f"yf_bars_{symbol}_{start_date.isoformat()}_{end_date.isoformat()}"
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cast(list[dict[str, Any]], cached)

        try:
            bars = await asyncio.to_thread(self._sync_fetch_bars, str(symbol), start_date, end_date)
            if bars:
                self._write_cache(cache_key, bars)
            return bars
        except Exception as e:
            raise ProviderError(f"yfinance fetch failed for {symbol}: {e}") from e

    async def fetch_corporate_actions(
        self,
        symbol: Symbol,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch dividends and splits from yfinance."""
        bars = await self.fetch_daily_bars(symbol, start_date, end_date)
        actions: list[dict[str, Any]] = []

        for bar in bars:
            bar_date = bar.get("date", "").split("T")[0]
            div = float(bar.get("dividends", 0.0) or 0.0)
            split = float(bar.get("stock_splits", 0.0) or 0.0)

            if div > 0:
                actions.append(
                    {
                        "symbol": symbol,
                        "ex_date": bar_date,
                        "action_type": "DIVIDEND",
                        "amount": div,
                        "ratio": None,
                    }
                )
            if split > 0 and split != 1.0:
                actions.append(
                    {
                        "symbol": symbol,
                        "ex_date": bar_date,
                        "action_type": "SPLIT",
                        "amount": None,
                        "ratio": split,
                    }
                )

        return actions
