"""Position sizing rules and volatility targeting calculations."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal

from atlas.core.money import Money
from atlas.core.types import BucketId, Quantity


def _default_vol_budgets() -> dict[BucketId, Decimal]:
    return {
        BucketId.CORE: Decimal("0.10"),
        BucketId.SWING: Decimal("0.15"),
        BucketId.MOONSHOT: Decimal("0.35"),
    }


@dataclass(frozen=True, slots=True)
class SizingCalculator:
    """Calculates position sizing according to Section 6.2 of ATLAS architecture.

    - Target Vol Budgets: CORE 10%, SWING 15%, MOONSHOT 35%.
    - Volatility targeting: raw_weight = (bucket_vol_budget / n) / realized_vol_20d
    - Conviction scaling: conviction = clip(|score|, 0.3, 1.0)
    - Weight capping: min(raw_weight * conviction, max_pos_pct)
    - Integer shares: qty = floor(weight * bucket_equity / price)
    """

    bucket_vol_budgets: dict[BucketId, Decimal] = field(default_factory=_default_vol_budgets)

    def calculate_quantity(
        self,
        bucket: BucketId,
        bucket_equity: Money,
        price: Decimal,
        composite_score: float,
        realized_vol_20d: Decimal | None = None,
        expected_n_positions: int = 5,
        max_position_pct: Decimal = Decimal("0.20"),
        available_cash: Money | None = None,
    ) -> Quantity:
        """Calculate whole number of shares to allocate for an instrument."""
        if price <= Decimal("0") or bucket_equity.amount <= Decimal("0"):
            return Quantity(0)

        vol_budget = self.bucket_vol_budgets.get(bucket, Decimal("0.15"))
        n_pos = max(1, expected_n_positions)
        target_vol_per_position = vol_budget / Decimal(n_pos)

        vol = (
            realized_vol_20d
            if (realized_vol_20d is not None and realized_vol_20d > Decimal("0"))
            else Decimal("0.20")
        )
        raw_weight = target_vol_per_position / vol

        # Conviction scaling: clip(|score|, 0.3, 1.0)
        abs_score = abs(composite_score)
        conviction = Decimal(str(max(0.3, min(1.0, abs_score))))

        # Weight cap
        weight = min(raw_weight * conviction, max_position_pct)
        target_notional = bucket_equity.amount * weight

        # Cap by available cash if provided
        if available_cash is not None and available_cash.amount > Decimal("0"):
            target_notional = min(target_notional, available_cash.amount)

        qty = int(math.floor(float(target_notional / price)))
        return Quantity(max(0, qty))
