"""Lookahead proofing, execution order-of-operations, and deterministic replay test suite."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import numpy as np
import polars as pl
import pytest

from atlas.backtest.engine import BacktestEngine
from atlas.core.clock import SimClock
from atlas.core.context import HistoricalMarketContext
from atlas.core.errors import LookaheadError
from atlas.core.types import Symbol
from atlas.strategies.spec import StrategySpec


def generate_synthetic_dataset(symbols: list[Symbol], start_d: date, end_d: date) -> pl.DataFrame:
    """Generate multi-symbol daily OHLCV dataset for deterministic backtest testing."""
    cur = start_d
    dates: list[datetime] = []
    while cur <= end_d:
        if cur.weekday() < 5:  # Monday to Friday
            dates.append(datetime.combine(cur, datetime.min.time(), tzinfo=UTC))
        cur += timedelta(days=1)

    records: list[dict[str, object]] = []
    for sym_idx, sym in enumerate(symbols):
        base_px = 100.0 + sym_idx * 50.0
        for i, dt in enumerate(dates):
            # Deterministic price drift
            px = base_px * (1.0 + 0.0005 * i + 0.02 * np.sin(i / 10.0 + sym_idx))
            records.append(
                {
                    "symbol": str(sym),
                    "ts": dt,
                    "open": px - 0.5,
                    "high": px + 1.5,
                    "low": px - 1.5,
                    "close": px,
                    "volume": 2_000_000,
                    "adj_factor": 1.0,
                }
            )

    return pl.DataFrame(records)


def test_market_context_zero_lookahead_enforcement() -> None:
    symbols = [Symbol("AAPL")]
    start_d = date(2021, 1, 1)
    end_d = date(2021, 1, 31)
    df = generate_synthetic_dataset(symbols, start_d, end_d)

    # Set clock to mid-month Jan 15
    clock_dt = datetime(2021, 1, 15, 21, 0, tzinfo=UTC)
    clock = SimClock(clock_dt)
    ctx = HistoricalMarketContext(clock=clock, bars_df=df)

    bars = ctx.bars(Symbol("AAPL"), lookback=100)
    assert not bars.is_empty()
    # Invariant: NO row returned may have timestamp > clock_dt
    max_ts = bars["ts"].max()
    assert max_ts <= clock_dt

    # Asserting future access raises LookaheadError
    with pytest.raises(LookaheadError):
        future_ts = clock_dt + timedelta(days=5)
        ctx._assert_no_future_access(future_ts)


def test_deterministic_backtest_replay() -> None:
    symbols = [Symbol("AAPL"), Symbol("MSFT"), Symbol("GOOG"), Symbol("AMZN"), Symbol("NVDA")]
    start_d = date(2021, 1, 1)
    end_d = date(2021, 6, 30)
    df = generate_synthetic_dataset(symbols, start_d, end_d)

    spec = StrategySpec.from_yaml("strategies/core_trend_v1.yaml")

    engine1 = BacktestEngine(spec=spec, data=df)
    result1 = engine1.run(start_date=start_d, end_date=end_d)

    engine2 = BacktestEngine(spec=spec, data=df)
    result2 = engine2.run(start_date=start_d, end_date=end_d)

    # Invariant: Two runs on the exact same spec and data MUST produce identical results
    assert result1.final_equity == result2.final_equity
    assert result1.metrics.total_return == result2.metrics.total_return
    assert result1.metrics.sharpe_ratio == result2.metrics.sharpe_ratio
    assert len(result1.fills) == len(result2.fills)
    assert len(result1.equity_curve) == len(result2.equity_curve)
    for s1, s2 in zip(result1.equity_curve, result2.equity_curve, strict=True):
        assert s1.equity == s2.equity
        assert s1.cash == s2.cash

    eq_df = result1.equity_dataframe()
    assert not eq_df.is_empty()


def test_buy_hold_spy_baseline() -> None:
    symbols = [Symbol("SPY")]
    start_d = date(2021, 1, 1)
    end_d = date(2021, 6, 30)
    df = generate_synthetic_dataset(symbols, start_d, end_d)

    spec = StrategySpec.from_yaml("strategies/buy_hold_spy.yaml")
    engine = BacktestEngine(spec=spec, data=df)
    result = engine.run(start_date=start_d, end_date=end_d)

    assert result.metrics.total_trades >= 1
    assert result.final_equity.amount > Decimal("0")


def test_swing_meanrev_baseline() -> None:
    symbols = [Symbol("AAPL"), Symbol("MSFT"), Symbol("TSLA")]
    start_d = date(2021, 1, 1)
    end_d = date(2021, 6, 30)
    df = generate_synthetic_dataset(symbols, start_d, end_d)

    spec = StrategySpec.from_yaml("strategies/swing_meanrev_v1.yaml")
    engine = BacktestEngine(spec=spec, data=df)
    result = engine.run(start_date=start_d, end_date=end_d, benchmark_symbol=Symbol("AAPL"))

    assert len(result.equity_curve) > 0
    assert result.final_equity.amount > Decimal("0")
