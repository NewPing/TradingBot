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
    HorizonMetricsResponse,
    RunCreateRequest,
    RunResponse,
    RunTradeResponse,
)
from atlas.backtest.engine import BacktestEngine
from atlas.backtest.metrics import compute_multi_horizon_metrics
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

    # 4. Format trades from fills using FIFO matching
    trade_data: list[dict[str, Any]] = []
    long_lots_map: dict[str, list[dict[str, Any]]] = {}
    short_lots_map: dict[str, list[dict[str, Any]]] = {}
    trade_counter = 1

    for f in result.fills:
        sym = (
            str(f.symbol)
            if f.symbol
            else (str(f.order_id).split("_")[1] if len(str(f.order_id).split("_")) > 1 else "SPY")
        )
        fill_price = float(f.price)
        total_fees = float(f.commission.amount + f.fees.amount)
        slippage_val = float(f.slippage_est.amount)
        fill_qty = abs(f.qty)
        is_buy = (
            (
                f.side.value.upper() == "BUY"
                if hasattr(f.side, "value")
                else str(f.side).upper() == "BUY"
            )
            if f.side is not None
            else (not str(f.order_id).startswith("stop_") and f.qty > 0)
        )

        if is_buy:
            if sym in short_lots_map and short_lots_map[sym]:
                qty_to_cover = fill_qty
                while qty_to_cover > 0 and short_lots_map[sym]:
                    lot = short_lots_map[sym][0]
                    matched_qty = min(qty_to_cover, lot["qty"])
                    fee_share = total_fees * (matched_qty / fill_qty) + lot["fees"] * (
                        matched_qty / lot["qty"]
                    )
                    trade_pnl = (lot["price"] - fill_price) * matched_qty
                    trade_pnl_net = trade_pnl - fee_share
                    ret_pct = (
                        (lot["price"] - fill_price) / lot["price"] if lot["price"] > 0 else 0.0
                    )

                    trade_data.append(
                        {
                            "trade_id": f"T{trade_counter:04d}",
                            "symbol": sym,
                            "direction": "SHORT",
                            "entry_time": lot["ts"],
                            "exit_time": f.ts,
                            "entry_price": lot["price"],
                            "exit_price": fill_price,
                            "quantity": matched_qty,
                            "pnl": round(trade_pnl, 2),
                            "pnl_net": round(trade_pnl_net, 2),
                            "return_pct": round(ret_pct, 4),
                            "fees": round(fee_share, 2),
                            "slippage": round(slippage_val * (matched_qty / fill_qty), 2),
                            "exit_reason": "COVER",
                        }
                    )
                    trade_counter += 1
                    qty_to_cover -= matched_qty
                    if matched_qty == lot["qty"]:
                        short_lots_map[sym].pop(0)
                    else:
                        lot["qty"] -= matched_qty
                        lot["fees"] -= lot["fees"] * (matched_qty / lot["qty"])

                if qty_to_cover > 0:
                    long_lots_map.setdefault(sym, []).append(
                        {
                            "qty": qty_to_cover,
                            "price": fill_price,
                            "ts": f.ts,
                            "fees": total_fees * (qty_to_cover / fill_qty),
                        }
                    )
            else:
                long_lots_map.setdefault(sym, []).append(
                    {"qty": fill_qty, "price": fill_price, "ts": f.ts, "fees": total_fees}
                )
        else:  # Sell
            if sym in long_lots_map and long_lots_map[sym]:
                qty_to_sell = fill_qty
                while qty_to_sell > 0 and long_lots_map[sym]:
                    lot = long_lots_map[sym][0]
                    matched_qty = min(qty_to_sell, lot["qty"])
                    fee_share = total_fees * (matched_qty / fill_qty) + lot["fees"] * (
                        matched_qty / lot["qty"]
                    )
                    trade_pnl = (fill_price - lot["price"]) * matched_qty
                    trade_pnl_net = trade_pnl - fee_share
                    ret_pct = (
                        (fill_price - lot["price"]) / lot["price"] if lot["price"] > 0 else 0.0
                    )

                    trade_data.append(
                        {
                            "trade_id": f"T{trade_counter:04d}",
                            "symbol": sym,
                            "direction": "LONG",
                            "entry_time": lot["ts"],
                            "exit_time": f.ts,
                            "entry_price": lot["price"],
                            "exit_price": fill_price,
                            "quantity": matched_qty,
                            "pnl": round(trade_pnl, 2),
                            "pnl_net": round(trade_pnl_net, 2),
                            "return_pct": round(ret_pct, 4),
                            "fees": round(fee_share, 2),
                            "slippage": round(slippage_val * (matched_qty / fill_qty), 2),
                            "exit_reason": "SELL",
                        }
                    )
                    trade_counter += 1
                    qty_to_sell -= matched_qty
                    if matched_qty == lot["qty"]:
                        long_lots_map[sym].pop(0)
                    else:
                        lot["qty"] -= matched_qty
                        lot["fees"] -= lot["fees"] * (matched_qty / lot["qty"])

                if qty_to_sell > 0:
                    short_lots_map.setdefault(sym, []).append(
                        {
                            "qty": qty_to_sell,
                            "price": fill_price,
                            "ts": f.ts,
                            "fees": total_fees * (qty_to_sell / fill_qty),
                        }
                    )
            else:
                short_lots_map.setdefault(sym, []).append(
                    {"qty": fill_qty, "price": fill_price, "ts": f.ts, "fees": total_fees}
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


@router.get("/{run_id}/multi-horizon", response_model=list[HorizonMetricsResponse])
def get_run_multi_horizon_metrics(
    run_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[HorizonMetricsResponse]:
    """Get multi-horizon performance comparison (10Y, 5Y, 3Y, 1Y, YTD, ALL) vs S&P 500 benchmark."""
    registry = RunRegistry(db)
    try:
        _ = registry.get_or_raise(run_id)
        points = registry.get_equity_curve(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if not points or len(points) < 2:
        return []

    timestamps = [pt.ts for pt in points]
    equity_series = [float(pt.total_equity) for pt in points]
    initial_cap = equity_series[0] if equity_series else 100_000.0

    # Load trades and reconstruct fills for accurate multi-horizon duration and trade analytics
    trades = registry.get_trades(run_id=run_id, limit=2000)
    reconstructed_fills: list[Any] = []
    from atlas.core.types import Fill, Side, Symbol

    for tr in trades:
        entry_side = Side.BUY if tr.direction == "LONG" else Side.SELL
        exit_side = Side.SELL if tr.direction == "LONG" else Side.BUY
        tr_fees = Money(Decimal(str(round(float(tr.fees), 4))), "USD")
        slip_half = Money(Decimal(str(round(float(tr.slippage) / 2.0, 4))), "USD")

        # In US equities, regulatory fees occur strictly on SELL legs (exits for longs, entries for shorts)
        entry_fees = tr_fees if entry_side == Side.SELL else Money.zero("USD")
        exit_fees = tr_fees if exit_side == Side.SELL else Money.zero("USD")

        reconstructed_fills.append(
            Fill(
                order_id=f"entry_{tr.trade_id}",
                ts=tr.entry_time,
                qty=tr.quantity,
                price=Decimal(str(tr.entry_price)),
                commission=Money.zero("USD"),
                fees=entry_fees,
                slippage_est=slip_half,
                venue="SIM",
                symbol=Symbol(tr.symbol),
                side=entry_side,
            )
        )
        reconstructed_fills.append(
            Fill(
                order_id=f"exit_{tr.trade_id}",
                ts=tr.exit_time,
                qty=tr.quantity,
                price=Decimal(str(tr.exit_price)),
                commission=Money.zero("USD"),
                fees=exit_fees,
                slippage_est=slip_half,
                venue="SIM",
                symbol=Symbol(tr.symbol),
                side=exit_side,
            )
        )

    # Sort reconstructed fills strictly by timestamp for chronological FIFO replay
    reconstructed_fills.sort(
        key=lambda f: (
            f.ts
            if isinstance(f.ts, datetime)
            else datetime.combine(f.ts, datetime.min.time(), tzinfo=UTC)
        )
    )

    horizon_metrics = compute_multi_horizon_metrics(
        timestamps=timestamps,
        equity_series=equity_series,
        initial_capital=initial_cap,
        fills=reconstructed_fills,
    )

    return [
        HorizonMetricsResponse(
            horizon=hm.horizon,
            start_date=hm.start_date,
            end_date=hm.end_date,
            trading_days=hm.trading_days,
            starting_capital=hm.starting_capital,
            ending_equity=hm.ending_equity,
            net_profit_usd=hm.net_profit_usd,
            strategy_return_pct=hm.strategy_return_pct,
            strategy_cagr=hm.strategy_cagr,
            strategy_sharpe=hm.strategy_sharpe,
            strategy_sortino=hm.strategy_sortino,
            strategy_max_drawdown=hm.strategy_max_drawdown,
            strategy_calmar=hm.strategy_calmar,
            win_rate=hm.win_rate,
            profit_factor=hm.profit_factor,
            total_trades=hm.total_trades,
            benchmark_starting_equity=hm.benchmark_starting_equity,
            benchmark_ending_equity=hm.benchmark_ending_equity,
            benchmark_profit_usd=hm.benchmark_profit_usd,
            benchmark_return_pct=hm.benchmark_return_pct,
            benchmark_cagr=hm.benchmark_cagr,
            benchmark_max_drawdown=hm.benchmark_max_drawdown,
            alpha=hm.alpha,
            beta=hm.beta,
            information_ratio=hm.information_ratio,
            tracking_error=hm.tracking_error,
            correlation=hm.correlation,
            avg_holding_days=hm.avg_holding_days,
            avg_win_holding_days=hm.avg_win_holding_days,
            avg_loss_holding_days=hm.avg_loss_holding_days,
            total_slippage_usd=hm.total_slippage_usd,
            total_commissions_usd=hm.total_commissions_usd,
            total_fees_usd=hm.total_fees_usd,
            total_frictional_drag_usd=hm.total_frictional_drag_usd,
            gross_profit_usd=hm.gross_profit_usd,
            frictional_drag_pct=hm.frictional_drag_pct,
        )
        for hm in horizon_metrics
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
