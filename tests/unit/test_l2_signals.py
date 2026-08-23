"""Unit tests for L2 signal providers, strategy builder, and lookahead invariants."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import polars as pl

from atlas.core.clock import SimClock
from atlas.core.context import HistoricalMarketContext
from atlas.core.types import SignalLayer, Symbol
from atlas.ml.bootstrap import bootstrap_default_lgbm_model
from atlas.ml.registry import ModelRegistry
from atlas.signals.l2_statistical import (
    CrossSectionalMomentumProvider,
    LightGBMSignalProvider,
    MarketRegimeSignalProvider,
)
from atlas.strategies.builder import build_signal_provider


def _make_df(symbol_str: str, n: int = 300) -> pl.DataFrame:
    rows = []
    price = 100.0
    for i in range(n):
        ts = datetime(2020, 1, 1, tzinfo=UTC) + pd.Timedelta(days=i)
        price = price * (1.0 + (0.001 if i % 2 == 0 else -0.0007))
        rows.append(
            {
                "symbol": symbol_str,
                "ts": ts,
                "open": price * 0.998,
                "high": price * 1.005,
                "low": price * 0.995,
                "close": price,
                "volume": 10_000_000,
            }
        )
    return pl.DataFrame(rows)


def test_cross_sectional_momentum_provider() -> None:
    df_a = _make_df("AAPL", 300)
    df_b = _make_df("MSFT", 300)
    df_c = _make_df("SPY", 300)

    cutoff = df_a["ts"][-1]
    clock = SimClock(cutoff)
    ctx = HistoricalMarketContext(
        clock=clock,
        bars_df={
            Symbol("AAPL"): df_a,
            Symbol("MSFT"): df_b,
            Symbol("SPY"): df_c,
        },
        universe_map={cutoff: [Symbol("AAPL"), Symbol("MSFT"), Symbol("SPY")]},
    )

    provider = CrossSectionalMomentumProvider(id="l2_cs_momentum")
    assert provider.layer == SignalLayer.L2_STATISTICAL
    sig = provider.evaluate(ctx, Symbol("AAPL"))

    assert sig is not None
    assert -1.0 <= sig.score <= 1.0
    assert 0.0 <= sig.confidence <= 1.0
    assert sig.layer == SignalLayer.L2_STATISTICAL
    assert "CS Momentum" in sig.rationale


def test_market_regime_provider() -> None:
    df_spy = _make_df("SPY", 300)
    cutoff = df_spy["ts"][-1]
    clock = SimClock(cutoff)
    ctx = HistoricalMarketContext(
        clock=clock,
        bars_df={Symbol("SPY"): df_spy},
        universe_map={cutoff: [Symbol("SPY")]},
    )

    provider = MarketRegimeSignalProvider(id="l2_market_regime", benchmark="SPY")
    sig = provider.evaluate(ctx, Symbol("SPY"))

    assert sig is not None
    assert sig.layer == SignalLayer.L2_STATISTICAL
    assert "Regime" in sig.rationale


def test_lightgbm_signal_provider() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        reg_dir = Path(tmp_dir)
        artifact = bootstrap_default_lgbm_model(registry_dir=reg_dir)
        registry = ModelRegistry(reg_dir)

        df_spy = _make_df("SPY", 300)
        cutoff = df_spy["ts"][-1]
        clock = SimClock(cutoff)
        ctx = HistoricalMarketContext(
            clock=clock,
            bars_df={Symbol("SPY"): df_spy},
            universe_map={cutoff: [Symbol("SPY")]},
        )

        provider = LightGBMSignalProvider(
            id="l2_lightgbm",
            registry=registry,
            artifact=artifact,
        )
        sig = provider.evaluate(ctx, Symbol("SPY"))

        assert sig is not None
        assert sig.layer == SignalLayer.L2_STATISTICAL
        assert -1.0 <= sig.score <= 1.0
        assert 0.0 <= sig.confidence <= 1.0
        assert len(sig.rationale) > 0


def test_l2_signal_provider_builder() -> None:
    cs_prov = build_signal_provider("l2_cs_momentum", {"skip_bars": 21, "lookback_bars": 252})
    assert isinstance(cs_prov, CrossSectionalMomentumProvider)

    reg_prov = build_signal_provider("l2_market_regime", {"benchmark": "SPY"})
    assert isinstance(reg_prov, MarketRegimeSignalProvider)

    lgbm_prov = build_signal_provider("l2_lightgbm", {"model_id": "lgbm_dir_5d_v1"})
    assert isinstance(lgbm_prov, LightGBMSignalProvider)
