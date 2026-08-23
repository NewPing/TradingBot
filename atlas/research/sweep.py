"""Parameter and feature exploration sweep engine (Phase 8).

Executes parallel or batched grid/random/perturbation sweeps across train partitions,
identifying optimal parameter regions and logging all multiple-testing trials.
"""

from __future__ import annotations

import itertools
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import numpy as np
import polars as pl
from sqlalchemy.orm import Session

from atlas.backtest.engine import BacktestEngine
from atlas.core.types import Symbol
from atlas.data.models import ResearchSweep
from atlas.research.trials import TrialTracker
from atlas.strategies.spec import StrategySpec


def build_research_dataset(
    symbols: list[Symbol],
    start_d: date,
    end_d: date,
    seed: int = 42,
) -> pl.DataFrame:
    """Generate multi-symbol daily OHLCV dataset using Geometric Brownian Motion (GBM) for backtest research."""
    cur = start_d
    dates: list[datetime] = []
    while cur <= end_d:
        if cur.weekday() < 5:
            dates.append(datetime.combine(cur, datetime.min.time(), tzinfo=UTC))
        cur += timedelta(days=1)

    n_bars = len(dates)
    if n_bars == 0:
        return pl.DataFrame()

    rng = np.random.default_rng(seed)
    records: list[dict[str, object]] = []
    dt = 1.0 / 252.0

    n_syms = len(symbols)
    if n_syms == 0:
        return pl.DataFrame()

    # Construct positive-definite correlation matrix (rho ~ 0.50 average equity market correlation)
    corr_matrix = np.full((n_syms, n_syms), 0.50)
    np.fill_diagonal(corr_matrix, 1.0)
    L = np.linalg.cholesky(corr_matrix)

    # Generate correlated standard normal diffusion innovations for overnight and intraday
    uncorrelated_id_shocks = rng.standard_normal((n_bars, n_syms))
    correlated_id_shocks = uncorrelated_id_shocks @ L.T
    uncorrelated_on_shocks = rng.standard_normal((n_bars, n_syms))
    correlated_on_shocks = uncorrelated_on_shocks @ L.T

    for sym_idx, sym in enumerate(symbols):
        base_px = 100.0 + sym_idx * 40.0
        mu = 0.08  # 8% annualized expected drift
        sigma = 0.18 + 0.02 * sym_idx  # 18-24% annual volatility

        # Step-by-step coupled Overnight and Intraday GBM path generation
        prev_c = base_px
        for i, dt_ts in enumerate(dates):
            # Overnight component with cross-sectional correlated diffusion (25% variance share)
            on_drift = (mu * 0.25 - 0.5 * (sigma * 0.5) ** 2) * dt
            on_diff = (sigma * 0.5) * np.sqrt(dt) * correlated_on_shocks[i, sym_idx]
            open_px = max(1.0, prev_c * np.exp(on_drift + on_diff))

            # Intraday component with cross-sectional correlated diffusion (75% variance share)
            id_drift = (mu * 0.75 - 0.5 * (sigma * 0.866) ** 2) * dt
            id_diff = (sigma * 0.866) * np.sqrt(dt) * correlated_id_shocks[i, sym_idx]
            close_px = max(0.5, open_px * np.exp(id_drift + id_diff))

            intraday_range = float(rng.exponential(0.010 * close_px))
            high_raw = max(open_px, close_px) + intraday_range * float(rng.uniform(0.2, 0.6))
            low_raw = max(
                0.01, min(open_px, close_px) - intraday_range * float(rng.uniform(0.2, 0.6))
            )

            o_round = round(open_px, 2)
            c_round = round(close_px, 2)
            h_round = max(o_round, c_round, round(high_raw, 2))
            l_round = min(o_round, c_round, max(0.01, round(low_raw, 2)))

            records.append(
                {
                    "symbol": str(sym),
                    "ts": dt_ts,
                    "open": o_round,
                    "high": h_round,
                    "low": l_round,
                    "close": c_round,
                    "volume": max(10_000, int(rng.lognormal(mean=14.73, sigma=0.25))),
                    "adj_factor": 1.0,
                }
            )
            prev_c = close_px

    return pl.DataFrame(records)


class SweepEngine:
    """Orchestrates strategy parameter and feature exploration sweeps."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.trial_tracker = TrialTracker(session)

    def create_grid_sweep(
        self,
        family: str,
        param_grid: dict[str, list[Any]],
        hypothesis_id: str | None = None,
        metric_name: str = "sharpe_ratio",
    ) -> ResearchSweep:
        """Create and persist a new parameter sweep record."""
        keys = list(param_grid.keys())
        combos = list(itertools.product(*[param_grid[k] for k in keys]))
        total_combinations = len(combos)

        sweep_id = f"swp_{str(uuid.uuid4())[:12]}"
        sweep = ResearchSweep(
            id=sweep_id,
            hypothesis_id=hypothesis_id,
            family=family,
            sweep_type="GRID",
            param_grid=json.dumps(param_grid, sort_keys=True),
            total_combinations=total_combinations,
            completed_combinations=0,
            best_candidate_params=None,
            best_metric_name=metric_name,
            best_metric_value=None,
            status="PENDING",
            created_at=datetime.now(UTC),
        )
        self.session.add(sweep)
        self.session.commit()
        self.session.refresh(sweep)
        return sweep

    def execute_sweep_sync(
        self,
        sweep_id: str,
        base_spec: StrategySpec,
        eval_fn: Any = None,
    ) -> ResearchSweep:
        """Execute all parameter combinations for a sweep on the train partition."""
        sweep = self.session.get(ResearchSweep, sweep_id)
        if not sweep:
            raise ValueError(f"Sweep '{sweep_id}' not found.")

        param_grid = json.loads(sweep.param_grid)
        keys = list(param_grid.keys())
        values = [param_grid[k] for k in keys]
        combinations = [dict(zip(keys, combo, strict=True)) for combo in itertools.product(*values)]

        sweep.status = "RUNNING"
        self.session.commit()

        best_score = -999.0
        best_params: dict[str, Any] | None = None
        completed = 0

        for params in combinations:
            # Evaluate combination (using custom evaluator or real BacktestEngine)
            if eval_fn is not None:
                metrics = eval_fn(base_spec, params)
            else:
                # Execute real backtest evaluation on train dataset
                updated_signals = []
                for sig in base_spec.signals:
                    sig_params = dict(sig.params)
                    for k, v in params.items():
                        if k in sig_params or k in (
                            "fast_period",
                            "slow_period",
                            "ma_period",
                            "period",
                            "lookback",
                        ):
                            sig_params[k] = v
                    updated_signals.append(sig.model_copy(update={"params": sig_params}))

                policy_updates = {}
                for k in ("n", "min_score", "enter_threshold", "exit_threshold"):
                    if k in params:
                        policy_updates[k] = params[k]

                updated_policy = (
                    base_spec.policy.model_copy(update=policy_updates)
                    if policy_updates
                    else base_spec.policy
                )
                spec_variant = base_spec.model_copy(
                    update={"signals": updated_signals, "policy": updated_policy}
                )

                syms = (
                    [Symbol(s) for s in base_spec.universe.symbols]
                    if base_spec.universe.symbols
                    else [Symbol("SPY"), Symbol("AAPL"), Symbol("MSFT")]
                )
                train_data = build_research_dataset(syms, date(2015, 1, 1), date(2018, 12, 31))
                engine = BacktestEngine(spec=spec_variant, data=train_data)
                res = engine.run(start_date=date(2015, 1, 1), end_date=date(2018, 12, 31))

                metrics = {
                    "sharpe_ratio": round(res.metrics.sharpe_ratio, 4),
                    "cagr": round(res.metrics.cagr, 4),
                    "max_drawdown": round(res.metrics.max_drawdown, 4),
                    "calmar_ratio": round(res.metrics.calmar_ratio, 4),
                    "win_rate": round(res.metrics.win_rate, 4),
                    "profit_factor": round(res.metrics.profit_factor, 2),
                    "total_trades": res.metrics.total_trades,
                    "duration_years": 4.0,
                }

            score = float(metrics.get(sweep.best_metric_name, 0.0))

            # Record trial in sacred multiple-testing ledger (§8.3 Invariant 12)
            self.trial_tracker.record_trial(
                family=sweep.family,
                parameters=params,
                metrics=metrics,
                outcome="COMPLETED",
                hypothesis_id=sweep.hypothesis_id,
                notes=f"Sweep {sweep.id} combo {completed + 1}/{len(combinations)}",
            )

            if score > best_score:
                best_score = score
                best_params = params

            completed += 1

        sweep.completed_combinations = completed
        sweep.best_candidate_params = (
            json.dumps(best_params, sort_keys=True) if best_params else "{}"
        )
        sweep.best_metric_value = Decimal(str(round(best_score, 4)))
        sweep.status = "COMPLETED"
        sweep.completed_at = datetime.now(UTC)

        self.session.commit()
        self.session.refresh(sweep)
        return sweep
