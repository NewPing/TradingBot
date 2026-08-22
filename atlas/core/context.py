"""Point-in-time MarketContext gating all data access to prevent lookahead."""

from __future__ import annotations

from datetime import datetime
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

    def bars(self, symbol: Symbol, lookback: int, resolution: str = "1d") -> pl.DataFrame:
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
