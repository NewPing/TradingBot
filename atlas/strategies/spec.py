"""Strategy specification models, YAML parsing, validation, and SHA-256 hash generation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from atlas.core.types import BucketId


class UniverseFilterConfig(BaseModel):
    min_adv_usd: float = 20_000_000.0
    min_price: float = 5.0
    exclude_otc: bool = True
    symbols: list[str] = Field(default_factory=list)


class RebalanceConfig(BaseModel):
    schedule: str = (
        "monthly_last_trading_day"  # daily, weekly_monday, monthly_last_trading_day, buy_and_hold
    )
    time: str = "15:45 America/New_York"


class SignalConfig(BaseModel):
    provider: str
    weight: float = 1.0
    params: dict[str, Any] = Field(default_factory=dict)


class AggregatorConfig(BaseModel):
    type: str = "weighted_confidence"
    min_confidence: float = 0.3


class PolicyConfig(BaseModel):
    type: str = "top_n_long_only"
    n: int = 5
    min_score: float = 0.2
    weight_by: str = "inverse_vol"
    max_position_pct: float = 0.20
    enter_threshold: float = 0.3
    exit_threshold: float = -0.1
    allow_short: bool = False


class StopConfig(BaseModel):
    type: str = "atr_trailing"  # atr_trailing, hard_pct, none
    atr_period: int = 14
    multiple: float = 3.0
    pct: float = 0.25


class CostConfig(BaseModel):
    model: str = "default_v1"
    k: float = 1.0
    broker: str = "alpaca"


class StrategySpec(BaseModel):
    """Immutable specification for a trading strategy version."""

    name: str
    family: str
    version: str = "1.0.0"
    parent_id: str | None = None
    bucket: BucketId = BucketId.CORE
    author: str = "system"
    description: str = ""

    universe: UniverseFilterConfig = Field(default_factory=UniverseFilterConfig)
    rebalance: RebalanceConfig = Field(default_factory=RebalanceConfig)
    signals: list[SignalConfig] = Field(default_factory=list)
    aggregator: AggregatorConfig = Field(default_factory=AggregatorConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    stop: StopConfig = Field(default_factory=StopConfig)
    costs: CostConfig = Field(default_factory=CostConfig)

    def spec_hash(self) -> str:
        """Compute deterministic SHA-256 hash of the canonical spec content."""
        canonical_dict = self.model_dump(mode="json")
        canonical_json = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @classmethod
    def from_yaml(cls, path_or_content: str | Path) -> StrategySpec:
        """Load and validate strategy specification from YAML file or string."""
        if isinstance(path_or_content, Path) or (
            isinstance(path_or_content, str)
            and ("\n" not in path_or_content and Path(path_or_content).exists())
        ):
            path = Path(path_or_content)
            with path.open(encoding="utf-8") as f:
                raw_data = yaml.safe_load(f)
        else:
            raw_data = yaml.safe_load(str(path_or_content))

        if not isinstance(raw_data, dict):
            raise ValueError(
                f"Invalid YAML strategy specification: expected dict, got {type(raw_data)}"
            )

        return cls.model_validate(raw_data)
