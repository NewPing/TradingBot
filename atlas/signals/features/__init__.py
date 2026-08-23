"""Statistical and Machine Learning Feature Store & Extractors."""

from __future__ import annotations

from atlas.signals.features.base import FeatureExtractor, FeatureMetadata
from atlas.signals.features.breadth import MarketBreadthCalculator
from atlas.signals.features.cross_sectional import CrossSectionalRanker
from atlas.signals.features.extractor import FeatureEngine
from atlas.signals.features.fundamental import (
    FundamentalFeatureExtractor,
    SectorRelativeNormalizer,
)
from atlas.signals.features.technical import StatisticalFeatureExtractor

__all__ = [
    "CrossSectionalRanker",
    "FeatureEngine",
    "FeatureExtractor",
    "FeatureMetadata",
    "FundamentalFeatureExtractor",
    "MarketBreadthCalculator",
    "SectorRelativeNormalizer",
    "StatisticalFeatureExtractor",
]
