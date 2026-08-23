"""Pydantic schemas for Shadow Execution and Divergence Telemetry (Phase 9)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ShadowLogRecord(BaseModel):
    id: str
    run_id: str
    symbol: str
    timestamp: datetime
    side: str
    quantity: int
    model_price_usd: float
    simulated_fill_price_usd: float
    slippage_bps: float
    quote_latency_ms: float
    routing_venue: str


class ShadowTelemetryResponse(BaseModel):
    total_shadow_trades: int
    mean_slippage_bps: float
    max_slippage_bps: float
    p95_slippage_bps: float
    mean_quote_latency_ms: float
    p95_quote_latency_ms: float
    positive_slippage_trades: int
    zero_or_better_trades: int
    sample_records: list[dict[str, Any]] = Field(default_factory=list)


class TOTPVerifyRequest(BaseModel):
    code: str
    action: str = "EMERGENCY_ACTION"


class TOTPVerifyResponse(BaseModel):
    valid: bool
    message: str
