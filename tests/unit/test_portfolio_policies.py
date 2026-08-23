"""Unit tests for portfolio allocation policies and position sizing."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from atlas.core.money import Money
from atlas.core.types import BucketId, Position, Signal, SignalLayer, Symbol
from atlas.portfolio.policies import (
    TargetWeightPolicy,
    ThresholdLongOnlyPolicy,
    TopNLongOnlyPolicy,
)
from atlas.portfolio.sizing import SizingCalculator


def test_sizing_calculator() -> None:
    calc = SizingCalculator()
    bucket_eq = Money(Decimal("100000.00"), "USD")
    price = Decimal("100.00")

    qty = calc.calculate_quantity(
        bucket=BucketId.CORE,
        bucket_equity=bucket_eq,
        price=price,
        composite_score=1.0,
        realized_vol_20d=Decimal("0.20"),
        expected_n_positions=5,
        max_position_pct=Decimal("0.20"),
    )

    # raw_weight = (0.10 / 5) / 0.20 = 0.02 / 0.20 = 0.10
    # conviction = 1.0 -> weight = min(0.10, 0.20) = 0.10
    # target notional = $10,000 -> qty = floor(10000 / 100) = 100
    assert qty == 100


def test_top_n_long_only_policy() -> None:
    policy = TopNLongOnlyPolicy(
        n=2, min_score=0.2, weight_by="equal_weight", max_position_pct=Decimal("0.50")
    )
    now_ts = datetime(2022, 1, 3, 21, 0, tzinfo=UTC)

    sig_a = Signal(
        "p1", SignalLayer.L1_TECHNICAL, Symbol("AAPL"), now_ts, score=0.8, confidence=0.9
    )
    sig_b = Signal(
        "p1", SignalLayer.L1_TECHNICAL, Symbol("MSFT"), now_ts, score=0.6, confidence=0.8
    )
    sig_c = Signal(
        "p1", SignalLayer.L1_TECHNICAL, Symbol("GOOG"), now_ts, score=0.1, confidence=0.5
    )  # Below min_score

    signals = {Symbol("AAPL"): sig_a, Symbol("MSFT"): sig_b, Symbol("GOOG"): sig_c}
    prices = {
        Symbol("AAPL"): Decimal("150"),
        Symbol("MSFT"): Decimal("300"),
        Symbol("GOOG"): Decimal("100"),
    }
    eq = Money(Decimal("100000.00"), "USD")

    # Currently holding GOOG
    old_pos = [
        Position(
            Symbol("GOOG"),
            BucketId.CORE,
            50,
            Decimal("100"),
            now_ts,
            Money.zero("USD"),
            Money.zero("USD"),
        )
    ]

    targets = policy.generate_targets(signals, old_pos, prices, eq, eq)

    # AAPL and MSFT selected (top 2), GOOG targeted for exit (qty=0)
    assert targets[Symbol("AAPL")] > 0
    assert targets[Symbol("MSFT")] > 0
    assert targets[Symbol("GOOG")] == 0


def test_threshold_long_only_hysteresis() -> None:
    policy = ThresholdLongOnlyPolicy(enter_threshold=0.4, exit_threshold=-0.1, max_positions=5)
    now_ts = datetime(2022, 1, 3, 21, 0, tzinfo=UTC)

    # AAPL is held and score is 0.1 (above exit -0.1) -> maintain
    # TSLA is held and score is -0.3 (below exit -0.1) -> exit (qty=0)
    # NVDA is not held and score is 0.5 (above enter 0.4) -> enter
    old_positions = [
        Position(
            Symbol("AAPL"),
            BucketId.SWING,
            100,
            Decimal("150"),
            now_ts,
            Money.zero("USD"),
            Money.zero("USD"),
        ),
        Position(
            Symbol("TSLA"),
            BucketId.SWING,
            50,
            Decimal("200"),
            now_ts,
            Money.zero("USD"),
            Money.zero("USD"),
        ),
    ]

    signals = {
        Symbol("AAPL"): Signal("p", SignalLayer.L1_TECHNICAL, Symbol("AAPL"), now_ts, 0.1, 0.8),
        Symbol("TSLA"): Signal("p", SignalLayer.L1_TECHNICAL, Symbol("TSLA"), now_ts, -0.3, 0.8),
        Symbol("NVDA"): Signal("p", SignalLayer.L1_TECHNICAL, Symbol("NVDA"), now_ts, 0.5, 0.9),
    }

    prices = {
        Symbol("AAPL"): Decimal("150"),
        Symbol("TSLA"): Decimal("200"),
        Symbol("NVDA"): Decimal("250"),
    }
    eq = Money(Decimal("100000.00"), "USD")

    targets = policy.generate_targets(signals, old_positions, prices, eq, eq)

    assert targets[Symbol("AAPL")] == 100  # Maintained
    assert targets[Symbol("TSLA")] == 0  # Exited
    assert targets[Symbol("NVDA")] > 0  # Entered


def test_target_weight_policy() -> None:
    policy = TargetWeightPolicy(max_position_pct=Decimal("0.50"), min_score=0.1)
    now_ts = datetime(2022, 1, 3, 21, 0, tzinfo=UTC)

    signals = {
        Symbol("AAPL"): Signal("p", SignalLayer.L1_TECHNICAL, Symbol("AAPL"), now_ts, 0.8, 0.9),
        Symbol("MSFT"): Signal("p", SignalLayer.L1_TECHNICAL, Symbol("MSFT"), now_ts, 0.05, 0.9),
    }
    prices = {Symbol("AAPL"): Decimal("100"), Symbol("MSFT"): Decimal("200")}
    eq = Money(Decimal("100000.00"), "USD")

    targets = policy.generate_targets(signals, [], prices, eq, eq)
    assert targets[Symbol("AAPL")] > 0
    assert Symbol("MSFT") not in targets or targets.get(Symbol("MSFT"), 0) == 0
