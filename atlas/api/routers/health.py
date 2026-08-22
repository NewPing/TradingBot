"""Health check and system version endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from atlas import __version__
from atlas.api.schemas import HealthResponse, VersionResponse
from atlas.core.config import get_settings

router = APIRouter(tags=["System"])


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Return system health status."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(UTC),
        environment=settings.atlas_env,
        version=__version__,
    )


@router.get("/version", response_model=VersionResponse)
async def get_version() -> VersionResponse:
    """Return system version, active phase, and safety status."""
    settings = get_settings()
    return VersionResponse(
        version=__version__,
        phase=0,
        environment=settings.atlas_env,
        allow_live=settings.atlas_allow_live,
    )
