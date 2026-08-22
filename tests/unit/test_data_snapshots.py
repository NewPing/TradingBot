"""Unit tests for immutable Parquet snapshots and byte-reproducibility."""

import tempfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from atlas.core.types import Bar, Symbol
from atlas.data.snapshots import SnapshotManager


def test_snapshot_creation_and_reproducibility() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        manager1 = SnapshotManager(base_dir=tmpdir)
        manager2 = SnapshotManager(base_dir=tmpdir)

        bars = [
            Bar(
                symbol=Symbol("AAPL"),
                ts=datetime(2023, 1, 3, 21, 0, 0, tzinfo=UTC),
                open=Decimal("130.0"),
                high=Decimal("135.0"),
                low=Decimal("128.0"),
                close=Decimal("132.0"),
                volume=10000000,
                adj_factor=Decimal("1.0"),
            ),
            Bar(
                symbol=Symbol("MSFT"),
                ts=datetime(2023, 1, 3, 21, 0, 0, tzinfo=UTC),
                open=Decimal("240.0"),
                high=Decimal("245.0"),
                low=Decimal("238.0"),
                close=Decimal("242.0"),
                volume=8000000,
                adj_factor=Decimal("1.0"),
            ),
        ]

        # First run
        meta1 = manager1.create_snapshot("2023-01-03", bars)
        parquet_file1 = Path(tmpdir) / "2023-01-03" / "bars_1d.parquet"
        content1 = parquet_file1.read_bytes()

        # Re-write the same data independently
        meta2 = manager2.create_snapshot("2023-01-03", bars)
        parquet_file2 = Path(tmpdir) / "2023-01-03" / "bars_1d.parquet"
        content2 = parquet_file2.read_bytes()

        # Byte-identical snapshot gate verification
        assert content1 == content2
        assert meta1.sha256_hash == meta2.sha256_hash
        assert meta1.bars_count == 2
        assert meta1.symbols_count == 2

        # Load back
        df = manager1.load_snapshot_dataframe("2023-01-03")
        assert len(df) == 2
        assert set(df["symbol"].to_list()) == {"AAPL", "MSFT"}
