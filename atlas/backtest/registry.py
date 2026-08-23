"""Run registry managing execution runs, reproducibility metadata, metrics, equity curves, and comparison."""

from __future__ import annotations

import contextlib
import importlib.metadata
import json
import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas import __version__
from atlas.core.errors import RunNotFoundError
from atlas.data.models import EquityPoint, Run, RunMetric, RunTrade


def get_current_git_sha() -> str:
    """Retrieve current HEAD git commit SHA or return fallback identifier."""
    try:
        output = (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, timeout=2
            )
            .decode("ascii")
            .strip()
        )
        return output
    except Exception:
        return "0000000000000000000000000000000000000000"


def get_environment_lib_versions() -> dict[str, str]:
    """Capture runtime package versions for strict reproducibility."""
    tracked_packages = [
        "atlas",
        "polars",
        "numpy",
        "scipy",
        "pydantic",
        "fastapi",
        "sqlalchemy",
        "alembic",
        "duckdb",
        "redis",
    ]
    versions: dict[str, str] = {"atlas": __version__}
    for pkg in tracked_packages:
        if pkg == "atlas":
            continue
        with contextlib.suppress(Exception):
            versions[pkg] = importlib.metadata.version(pkg)
    return versions


class RunRegistry:
    """Registry managing execution runs, reproducibility metadata, metrics, and comparisons."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def record_run(
        self,
        run_id: str,
        strategy_version_id: str,
        mode: str,
        start_ts: datetime,
        end_ts: datetime,
        data_snapshot_id: str,
        spec_hash: str,
        cost_model_hash: str,
        seed: int = 42,
        summary_metrics: dict[str, Any] | None = None,
        equity_curve: list[dict[str, Any]] | None = None,
        trades: list[dict[str, Any]] | None = None,
        git_sha: str | None = None,
        universe_hash: str | None = None,
        status: str = "COMPLETED",
    ) -> Run:
        """Record a completed execution run with full reproducibility metadata."""
        current_git = git_sha if git_sha is not None else get_current_git_sha()
        lib_vers = get_environment_lib_versions()
        metrics_dict = summary_metrics or {}

        run = Run(
            id=run_id,
            strategy_version_id=strategy_version_id,
            mode=mode.upper(),
            start_ts=start_ts,
            end_ts=end_ts,
            universe_hash=universe_hash,
            data_snapshot_id=data_snapshot_id,
            seed=seed,
            git_sha=current_git,
            spec_hash=spec_hash,
            cost_model_hash=cost_model_hash,
            lib_versions=json.dumps(lib_vers, sort_keys=True),
            status=status.upper(),
            summary_metrics=json.dumps(metrics_dict, sort_keys=True),
            created_at=datetime.now(UTC),
            completed_at=datetime.now(UTC) if status.upper() == "COMPLETED" else None,
        )
        self.session.add(run)

        # 1. Add run metrics
        for metric_name, value in metrics_dict.items():
            if isinstance(value, (int, float, Decimal)):
                try:
                    numeric_val = Decimal(str(value))
                    metric_record = RunMetric(
                        run_id=run_id,
                        metric_name=metric_name,
                        value=numeric_val,
                        window="FULL",
                    )
                    self.session.add(metric_record)
                except Exception:
                    pass

        # 2. Add equity curve
        if equity_curve:
            for pt in equity_curve:
                eq_point = EquityPoint(
                    run_id=run_id,
                    ts=pt["ts"]
                    if isinstance(pt["ts"], datetime)
                    else datetime.fromisoformat(str(pt["ts"])),
                    total_equity=Decimal(str(pt.get("total_equity", pt.get("equity", 0)))),
                    cash=Decimal(str(pt.get("cash", 0))),
                    per_bucket=json.dumps(pt.get("per_bucket", {})),
                    drawdown=Decimal(str(pt.get("drawdown", 0))),
                )
                self.session.add(eq_point)

        # 3. Add trades
        if trades:
            for tr in trades:
                trade_record = RunTrade(
                    run_id=run_id,
                    trade_id=str(tr.get("trade_id", tr.get("id", ""))),
                    symbol=str(tr.get("symbol", "")),
                    direction=str(tr.get("direction", "LONG")).upper(),
                    entry_time=tr["entry_time"]
                    if isinstance(tr["entry_time"], datetime)
                    else datetime.fromisoformat(str(tr["entry_time"])),
                    exit_time=tr["exit_time"]
                    if isinstance(tr["exit_time"], datetime)
                    else datetime.fromisoformat(str(tr["exit_time"])),
                    entry_price=Decimal(str(tr.get("entry_price", 0))),
                    exit_price=Decimal(str(tr.get("exit_price", 0))),
                    quantity=int(tr.get("quantity", tr.get("qty", 0))),
                    pnl=Decimal(str(tr.get("pnl", 0))),
                    pnl_net=Decimal(str(tr.get("pnl_net", tr.get("pnl", 0)))),
                    return_pct=Decimal(str(tr.get("return_pct", 0))),
                    fees=Decimal(str(tr.get("fees", 0))),
                    slippage=Decimal(str(tr.get("slippage", 0))),
                    exit_reason=str(tr.get("exit_reason", "SIGNAL")),
                )
                self.session.add(trade_record)

        self.session.commit()
        self.session.refresh(run)
        return run

    def get(self, run_id: str) -> Run | None:
        """Fetch run by ID."""
        return self.session.execute(select(Run).where(Run.id == run_id)).scalar_one_or_none()

    def get_or_raise(self, run_id: str) -> Run:
        """Fetch run by ID or raise RunNotFoundError."""
        run = self.get(run_id)
        if run is None:
            raise RunNotFoundError(f"Run '{run_id}' not found.")
        return run

    def list_runs(
        self, strategy_version_id: str | None = None, mode: str | None = None, limit: int = 50
    ) -> list[Run]:
        """List recent runs with optional filtering."""
        stmt = select(Run)
        if strategy_version_id:
            stmt = stmt.where(Run.strategy_version_id == strategy_version_id)
        if mode:
            stmt = stmt.where(Run.mode == mode.upper())
        stmt = stmt.order_by(Run.created_at.desc()).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def get_equity_curve(self, run_id: str) -> list[EquityPoint]:
        """Get ordered equity curve points for a run."""
        self.get_or_raise(run_id)
        stmt = (
            select(EquityPoint).where(EquityPoint.run_id == run_id).order_by(EquityPoint.ts.asc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_trades(
        self, run_id: str, symbol: str | None = None, limit: int = 500
    ) -> list[RunTrade]:
        """Get trade log for a run."""
        self.get_or_raise(run_id)
        stmt = select(RunTrade).where(RunTrade.run_id == run_id)
        if symbol:
            stmt = stmt.where(RunTrade.symbol == symbol.upper())
        stmt = stmt.order_by(RunTrade.entry_time.asc()).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def compare_runs(self, run_ids: list[str]) -> dict[str, Any]:
        """Compare multiple runs: aligned metrics table, normalized equity curves, and drawdowns."""
        runs = [self.get_or_raise(rid) for rid in run_ids]
        if not runs:
            return {"runs": [], "metrics_diff": {}, "equity_series": []}

        # 1. Extract summary metrics diff
        metrics_diff: dict[str, dict[str, float]] = {}
        metric_keys = [
            "cagr",
            "sharpe",
            "sortino",
            "max_drawdown",
            "calmar",
            "win_rate",
            "profit_factor",
            "expectancy_pct",
            "total_trades",
            "turnover_annual",
        ]
        for key in metric_keys:
            metrics_diff[key] = {}
            for r in runs:
                try:
                    summary = json.loads(r.summary_metrics) if r.summary_metrics else {}
                    val = float(summary.get(key, 0.0))
                    metrics_diff[key][r.id] = round(val, 4)
                except Exception:
                    metrics_diff[key][r.id] = 0.0

        # 2. Extract equity series aligned by timestamp
        equity_by_run: dict[str, list[dict[str, Any]]] = {}
        for r in runs:
            points = self.get_equity_curve(r.id)
            equity_by_run[r.id] = [
                {
                    "ts": pt.ts.isoformat(),
                    "equity": float(pt.total_equity),
                    "drawdown": float(pt.drawdown),
                }
                for pt in points
            ]

        return {
            "runs": [
                {
                    "id": r.id,
                    "strategy_version_id": r.strategy_version_id,
                    "mode": r.mode,
                    "start_ts": r.start_ts.isoformat(),
                    "end_ts": r.end_ts.isoformat(),
                    "data_snapshot_id": r.data_snapshot_id,
                    "git_sha": r.git_sha[:8],
                    "spec_hash": r.spec_hash[:8],
                    "cost_model_hash": r.cost_model_hash[:8],
                    "seed": r.seed,
                    "summary_metrics": json.loads(r.summary_metrics) if r.summary_metrics else {},
                }
                for r in runs
            ],
            "metrics_diff": metrics_diff,
            "equity_by_run": equity_by_run,
        }
