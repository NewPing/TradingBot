"""Signals subsystem: L1 technical indicators, base providers, and aggregators."""

from __future__ import annotations

from atlas.signals.aggregator import WeightedConfidenceAggregator
from atlas.signals.base import SignalProvider
from atlas.signals.l1_technical import (
    BollingerSignalProvider,
    FiftyTwoWeekSignalProvider,
    MacdSignalProvider,
    MomentumSignalProvider,
    RsiSignalProvider,
    TrendFilterSignalProvider,
    VolumeZScoreSignalProvider,
)

__all__ = [
    "BollingerSignalProvider",
    "FiftyTwoWeekSignalProvider",
    "MacdSignalProvider",
    "MomentumSignalProvider",
    "RsiSignalProvider",
    "SignalProvider",
    "TrendFilterSignalProvider",
    "VolumeZScoreSignalProvider",
    "WeightedConfidenceAggregator",
]
