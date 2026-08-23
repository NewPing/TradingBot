"""FastAPI router for sacred trial tracking and multiple testing budget telemetry."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from atlas.api.schemas.trials import TrialBudgetResponse, TrialResponse
from atlas.data.db import get_db
from atlas.research.trials import TrialTracker

router = APIRouter(prefix="/api/v1/trials", tags=["Trial Ledger"])


@router.get("", response_model=list[TrialResponse])
def list_trials(
    db: Annotated[Session, Depends(get_db)],
    family: Annotated[str | None, Query(description="Filter by strategy family")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[TrialResponse]:
    """List historical trials recorded in the multiple testing ledger."""
    tracker = TrialTracker(db)
    records = tracker.list_trials(family=family, limit=limit)
    return [
        TrialResponse(
            id=r.id,
            hypothesis_id=r.hypothesis_id,
            run_id=r.run_id,
            family=r.family,
            params=json.loads(r.params) if r.params else {},
            metrics=json.loads(r.metrics) if r.metrics else {},
            outcome=r.outcome,
            notes=r.notes,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.get("/budget", response_model=TrialBudgetResponse)
def get_trial_budget(
    db: Annotated[Session, Depends(get_db)],
    family: Annotated[str | None, Query(description="Filter by strategy family")] = None,
    weekly_budget: Annotated[
        int, Query(description="Weekly budget constraint (0 or negative for unlimited in v1.5)")
    ] = 0,
) -> TrialBudgetResponse:
    """Get sacred trial budget status and multiple testing consumption rate."""
    tracker = TrialTracker(db)
    status = tracker.get_budget_status(family=family, weekly_budget=weekly_budget)
    return TrialBudgetResponse(**status)
