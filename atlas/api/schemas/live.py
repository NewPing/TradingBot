"""Pydantic schemas for Live and Paper Trading API endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BucketEquityResponse(BaseModel):
    bucket: str
    target_allocation_pct: float
    current_allocation_pct: float
    equity: float
    cash: float
    positions_count: int
    unrealized_pnl: float


class LiveStateResponse(BaseModel):
    ts: datetime
    run_id: str
    mode: str
    is_halted: bool
    total_equity: float
    cash: float
    buying_power: float
    today_pnl: float
    today_pnl_pct: float
    open_positions_count: int
    active_orders_count: int
    buckets: list[BucketEquityResponse] = Field(default_factory=list)


class LivePositionResponse(BaseModel):
    symbol: str
    bucket: str
    qty: int
    avg_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    opened_ts: datetime
    stop_px: float | None = None


class LiveOrderResponse(BaseModel):
    id: str
    run_id: str
    strategy_version_id: str
    bucket: str
    symbol: str
    side: str
    qty: int
    order_type: str
    tif: str
    limit_px: float | None = None
    stop_px: float | None = None
    status: str
    created_ts: datetime


class LiveFillResponse(BaseModel):
    id: int
    order_id: str
    ts: datetime
    qty: int
    price: float
    commission: float
    fees: float
    venue: str
