"""Statistical methods and financial econometric tests for ATLAS Research (Phase 8).

Implements Deflated Sharpe Ratio (DSR), Probability of Backtest Overfitting (PBO),
Monte Carlo trade permutation distributions, and partition cross-validation math.
Based on Bailey, Borwein, López de Prado, and Zhu (2014/2016).
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from typing import Any

import numpy as np
from scipy.stats import norm  # type: ignore[import-untyped]


def calculate_deflated_sharpe(
    sharpe: float,
    trials: int,
    var_trials: float = 0.05,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
    n_periods: int = 252,
    annual_factor: float = 252.0,
) -> float:
    """Calculate the Deflated Sharpe Ratio (DSR) accounting for multiple testing.

    DSR computes the probability that the observed Sharpe ratio is greater than zero
    after deflating the standard error for non-normality and adjusting the benchmark
    for the maximum expected Sharpe among N trials.

    References:
        Bailey, D. H., & López de Prado, M. (2014). The Deflated Sharpe Ratio:
        Correcting for Selection Bias, Backtest Overfitting, and Non-Normality.
        Journal of Portfolio Management.
    """
    if trials <= 1:
        trials = 1

    # Standard error of Sharpe ratio under non-normality (Mertens 2002 / Lo 2002 / Bailey & de Prado 2014)
    # Convert annualized Sharpe to daily frequency for Mertens standard error, then scale back by sqrt(annual_factor)
    sr_ann = sharpe
    sr_daily = sr_ann / math.sqrt(annual_factor) if annual_factor > 0 else sr_ann
    n = max(n_periods, 10)
    se_daily_sq = (1.0 - skewness * sr_daily + ((kurtosis - 1.0) / 4.0) * (sr_daily**2)) / (n - 1.0)
    se_ann = math.sqrt(max(se_daily_sq, 1e-8)) * math.sqrt(annual_factor)

    # Expected maximum Sharpe among N independent trials under null hypothesis
    # E[max_N] ~= sqrt(var_trials) * ((1 - gamma) * Z^{-1}(1 - 1/N) + gamma * Z^{-1}(1 - 1/(N*e)))
    gamma_const = 0.57721566490153286
    if trials > 1:
        p1 = min(0.99999, max(0.00001, 1.0 - 1.0 / trials))
        p2 = min(0.99999, max(0.00001, 1.0 - 1.0 / (trials * math.e)))
        q1 = float(norm.ppf(p1))
        q2 = float(norm.ppf(p2))
        sr_benchmark = math.sqrt(max(var_trials, 1e-6)) * (
            (1.0 - gamma_const) * q1 + gamma_const * q2
        )
    else:
        sr_benchmark = 0.0

    # Deflated test statistic in annualized units
    test_stat = (sr_ann - sr_benchmark) / se_ann

    # Standard normal CDF
    dsr = float(norm.cdf(test_stat))
    return float(max(0.0, min(1.0, dsr)))


def calculate_pbo(
    returns_matrix: np.ndarray,
    n_splits: int = 8,
    purge_window: int = 0,
) -> dict[str, Any]:
    """Calculate the Probability of Backtest Overfitting (PBO) via CSCV.

    Combinatorially Symmetric Cross-Validation (CSCV) splits the matrix of T periods
    x N strategy configurations into sub-matrices, computes optimal in-sample
    configurations, and evaluates the probability that the in-sample winner underperforms
    the median out-of-sample configuration.

    Parameters:
        returns_matrix: 2D array of shape (T_periods, N_strategies)
        n_splits: Number of time slices (must be even, e.g. 6, 8, 10)
        purge_window: Number of boundary periods to purge from OOS slices
    """
    t_periods, n_strategies = returns_matrix.shape
    if n_strategies < 2:
        return {
            "pbo": 0.0,
            "logits": [],
            "n_combinations": 0,
            "message": "At least 2 strategy configurations required for PBO.",
        }

    if n_splits % 2 != 0:
        n_splits = max(4, n_splits - 1)

    chunk_size = t_periods // n_splits
    if chunk_size < 5:
        # Fallback to 4 splits if too few periods
        n_splits = 4
        chunk_size = max(2, t_periods // n_splits)

    chunks: list[np.ndarray] = []
    for i in range(n_splits):
        start = i * chunk_size
        end = (i + 1) * chunk_size if i < n_splits - 1 else t_periods
        chunks.append(returns_matrix[start:end, :])

    # All combinations of (n_splits / 2) chunks for In-Sample (IS)
    k = n_splits // 2
    combinations = list(itertools.combinations(range(n_splits), k))
    total_combs = len(combinations)

    overfit_count = 0
    relative_ranks: list[float] = []

    for is_indices in combinations:
        oos_indices = [i for i in range(n_splits) if i not in is_indices]

        is_data = np.vstack([chunks[i] for i in is_indices])
        oos_chunks_clean = []
        for i in oos_indices:
            c = chunks[i]
            if purge_window > 0 and len(c) > purge_window:
                oos_chunks_clean.append(c[purge_window:])
            else:
                oos_chunks_clean.append(c)
        oos_data = np.vstack(oos_chunks_clean)

        # Compute In-Sample Sharpe
        is_mean = np.mean(is_data, axis=0)
        is_std = np.std(is_data, axis=0, ddof=1) + 1e-8
        is_sharpe = is_mean / is_std

        # Best IS strategy
        best_is_idx = int(np.argmax(is_sharpe))

        # Compute Out-of-Sample Sharpe
        oos_mean = np.mean(oos_data, axis=0)
        oos_std = np.std(oos_data, axis=0, ddof=1) + 1e-8
        oos_sharpe = oos_mean / oos_std

        # Rank of IS-winner in OOS distribution
        # Rank normalized between 0 (worst) and 1 (best)
        oos_winner_score = oos_sharpe[best_is_idx]
        rank_oos = float(np.sum(oos_sharpe <= oos_winner_score) / n_strategies)
        relative_ranks.append(rank_oos)

        # Overfit if IS winner performs below median (rank <= 0.5) in OOS
        if rank_oos <= 0.5:
            overfit_count += 1

    pbo = float(overfit_count / total_combs) if total_combs > 0 else 0.0

    return {
        "pbo": round(pbo, 4),
        "median_oos_rank": round(float(np.median(relative_ranks)), 4) if relative_ranks else 0.5,
        "n_combinations": total_combs,
        "overfit_count": overfit_count,
    }


def monte_carlo_trade_shuffle(
    trade_pct_returns: list[float],
    n_sims: int = 1000,
    initial_capital: float = 100_000.0,
    position_fraction: float = 0.10,
    total_years: float | None = None,
    seed: int = 42,
    daily_returns: Sequence[float] | None = None,
) -> dict[str, float]:
    """Perform bootstrap Monte Carlo simulation to evaluate luck vs robust edge.

    If daily_returns is provided, resamples daily portfolio returns to preserve
    concurrent multi-asset netting and exposure structure. Otherwise, resamples
    individual trade returns.
    """
    if not trade_pct_returns and (daily_returns is None or len(daily_returns) == 0):
        return {
            "p5_cagr": 0.0,
            "p50_cagr": 0.0,
            "p95_cagr": 0.0,
            "p5_max_dd": 0.0,
            "p50_max_dd": 0.0,
            "p95_max_dd": 0.0,
            "prob_profit": 0.0,
        }

    rng = np.random.default_rng(seed)
    terminal_values: list[float] = []
    max_drawdowns: list[float] = []

    if daily_returns is not None and len(daily_returns) > 5:
        daily_arr = np.array(daily_returns, dtype=float)
        n_days = len(daily_arr)
        years = (
            total_years
            if (total_years is not None and total_years > 0.0)
            else max(0.5, n_days / 252.0)
        )

        for _ in range(n_sims):
            sample_daily = rng.choice(daily_arr, size=n_days, replace=True)
            equity_curve = initial_capital * np.cumprod(1.0 + sample_daily)
            terminal_values.append(float(equity_curve[-1]))

            running_max = np.maximum.accumulate(equity_curve)
            drawdowns = (equity_curve - running_max) / running_max
            max_dd = abs(float(np.min(drawdowns)))
            max_drawdowns.append(max_dd)
    else:
        returns_arr = np.array(trade_pct_returns, dtype=float)
        n_trades = len(returns_arr)
        pos_frac = max(0.01, min(1.0, position_fraction))
        years = (
            total_years
            if (total_years is not None and total_years > 0.0)
            else max(0.5, n_trades * 10.0 / 252.0)
        )

        for _ in range(n_sims):
            sample_returns = rng.choice(returns_arr, size=n_trades, replace=True)
            portfolio_returns = sample_returns * pos_frac
            equity_curve = initial_capital * np.cumprod(1.0 + portfolio_returns)
            terminal_values.append(float(equity_curve[-1]))

            running_max = np.maximum.accumulate(equity_curve)
            drawdowns = (equity_curve - running_max) / running_max
            max_dd = abs(float(np.min(drawdowns)))
            max_drawdowns.append(max_dd)

    cagrs = [(max(1e-4, v) / initial_capital) ** (1.0 / years) - 1.0 for v in terminal_values]

    p5_cagr = float(np.percentile(cagrs, 5))
    p50_cagr = float(np.percentile(cagrs, 50))
    p95_cagr = float(np.percentile(cagrs, 95))

    p5_dd = float(np.percentile(max_drawdowns, 5))
    p50_dd = float(np.percentile(max_drawdowns, 50))
    p95_dd = float(np.percentile(max_drawdowns, 95))

    prob_profit = float(np.mean(np.array(terminal_values) > initial_capital))

    return {
        "p5_cagr": round(p5_cagr, 4),
        "p50_cagr": round(p50_cagr, 4),
        "p95_cagr": round(p95_cagr, 4),
        "p5_max_dd": round(p5_dd, 4),
        "p50_max_dd": round(p50_dd, 4),
        "p95_max_dd": round(p95_dd, 4),
        "prob_profit": round(prob_profit, 4),
    }


def generate_walk_forward_folds(
    start_year: int = 2005,
    end_year: int = 2018,
    train_years: int = 3,
    test_years: int = 1,
) -> list[dict[str, str]]:
    """Generate rolling walk-forward train and out-of-sample test date windows."""
    folds: list[dict[str, str]] = []
    current_start = start_year

    while current_start + train_years + test_years - 1 <= end_year:
        train_start = f"{current_start}-01-01"
        train_end = f"{current_start + train_years - 1}-12-31"
        test_start = f"{current_start + train_years}-01-01"
        test_end = f"{current_start + train_years + test_years - 1}-12-31"

        folds.append(
            {
                "fold_id": f"fold_{len(folds) + 1}",
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
            }
        )
        current_start += test_years

    return folds
