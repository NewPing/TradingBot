"""FastAPI router for strategy version registry and lineage management."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from atlas.api.schemas.versions import (
    LineageNode,
    LineageResponse,
    StrategyStatusUpdate,
    StrategyVersionCreate,
    StrategyVersionResponse,
)
from atlas.core.errors import SpecImmutabilityError, StrategyVersionNotFoundError
from atlas.data.db import get_db
from atlas.strategies.registry import StrategyVersionRegistry
from atlas.strategies.spec import StrategySpec

router = APIRouter(prefix="/api/v1/versions", tags=["Strategy Versions"])


@router.get("", response_model=list[StrategyVersionResponse])
def list_strategy_versions(
    db: Annotated[Session, Depends(get_db)],
    family: Annotated[str | None, Query(description="Filter by strategy family")] = None,
) -> list[StrategyVersionResponse]:
    """List all registered strategy versions."""
    registry = StrategyVersionRegistry(db)
    records = registry.list_all(family=family)
    return [
        StrategyVersionResponse(
            id=r.id,
            family=r.family,
            version=r.version,
            spec_hash=r.spec_hash,
            git_sha=r.git_sha,
            parent_id=r.parent_id,
            status=r.status,
            notes=r.notes,
            created_at=r.created_at,
            spec_yaml=r.spec_yaml,
        )
        for r in records
    ]


@router.post("", response_model=StrategyVersionResponse, status_code=status.HTTP_201_CREATED)
def create_strategy_version(
    payload: StrategyVersionCreate,
    db: Annotated[Session, Depends(get_db)],
) -> StrategyVersionResponse:
    """Register a new strategy version from YAML specification."""
    try:
        spec = StrategySpec.from_yaml(payload.spec_yaml)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse strategy YAML spec: {exc}",
        ) from exc

    registry = StrategyVersionRegistry(db)
    try:
        record = registry.register_spec(
            spec=spec,
            raw_yaml=payload.spec_yaml,
            notes=payload.notes,
            status=payload.status,
        )
    except SpecImmutabilityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except StrategyVersionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return StrategyVersionResponse(
        id=record.id,
        family=record.family,
        version=record.version,
        spec_hash=record.spec_hash,
        git_sha=record.git_sha,
        parent_id=record.parent_id,
        status=record.status,
        notes=record.notes,
        created_at=record.created_at,
        spec_yaml=record.spec_yaml,
    )


@router.post("/sync", response_model=list[StrategyVersionResponse])
def sync_strategies_directory(
    db: Annotated[Session, Depends(get_db)],
) -> list[StrategyVersionResponse]:
    """Auto-discover and register all YAML specifications in strategies/ directory."""
    registry = StrategyVersionRegistry(db)
    strategies_dir = Path("strategies")
    records = registry.sync_directory(strategies_dir)
    return [
        StrategyVersionResponse(
            id=r.id,
            family=r.family,
            version=r.version,
            spec_hash=r.spec_hash,
            git_sha=r.git_sha,
            parent_id=r.parent_id,
            status=r.status,
            notes=r.notes,
            created_at=r.created_at,
            spec_yaml=r.spec_yaml,
        )
        for r in records
    ]


@router.get("/{version_id}", response_model=StrategyVersionResponse)
def get_strategy_version(
    version_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> StrategyVersionResponse:
    """Get strategy version details by ID."""
    registry = StrategyVersionRegistry(db)
    try:
        r = registry.get_or_raise(version_id)
    except StrategyVersionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return StrategyVersionResponse(
        id=r.id,
        family=r.family,
        version=r.version,
        spec_hash=r.spec_hash,
        git_sha=r.git_sha,
        parent_id=r.parent_id,
        status=r.status,
        notes=r.notes,
        created_at=r.created_at,
        spec_yaml=r.spec_yaml,
    )


@router.patch("/{version_id}/status", response_model=StrategyVersionResponse)
def update_strategy_status(
    version_id: str,
    payload: StrategyStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> StrategyVersionResponse:
    """Update promotion lifecycle status of a strategy version."""
    registry = StrategyVersionRegistry(db)
    try:
        r = registry.update_status(version_id, payload.status, payload.notes)
    except StrategyVersionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return StrategyVersionResponse(
        id=r.id,
        family=r.family,
        version=r.version,
        spec_hash=r.spec_hash,
        git_sha=r.git_sha,
        parent_id=r.parent_id,
        status=r.status,
        notes=r.notes,
        created_at=r.created_at,
        spec_yaml=r.spec_yaml,
    )


@router.get("/{version_id}/lineage", response_model=LineageResponse)
def get_strategy_lineage(
    version_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> LineageResponse:
    """Get full lineage graph for a strategy version."""
    registry = StrategyVersionRegistry(db)
    try:
        data = registry.get_lineage(version_id)
    except StrategyVersionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return LineageResponse(
        current=LineageNode(**data["current"]),
        ancestors=[LineageNode(**a) for a in data["ancestors"]],
        children=[LineageNode(**c) for c in data["children"]],
    )
