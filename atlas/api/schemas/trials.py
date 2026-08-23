"""Pydantic schemas for Trial counter API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TrialResponse(BaseModel):
    id: int
    hypothesis_id: str | None = None
    run_id: str | None = None
    family: str
    params: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    outcome: str
    notes: str = ""
    created_at: datetime


class TrialBudgetResponse(BaseModel):
    total_trials: int
    trials_this_week: int
    weekly_budget: int
    budget_remaining: int
    budget_pct_used: float
    family: str
