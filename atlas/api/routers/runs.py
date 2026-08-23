"""FastAPI router for execution runs, metrics, trades, equity series, and reproducibility metadata."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from atlas.api.schemas.runs import (
    EquityPointResponse,
    RunCreateRequest,
    RunResponse,
    RunTradeResponse,
)
from atlas.backtest.engine import BacktestEngine
from atlas.backtest.registry import RunRegistry
from atlas.core.errors import RunNotFoundError, StrategyVersionNotFoundError
from atlas.core.money import Money
from atlas.data.db import get_db
from atlas.data.snapshots import SnapshotManager
from atlas.research.trials import TrialTracker
from atlas.strategies.registry import StrategyVersionRegistry
from atlas.strategies.spec import StrategySpec

router = APIRouter(prefix="/api/v1/runs", tags=["Runs & Execution"])


@router.get("", response_model=list[RunResponse])
def list_runs(
    db: Annotated[Session, Depends(get_db)],
    strategy_version_id: Annotated[
        str | None, Query(description="Filter by strategy version ID")
    ] = None,
    mode: Annotated[str | None, Query(description="Filter by mode (BACKTEST, PAPER, etc)")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[RunResponse]:
    """List recent execution runs."""
    registry = RunRegistry(db)
    records = registry.list_runs(strategy_version_id=strategy_version_id, mode=mode, limit=limit)
    results: list[RunResponse] = []
    for r in records:
        lib_vers = json.loads(r.lib_versions) if r.lib_versions else {}
        summary_m = json.loads(r.summary_metrics) if r.summary_metrics else {}
        results.append(
            RunResponse(
                id=r.id,
                strategy_version_id=r.strategy_version_id,
                mode=r.mode,
                start_ts=r.start_ts,
                end_ts=r.end_ts,
                data_snapshot_id=r.data_snapshot_id,
                seed=r.seed,
                git_sha=r.git_sha,
                spec_hash=r.spec_hash,
                cost_model_hash=r.cost_model_hash,
                lib_versions=lib_vers,
                status=r.status,
                summary_metrics=summary_m,
                created_at=r.created_at,
                completed_at=r.completed_at,
            )
        )
    return results


@router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
def trigger_backtest_run(
    payload: RunCreateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> RunResponse:
    """Execute and record a backtest run against a registered strategy version and snapshot."""
    version_registry = StrategyVersionRegistry(db)
    try:
        version_rec = version_registry.get_or_raise(payload.strategy_version_id)
    except StrategyVersionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    snapshot_path = Path(payload.snapshot_path)
    if not snapshot_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot path '{payload.snapshot_path}' does not exist.",
        )

    spec = StrategySpec.from_yaml(version_rec.spec_yaml)

    # 1. Load snapshot DataFrame
    mgr = SnapshotManager(snapshot_path.parent)
    df = mgr.load_snapshot_dataframe(snapshot_path.name)

    engine = BacktestEngine(
        spec=spec,
        data=df,
        initial_capital=Money(Decimal(str(payload.capital_usd)), "USD"),
    )

    # Dates
    start_d = (
        date.fromisoformat(payload.start_date) if payload.start_date else df["ts"].min().date()  # type: ignore[union-attr]
    )
    end_d = (
        date.fromisoformat(payload.end_date) if payload.end_date else df["ts"].max().date()  # type: ignore[union-attr]
    )

    result = engine.run(start_date=start_d, end_date=end_d)

    # 2. Extract metrics dictionary
    metrics_dict: dict[str, Any] = asdict(result.metrics)
    metrics_dict["sharpe"] = result.metrics.sharpe_ratio
    metrics_dict["sortino"] = result.metrics.sortino_ratio
    metrics_dict["calmar"] = result.metrics.calmar_ratio

    # 3. Format equity curve
    equity_curve_data: list[dict[str, Any]] = [
        {
            "ts": pt.ts,
            "total_equity": pt.equity,
            "cash": pt.cash,
            "drawdown": 0.0,
            "per_bucket": {},
        }
        for pt in result.equity_curve
    ]

    # Calculate drawdowns
    peak = 0.0
    for pt in equity_curve_data:
        eq = float(str(pt["total_equity"]))
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak if peak > 0 else 0.0
        pt["drawdown"] = dd

    # 4. Format trades from fills
    trade_data: list[dict[str, Any]] = []
    for idx, f in enumerate(result.fills):
        trade_data.append(
            {
                "trade_id": f"T{idx + 1:04d}",
                "symbol": str(f.order_id),
                "direction": "LONG" if f.qty > 0 else "SHORT",
                "entry_time": f.ts,
                "exit_time": f.ts,
                "entry_price": float(f.price),
                "exit_price": float(f.price),
                "quantity": abs(f.qty),
                "pnl": 0.0,
                "pnl_net": -float(f.commission.amount + f.fees.amount),
                "return_pct": 0.0,
                "fees": float(f.fees.amount),
                "slippage": float(f.slippage_est.amount),
                "exit_reason": "FILL",
            }
        )

    # 5. Record run in registry
    run_reg = RunRegistry(db)
    run_id = f"run_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{version_rec.family}"
    cost_hash = spec.costs.model

    start_datetime = datetime.combine(result.start_date, datetime.min.time(), tzinfo=UTC)
    end_datetime = datetime.combine(result.end_date, datetime.max.time(), tzinfo=UTC)

    run_rec = run_reg.record_run(
        run_id=run_id,
        strategy_version_id=version_rec.id,
        mode="BACKTEST",
        start_ts=start_datetime,
        end_ts=end_datetime,
        data_snapshot_id=snapshot_path.name,
        spec_hash=version_rec.spec_hash,
        cost_model_hash=cost_hash,
        seed=payload.seed,
        summary_metrics=metrics_dict,
        equity_curve=equity_curve_data,
        trades=trade_data,
        status="COMPLETED",
    )

    # 6. Record trial
    trial_tracker = TrialTracker(db)
    trial_tracker.record_trial(
        family=version_rec.family,
        parameters=spec.model_dump(mode="json"),
        metrics=metrics_dict,
        run_id=run_id,
        outcome="COMPLETED",
        notes=f"Backtest run against {snapshot_path.name}",
    )

    return RunResponse(
        id=run_rec.id,
        strategy_version_id=run_rec.strategy_version_id,
        mode=run_rec.mode,
        start_ts=run_rec.start_ts,
        end_ts=run_rec.end_ts,
        data_snapshot_id=run_rec.data_snapshot_id,
        seed=run_rec.seed,
        git_sha=run_rec.git_sha,
        spec_hash=run_rec.spec_hash,
        cost_model_hash=run_rec.cost_model_hash,
        lib_versions=json.loads(run_rec.lib_versions) if run_rec.lib_versions else {},
        status=run_rec.status,
        summary_metrics=json.loads(run_rec.summary_metrics) if run_rec.summary_metrics else {},
        created_at=run_rec.created_at,
        completed_at=run_rec.completed_at,
    )


@router.get("/{run_id}", response_model=RunResponse)
def get_run_detail(
    run_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> RunResponse:
    """Get run details and full reproducibility footer metadata."""
    registry = RunRegistry(db)
    try:
        r = registry.get_or_raise(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return RunResponse(
        id=r.id,
        strategy_version_id=r.strategy_version_id,
        mode=r.mode,
        start_ts=r.start_ts,
        end_ts=r.end_ts,
        data_snapshot_id=r.data_snapshot_id,
        seed=r.seed,
        git_sha=r.git_sha,
        spec_hash=r.spec_hash,
        cost_model_hash=r.cost_model_hash,
        lib_versions=json.loads(r.lib_versions) if r.lib_versions else {},
        status=r.status,
        summary_metrics=json.loads(r.summary_metrics) if r.summary_metrics else {},
        created_at=r.created_at,
        completed_at=r.completed_at,
    )


@router.get("/{run_id}/metrics", response_model=dict[str, Any])
def get_run_metrics(
    run_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Get detailed performance and risk metrics dictionary for a run."""
    registry = RunRegistry(db)
    try:
        r = registry.get_or_raise(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return json.loads(r.summary_metrics) if r.summary_metrics else {}


@router.get("/{run_id}/equity", response_model=list[EquityPointResponse])
def get_run_equity_curve(
    run_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[EquityPointResponse]:
    """Get time-series equity points for charting."""
    registry = RunRegistry(db)
    try:
        points = registry.get_equity_curve(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return [
        EquityPointResponse(
            ts=pt.ts,
            total_equity=float(pt.total_equity),
            cash=float(pt.cash),
            drawdown=float(pt.drawdown),
            per_bucket=json.loads(pt.per_bucket) if pt.per_bucket else {},
        )
        for pt in points
    ]


@router.get("/{run_id}/trades", response_model=list[RunTradeResponse])
def get_run_trades(
    run_id: str,
    db: Annotated[Session, Depends(get_db)],
    symbol: Annotated[str | None, Query(description="Filter by symbol")] = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> list[RunTradeResponse]:
    """Get trade blotter for a run."""
    registry = RunRegistry(db)
    try:
        trades = registry.get_trades(run_id=run_id, symbol=symbol, limit=limit)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return [
        RunTradeResponse(
            trade_id=tr.trade_id,
            symbol=tr.symbol,
            direction=tr.direction,
            entry_time=tr.entry_time,
            exit_time=tr.exit_time,
            entry_price=float(tr.entry_price),
            exit_price=float(tr.exit_price),
            quantity=tr.quantity,
            pnl=float(tr.pnl),
            pnl_net=float(tr.pnl_net),
            return_pct=float(tr.return_pct),
            fees=float(tr.fees),
            slippage=float(tr.slippage),
            exit_reason=tr.exit_reason,
        )
        for tr in trades
    ]
