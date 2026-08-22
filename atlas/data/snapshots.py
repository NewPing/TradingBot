"""Immutable, byte-reproducible Parquet snapshot generator and loader."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import polars as pl

from atlas.core.config import get_settings
from atlas.core.types import Bar, Symbol


@dataclass(frozen=True, slots=True)
class SnapshotMetadata:
    """Metadata describing a generated immutable data snapshot."""

    snapshot_id: str
    snapshot_date: str
    symbols_count: int
    bars_count: int
    created_at: str
    sha256_hash: str


class SnapshotManager:
    """Manages creation and loading of deterministic Parquet snapshots."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        settings = get_settings()
        self.base_dir = Path(base_dir or settings.atlas_snapshot_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_snapshot_dir(self, snapshot_date: date | str) -> Path:
        date_str = (
            snapshot_date.isoformat() if isinstance(snapshot_date, date) else str(snapshot_date)
        )
        return self.base_dir / date_str

    @staticmethod
    def bars_to_dataframe(bars: Sequence[Bar]) -> pl.DataFrame:
        """Convert a sequence of Bar objects into a sorted, strongly typed Polars DataFrame."""
        if not bars:
            return pl.DataFrame(
                {
                    "symbol": pl.Series([], dtype=pl.Utf8),
                    "ts": pl.Series([], dtype=pl.Datetime("ms", "UTC")),
                    "open": pl.Series([], dtype=pl.Float64),
                    "high": pl.Series([], dtype=pl.Float64),
                    "low": pl.Series([], dtype=pl.Float64),
                    "close": pl.Series([], dtype=pl.Float64),
                    "volume": pl.Series([], dtype=pl.Int64),
                    "adj_factor": pl.Series([], dtype=pl.Float64),
                    "vwap": pl.Series([], dtype=pl.Float64),
                    "source": pl.Series([], dtype=pl.Utf8),
                    "resolution": pl.Series([], dtype=pl.Utf8),
                }
            )

        data = {
            "symbol": [str(b.symbol) for b in bars],
            "ts": [b.ts for b in bars],
            "open": [float(b.open) for b in bars],
            "high": [float(b.high) for b in bars],
            "low": [float(b.low) for b in bars],
            "close": [float(b.close) for b in bars],
            "volume": [int(b.volume) for b in bars],
            "adj_factor": [float(b.adj_factor) for b in bars],
            "vwap": [float(b.vwap) if b.vwap is not None else None for b in bars],
            "source": [str(b.source) for b in bars],
            "resolution": [str(b.resolution) for b in bars],
        }

        df = pl.DataFrame(data)
        # Enforce deterministic column sorting and row sorting
        df = df.sort(["symbol", "ts"])
        return df

    def create_snapshot(
        self,
        snapshot_date: date | str,
        bars: Sequence[Bar],
        universe: Sequence[Symbol] | None = None,
    ) -> SnapshotMetadata:
        """
        Write a deterministic Parquet dataset to disk and return its metadata and SHA256 hash.
        """
        date_str = (
            snapshot_date.isoformat() if isinstance(snapshot_date, date) else str(snapshot_date)
        )
        target_dir = self._get_snapshot_dir(date_str)
        target_dir.mkdir(parents=True, exist_ok=True)

        bars_path = target_dir / "bars_1d.parquet"
        universe_path = target_dir / "universe.json"
        meta_path = target_dir / "metadata.json"

        # 1. Deterministic Parquet writing
        df = self.bars_to_dataframe(bars)
        # Write with fixed parquet options for byte-reproducibility
        df.write_parquet(
            bars_path,
            compression="zstd",
            compression_level=3,
            use_pyarrow=False,
        )

        # 2. Write universe
        symbols_list = sorted(
            str(s) for s in (universe if universe is not None else df["symbol"].unique().to_list())
        )
        with universe_path.open("w", encoding="utf-8") as f:
            json.dump(symbols_list, f, indent=2, sort_keys=True)

        # 3. Calculate SHA256 hash of the parquet file for strict byte-reproducibility tracking
        hasher = hashlib.sha256()
        with bars_path.open("rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        parquet_hash = hasher.hexdigest()

        metadata = SnapshotMetadata(
            snapshot_id=f"snap_{date_str}_{parquet_hash[:12]}",
            snapshot_date=date_str,
            symbols_count=len(symbols_list),
            bars_count=len(df),
            created_at=datetime.utcnow().isoformat() + "Z",
            sha256_hash=parquet_hash,
        )

        with meta_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "snapshot_id": metadata.snapshot_id,
                    "snapshot_date": metadata.snapshot_date,
                    "symbols_count": metadata.symbols_count,
                    "bars_count": metadata.bars_count,
                    "created_at": metadata.created_at,
                    "sha256_hash": metadata.sha256_hash,
                },
                f,
                indent=2,
                sort_keys=True,
            )

        return metadata

    def load_snapshot_dataframe(self, snapshot_date: date | str) -> pl.DataFrame:
        """Load the Parquet bars DataFrame for a snapshot date."""
        target_dir = self._get_snapshot_dir(snapshot_date)
        bars_path = target_dir / "bars_1d.parquet"
        if not bars_path.exists():
            raise FileNotFoundError(f"Snapshot not found at {bars_path}")
        return pl.read_parquet(bars_path)

    def load_snapshot_metadata(self, snapshot_date: date | str) -> SnapshotMetadata:
        """Load snapshot metadata."""
        target_dir = self._get_snapshot_dir(snapshot_date)
        meta_path = target_dir / "metadata.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Metadata not found at {meta_path}")
        with meta_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return SnapshotMetadata(
            snapshot_id=data["snapshot_id"],
            snapshot_date=data["snapshot_date"],
            symbols_count=data["symbols_count"],
            bars_count=data["bars_count"],
            created_at=data["created_at"],
            sha256_hash=data["sha256_hash"],
        )
