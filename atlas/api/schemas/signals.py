"""Pydantic schemas for Signals Explorer API endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SignalSeriesPoint(BaseModel):
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    signals: dict[str, float] = Field(default_factory=dict)


class SignalExploreResponse(BaseModel):
    symbol: str
    points: list[SignalSeriesPoint] = Field(default_factory=list)
    available_indicators: list[str] = Field(default_factory=list)
