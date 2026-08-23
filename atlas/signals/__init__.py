"""Signals subsystem: L1 technical indicators, L2 statistical/ML signals, regime detection, and aggregators."""

from __future__ import annotations

from atlas.signals.aggregator import WeightedConfidenceAggregator
from atlas.signals.base import SignalProvider
from atlas.signals.features.base import FeatureExtractor, FeatureMetadata
from atlas.signals.features.breadth import MarketBreadthCalculator
from atlas.signals.features.cross_sectional import CrossSectionalRanker
from atlas.signals.features.extractor import FeatureEngine
from atlas.signals.features.technical import StatisticalFeatureExtractor
from atlas.signals.l1_technical import (
    BollingerSignalProvider,
    FiftyTwoWeekSignalProvider,
    MacdSignalProvider,
    MomentumSignalProvider,
    RsiSignalProvider,
    TrendFilterSignalProvider,
    VolumeZScoreSignalProvider,
)
from atlas.signals.l2_statistical import (
    CrossSectionalMomentumProvider,
    LightGBMSignalProvider,
    MarketRegimeSignalProvider,
)
from atlas.signals.l3_fundamental import (
    EarningsSurpriseSignalProvider,
    ValuationQualitySignalProvider,
)
from atlas.signals.l4_narrative import (
    ExecutiveCatalystSignalProvider,
    MacroGeopoliticalShockSignalProvider,
    NarrativeMomentumSignalProvider,
    NewsSentimentSignalProvider,
)
from atlas.signals.regime import (
    MarketQuadrant,
    RegimeDetector,
    RegimeState,
    TrendRegime,
    VolatilityRegime,
)

__all__ = [
    "BollingerSignalProvider",
    "CrossSectionalMomentumProvider",
    "CrossSectionalRanker",
    "EarningsSurpriseSignalProvider",
    "ExecutiveCatalystSignalProvider",
    "FeatureEngine",
    "FeatureExtractor",
    "FeatureMetadata",
    "FiftyTwoWeekSignalProvider",
    "LightGBMSignalProvider",
    "MacdSignalProvider",
    "MacroGeopoliticalShockSignalProvider",
    "MarketBreadthCalculator",
    "MarketQuadrant",
    "MarketRegimeSignalProvider",
    "MomentumSignalProvider",
    "NarrativeMomentumSignalProvider",
    "NewsSentimentSignalProvider",
    "RegimeDetector",
    "RegimeState",
    "RsiSignalProvider",
    "SignalProvider",
    "StatisticalFeatureExtractor",
    "TrendFilterSignalProvider",
    "TrendRegime",
    "ValuationQualitySignalProvider",
    "VolatilityRegime",
    "VolumeZScoreSignalProvider",
    "WeightedConfidenceAggregator",
]
