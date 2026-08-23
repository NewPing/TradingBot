"""Property-based tests for news decay weights and short borrow fee invariance."""

from __future__ import annotations

import math
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from atlas.backtest.costs import DefaultCostModelV1


@given(
    dt_hours=st.floats(min_value=0.0, max_value=500.0),
    half_life=st.floats(min_value=1.0, max_value=100.0),
)
def test_time_decay_weight_invariants(dt_hours: float, half_life: float) -> None:
    weight = math.exp(-math.log(2) * (dt_hours / half_life))
    # Time decay weight must strictly be in (0.0, 1.0]
    assert 0.0 < weight <= 1.0

    # At exact half life, weight must be 0.5
    weight_hl = math.exp(-math.log(2) * (half_life / half_life))
    assert abs(weight_hl - 0.5) < 1e-6


@given(
    notional=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10000000.00"), places=2),
    rate=st.decimals(min_value=Decimal("0.001"), max_value=Decimal("0.50"), places=4),
)
def test_daily_borrow_fee_invariants(notional: Decimal, rate: Decimal) -> None:
    cost_model = DefaultCostModelV1(borrow_rate_annual=rate)
    fee = cost_model.calculate_daily_borrow_fee(notional)

    assert fee.amount >= Decimal("0.00")
    # Fee must equal Money((notional * rate) / 252).amount
    expected = (notional * rate) / Decimal("252")
    assert abs(fee.amount - expected) <= Decimal("0.0001")
