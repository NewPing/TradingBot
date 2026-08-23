"""Pydantic v2 API request and response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from atlas.api.schemas.runs import (
    CompareRequest,
    CompareResponse,
    EquityPointResponse,
    RunCreateRequest,
    RunResponse,
    RunTradeResponse,
)
from atlas.api.schemas.signals import SignalExploreResponse, SignalSeriesPoint
from atlas.api.schemas.trials import TrialBudgetResponse, TrialResponse
from atlas.api.schemas.versions import (
    LineageNode,
    LineageResponse,
    StrategyStatusUpdate,
    StrategyVersionCreate,
    StrategyVersionResponse,
)


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service health status: ok | degraded | unhealthy")
    timestamp: datetime = Field(..., description="Current UTC timestamp")
    environment: str = Field(..., description="Runtime environment")
    version: str = Field(..., description="Application version")


class VersionResponse(BaseModel):
    version: str
    phase: int
    environment: str
    allow_live: bool


__all__ = [
    "CompareRequest",
    "CompareResponse",
    "EquityPointResponse",
    "HealthResponse",
    "LineageNode",
    "LineageResponse",
    "RunCreateRequest",
    "RunResponse",
    "RunTradeResponse",
    "SignalExploreResponse",
    "SignalSeriesPoint",
    "StrategyStatusUpdate",
    "StrategyVersionCreate",
    "StrategyVersionResponse",
    "TrialBudgetResponse",
    "TrialResponse",
    "VersionResponse",
]
