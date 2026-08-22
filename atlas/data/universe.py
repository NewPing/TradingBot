"""Point-in-time universe builder to prevent survivorship bias."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from atlas.core.types import Bar, Symbol


@dataclass(frozen=True, slots=True)
class UniverseCriteria:
    """Configurable criteria for filtering a tradable universe on a given date."""

    min_adv_usd: Decimal = Decimal("20000000")  # Minimum Average Dollar Volume (e.g., $20M)
    min_price: Decimal = Decimal("5.0")  # Minimum share price (e.g., $5.00)
    adv_lookback_days: int = 20  # Rolling window for calculating ADV
    exclude_zero_volume: bool = True  # Exclude symbols with 0 volume on date


class UniverseBuilder:
    """Builds point-in-time tradable equity universes."""

    @staticmethod
    def calculate_adv_usd(bars: Sequence[Bar], lookback_days: int = 20) -> Decimal:
        """Calculate Average Daily Dollar Volume over the last lookback_days bars."""
        if not bars:
            return Decimal("0")

        recent_bars = bars[-lookback_days:]
        if not recent_bars:
            return Decimal("0")

        total_dv = sum(b.close * Decimal(b.volume) for b in recent_bars)
        return total_dv / Decimal(len(recent_bars))

    @classmethod
    def filter_universe_for_date(
        cls,
        as_of_date: date,
        symbol_bars: dict[Symbol, Sequence[Bar]],
        criteria: UniverseCriteria | None = None,
        index_constituents: set[Symbol] | None = None,
    ) -> list[Symbol]:
        """
        Evaluate and return the list of eligible symbols on as_of_date based on PIT criteria.
        Only bars with ts.date() <= as_of_date are considered (strict no lookahead).
        """
        if criteria is None:
            criteria = UniverseCriteria()

        eligible: list[Symbol] = []

        for symbol, all_bars in symbol_bars.items():
            # Index membership check if specified
            if index_constituents is not None and symbol not in index_constituents:
                continue

            # Filter bars strictly on or before as_of_date (NO LOOKAHEAD)
            hist_bars = [b for b in all_bars if b.ts.date() <= as_of_date]
            if not hist_bars:
                continue

            latest_bar = hist_bars[-1]
            # Must have a bar on the current date or within recent trading days
            if latest_bar.ts.date() != as_of_date and (as_of_date - latest_bar.ts.date()).days > 5:
                continue

            # Minimum price check
            if latest_bar.close < criteria.min_price:
                continue

            # Zero volume exclusion
            if criteria.exclude_zero_volume and latest_bar.volume <= 0:
                continue

            # ADV check
            adv = cls.calculate_adv_usd(hist_bars, lookback_days=criteria.adv_lookback_days)
            if adv < criteria.min_adv_usd:
                continue

            eligible.append(symbol)

        return sorted(eligible)
