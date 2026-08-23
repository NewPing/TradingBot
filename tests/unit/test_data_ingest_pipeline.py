"""Unit tests for the DataIngestPipeline."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from atlas.core.types import Symbol
from atlas.data.ingest import DataIngestPipeline
from atlas.data.models import Bar1D, Base, Instrument
from atlas.data.providers.base import BaseDataProvider


class MockDataProvider(BaseDataProvider):
    def __init__(self) -> None:
        super().__init__(name="mock", rate_limit_per_sec=100.0)

    async def is_healthy(self) -> bool:
        return True

    async def fetch_daily_bars(
        self,
        symbol: Symbol,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        _ = (symbol, start_date, end_date)
        return [
            {
                "date": "2023-01-03T00:00:00.000Z",
                "open": 100.0,
                "high": 105.0,
                "low": 95.0,
                "close": 102.0,
                "volume": 500000,
                "adjClose": 102.0,
            }
        ]

    async def fetch_corporate_actions(
        self,
        symbol: Symbol,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        _ = (symbol, start_date, end_date)
        return []


@pytest.mark.asyncio
async def test_data_ingest_pipeline_with_db() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)

    provider = MockDataProvider()
    pipeline = DataIngestPipeline(primary_provider=provider)

    bars, issues, result = await pipeline.ingest_symbol(
        symbol=Symbol("AAPL"),
        start_date=date(2023, 1, 3),
        end_date=date(2023, 1, 3),
        session=session,
    )

    assert len(bars) == 1
    assert result.bars_ingested == 1

    # Verify DB records
    inst = session.get(Instrument, "AAPL")
    assert inst is not None

    db_bars = session.query(Bar1D).all()
    assert len(db_bars) == 1
    assert db_bars[0].symbol == "AAPL"

    session.close()
