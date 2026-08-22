"""Unit tests for Point-in-Time Universe Builder."""

from datetime import UTC, date, datetime
from decimal import Decimal

from atlas.core.types import Bar, Symbol
from atlas.data.universe import UniverseBuilder, UniverseCriteria


def test_adv_calculation() -> None:
    bars = [
        Bar(
            symbol=Symbol("AAPL"),
            ts=datetime(2023, 1, d, 21, 0, 0, tzinfo=UTC),
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("95"),
            close=Decimal("100"),
            volume=100000,
        )
        for d in range(3, 8)
    ]
    # Dollar volume per day = 100 * 100,000 = $10,000,000
    adv = UniverseBuilder.calculate_adv_usd(bars, lookback_days=5)
    assert adv == Decimal("10000000")


def test_filter_universe_for_date_pit_discipline() -> None:
    # AAPL meets criteria ($100 price, $30M ADV)
    aapl_bars = [
        Bar(
            symbol=Symbol("AAPL"),
            ts=datetime(2023, 1, 3, 21, 0, 0, tzinfo=UTC),
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("95"),
            close=Decimal("100"),
            volume=300000,  # $30M DV
        )
    ]

    # PENNY has price < $5 ($2 price)
    penny_bars = [
        Bar(
            symbol=Symbol("PENNY"),
            ts=datetime(2023, 1, 3, 21, 0, 0, tzinfo=UTC),
            open=Decimal("2"),
            high=Decimal("2.5"),
            low=Decimal("1.8"),
            close=Decimal("2"),
            volume=50000000,
        )
    ]

    # ILLIQUID has ADV < $20M ($10 price, 50,000 vol = $500k)
    illiquid_bars = [
        Bar(
            symbol=Symbol("ILLIQUID"),
            ts=datetime(2023, 1, 3, 21, 0, 0, tzinfo=UTC),
            open=Decimal("10"),
            high=Decimal("11"),
            low=Decimal("9"),
            close=Decimal("10"),
            volume=50000,
        )
    ]

    symbol_bars = {
        Symbol("AAPL"): aapl_bars,
        Symbol("PENNY"): penny_bars,
        Symbol("ILLIQUID"): illiquid_bars,
    }

    criteria = UniverseCriteria(
        min_adv_usd=Decimal("20000000"),
        min_price=Decimal("5.0"),
        adv_lookback_days=1,
    )

    eligible = UniverseBuilder.filter_universe_for_date(
        as_of_date=date(2023, 1, 3),
        symbol_bars=symbol_bars,
        criteria=criteria,
    )

    assert eligible == [Symbol("AAPL")]
