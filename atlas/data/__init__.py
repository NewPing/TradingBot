"""Data ingestion, normalization, validation, and snapshot management."""

from atlas.data.ingest import DataIngestPipeline, IngestionResult
from atlas.data.models import Bar1D, Base, CorporateAction, DataHealth, Instrument, UniverseSnapshot
from atlas.data.normalize import (
    compute_adjusted_series,
    normalize_alpaca_bar,
    normalize_tiingo_bar,
    normalize_yfinance_bar,
)
from atlas.data.snapshots import SnapshotManager, SnapshotMetadata
from atlas.data.universe import UniverseBuilder, UniverseCriteria
from atlas.data.validate import DataValidator, ValidationIssue, ValidationSeverity

__all__ = [
    "Bar1D",
    "Base",
    "CorporateAction",
    "DataHealth",
    "DataIngestPipeline",
    "DataValidator",
    "IngestionResult",
    "Instrument",
    "SnapshotManager",
    "SnapshotMetadata",
    "UniverseBuilder",
    "UniverseCriteria",
    "UniverseSnapshot",
    "ValidationIssue",
    "ValidationSeverity",
    "compute_adjusted_series",
    "normalize_alpaca_bar",
    "normalize_tiingo_bar",
    "normalize_yfinance_bar",
]
