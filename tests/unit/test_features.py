"""Unit tests for Phase 5 statistical features, cross-sectional ranking, and market breadth."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import polars as pl

from atlas.core.clock import SimClock
from atlas.core.context import HistoricalMarketContext
from atlas.core.types import Symbol
from atlas.signals.features.breadth import MarketBreadthCalculator
from atlas.signals.features.cross_sectional import CrossSectionalRanker
from atlas.signals.features.extractor import FeatureEngine
from atlas.signals.features.technical import StatisticalFeatureExtractor


def _make_dummy_df(n: int = 300, base_price: float = 100.0) -> pd.DataFrame:
    rows = []
    price = base_price
    for i in range(n):
        ts = datetime(2020, 1, 1, tzinfo=UTC) + pd.Timedelta(days=i)
        price = price * (1.0 + (0.001 if i % 2 == 0 else -0.0008))
        rows.append(
            {
                "symbol": "TEST",
                "ts": ts,
                "open": price * 0.995,
                "high": price * 1.01,
                "low": price * 0.99,
                "close": price,
                "volume": 1_000_000,
            }
        )
    return pd.DataFrame(rows)


def test_statistical_feature_extractor_warmup_and_names() -> None:
    extractor = StatisticalFeatureExtractor()
    assert extractor.warmup_bars >= 252
    assert len(extractor.feature_names) == 20
    assert "return_1d" in extractor.feature_names
    assert "realized_vol_21d" in extractor.feature_names
    assert "garman_klass_vol_21d" in extractor.feature_names
    assert "parkinson_vol_21d" in extractor.feature_names
    assert "rsi_14d" in extractor.feature_names


def test_statistical_feature_extractor_batch() -> None:
    extractor = StatisticalFeatureExtractor()
    df = _make_dummy_df(300)
    feat_df = extractor.extract_batch(df)
    assert len(feat_df) == 300
    assert not feat_df.empty
    # Check that latest row has computed values
    latest = feat_df.iloc[-1]
    assert 0.0 <= latest["rsi_14d"] <= 100.0
    assert 0.0 <= latest["range_pos_52w"] <= 1.0
    assert latest["realized_vol_21d"] >= 0.0


def test_cross_sectional_ranker_pct_and_zscore() -> None:
    values = {
        Symbol("AAPL"): 0.10,
        Symbol("MSFT"): 0.20,
        Symbol("NVDA"): 0.50,
        Symbol("TSLA"): -0.05,
    }
    ranks = CrossSectionalRanker.compute_ranks(values)
    assert len(ranks) == 4
    # NVDA is highest -> rank 1.0, TSLA is lowest -> rank 0.25
    assert ranks[Symbol("NVDA")] == 1.0
    assert ranks[Symbol("TSLA")] == 0.25
    assert ranks[Symbol("MSFT")] > ranks[Symbol("AAPL")]

    zscores = CrossSectionalRanker.compute_zscores(values)
    assert zscores[Symbol("NVDA")] > 0
    assert zscores[Symbol("TSLA")] < 0


def test_market_breadth_calculator() -> None:
    calc = MarketBreadthCalculator()
    clock = SimClock(datetime(2020, 1, 1, tzinfo=UTC))
    ctx = HistoricalMarketContext(clock=clock, bars_df=pl.DataFrame())
    breadth = calc.compute_breadth(ctx, [])
    assert breadth["breadth_advance_decline"] == 0.5
    assert breadth["breadth_avg_rsi"] == 50.0


def test_feature_engine_orchestration() -> None:
    engine = FeatureEngine()
    assert len(engine.all_feature_names) > 20
    assert "cs_rank_momentum_12m_1m" in engine.all_feature_names
    assert "breadth_pct_above_50d" in engine.all_feature_names

    # Test batch dataset building
    df1 = _make_dummy_df(280)
    df1["timestamp"] = df1["ts"]
    dataset = engine.build_dataset_from_bars({Symbol("SPY"): df1}, forward_horizons=[5])
    assert not dataset.empty
    assert "target_return_5d" in dataset.columns
    assert "target_dir_5d" in dataset.columns

    # Test parquet snapshot saving and loading
    with tempfile.TemporaryDirectory() as tmp:
        snap_path = Path(tmp) / "feats.parquet"
        engine.save_feature_snapshot(dataset, snap_path)
        assert snap_path.exists()
        loaded = engine.load_feature_snapshot(snap_path)
        assert len(loaded) == len(dataset)
