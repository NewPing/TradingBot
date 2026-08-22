"""Unit tests for Data CLI commands."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from atlas.core.types import Symbol
from atlas.data.cli import handle_coverage, handle_ingest, handle_snapshot, main
from atlas.data.ingest import IngestionResult
from atlas.data.models import Base


@pytest.fixture
def test_db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


@pytest.mark.asyncio
async def test_cli_handle_ingest() -> None:
    mock_result = IngestionResult(
        symbol=Symbol("AAPL"),
        start_date=date(2023, 1, 1),
        end_date=date(2023, 1, 5),
        bars_ingested=1,
        corporate_actions_count=0,
        issues_found=0,
    )

    with patch(
        "atlas.data.cli.DataIngestPipeline.ingest_symbol",
        new=AsyncMock(return_value=([], [], mock_result)),
    ):
        with patch("atlas.data.cli.get_db_session"):

            class Args:
                symbols = "AAPL,MSFT"
                start = "2023-01-01"
                end = "2023-01-05"
                provider = "tiingo"
                dry_run = True

            await handle_ingest(Args())


def test_cli_handle_snapshot(tmp_path) -> None:
    class Args:
        date = "2023-01-05"

    with patch("atlas.data.cli.get_db_session") as mock_session_getter:
        mock_session = mock_session_getter.return_value
        mock_session.scalars.return_value.all.return_value = []
        with patch("atlas.data.cli.SnapshotManager") as MockSnapMgr:
            mock_meta = MockSnapMgr.return_value.create_snapshot.return_value
            mock_meta.snapshot_id = "snap_1"
            mock_meta.symbols_count = 0
            mock_meta.bars_count = 0
            mock_meta.sha256_hash = "abc"
            handle_snapshot(Args())


def test_cli_handle_coverage(capsys) -> None:
    with patch("atlas.data.cli.get_db_session") as mock_session_getter:
        mock_session = mock_session_getter.return_value
        mock_session.execute.return_value.all.return_value = [
            ("SPY", 100, "2023-01-01", "2023-05-01")
        ]

        class Args:
            pass

        handle_coverage(Args())
        captured = capsys.readouterr()
        assert "SPY" in captured.out
        assert "100" in captured.out


def test_cli_main_entry() -> None:
    with patch("atlas.data.cli.handle_coverage"):
        ret = main(["coverage"])
        assert ret == 0
