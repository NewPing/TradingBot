"""Pydantic schemas for Fundamental, Valuation, and Earnings APIs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FundamentalSnapshotResponse(BaseModel):
    """Detailed point-in-time fundamental filing and calculated metrics."""

    symbol: str
    report_date: str
    filing_date: str
    period: str
    metrics: dict[str, float] = Field(default_factory=dict)
    quality_score: float = 0.5
    value_score: float = 0.5
    roic: float = 0.0
    fcf_yield: float = 0.0
    sloan_accrual: float = 0.0
    ev_ebitda: float = 0.0
    pe_ratio: float = 0.0
    debt_to_equity: float = 0.0
    gross_margin: float = 0.0
    operating_margin: float = 0.0
    rationale: str = ""


class EarningsEventResponse(BaseModel):
    """Earnings announcement event with active blackout status."""

    symbol: str
    event_date: str
    time_of_day: str
    fiscal_period: str | None = None
    eps_estimated: float | None = None
    eps_actual: float | None = None
    revenue_estimated: float | None = None
    revenue_actual: float | None = None
    blackout_status: str = "SAFE"  # SAFE | BLACKOUT_ACTIVE | PAST
    days_until_event: int = 0


class FundamentalScreenerItem(BaseModel):
    """Ranked item in the universe fundamental screener."""

    symbol: str
    sector: str = "General"
    quality_score: float
    value_score: float
    roic: float
    fcf_yield: float
    sloan_accrual: float
    ev_ebitda: float
    pe_ratio: float
    sector_zscore_quality: float = 0.0
    sector_zscore_value: float = 0.0


class FundamentalScreenerResponse(BaseModel):
    """Complete screener output containing all active universe symbols."""

    total: int
    items: list[FundamentalScreenerItem] = Field(default_factory=list)
