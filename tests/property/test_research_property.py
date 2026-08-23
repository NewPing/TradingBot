"""Property-based tests for Phase 8 statistical methods and financial invariant bounds."""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given, settings

from atlas.research.stats import calculate_deflated_sharpe, monte_carlo_trade_shuffle


@settings(max_examples=50)
@given(
    sharpe=st.floats(min_value=-2.0, max_value=4.0, allow_nan=False),
    trials=st.integers(min_value=1, max_value=5000),
    skewness=st.floats(min_value=-2.0, max_value=2.0, allow_nan=False),
    kurtosis=st.floats(min_value=1.5, max_value=10.0, allow_nan=False),
)
def test_deflated_sharpe_bounds(
    sharpe: float,
    trials: int,
    skewness: float,
    kurtosis: float,
) -> None:
    """Deflated Sharpe probability must strictly reside in [0.0, 1.0]."""
    dsr = calculate_deflated_sharpe(
        sharpe=sharpe,
        trials=trials,
        var_trials=0.04,
        skewness=skewness,
        kurtosis=kurtosis,
        n_periods=252,
    )
    assert 0.0 <= dsr <= 1.0


@settings(max_examples=30)
@given(
    sharpe=st.floats(min_value=0.5, max_value=3.0, allow_nan=False),
    trials_a=st.integers(min_value=1, max_value=50),
    trials_b=st.integers(min_value=100, max_value=2000),
)
def test_deflated_sharpe_monotonicity_in_trials(
    sharpe: float,
    trials_a: int,
    trials_b: int,
) -> None:
    """Higher number of trials must penalize (deflate) statistical confidence."""
    dsr_few = calculate_deflated_sharpe(sharpe=sharpe, trials=trials_a, n_periods=252)
    dsr_many = calculate_deflated_sharpe(sharpe=sharpe, trials=trials_b, n_periods=252)
    assert dsr_few >= dsr_many


@settings(max_examples=30)
@given(
    returns=st.lists(
        st.floats(min_value=-0.10, max_value=0.15, allow_nan=False),
        min_size=10,
        max_size=50,
    )
)
def test_monte_carlo_permutation_invariants(returns: list[float]) -> None:
    """Monte Carlo percentiles must maintain strict ordering: P5 <= P50 <= P95."""
    mc = monte_carlo_trade_shuffle(returns, n_sims=100, seed=42)
    assert mc["p5_cagr"] <= mc["p50_cagr"] <= mc["p95_cagr"]
    assert mc["p5_max_dd"] <= mc["p50_max_dd"] <= mc["p95_max_dd"]
    assert 0.0 <= mc["prob_profit"] <= 1.0
