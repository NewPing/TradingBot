"""Unit tests for exchange calendar utilities."""

from datetime import UTC, date, datetime

from atlas.core.calendar import get_calendar, get_trading_days, is_market_open, is_trading_day


def test_calendar_trading_day() -> None:
    # 2026-01-01 is New Year's Day (holiday)
    assert not is_trading_day(date(2026, 1, 1))

    # 2026-01-02 is a Friday trading day
    assert is_trading_day(date(2026, 1, 2))


def test_calendar_sessions_range() -> None:
    days = get_trading_days(date(2026, 1, 1), date(2026, 1, 10))
    assert len(days) > 0
    assert all(isinstance(d, date) for d in days)


def test_calendar_market_open_check() -> None:
    # Closed at midnight UTC
    closed_time = datetime(2026, 1, 2, 0, 0, tzinfo=UTC)
    assert not is_market_open(closed_time)

    cal = get_calendar()
    assert cal.name == "XNYS"
