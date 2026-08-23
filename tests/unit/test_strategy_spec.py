"""Unit tests for StrategySpec parsing, validation, hashing, and builder."""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas.portfolio.policies import (
    TargetWeightPolicy,
    ThresholdLongOnlyPolicy,
    TopNLongOnlyPolicy,
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
from atlas.strategies.builder import (
    build_position_policy,
    build_signal_provider,
)
from atlas.strategies.spec import StrategySpec


def test_load_all_baseline_specs() -> None:
    specs_dir = Path("strategies")
    yaml_files = list(specs_dir.glob("*.yaml"))
    assert len(yaml_files) >= 5

    for yf in yaml_files:
        spec = StrategySpec.from_yaml(yf)
        assert spec.name
        assert spec.version
        assert len(spec.spec_hash()) == 64  # SHA-256


def test_spec_hash_determinism_and_immutability() -> None:
    spec1 = StrategySpec.from_yaml("strategies/core_trend_v1.yaml")
    spec2 = StrategySpec.from_yaml("strategies/core_trend_v1.yaml")

    assert spec1.spec_hash() == spec2.spec_hash()


def test_builder_factories() -> None:
    # Test builder for all signal provider types
    p_trend = build_signal_provider("l1_trend_filter", {"ma_period": 100, "ma_type": "ema"})
    assert isinstance(p_trend, TrendFilterSignalProvider)

    p_mom = build_signal_provider("l1_momentum", {"lookback": 126, "skip": 10})
    assert isinstance(p_mom, MomentumSignalProvider)

    p_rsi = build_signal_provider("l1_rsi", {"period": 2})
    assert isinstance(p_rsi, RsiSignalProvider)

    p_macd = build_signal_provider("l1_macd", {})
    assert isinstance(p_macd, MacdSignalProvider)

    p_bb = build_signal_provider("l1_bollinger", {})
    assert isinstance(p_bb, BollingerSignalProvider)

    p_52 = build_signal_provider("l1_52w_position", {})
    assert isinstance(p_52, FiftyTwoWeekSignalProvider)

    p_vol = build_signal_provider("l1_volume_zscore", {})
    assert isinstance(p_vol, VolumeZScoreSignalProvider)

    with pytest.raises(ValueError):
        build_signal_provider("unknown_provider", {})

    # Test builder for policies
    spec_top_n = StrategySpec.from_yaml("strategies/core_trend_v1.yaml")
    pol_top_n = build_position_policy(spec_top_n)
    assert isinstance(pol_top_n, TopNLongOnlyPolicy)

    spec_thresh = StrategySpec.from_yaml("strategies/swing_meanrev_v1.yaml")
    pol_thresh = build_position_policy(spec_thresh)
    assert isinstance(pol_thresh, ThresholdLongOnlyPolicy)

    spec_target = StrategySpec.from_yaml("strategies/buy_hold_spy.yaml")
    pol_target = build_position_policy(spec_target)
    assert isinstance(pol_target, TargetWeightPolicy)
