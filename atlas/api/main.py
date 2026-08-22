"""FastAPI main application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas import __version__
from atlas.api.routers import health
from atlas.core.config import get_settings
from atlas.core.logging import get_logger, setup_logging

logger = get_logger("api")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.atlas_log_level, settings.atlas_log_format)
    logger.info(
        f"Starting ATLAS API v{__version__} [env={settings.atlas_env}, live_allowed={settings.atlas_allow_live}]"
    )
    yield
    logger.info("Stopping ATLAS API")


app = FastAPI(
    title="ATLAS Trading Engine API",
    description="Autonomous Trading & Learning Analysis System",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
