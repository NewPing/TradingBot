"""Unit tests for L1 technical indicators and signal providers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl

from atlas.core.clock import SimClock
from atlas.core.context import HistoricalMarketContext
from atlas.core.types import Signal, SignalLayer, Symbol
from atlas.signals.aggregator import WeightedConfidenceAggregator
from atlas.signals.indicators import (
    compute_52w_position,
    compute_atr,
    compute_bollinger_bands,
    compute_ema,
    compute_macd,
    compute_realized_volatility,
    compute_rsi,
    compute_sma,
    compute_volume_zscore,
)
from atlas.signals.l1_technical import (
    BollingerSignalProvider,
    FiftyTwoWeekSignalProvider,
    MacdSignalProvider,
    MomentumSignalProvider,
    RsiSignalProvider,
    TrendFilterSignalProvider,
    VolumeZScoreSignalProvider,
)


def test_pure_indicators() -> None:
    # SMA
    arr = np.array([10, 20, 30, 40, 50], dtype=np.float64)
    assert compute_sma(arr, 3) == 40.0
    assert compute_sma(arr, 10) is None

    # EMA
    assert compute_ema(arr, 3) is not None

    # RSI on monotone increasing -> 100
    inc_arr = np.array(
        [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25], dtype=np.float64
    )
    rsi = compute_rsi(inc_arr, 14)
    assert rsi is not None and rsi > 90.0

    # MACD
    macd = compute_macd(inc_arr, fast_period=5, slow_period=10, signal_period=3)
    assert macd is not None
    assert len(macd) == 3

    # ATR
    highs = np.array([12, 13, 14, 15, 16], dtype=np.float64)
    lows = np.array([9, 10, 11, 12, 13], dtype=np.float64)
    closes = np.array([11, 12, 13, 14, 15], dtype=np.float64)
    atr = compute_atr(highs, lows, closes, 3)
    assert atr is not None and atr > 0.0

    # Bollinger Bands
    bb = compute_bollinger_bands(arr, 5)
    assert bb is not None
    mid, up, lo, pct_b = bb
    assert mid == 30.0
    assert up > mid > lo

    # 52w position
    pos52 = compute_52w_position(arr, 5)
    assert pos52 == 1.0  # Last value is highest

    # Realized Vol
    vol = compute_realized_volatility(inc_arr, period=10)
    assert vol is not None and vol > 0.0

    # Volume Z-Score
    vols = np.array([100, 100, 100, 100, 200], dtype=np.float64)
    vz = compute_volume_zscore(vols, 5)
    assert vz is not None and vz > 0.0


def make_test_market_context(symbol: Symbol, n_bars: int = 300) -> HistoricalMarketContext:
    start_dt = datetime(2020, 1, 1, 21, 0, tzinfo=UTC)
    dates = [start_dt + timedelta(days=i) for i in range(n_bars)]

    # Generate synthetic upward trend
    base = 100.0
    prices = [base + i * 0.5 + np.sin(i / 5.0) * 2.0 for i in range(n_bars)]

    df = pl.DataFrame(
        {
            "symbol": [str(symbol)] * n_bars,
            "ts": dates,
            "open": [p - 0.2 for p in prices],
            "high": [p + 1.0 for p in prices],
            "low": [p - 1.0 for p in prices],
            "close": prices,
            "volume": [1_000_000 + i * 1000 for i in range(n_bars)],
            "adj_factor": [1.0] * n_bars,
        }
    )

    clock = SimClock(dates[-1])
    return HistoricalMarketContext(clock=clock, bars_df=df)


def test_l1_signal_providers_evaluation() -> None:
    sym = Symbol("MSFT")
    ctx = make_test_market_context(sym, n_bars=300)

    # 1. Trend Filter (SMA & EMA)
    trend_p = TrendFilterSignalProvider(ma_period=200, ma_type="sma")
    sig_trend = trend_p.evaluate(ctx, sym)
    assert sig_trend is not None
    assert sig_trend.layer == SignalLayer.L1_TECHNICAL
    assert -1.0 <= sig_trend.score <= 1.0
    assert 0.0 <= sig_trend.confidence <= 1.0

    trend_ema = TrendFilterSignalProvider(ma_period=50, ma_type="ema")
    assert trend_ema.evaluate(ctx, sym) is not None

    # 2. Momentum
    mom_p = MomentumSignalProvider(lookback=252, skip=21)
    sig_mom = mom_p.evaluate(ctx, sym)
    assert sig_mom is not None
    assert sig_mom.score > 0.0  # Synthetic series is up-trending

    # 3. RSI (mean reversion & trend)
    rsi_mr = RsiSignalProvider(period=2, mode="mean_reversion")
    assert rsi_mr.evaluate(ctx, sym) is not None
    rsi_tr = RsiSignalProvider(period=14, mode="trend")
    assert rsi_tr.evaluate(ctx, sym) is not None

    # 4. Bollinger (mean reversion & breakout)
    bb_p = BollingerSignalProvider(period=20, mode="mean_reversion")
    assert bb_p.evaluate(ctx, sym) is not None
    bb_bo = BollingerSignalProvider(period=20, mode="breakout")
    assert bb_bo.evaluate(ctx, sym) is not None

    # 5. 52-week position
    f52_p = FiftyTwoWeekSignalProvider(period=252)
    sig_52 = f52_p.evaluate(ctx, sym)
    assert sig_52 is not None

    # 6. MACD
    macd_p = MacdSignalProvider(fast_period=12, slow_period=26, signal_period=9)
    assert macd_p.evaluate(ctx, sym) is not None

    # 7. Volume Z-score
    vz_p = VolumeZScoreSignalProvider(period=20)
    assert vz_p.evaluate(ctx, sym) is not None


def test_weighted_confidence_aggregator() -> None:
    now_ts = datetime(2022, 1, 3, 21, 0, tzinfo=UTC)
    sym = Symbol("NVDA")

    sig1 = Signal(
        provider="l1_trend",
        layer=SignalLayer.L1_TECHNICAL,
        symbol=sym,
        ts=now_ts,
        score=1.0,
        confidence=0.8,
    )
    sig2 = Signal(
        provider="l1_momentum",
        layer=SignalLayer.L1_TECHNICAL,
        symbol=sym,
        ts=now_ts,
        score=0.5,
        confidence=0.6,
    )

    agg = WeightedConfidenceAggregator(
        min_confidence=0.3, weights={"l1_trend": 0.5, "l1_momentum": 0.5}
    )
    composite = agg.combine([sig1, sig2], now_ts, sym)

    assert composite is not None
    assert composite.symbol == sym
    assert composite.score > 0.0
    assert composite.confidence >= 0.3

    # Test confidence gating / abstention
    low_conf_sig = Signal(
        provider="l1_trend",
        layer=SignalLayer.L1_TECHNICAL,
        symbol=sym,
        ts=now_ts,
        score=1.0,
        confidence=0.1,  # Below min_confidence 0.3
    )
    assert agg.combine([low_conf_sig], now_ts, sym) is None
