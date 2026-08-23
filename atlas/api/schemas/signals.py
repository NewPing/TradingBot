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


class UniverseCandidateResponse(BaseModel):
    symbol: str
    price: float
    adv_20_usd: float
    is_liquid: bool
    is_price_eligible: bool
    roic_pct: float | None = None
    piotroski_f_score: int | None = None
    status: str


class UniverseScreenerResponse(BaseModel):
    as_of_date: str
    total_evaluated: int
    qualified_count: int
    filtered_count: int
    min_adv_usd: float
    min_price_usd: float
    candidates: list[UniverseCandidateResponse]
