"""Point-in-time MarketContext gating all data access to prevent lookahead."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol

import polars as pl

from atlas.core.clock import Clock
from atlas.core.errors import LookaheadError
from atlas.core.types import Bar, FundamentalSnapshot, NewsItem, Symbol


class MarketContext(Protocol):
    """Point-in-time interface for strategy and signal data reads.

    Guarantees that all queries only see data strictly <= clock.now.
    """

    @property
    def now(self) -> datetime:
        """Current simulation or real timestamp (tz-aware UTC)."""
        ...

    def bars(
        self,
        symbol: Symbol,
        lookback: int,
        resolution: str = "1d",
        adjusted: bool = False,
    ) -> pl.DataFrame:
        """Return historical bars up to lookback rows with timestamp <= clock.now."""
        ...

    def latest(self, symbol: Symbol, resolution: str = "1d") -> Bar | None:
        """Return the most recent bar with timestamp <= clock.now."""
        ...

    def universe(self) -> list[Symbol]:
        """Return point-in-time universe of tradable symbols at clock.now."""
        ...

    def fundamentals(self, symbol: Symbol) -> FundamentalSnapshot | None:
        """Return latest fundamental filing with filing_date <= clock.now."""
        ...

    def upcoming_earnings(self, symbol: Symbol, lookahead_days: int = 5) -> datetime | None:
        """Return next scheduled earnings announcement within lookahead_days from clock.now."""
        ...

    def news(self, symbol: Symbol, lookback_hours: int = 24) -> list[NewsItem]:
        """Return published news items with ts <= clock.now."""
        ...

    def calendar_is_open(self) -> bool:
        """Return True if exchange is open at clock.now."""
        ...


class BaseMarketContext:
    """Base MarketContext enforcing clock timestamp gating."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    @property
    def now(self) -> datetime:
        return self._clock.now

    def _assert_no_future_access(self, requested_ts: datetime) -> None:
        if requested_ts > self.now:
            raise LookaheadError(
                f"Requested timestamp {requested_ts} is in the future relative to current time {self.now}"
            )


class HistoricalMarketContext(BaseMarketContext):
    """Historical MarketContext backed by in-memory Polars DataFrame(s).

    Strictly restricts all data access to timestamps <= clock.now.
    """

    def __init__(
        self,
        clock: Clock,
        bars_df: pl.DataFrame | dict[Symbol, pl.DataFrame],
        universe_map: dict[datetime, list[Symbol]] | None = None,
        fundamentals_map: dict[Symbol, list[FundamentalSnapshot]] | None = None,
        earnings_calendar_map: dict[Symbol, list[datetime]] | None = None,
        news_map: dict[Symbol, list[NewsItem]] | None = None,
    ) -> None:
        super().__init__(clock)
        self._universe_map = universe_map or {}
        self._fundamentals_map = fundamentals_map or {}
        self._earnings_calendar_map = earnings_calendar_map or {}
        self._news_map = news_map or {}
        self._bars_by_symbol: dict[Symbol, pl.DataFrame] = {}

        if isinstance(bars_df, dict):
            for sym, df in bars_df.items():
                if not df.is_empty():
                    sorted_df = df.sort("ts")
                    self._bars_by_symbol[Symbol(str(sym))] = sorted_df
        else:
            if not bars_df.is_empty():
                for sym_val in bars_df["symbol"].unique().to_list():
                    sub_df = bars_df.filter(pl.col("symbol") == sym_val).sort("ts")
                    self._bars_by_symbol[Symbol(str(sym_val))] = sub_df

    def bars(
        self,
        symbol: Symbol,
        lookback: int,
        resolution: str = "1d",
        adjusted: bool = False,
    ) -> pl.DataFrame:
        """Return historical bars up to lookback rows with timestamp <= clock.now."""
        _ = resolution
        if lookback <= 0:
            raise ValueError(f"Lookback must be positive: {lookback}")

        df = self._bars_by_symbol.get(symbol)
        if df is None or df.is_empty():
            return pl.DataFrame()

        current_now = self.now
        # Filter strictly <= current_now
        filtered = df.filter(pl.col("ts") <= current_now)
        if filtered.is_empty():
            return pl.DataFrame()

        res_df = filtered.tail(lookback) if len(filtered) > lookback else filtered

        if adjusted and "adj_factor" in res_df.columns:
            return res_df.with_columns(
                [
                    (pl.col("open") * pl.col("adj_factor")).alias("open"),
                    (pl.col("high") * pl.col("adj_factor")).alias("high"),
                    (pl.col("low") * pl.col("adj_factor")).alias("low"),
                    (pl.col("close") * pl.col("adj_factor")).alias("close"),
                ]
            )
        return res_df

    def latest(self, symbol: Symbol, resolution: str = "1d") -> Bar | None:
        """Return the most recent bar with timestamp <= clock.now."""
        df = self.bars(symbol, lookback=1, resolution=resolution)
        if df.is_empty():
            return None

        row = df.row(0, named=True)
        return Bar(
            symbol=symbol,
            ts=row["ts"],
            open=Decimal(str(row["open"])),
            high=Decimal(str(row["high"])),
            low=Decimal(str(row["low"])),
            close=Decimal(str(row["close"])),
            volume=int(row["volume"]),
            adj_factor=Decimal(str(row.get("adj_factor", "1.0"))),
            vwap=Decimal(str(row["vwap"])) if row.get("vwap") is not None else None,
            source=str(row.get("source", "historical")),
            resolution=str(row.get("resolution", resolution)),
        )

    def universe(self) -> list[Symbol]:
        """Return point-in-time universe of tradable symbols at clock.now."""
        current_now = self.now
        if self._universe_map:
            # Find the latest universe snapshot timestamp <= current_now
            valid_dates = [ts for ts in self._universe_map if ts <= current_now]
            if valid_dates:
                latest_ts = max(valid_dates)
                return self._universe_map[latest_ts]

        # Default fallback: all symbols that have at least one bar <= current_now
        active_symbols: list[Symbol] = []
        for sym, df in self._bars_by_symbol.items():
            if not df.filter(pl.col("ts") <= current_now).is_empty():
                active_symbols.append(sym)
        return sorted(active_symbols)

    def fundamentals(self, symbol: Symbol) -> FundamentalSnapshot | None:
        """Return latest fundamental filing with filing_date <= clock.now."""
        filings = self._fundamentals_map.get(symbol)
        if not filings:
            return None

        current_now = self.now
        valid_filings = [f for f in filings if f.filing_date <= current_now]
        if not valid_filings:
            return None

        return max(valid_filings, key=lambda f: f.filing_date)

    def upcoming_earnings(self, symbol: Symbol, lookahead_days: int = 5) -> datetime | None:
        """Return next scheduled earnings announcement within lookahead_days from clock.now."""
        events = self._earnings_calendar_map.get(symbol)
        if not events:
            return None

        current_now = self.now
        window_end = current_now + timedelta(days=lookahead_days)
        upcoming = [dt for dt in events if current_now <= dt <= window_end]
        if not upcoming:
            return None

        return min(upcoming)

    def news(self, symbol: Symbol, lookback_hours: int = 24) -> list[NewsItem]:
        """Return published news items with ts <= clock.now within lookback window."""
        items = self._news_map.get(symbol, [])
        if not items:
            return []

        current_now = self.now
        cutoff = current_now - timedelta(hours=lookback_hours)

        valid_items = [item for item in items if cutoff <= item.ts <= current_now]
        valid_items.sort(key=lambda x: x.ts, reverse=True)
        return valid_items

    def calendar_is_open(self) -> bool:
        """Return True if exchange is open at clock.now."""
        from atlas.core.calendar import is_trading_day

        return is_trading_day(self.now)
