"""Database engine and session management for ATLAS."""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from atlas.core.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Get or create singleton SQLAlchemy database engine."""
    settings = get_settings()
    return create_engine(
        settings.atlas_db_url,
        pool_pre_ping=True,
    )


def get_session_factory() -> sessionmaker[Session]:
    """Get SQLAlchemy sessionmaker factory."""
    return sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding an active SQLAlchemy database session."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()
