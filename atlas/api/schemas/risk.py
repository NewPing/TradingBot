"""Pydantic schemas for Risk Management and Kill Switch API endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ActiveKillSwitchResponse(BaseModel):
    trigger: str
    action: str
    detail: str
    triggered_at: datetime
    affected_bucket: str | None = None
    reset_type: str


class RiskStatusResponse(BaseModel):
    is_halted: bool
    active_switches: list[ActiveKillSwitchResponse] = Field(default_factory=list)
    allows_entries: dict[str, bool] = Field(default_factory=dict)
    daily_order_counts: dict[str, int] = Field(default_factory=dict)
    peak_equity: float
    session_open_equity: float


class KillSwitchResetRequest(BaseModel):
    trigger: str
    resolved_by: str = "operator"


class EmergencyFlattenRequest(BaseModel):
    bucket: str | None = None  # None = flatten all
    reason: str = "Manual operator emergency flatten"
