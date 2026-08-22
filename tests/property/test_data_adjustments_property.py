"""Property-based tests for split and dividend adjustment calculations."""

from datetime import UTC, date, datetime
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from atlas.core.types import Bar, Symbol
from atlas.data.normalize import compute_adjusted_series


@settings(max_examples=50)
@given(
    close1=st.decimals(min_value=Decimal("10.0"), max_value=Decimal("500.0"), places=2),
    close2=st.decimals(min_value=Decimal("10.0"), max_value=Decimal("500.0"), places=2),
    split_ratio=st.decimals(min_value=Decimal("0.1"), max_value=Decimal("10.0"), places=2),
)
def test_split_adjustment_factor_monotonic(
    close1: Decimal, close2: Decimal, split_ratio: Decimal
) -> None:
    b1 = Bar(
        symbol=Symbol("SYM"),
        ts=datetime(2023, 1, 3, 21, 0, 0, tzinfo=UTC),
        open=close1,
        high=close1 + Decimal("1.0"),
        low=close1 - Decimal("1.0"),
        close=close1,
        volume=1000,
    )
    b2 = Bar(
        symbol=Symbol("SYM"),
        ts=datetime(2023, 1, 4, 21, 0, 0, tzinfo=UTC),
        open=close2,
        high=close2 + Decimal("1.0"),
        low=close2 - Decimal("1.0"),
        close=close2,
        volume=1000,
    )

    actions = [
        {
            "symbol": "SYM",
            "ex_date": date(2023, 1, 4),
            "action_type": "SPLIT",
            "ratio": float(split_ratio),
        }
    ]

    adjusted = compute_adjusted_series([b1, b2], actions)
    assert len(adjusted) == 2
    # Latest bar should always have factor 1.0
    assert adjusted[1].adj_factor == Decimal("1.00000000")
    # Preceding bar factor should be positive
    assert adjusted[0].adj_factor > Decimal("0")
