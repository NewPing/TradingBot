"""Trading calendar utilities wrapping exchange_calendars (XNYS)."""

from __future__ import annotations

from datetime import date, datetime

import exchange_calendars as xcals
import pandas as pd

_calendar: xcals.ExchangeCalendar | None = None


def get_calendar() -> xcals.ExchangeCalendar:
    global _calendar
    if _calendar is None:
        _calendar = xcals.get_calendar("XNYS")
    return _calendar


def is_trading_day(dt: date | datetime) -> bool:
    """Check if the given date is an open trading day on NYSE."""
    cal = get_calendar()
    check_date = dt.date() if isinstance(dt, datetime) else dt
    return bool(cal.is_session(check_date.isoformat()))


def is_market_open(dt: datetime) -> bool:
    """Check if the market is open at the given UTC datetime."""
    cal = get_calendar()
    if dt.tzinfo is None:
        raise ValueError("Datetime must be timezone-aware UTC")
    ts = pd.Timestamp(dt)
    return bool(cal.is_open_on_minute(ts))


def get_trading_days(start_date: date, end_date: date) -> list[date]:
    """Return list of trading days between start and end (inclusive)."""
    cal = get_calendar()
    sessions = cal.sessions_in_range(start_date.isoformat(), end_date.isoformat())
    return [s.to_pydatetime().date() for s in sessions]
