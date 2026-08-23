"""FastAPI router for Live and Paper Trading state, orders, fills, and blotter."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from atlas.api.routers.risk import get_risk_manager
from atlas.api.schemas.live import (
    BucketEquityResponse,
    LiveFillResponse,
    LiveOrderResponse,
    LivePositionResponse,
    LiveStateResponse,
)
from atlas.core.money import Money
from atlas.core.types import Symbol
from atlas.data.db import get_db
from atlas.data.models import FillRecord, OrderRecord
from atlas.portfolio.buckets import DEFAULT_BUCKET_CONFIGS
from atlas.portfolio.ledger import BucketLedger
from atlas.risk.manager import RiskManager

router = APIRouter(prefix="/api/v1/live", tags=["Live / Paper Trading"])

# Global runtime ledger instance
_global_ledger: BucketLedger | None = None


def get_ledger() -> BucketLedger:
    global _global_ledger
    if _global_ledger is None:
        _global_ledger = BucketLedger()
        # Seed default starting paper capital ($100,000)
        _global_ledger.deposit(Money(Decimal("100000.00"), "USD"))
    return _global_ledger


@router.get("/state", response_model=LiveStateResponse)
def get_live_state(
    ledger: Annotated[BucketLedger, Depends(get_ledger)],
    risk: Annotated[RiskManager, Depends(get_risk_manager)],
    db: Annotated[Session, Depends(get_db)],
) -> LiveStateResponse:
    """Get current live/paper trading account equity, cash, and bucket breakdown."""
    now = datetime.now(UTC)
    current_prices: dict[Symbol, Decimal] = {}

    tot_eq = ledger.total_equity(current_prices)
    tot_cash = ledger.total_cash()
    open_pos = ledger.all_positions()

    # Query active orders count
    active_orders_count = (
        db.query(OrderRecord)
        .filter(OrderRecord.status.in_(["NEW", "SUBMITTED", "PARTIALLY_FILLED"]))
        .count()
    )

    # Bucket breakdown
    bucket_list: list[BucketEquityResponse] = []
    for b_id, cfg in DEFAULT_BUCKET_CONFIGS.items():
        acc = ledger.accounts[b_id]
        b_eq = acc.equity(current_prices)
        b_cash = acc.cash
        alloc_pct = float(b_eq.amount / tot_eq.amount) if tot_eq.amount > Decimal("0") else 0.0
        bucket_list.append(
            BucketEquityResponse(
                bucket=b_id.value,
                target_allocation_pct=float(cfg.target_allocation),
                current_allocation_pct=alloc_pct,
                equity=float(b_eq.amount),
                cash=float(b_cash.amount),
                positions_count=len(acc.positions),
                unrealized_pnl=float(acc.unrealized_pnl(current_prices).amount),
            )
        )

    # Daily P&L calculation
    session_open = risk.kill_switches.session_open_equity
    if session_open > Decimal("0"):
        today_pnl_amt = tot_eq.amount - session_open
        today_pnl_pct = float(today_pnl_amt / session_open)
    else:
        today_pnl_amt = Decimal("0")
        today_pnl_pct = 0.0

    return LiveStateResponse(
        ts=now,
        run_id="live-paper-session",
        mode="PAPER",
        is_halted=risk.kill_switches.is_triggered(),
        total_equity=float(tot_eq.amount),
        cash=float(tot_cash.amount),
        buying_power=float(tot_cash.amount),
        today_pnl=float(today_pnl_amt),
        today_pnl_pct=today_pnl_pct,
        open_positions_count=len(open_pos),
        active_orders_count=active_orders_count,
        buckets=bucket_list,
    )


@router.get("/positions", response_model=list[LivePositionResponse])
def get_live_positions(
    ledger: Annotated[BucketLedger, Depends(get_ledger)],
) -> list[LivePositionResponse]:
    """Get list of all currently open positions."""
    current_prices: dict[Symbol, Decimal] = {}
    positions = ledger.all_positions()
    result: list[LivePositionResponse] = []

    for p in positions:
        cur_px = current_prices.get(p.symbol, p.avg_price)
        mv = cur_px * p.qty
        unrealized = (cur_px - p.avg_price) * p.qty
        unrealized_pct = (
            float((cur_px - p.avg_price) / p.avg_price) if p.avg_price > Decimal("0") else 0.0
        )

        result.append(
            LivePositionResponse(
                symbol=str(p.symbol),
                bucket=p.bucket.value,
                qty=p.qty,
                avg_price=float(p.avg_price),
                current_price=float(cur_px),
                market_value=float(mv),
                unrealized_pnl=float(unrealized),
                unrealized_pnl_pct=unrealized_pct,
                opened_ts=p.opened_ts,
                stop_px=float(p.stop_px) if p.stop_px is not None else None,
            )
        )
    return result


@router.get("/orders", response_model=list[LiveOrderResponse])
def get_live_orders(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[LiveOrderResponse]:
    """Get recent order blotter history."""
    stmt = select(OrderRecord).order_by(desc(OrderRecord.created_ts)).limit(limit)
    records = db.execute(stmt).scalars().all()
    return [
        LiveOrderResponse(
            id=r.id,
            run_id=r.run_id,
            strategy_version_id=r.strategy_version_id,
            bucket=r.bucket,
            symbol=r.symbol,
            side=r.side,
            qty=r.qty,
            order_type=r.order_type,
            tif=r.tif,
            limit_px=float(r.limit_px) if r.limit_px is not None else None,
            stop_px=float(r.stop_px) if r.stop_px is not None else None,
            status=r.status,
            created_ts=r.created_ts,
        )
        for r in records
    ]


@router.get("/fills", response_model=list[LiveFillResponse])
def get_live_fills(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[LiveFillResponse]:
    """Get recent execution fills history."""
    stmt = select(FillRecord).order_by(desc(FillRecord.ts)).limit(limit)
    records = db.execute(stmt).scalars().all()
    return [
        LiveFillResponse(
            id=r.id,
            order_id=r.order_id,
            ts=r.ts,
            qty=r.qty,
            price=float(r.price),
            commission=float(r.commission),
            fees=float(r.fees),
            venue=r.venue,
        )
        for r in records
    ]
