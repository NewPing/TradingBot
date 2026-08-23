"""Unit tests for MarketContext lookahead enforcement and HistoricalMarketContext."""

from datetime import UTC, datetime
from decimal import Decimal

import polars as pl
import pytest

from atlas.core.clock import SimClock
from atlas.core.context import BaseMarketContext, HistoricalMarketContext
from atlas.core.errors import LookaheadError
from atlas.core.types import Symbol


def test_base_context_lookahead_detection() -> None:
    current_time = datetime(2025, 1, 15, 16, 0, tzinfo=UTC)
    future_time = datetime(2025, 1, 16, 9, 30, tzinfo=UTC)
    past_time = datetime(2025, 1, 14, 16, 0, tzinfo=UTC)

    clock = SimClock(current_time)
    ctx = BaseMarketContext(clock)

    assert ctx.now == current_time

    # Past time is allowed
    ctx._assert_no_future_access(past_time)

    # Current time is allowed
    ctx._assert_no_future_access(current_time)

    # Future time must raise LookaheadError
    with pytest.raises(LookaheadError, match="in the future relative to current time"):
        ctx._assert_no_future_access(future_time)


def test_historical_market_context_operations() -> None:
    t0 = datetime(2021, 1, 4, 21, 0, tzinfo=UTC)
    t1 = datetime(2021, 1, 5, 21, 0, tzinfo=UTC)
    t2 = datetime(2021, 1, 6, 21, 0, tzinfo=UTC)

    df = pl.DataFrame(
        {
            "symbol": ["AAPL", "AAPL", "AAPL", "MSFT", "MSFT", "MSFT"],
            "ts": [t0, t1, t2, t0, t1, t2],
            "open": [100.0, 101.0, 102.0, 200.0, 201.0, 202.0],
            "high": [102.0, 103.0, 104.0, 202.0, 203.0, 204.0],
            "low": [99.0, 100.0, 101.0, 199.0, 200.0, 201.0],
            "close": [101.0, 102.0, 103.0, 201.0, 202.0, 203.0],
            "volume": [1000, 1100, 1200, 2000, 2100, 2200],
            "adj_factor": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            "vwap": [101.0, 102.0, 103.0, 201.0, 202.0, 203.0],
            "source": ["test"] * 6,
            "resolution": ["1d"] * 6,
        }
    )

    clock = SimClock(t1)
    universe_map = {t1: [Symbol("AAPL"), Symbol("MSFT")]}
    ctx = HistoricalMarketContext(clock=clock, bars_df=df, universe_map=universe_map)

    # Bars at t1 should return max 2 rows (t0 and t1)
    bars = ctx.bars(Symbol("AAPL"), lookback=10)
    assert len(bars) == 2
    assert bars["ts"].max() == t1

    # Lookback validation
    with pytest.raises(ValueError):
        ctx.bars(Symbol("AAPL"), lookback=0)

    # Missing symbol
    assert ctx.bars(Symbol("NONEXISTENT"), lookback=5).is_empty()

    # Latest bar
    latest_bar = ctx.latest(Symbol("AAPL"))
    assert latest_bar is not None
    assert latest_bar.ts == t1
    assert latest_bar.close == Decimal("102.0")

    assert ctx.latest(Symbol("NONEXISTENT")) is None

    # Universe
    u = ctx.universe()
    assert u == [Symbol("AAPL"), Symbol("MSFT")]

    # Protocol defaults
    assert ctx.fundamentals(Symbol("AAPL")) is None
    assert ctx.news(Symbol("AAPL")) == []
    assert isinstance(ctx.calendar_is_open(), bool)


def test_historical_market_context_with_dict() -> None:
    t0 = datetime(2021, 1, 4, 21, 0, tzinfo=UTC)
    t1 = datetime(2021, 1, 5, 21, 0, tzinfo=UTC)

    df_aapl = pl.DataFrame(
        {
            "ts": [t0, t1],
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [1000, 1100],
        }
    )

    clock = SimClock(t0)
    ctx = HistoricalMarketContext(clock=clock, bars_df={Symbol("AAPL"): df_aapl})

    assert ctx.universe() == [Symbol("AAPL")]
    bars = ctx.bars(Symbol("AAPL"), lookback=5)
    assert len(bars) == 1
