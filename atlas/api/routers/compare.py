"""FastAPI router for multi-run comparison and visualization."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from atlas.api.schemas.runs import CompareRequest, CompareResponse
from atlas.backtest.registry import RunRegistry
from atlas.core.errors import RunNotFoundError
from atlas.data.db import get_db

router = APIRouter(prefix="/api/v1/compare", tags=["Run Comparison"])


@router.post("", response_model=CompareResponse)
def compare_runs_post(
    payload: CompareRequest,
    db: Annotated[Session, Depends(get_db)],
) -> CompareResponse:
    """Compare multiple runs by IDs (aligned metrics diff and overlaid equity series)."""
    if not payload.run_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No run_ids provided.")

    registry = RunRegistry(db)
    try:
        data = registry.compare_runs(payload.run_ids)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return CompareResponse(**data)


@router.get("", response_model=CompareResponse)
def compare_runs_get(
    run_ids: Annotated[list[str], Query(description="List of run IDs to compare")],
    db: Annotated[Session, Depends(get_db)],
) -> CompareResponse:
    """Compare multiple runs via query parameters."""
    if not run_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No run_ids provided.")

    # Flatten if comma-separated
    flat_ids: list[str] = []
    for item in run_ids:
        flat_ids.extend([x.strip() for x in item.split(",") if x.strip()])

    registry = RunRegistry(db)
    try:
        data = registry.compare_runs(flat_ids)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return CompareResponse(**data)
