"""Precise monetary arithmetic domain model wrapping Decimal.

Hard invariant D15: Internal accounting strictly in Decimal via Money.
Floats are strictly forbidden in all financial arithmetic and initialization.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal
from enum import StrEnum
from typing import Any

from atlas.core.errors import CurrencyMismatchError, MoneyTypeError


class Currency(StrEnum):
    USD = "USD"
    EUR = "EUR"


INTERNAL_QUANT = Decimal("0.0001")
DISPLAY_QUANT = Decimal("0.01")


class Money:
    """Immutable monetary amount represented in fixed-point Decimal.

    Raises MoneyTypeError / TypeError if constructed or combined with float.
    Internal precision quantized to 4 decimal places (ROUND_HALF_EVEN).
    """

    __slots__ = ("_amount", "_currency")

    def __init__(
        self,
        amount: Decimal | str | int | Money,
        currency: Currency | str = Currency.USD,
    ) -> None:
        if isinstance(amount, float):
            raise MoneyTypeError(
                f"Float is strictly forbidden in Money. Received float: {amount!r}. "
                "Use Decimal, str, or int instead."
            )

        if isinstance(amount, Money):
            self._amount = amount.amount
            self._currency = amount.currency
            return

        if isinstance(currency, str):
            currency = Currency(currency)

        if isinstance(amount, int):
            dec_amount = Decimal(amount)
        elif isinstance(amount, str):
            try:
                dec_amount = Decimal(amount)
            except Exception as e:
                raise ValueError(f"Invalid monetary string: {amount!r}") from e
        elif isinstance(amount, Decimal):
            dec_amount = amount
        else:
            raise MoneyTypeError(f"Unsupported amount type: {type(amount).__name__}")

        self._amount = dec_amount.quantize(INTERNAL_QUANT, rounding=ROUND_HALF_EVEN)
        self._currency = currency

    @classmethod
    def zero(cls, currency: Currency | str = Currency.USD) -> Money:
        return cls(Decimal("0.0000"), currency=currency)

    @classmethod
    def from_cents(cls, cents: int, currency: Currency | str = Currency.USD) -> Money:
        if isinstance(cents, float):
            raise MoneyTypeError("cents cannot be a float")
        return cls(Decimal(cents) / Decimal(100), currency=currency)

    @property
    def amount(self) -> Decimal:
        return self._amount

    @property
    def currency(self) -> Currency:
        return self._currency

    def to_display(self) -> Decimal:
        """Return amount quantized to 2 decimal places for user display."""
        return self._amount.quantize(DISPLAY_QUANT, rounding=ROUND_HALF_EVEN)

    def _check_currency(self, other: Money) -> None:
        if self._currency != other._currency:
            raise CurrencyMismatchError(
                f"Currency mismatch: {self._currency.value} vs {other._currency.value}"
            )

    def __repr__(self) -> str:
        return f"Money('{self._amount}', {self._currency.value!r})"

    def __str__(self) -> str:
        return f"{self.to_display():.2f} {self._currency.value}"

    def __hash__(self) -> int:
        return hash((self._amount, self._currency))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, float):
            raise MoneyTypeError("Cannot compare Money with float")
        if isinstance(other, Money):
            return self._amount == other._amount and self._currency == other._currency
        if isinstance(other, (int, Decimal)):
            if other == 0:
                return self._amount == Decimal(0)
            return False
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, float):
            raise MoneyTypeError("Cannot compare Money with float")
        if isinstance(other, Money):
            self._check_currency(other)
            return self._amount < other._amount
        if isinstance(other, (int, Decimal)) and other == 0:
            return self._amount < Decimal(0)
        return NotImplemented

    def __le__(self, other: Any) -> bool:
        if isinstance(other, float):
            raise MoneyTypeError("Cannot compare Money with float")
        if isinstance(other, Money):
            self._check_currency(other)
            return self._amount <= other._amount
        if isinstance(other, (int, Decimal)) and other == 0:
            return self._amount <= Decimal(0)
        return NotImplemented

    def __gt__(self, other: Any) -> bool:
        if isinstance(other, float):
            raise MoneyTypeError("Cannot compare Money with float")
        if isinstance(other, Money):
            self._check_currency(other)
            return self._amount > other._amount
        if isinstance(other, (int, Decimal)) and other == 0:
            return self._amount > Decimal(0)
        return NotImplemented

    def __ge__(self, other: Any) -> bool:
        if isinstance(other, float):
            raise MoneyTypeError("Cannot compare Money with float")
        if isinstance(other, Money):
            self._check_currency(other)
            return self._amount >= other._amount
        if isinstance(other, (int, Decimal)) and other == 0:
            return self._amount >= Decimal(0)
        return NotImplemented

    def __add__(self, other: Any) -> Money:
        if isinstance(other, float):
            raise MoneyTypeError("Cannot add float to Money")
        if not isinstance(other, Money):
            return NotImplemented
        self._check_currency(other)
        return Money(self._amount + other._amount, self._currency)

    def __radd__(self, other: Any) -> Money:
        if isinstance(other, (int, Decimal)) and other == 0:
            return self
        return self.__add__(other)

    def __sub__(self, other: Any) -> Money:
        if isinstance(other, float):
            raise MoneyTypeError("Cannot subtract float from Money")
        if not isinstance(other, Money):
            return NotImplemented
        self._check_currency(other)
        return Money(self._amount - other._amount, self._currency)

    def __rsub__(self, other: Any) -> Money:
        if isinstance(other, float):
            raise MoneyTypeError("Cannot subtract Money from float")
        if not isinstance(other, Money):
            return NotImplemented
        other._check_currency(self)
        return Money(other._amount - self._amount, self._currency)

    def __mul__(self, other: Any) -> Money:
        if isinstance(other, float):
            raise MoneyTypeError("Cannot multiply Money by float. Use Decimal or int.")
        if isinstance(other, (int, Decimal)):
            return Money(self._amount * Decimal(other), self._currency)
        return NotImplemented

    def __rmul__(self, other: Any) -> Money:
        return self.__mul__(other)

    def __truediv__(self, other: Any) -> Money | Decimal:
        if isinstance(other, float):
            raise MoneyTypeError("Cannot divide Money by float. Use Decimal or int.")
        if isinstance(other, Money):
            self._check_currency(other)
            if other._amount == Decimal(0):
                raise ZeroDivisionError("Cannot divide Money by zero Money")
            return self._amount / other._amount
        if isinstance(other, (int, Decimal)):
            if Decimal(other) == Decimal(0):
                raise ZeroDivisionError("Cannot divide Money by zero")
            return Money(self._amount / Decimal(other), self._currency)
        return NotImplemented

    def __floordiv__(self, other: Any) -> int | Money:
        if isinstance(other, float):
            raise MoneyTypeError("Cannot floor divide Money by float")
        if isinstance(other, Money):
            self._check_currency(other)
            return int(self._amount // other._amount)
        if isinstance(other, (int, Decimal)):
            return Money(self._amount // Decimal(other), self._currency)
        return NotImplemented

    def __neg__(self) -> Money:
        return Money(-self._amount, self._currency)

    def __pos__(self) -> Money:
        return Money(self._amount, self._currency)

    def __abs__(self) -> Money:
        return Money(abs(self._amount), self._currency)

    def is_positive(self) -> bool:
        return self._amount > Decimal(0)

    def is_negative(self) -> bool:
        return self._amount < Decimal(0)

    def is_zero(self) -> bool:
        return self._amount == Decimal(0)
