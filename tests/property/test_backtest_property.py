"""Hypothesis property tests for backtest math, sizing, and invariants."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from atlas.backtest.costs import DefaultCostModelV1
from atlas.core.types import Signal, SignalLayer, Symbol
from atlas.signals.aggregator import WeightedConfidenceAggregator


@given(
    scores=st.lists(
        st.floats(min_value=-1.0, max_value=1.0, allow_nan=False), min_size=1, max_size=10
    ),
    confidences=st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False), min_size=1, max_size=10
    ),
    weights=st.lists(
        st.floats(min_value=0.1, max_value=5.0, allow_nan=False), min_size=1, max_size=10
    ),
)
def test_aggregator_score_and_confidence_bounds(
    scores: list[float],
    confidences: list[float],
    weights: list[float],
) -> None:
    now_ts = datetime(2022, 1, 1, 12, 0, tzinfo=UTC)
    sym = Symbol("TEST")
    min_len = min(len(scores), len(confidences), len(weights))

    signals: list[Signal] = []
    weight_map: dict[str, float] = {}

    for i in range(min_len):
        provider_name = f"p_{i}"
        weight_map[provider_name] = weights[i]
        signals.append(
            Signal(
                provider=provider_name,
                layer=SignalLayer.L1_TECHNICAL,
                symbol=sym,
                ts=now_ts,
                score=scores[i],
                confidence=confidences[i],
            )
        )

    agg = WeightedConfidenceAggregator(min_confidence=0.0, weights=weight_map)
    composite = agg.combine(signals, now_ts, sym)

    if composite is not None:
        assert -1.0 <= composite.score <= 1.0
        assert 0.0 <= composite.confidence <= 1.0


@given(
    qty1=st.integers(min_value=1, max_value=5000),
    qty2=st.integers(min_value=5001, max_value=50000),
    price=st.decimals(min_value=Decimal("1.00"), max_value=Decimal("1000.00"), places=2),
)
def test_slippage_monotonicity(qty1: int, qty2: int, price: Decimal) -> None:
    cost_model = DefaultCostModelV1(k=1.0)
    adv = Decimal("50000000")

    slip1 = cost_model.calculate_slippage(qty1, price, adv)
    slip2 = cost_model.calculate_slippage(qty2, price, adv)

    assert slip2 >= slip1
