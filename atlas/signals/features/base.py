"""Base feature extraction protocol and metadata definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from atlas.core.context import MarketContext
from atlas.core.types import Symbol


@dataclass(frozen=True)
class FeatureMetadata:
    """Metadata describing a statistical or ML feature."""

    name: str
    description: str
    category: str  # technical, statistical, cross_sectional, breadth, regime
    lookback_bars: int
    min_value: float | None = None
    max_value: float | None = None
    is_normalized: bool = False


class FeatureExtractor(Protocol):
    """Protocol for single or multi-feature extractors."""

    @property
    def feature_names(self) -> list[str]:
        """List of feature column names produced by this extractor."""
        ...

    @property
    def warmup_bars(self) -> int:
        """Minimum bars required before extracting valid features."""
        ...

    def metadata(self) -> list[FeatureMetadata]:
        """List of metadata objects for the generated features."""
        ...

    def extract_pit(self, ctx: MarketContext, symbol: Symbol) -> dict[str, float]:
        """Extract latest feature dictionary strictly at or before ctx.now."""
        ...

    def extract_batch(self, df_bars: pd.DataFrame) -> pd.DataFrame:
        """Extract full time-series feature matrix from historical bars DataFrame.

        Expected columns in df_bars: ['timestamp', 'open', 'high', 'low', 'close', 'volume'].
        """
        ...
