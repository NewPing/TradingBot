"""Unit tests for Phase 1 data schema and SQLAlchemy models."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from atlas.data.models import Bar1D, Base, CorporateAction, DataHealth, Instrument, UniverseSnapshot


@pytest.fixture
def memory_db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


def test_instrument_model(memory_db_session: Session) -> None:
    inst = Instrument(
        symbol="AAPL",
        name="Apple Inc.",
        exchange="NASDAQ",
        sector="Technology",
        industry="Consumer Electronics",
        listed_on=date(1980, 12, 12),
        is_etf=False,
        adv_usd=Decimal("5000000000.00"),
    )
    memory_db_session.add(inst)
    memory_db_session.commit()

    retrieved = memory_db_session.get(Instrument, "AAPL")
    assert retrieved is not None
    assert retrieved.name == "Apple Inc."
    assert retrieved.exchange == "NASDAQ"
    assert retrieved.is_etf is False


def test_bar_1d_model(memory_db_session: Session) -> None:
    ts = datetime(2023, 1, 3, 21, 0, 0, tzinfo=UTC)
    bar = Bar1D(
        symbol="SPY",
        ts=ts,
        open=Decimal("384.37"),
        high=Decimal("386.43"),
        low=Decimal("377.83"),
        close=Decimal("380.82"),
        volume=74850700,
        adj_factor=Decimal("0.98500000"),
        source="tiingo",
    )
    memory_db_session.add(bar)
    memory_db_session.commit()

    retrieved = memory_db_session.get(Bar1D, ("SPY", ts))
    assert retrieved is not None
    assert retrieved.close == Decimal("380.8200")
    assert retrieved.volume == 74850700


def test_corporate_action_and_data_health(memory_db_session: Session) -> None:
    ca = CorporateAction(
        symbol="NVDA",
        ex_date=date(2024, 6, 10),
        action_type="SPLIT",
        ratio=Decimal("10.0"),
    )
    dh = DataHealth(
        check_name="unexplained_price_jump",
        ts=datetime.now(UTC),
        symbol="NVDA",
        severity="WARNING",
        detail="Price jumped 15%",
    )
    us = UniverseSnapshot(
        snapshot_date=date(2024, 6, 10),
        symbol="NVDA",
    )

    memory_db_session.add_all([ca, dh, us])
    memory_db_session.commit()

    assert ca.id is not None
    assert dh.id is not None
    assert memory_db_session.get(UniverseSnapshot, (date(2024, 6, 10), "NVDA")) is not None
