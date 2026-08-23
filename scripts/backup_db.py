"""Automated database and data snapshot backup script (Phase 9)."""

from __future__ import annotations

import argparse
import logging
import tarfile
from datetime import UTC, datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("atlas.backup")


def create_backup(
    db_path: str = "atlas.db",
    data_dir: str = "data",
    output_dir: str = "backups",
) -> Path:
    """Create timestamped tar.gz archive containing database and snapshot datasets."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    ts_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    archive_name = f"atlas_backup_{ts_str}.tar.gz"
    archive_path = out_path / archive_name

    logger.info("Starting backup into %s...", archive_path)

    with tarfile.open(archive_path, "w:gz") as tar:
        # Backup sqlite db if present
        db_file = Path(db_path)
        if db_file.exists():
            logger.info("Archiving database file: %s", db_file)
            tar.add(db_file, arcname=db_file.name)
        else:
            logger.warning("Database file %s not found; skipping.", db_path)

        # Backup data snapshots if present
        data_path = Path(data_dir)
        if data_path.exists():
            logger.info("Archiving data directory: %s", data_path)
            tar.add(data_path, arcname="data")

    file_size_kb = archive_path.stat().st_size / 1024.0
    logger.info("Backup created successfully: %s (%.1f KB)", archive_path, file_size_kb)
    return archive_path


def main() -> None:
    parser = argparse.ArgumentParser(description="ATLAS automated backup tool")
    parser.add_argument("--db-path", default="atlas.db", help="Path to SQLite or DB export")
    parser.add_argument("--data-dir", default="data", help="Path to snapshots directory")
    parser.add_argument("--output-dir", default="backups", help="Target backup directory")
    args = parser.parse_args()

    create_backup(
        db_path=args.db_path,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
