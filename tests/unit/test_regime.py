"""Unit tests for Phase 5 Market Regime Detection and 4-Quadrant Classification."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import polars as pl

from atlas.core.clock import SimClock
from atlas.core.context import HistoricalMarketContext
from atlas.core.types import Symbol
from atlas.signals.regime import (
    MarketQuadrant,
    RegimeDetector,
    TrendRegime,
    VolatilityRegime,
)


def _build_context_with_trend(
    is_bull: bool = True, high_vol: bool = False
) -> HistoricalMarketContext:
    n = 260
    rows = []
    price = 100.0
    for i in range(n):
        ts = datetime(2020, 1, 1, tzinfo=UTC) + pd.Timedelta(days=i)
        step = 0.005 if is_bull else -0.005
        vol = 0.03 if high_vol else 0.005
        price = price * (1.0 + step + (vol if i % 2 == 0 else -vol))
        rows.append(
            {
                "symbol": "SPY",
                "ts": ts,
                "open": price * 0.999,
                "high": price * 1.002,
                "low": price * 0.998,
                "close": price,
                "volume": 50_000_000,
            }
        )
    df_pl = pl.DataFrame(rows)
    clock = SimClock(rows[-1]["ts"])
    return HistoricalMarketContext(
        clock=clock,
        bars_df={Symbol("SPY"): df_pl},
    )


def test_regime_classification_bull_low_vol() -> None:
    ctx = _build_context_with_trend(is_bull=True, high_vol=False)
    detector = RegimeDetector(default_benchmark="SPY")
    state = detector.classify(ctx, benchmark=Symbol("SPY"))

    assert state.trend == TrendRegime.BULL
    assert state.volatility == VolatilityRegime.LOW_VOL
    assert state.quadrant == MarketQuadrant.BULL_LOW_VOL
    assert state.confidence > 0.5
    assert len(state.rationale) > 10


def test_regime_classification_bear_high_vol() -> None:
    ctx = _build_context_with_trend(is_bull=False, high_vol=True)
    detector = RegimeDetector(default_benchmark="SPY")
    state = detector.classify(ctx, benchmark=Symbol("SPY"))

    assert state.trend == TrendRegime.BEAR
    assert state.volatility == VolatilityRegime.HIGH_VOL
    assert state.quadrant == MarketQuadrant.BEAR_HIGH_VOL
    assert state.confidence > 0.5


def test_regime_insufficient_warmup() -> None:
    clock = SimClock(datetime(2020, 1, 1, tzinfo=UTC))
    ctx = HistoricalMarketContext(clock=clock, bars_df=pl.DataFrame())
    detector = RegimeDetector(default_benchmark="SPY")
    state = detector.classify(ctx, benchmark=Symbol("SPY"))

    assert state.trend == TrendRegime.SIDEWAYS
    assert state.quadrant == MarketQuadrant.SIDEWAYS_NORMAL
    assert "Insufficient" in state.rationale
