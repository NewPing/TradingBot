"""Unit tests for Statistical Gatekeeper and deliberate overfitting rejection (§8.3)."""

from __future__ import annotations

import pytest

from atlas.core.types import BucketId
from atlas.research.gatekeeper import StatisticalGatekeeper
from atlas.strategies.spec import SignalConfig, StrategySpec, UniverseFilterConfig


@pytest.fixture
def base_spec() -> StrategySpec:
    return StrategySpec(
        name="test_candidate",
        family="core_trend",
        version="1.0.0",
        bucket=BucketId.CORE,
        universe=UniverseFilterConfig(symbols=["SPY", "QQQ"]),
        signals=[SignalConfig(provider="l1_trend_filter", weight=1.0)],
    )


def test_gatekeeper_passes_robust_strategy(base_spec: StrategySpec) -> None:
    """A robust strategy with strong walk-forward, low degradation, and diverse regimes passes."""
    gatekeeper = StatisticalGatekeeper()
    train_metrics = {
        "sharpe_ratio": 1.8,
        "cagr": 0.22,
        "max_drawdown": 0.12,
        "total_trades": 180,
        "duration_years": 5.0,
    }
    trade_returns = [0.04, -0.01, 0.03, -0.015, 0.02, -0.01] * 30

    eval_result = gatekeeper.evaluate(
        spec=base_spec,
        train_metrics=train_metrics,
        trade_returns=trade_returns,
        walk_forward_fold_sharpes=[1.2, 1.4, 0.9, 1.5, 1.1, 1.3],
        perturbed_sharpes=[1.7, 1.65, 1.8, 1.72, 1.68],
        stressed_cost_sharpe=1.2,
        regime_sharpes={
            "BULL_LOW_VOL": 2.1,
            "BULL_HIGH_VOL": 1.6,
            "BEAR_HIGH_VOL": 0.4,
            "BEAR_LOW_VOL": 0.8,
        },
        active_strategy_correlations=[0.25, 0.35],
        total_trials_in_family=5,
    )

    assert eval_result.passed_all is True
    assert eval_result.gates_passed == 8
    assert eval_result.verdict == "PASSED"
    assert "Passed" in eval_result.summary_markdown or "PASSED" in eval_result.summary_markdown


def test_gatekeeper_rejects_overfit_walk_forward_collapse(base_spec: StrategySpec) -> None:
    """Deliberately planted overfit strategy collapsing out-of-sample must be rejected."""
    gatekeeper = StatisticalGatekeeper()
    train_metrics = {
        "sharpe_ratio": 2.5,
        "cagr": 0.35,
        "max_drawdown": 0.08,
        "total_trades": 150,
        "duration_years": 4.0,
    }
    trade_returns = [0.03, -0.01] * 75

    # Out-of-sample walk-forward folds collapse near zero/negative
    eval_result = gatekeeper.evaluate(
        spec=base_spec,
        train_metrics=train_metrics,
        trade_returns=trade_returns,
        walk_forward_fold_sharpes=[0.1, -0.2, 0.05, -0.15, 0.2, -0.05],
    )

    assert eval_result.passed_all is False
    assert eval_result.verdict == "REJECTED_OVERFIT"


def test_gatekeeper_rejects_high_correlation(base_spec: StrategySpec) -> None:
    """Strategy with > 0.60 correlation to active paper/live strategy is rejected."""
    gatekeeper = StatisticalGatekeeper()
    train_metrics = {
        "sharpe_ratio": 1.5,
        "cagr": 0.18,
        "max_drawdown": 0.12,
        "total_trades": 200,
        "duration_years": 5.0,
    }
    trade_returns = [0.02, -0.01] * 100

    eval_result = gatekeeper.evaluate(
        spec=base_spec,
        train_metrics=train_metrics,
        trade_returns=trade_returns,
        active_strategy_correlations=[0.88],  # Excess correlation
    )

    assert eval_result.passed_all is False
    assert eval_result.verdict == "REJECTED_CORRELATION"


def test_gatekeeper_rejects_insufficient_sample_size(base_spec: StrategySpec) -> None:
    """Strategy with < 100 trades is rejected by Gate 6."""
    gatekeeper = StatisticalGatekeeper()
    train_metrics = {
        "sharpe_ratio": 1.9,
        "cagr": 0.25,
        "max_drawdown": 0.10,
        "total_trades": 35,  # Too few trades
        "duration_years": 2.0,
    }
    trade_returns = [0.03, -0.01] * 17

    eval_result = gatekeeper.evaluate(
        spec=base_spec,
        train_metrics=train_metrics,
        trade_returns=trade_returns,
    )

    assert eval_result.passed_all is False
    assert eval_result.verdict == "REJECTED_SAMPLE"
