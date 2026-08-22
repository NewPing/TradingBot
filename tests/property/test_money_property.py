"""Property-based tests for Money invariant guarantees."""

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from atlas.core.money import Money

decimal_strategy = st.decimals(
    min_value=Decimal("-1000000.00"),
    max_value=Decimal("1000000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

int_strategy = st.integers(min_value=-1000, max_value=1000)


@given(d1=decimal_strategy, d2=decimal_strategy)
def test_money_addition_commutativity(d1: Decimal, d2: Decimal) -> None:
    m1 = Money(d1)
    m2 = Money(d2)
    assert (m1 + m2) == (m2 + m1)


@given(d1=decimal_strategy, d2=decimal_strategy, d3=decimal_strategy)
def test_money_addition_associativity(d1: Decimal, d2: Decimal, d3: Decimal) -> None:
    m1 = Money(d1)
    m2 = Money(d2)
    m3 = Money(d3)
    assert ((m1 + m2) + m3) == (m1 + (m2 + m3))


@given(d=decimal_strategy)
def test_money_zero_identity(d: Decimal) -> None:
    m = Money(d)
    zero = Money.zero()
    assert (m + zero) == m
    assert (m - zero) == m
    assert (m - m) == zero


@given(d=decimal_strategy, factor=int_strategy)
def test_money_scalar_multiplication_commutativity(d: Decimal, factor: int) -> None:
    m = Money(d)
    assert (m * factor) == (factor * m)


@given(d=decimal_strategy)
def test_money_negation_involution(d: Decimal) -> None:
    m = Money(d)
    neg = -m
    assert -neg == m
