"""Tests strictly verifying that fundamental filings enforce Point-in-Time discipline with zero lookahead."""

from __future__ import annotations

from datetime import UTC, datetime

import polars as pl

from atlas.core.clock import SimClock
from atlas.core.context import HistoricalMarketContext
from atlas.core.types import FundamentalSnapshot, Symbol


def test_fundamentals_point_in_time_lookahead_prevention() -> None:
    # Filing 1: Q1 filing published on 2026-04-25
    f1 = FundamentalSnapshot(
        symbol=Symbol("AAPL"),
        report_date=datetime(2026, 3, 31, tzinfo=UTC),
        filing_date=datetime(2026, 4, 25, 20, 0, tzinfo=UTC),
        period="Q1",
        metrics={"roic": 0.30, "revenue": 90000.0},
    )

    # Filing 2: Q2 filing published on 2026-07-28
    f2 = FundamentalSnapshot(
        symbol=Symbol("AAPL"),
        report_date=datetime(2026, 6, 30, tzinfo=UTC),
        filing_date=datetime(2026, 7, 28, 20, 0, tzinfo=UTC),
        period="Q2",
        metrics={"roic": 0.45, "revenue": 110000.0},
    )

    # State 1: Before Q1 filing date -> None
    clock = SimClock(datetime(2026, 4, 20, 12, 0, tzinfo=UTC))
    ctx = HistoricalMarketContext(
        clock=clock,
        bars_df=pl.DataFrame(),
        fundamentals_map={Symbol("AAPL"): [f1, f2]},
    )
    assert ctx.fundamentals(Symbol("AAPL")) is None

    # State 2: After Q1 filing date, but before Q2 filing date -> Returns Q1
    # Even though Q2 report_date (2026-06-30) has passed on 2026-07-15, filing_date (2026-07-28) is in the future!
    clock.set(datetime(2026, 7, 15, 12, 0, tzinfo=UTC))
    snap = ctx.fundamentals(Symbol("AAPL"))
    assert snap is not None
    assert snap.period == "Q1"
    assert snap.metrics["roic"] == 0.30

    # State 3: After Q2 filing date -> Returns Q2
    clock.set(datetime(2026, 7, 29, 12, 0, tzinfo=UTC))
    snap_after = ctx.fundamentals(Symbol("AAPL"))
    assert snap_after is not None
    assert snap_after.period == "Q2"
    assert snap_after.metrics["roic"] == 0.45


def test_upcoming_earnings_lookahead_window() -> None:
    earnings_dt = datetime(2026, 8, 25, 20, 0, tzinfo=UTC)

    clock = SimClock(datetime(2026, 8, 20, 10, 0, tzinfo=UTC))
    ctx = HistoricalMarketContext(
        clock=clock,
        bars_df=pl.DataFrame(),
        earnings_calendar_map={Symbol("NVDA"): [earnings_dt]},
    )

    # Event is 5 days away:
    # Within 7 day lookahead -> Found
    assert ctx.upcoming_earnings(Symbol("NVDA"), lookahead_days=7) == earnings_dt
    # Within 2 day lookahead -> None
    assert ctx.upcoming_earnings(Symbol("NVDA"), lookahead_days=2) is None

    # Advance clock to 2026-08-24 (1 day away)
    clock.set(datetime(2026, 8, 24, 10, 0, tzinfo=UTC))
    assert ctx.upcoming_earnings(Symbol("NVDA"), lookahead_days=2) == earnings_dt
