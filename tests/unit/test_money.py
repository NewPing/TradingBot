"""Unit tests for Money type and strict Decimal arithmetic."""

from decimal import Decimal

import pytest

from atlas.core.errors import CurrencyMismatchError, MoneyTypeError
from atlas.core.money import Currency, Money


def test_money_initialization_from_decimal() -> None:
    m = Money(Decimal("100.50"))
    assert m.amount == Decimal("100.5000")
    assert m.currency == Currency.USD
    assert m.to_display() == Decimal("100.50")


def test_money_initialization_from_str() -> None:
    m = Money("250.75", currency=Currency.EUR)
    assert m.amount == Decimal("250.7500")
    assert m.currency == Currency.EUR
    assert str(m) == "250.75 EUR"


def test_money_initialization_from_int() -> None:
    m = Money(100)
    assert m.amount == Decimal("100.0000")


def test_money_copy_constructor() -> None:
    m1 = Money("150.00", Currency.USD)
    m2 = Money(m1)
    assert m1 == m2
    assert m2.amount == Decimal("150.0000")


def test_money_from_cents() -> None:
    m = Money.from_cents(1050)
    assert m == Money("10.50")


def test_money_invalid_inputs() -> None:
    with pytest.raises(MoneyTypeError, match="Float is strictly forbidden"):
        Money(100.5)  # type: ignore[arg-type]

    with pytest.raises(MoneyTypeError):
        Money.from_cents(100.5)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="Invalid monetary string"):
        Money("invalid_number")

    with pytest.raises(MoneyTypeError, match="Unsupported amount type"):
        Money([100])  # type: ignore[arg-type]


def test_money_hash_and_repr() -> None:
    m1 = Money("100.00")
    m2 = Money("100.00")
    assert hash(m1) == hash(m2)
    assert "Money('100.0000', 'USD')" in repr(m1)


def test_money_arithmetic_addition() -> None:
    m1 = Money("50.25")
    m2 = Money("49.75")
    res = m1 + m2
    assert res == Money("100.00")
    assert res.amount == Decimal("100.0000")


def test_money_arithmetic_subtraction() -> None:
    m1 = Money("100.00")
    m2 = Money("40.00")
    assert m1 - m2 == Money("60.00")


def test_money_multiplication_with_int_and_decimal() -> None:
    m = Money("25.00")
    assert m * 4 == Money("100.00")
    assert 4 * m == Money("100.00")
    assert m * Decimal("1.5") == Money("37.50")


def test_money_division() -> None:
    m = Money("100.00")
    assert m / 4 == Money("25.00")
    assert m / Money("25.00") == Decimal("4.0000")

    with pytest.raises(ZeroDivisionError):
        _ = m / 0

    with pytest.raises(ZeroDivisionError):
        _ = m / Money.zero()


def test_money_floor_division() -> None:
    m1 = Money("100.00")
    m2 = Money("30.00")
    assert m1 // m2 == 3
    assert m1 // 3 == Money("33.00")


def test_money_arithmetic_float_rejection() -> None:
    m = Money("100.00")
    with pytest.raises(MoneyTypeError):
        _ = m + 5.0

    with pytest.raises(MoneyTypeError):
        _ = m - 5.0

    with pytest.raises(MoneyTypeError):
        _ = m * 1.5

    with pytest.raises(MoneyTypeError):
        _ = m / 2.0

    with pytest.raises(MoneyTypeError):
        _ = m // 2.0

    with pytest.raises(MoneyTypeError):
        _ = m == 100.0

    with pytest.raises(MoneyTypeError):
        _ = m < 100.0

    with pytest.raises(MoneyTypeError):
        _ = m <= 100.0

    with pytest.raises(MoneyTypeError):
        _ = m > 100.0

    with pytest.raises(MoneyTypeError):
        _ = m >= 100.0


def test_currency_mismatch_rejection() -> None:
    usd = Money("100.00", Currency.USD)
    eur = Money("100.00", Currency.EUR)

    with pytest.raises(CurrencyMismatchError):
        _ = usd + eur

    with pytest.raises(CurrencyMismatchError):
        _ = usd - eur

    with pytest.raises(CurrencyMismatchError):
        _ = usd / eur

    with pytest.raises(CurrencyMismatchError):
        _ = usd // eur

    with pytest.raises(CurrencyMismatchError):
        _ = usd < eur


def test_money_comparisons() -> None:
    m1 = Money("10.00")
    m2 = Money("20.00")
    m3 = Money("10.00")

    assert m1 < m2
    assert m1 <= m3
    assert m2 > m1
    assert m1 >= m3
    assert m1 == m3
    assert m1 != m2

    # Zero comparisons
    assert m1 > 0
    assert Money("-5.00") < 0
    assert Money.zero() == 0
    assert Money.zero() <= 0
    assert Money.zero() >= 0
    assert Money("5.00") != 10


def test_money_unary_operations() -> None:
    m = Money("50.00")
    assert -m == Money("-50.00")
    assert +m == Money("50.00")
    assert abs(-m) == Money("50.00")
    assert (-m).is_negative()
    assert m.is_positive()
    assert Money.zero().is_zero()
