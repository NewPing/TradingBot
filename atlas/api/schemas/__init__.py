"""Pydantic v2 API request and response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


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
