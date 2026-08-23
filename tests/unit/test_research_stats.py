"""Unit tests for Phase 8 statistical methods (DSR, PBO, Monte Carlo)."""

from __future__ import annotations

import numpy as np

from atlas.research.stats import (
    calculate_deflated_sharpe,
    calculate_pbo,
    generate_walk_forward_folds,
    monte_carlo_trade_shuffle,
)


def test_deflated_sharpe_single_trial() -> None:
    """A high Sharpe ratio with 1 trial should have high confidence."""
    dsr = calculate_deflated_sharpe(sharpe=2.0, trials=1, n_periods=252)
    assert 0.8 <= dsr <= 1.0


def test_deflated_sharpe_multiple_trials_haircut() -> None:
    """DSR should decrease substantially when 500 trials were tested."""
    dsr_1 = calculate_deflated_sharpe(sharpe=1.2, trials=1, n_periods=252)
    dsr_500 = calculate_deflated_sharpe(sharpe=1.2, trials=500, n_periods=252)
    assert dsr_1 > dsr_500
    assert 0.0 <= dsr_500 <= 1.0


def test_pbo_calculation() -> None:
    """Test CSCV PBO estimation on synthetic returns matrix."""
    rng = np.random.default_rng(42)
    # 500 periods x 8 strategy variations
    returns_matrix = rng.normal(0.0005, 0.01, size=(500, 8))

    res = calculate_pbo(returns_matrix, n_splits=6)
    assert "pbo" in res
    assert 0.0 <= res["pbo"] <= 1.0
    assert res["n_combinations"] == 20  # 6 choose 3


def test_monte_carlo_trade_shuffle() -> None:
    """Test bootstrap trade shuffling metrics."""
    trade_returns = [0.03, -0.01, 0.04, -0.02, 0.015, -0.005, 0.02] * 10
    mc = monte_carlo_trade_shuffle(trade_returns, n_sims=500, seed=42)

    assert "p5_cagr" in mc
    assert "p50_cagr" in mc
    assert "p95_cagr" in mc
    assert mc["p5_cagr"] <= mc["p50_cagr"] <= mc["p95_cagr"]
    assert mc["prob_profit"] > 0.0


def test_generate_walk_forward_folds() -> None:
    """Test rolling walk-forward fold generation."""
    folds = generate_walk_forward_folds(start_year=2005, end_year=2018, train_years=3, test_years=1)
    assert len(folds) >= 10
    assert folds[0]["train_start"] == "2005-01-01"
    assert folds[0]["train_end"] == "2007-12-31"
    assert folds[0]["test_start"] == "2008-01-01"
    assert folds[0]["test_end"] == "2008-12-31"
