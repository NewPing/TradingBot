"""Unit tests for §4.5 data validation checks."""

from datetime import UTC, date, datetime
from decimal import Decimal

from atlas.core.types import Bar, Symbol
from atlas.data.validate import DataValidator


def test_validate_bar_bounds() -> None:
    # Valid bar
    valid_bar = Bar(
        symbol=Symbol("SPY"),
        ts=datetime(2023, 1, 3, 21, 0, 0, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("105"),
        low=Decimal("95"),
        close=Decimal("102"),
        volume=1000,
    )
    assert len(DataValidator.validate_bar_bounds(valid_bar)) == 0

    # Frozen Bar raises ValueError on inverted high/low
    import pytest

    with pytest.raises(ValueError, match="cannot be less than low"):
        Bar(
            symbol=Symbol("SPY"),
            ts=datetime(2023, 1, 3, 21, 0, 0, tzinfo=UTC),
            open=Decimal("100"),
            high=Decimal("90"),
            low=Decimal("95"),
            close=Decimal("92"),
            volume=1000,
        )


def test_validate_volume() -> None:
    # 2023-01-03 was an open trading day (Tuesday after New Year's)
    zero_vol_bar = Bar(
        symbol=Symbol("SPY"),
        ts=datetime(2023, 1, 3, 21, 0, 0, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("105"),
        low=Decimal("95"),
        close=Decimal("102"),
        volume=0,
    )
    issues = DataValidator.validate_volume(zero_vol_bar)
    assert len(issues) == 1
    assert issues[0].check_name == "zero_volume_trading_day"


def test_validate_calendar_completeness() -> None:
    # Tuesday 2023-01-03 and Thursday 2023-01-05 (missing Wednesday 2023-01-04)
    b1 = Bar(
        symbol=Symbol("SPY"),
        ts=datetime(2023, 1, 3, 21, 0, 0, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("105"),
        low=Decimal("95"),
        close=Decimal("102"),
        volume=1000,
    )
    b2 = Bar(
        symbol=Symbol("SPY"),
        ts=datetime(2023, 1, 5, 21, 0, 0, tzinfo=UTC),
        open=Decimal("102"),
        high=Decimal("106"),
        low=Decimal("100"),
        close=Decimal("104"),
        volume=1000,
    )
    issues = DataValidator.validate_calendar_completeness(
        symbol=Symbol("SPY"),
        bars=[b1, b2],
        start_date=date(2023, 1, 3),
        end_date=date(2023, 1, 5),
    )
    assert len(issues) == 1
    assert issues[0].check_name == "missing_trading_bar"
    assert issues[0].ts.date() == date(2023, 1, 4)


def test_validate_price_jumps() -> None:
    b1 = Bar(
        symbol=Symbol("SPY"),
        ts=datetime(2023, 1, 3, 21, 0, 0, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("105"),
        low=Decimal("95"),
        close=Decimal("100"),
        volume=1000,
    )
    # 50% jump next day with no corporate action
    b2 = Bar(
        symbol=Symbol("SPY"),
        ts=datetime(2023, 1, 4, 21, 0, 0, tzinfo=UTC),
        open=Decimal("150"),
        high=Decimal("155"),
        low=Decimal("145"),
        close=Decimal("150"),
        volume=1000,
    )

    issues = DataValidator.validate_price_jumps([b1, b2], corporate_actions=[])
    assert len(issues) == 1
    assert issues[0].check_name == "unexplained_price_jump"

    # If corporate action exists on 2023-01-04, no issue should be flagged
    ca = [{"symbol": "SPY", "ex_date": date(2023, 1, 4), "action_type": "SPLIT"}]
    issues_with_ca = DataValidator.validate_price_jumps([b1, b2], corporate_actions=ca)
    assert len(issues_with_ca) == 0


def test_validate_cross_source_consistency() -> None:
    ts = datetime(2023, 1, 3, 21, 0, 0, tzinfo=UTC)
    tiingo_bar = Bar(
        symbol=Symbol("SPY"),
        ts=ts,
        open=Decimal("100"),
        high=Decimal("105"),
        low=Decimal("95"),
        close=Decimal("100"),
        volume=1000,
        source="tiingo",
    )
    # Alpaca bar with 2% diff
    alpaca_bar = Bar(
        symbol=Symbol("SPY"),
        ts=ts,
        open=Decimal("102"),
        high=Decimal("106"),
        low=Decimal("96"),
        close=Decimal("102"),
        volume=1000,
        source="alpaca",
    )

    issues = DataValidator.validate_cross_source_consistency(
        primary_bars=[tiingo_bar],
        secondary_bars=[alpaca_bar],
        diff_threshold=0.005,
    )
    assert len(issues) == 1
    assert issues[0].check_name == "cross_source_divergence"
