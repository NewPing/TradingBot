"""Strategy specification, validation, and component builder."""

from __future__ import annotations

from atlas.strategies.builder import (
    build_aggregator,
    build_cost_model,
    build_position_policy,
    build_signal_provider,
)
from atlas.strategies.spec import (
    AggregatorConfig,
    CostConfig,
    PolicyConfig,
    RebalanceConfig,
    SignalConfig,
    StopConfig,
    StrategySpec,
    UniverseFilterConfig,
)

__all__ = [
    "AggregatorConfig",
    "CostConfig",
    "PolicyConfig",
    "RebalanceConfig",
    "SignalConfig",
    "StopConfig",
    "StrategySpec",
    "UniverseFilterConfig",
    "build_aggregator",
    "build_cost_model",
    "build_position_policy",
    "build_signal_provider",
]
