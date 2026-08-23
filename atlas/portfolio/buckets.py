"""Bucket specifications, configuration, and allocation limits."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from atlas.core.types import BucketId


@dataclass(frozen=True, slots=True)
class BucketConfig:
    """Static parameters and constraints governing an independent sub-portfolio bucket."""

    bucket_id: BucketId
    target_allocation: Decimal  # e.g. Decimal("0.50")
    rebalance_band: Decimal  # e.g. Decimal("0.05") -> [0.45, 0.55]
    vol_budget: Decimal  # Annualized volatility budget, e.g. Decimal("0.10")
    max_positions: int  # Max concurrent positions
    max_single_position_pct: Decimal  # Max notional as % of bucket equity, e.g. Decimal("0.20")
    horizon: str  # Human readable horizon
    stop_policy: str  # Stop policy description

    @property
    def min_allocation(self) -> Decimal:
        return max(Decimal("0.0"), self.target_allocation - self.rebalance_band)

    @property
    def max_allocation(self) -> Decimal:
        return min(Decimal("1.0"), self.target_allocation + self.rebalance_band)


# Master Plan §6.1 canonical bucket definitions
DEFAULT_BUCKET_CONFIGS: dict[BucketId, BucketConfig] = {
    BucketId.CORE: BucketConfig(
        bucket_id=BucketId.CORE,
        target_allocation=Decimal("0.50"),
        rebalance_band=Decimal("0.05"),
        vol_budget=Decimal("0.10"),
        max_positions=8,
        max_single_position_pct=Decimal("0.20"),
        horizon="1-12 months",
        stop_policy="ATR-trailing 3x or regime exit",
    ),
    BucketId.SWING: BucketConfig(
        bucket_id=BucketId.SWING,
        target_allocation=Decimal("0.30"),
        rebalance_band=Decimal("0.05"),
        vol_budget=Decimal("0.15"),
        max_positions=12,
        max_single_position_pct=Decimal("0.10"),
        horizon="2-20 days",
        stop_policy="ATR 2x + 20-day time stop",
    ),
    BucketId.MOONSHOT: BucketConfig(
        bucket_id=BucketId.MOONSHOT,
        target_allocation=Decimal("0.15"),
        rebalance_band=Decimal("0.03"),
        vol_budget=Decimal("0.35"),
        max_positions=6,
        max_single_position_pct=Decimal("0.025"),
        horizon="hours-5 days",
        stop_policy="Hard -25% stop, 5-day time stop",
    ),
    BucketId.CASH: BucketConfig(
        bucket_id=BucketId.CASH,
        target_allocation=Decimal("0.05"),
        rebalance_band=Decimal("0.00"),
        vol_budget=Decimal("0.00"),
        max_positions=0,
        max_single_position_pct=Decimal("0.00"),
        horizon="continuous",
        stop_policy="None",
    ),
}
