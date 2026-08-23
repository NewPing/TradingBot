"""FastAPI router for sacred multiple-testing trial counters and budget metrics."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from atlas.api.schemas.trials import TrialBudgetResponse, TrialResponse
from atlas.data.db import get_db
from atlas.research.trials import TrialTracker

router = APIRouter(prefix="/api/v1/trials", tags=["Research Trials"])


@router.get("", response_model=list[TrialResponse])
def list_trials(
    db: Annotated[Session, Depends(get_db)],
    family: Annotated[str | None, Query(description="Filter by strategy family")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[TrialResponse]:
    """List recorded trial evaluations."""
    tracker = TrialTracker(db)
    records = tracker.list_trials(family=family, limit=limit)
    return [
        TrialResponse(
            id=t.id,
            hypothesis_id=t.hypothesis_id,
            run_id=t.run_id,
            family=t.family,
            params=json.loads(t.params) if t.params else {},
            metrics=json.loads(t.metrics) if t.metrics else {},
            outcome=t.outcome,
            notes=t.notes,
            created_at=t.created_at,
        )
        for t in records
    ]


@router.get("/budget", response_model=TrialBudgetResponse)
def get_trial_budget(
    db: Annotated[Session, Depends(get_db)],
    family: Annotated[str | None, Query(description="Filter by strategy family")] = None,
    weekly_budget: Annotated[int, Query(ge=1, le=5000)] = 500,
) -> TrialBudgetResponse:
    """Get trial counter and weekly testing budget consumption."""
    tracker = TrialTracker(db)
    status_data = tracker.get_budget_status(family=family, weekly_budget=weekly_budget)
    return TrialBudgetResponse(**status_data)
