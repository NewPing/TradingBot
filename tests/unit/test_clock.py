"""Unit tests for SimClock and RealClock."""

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.clock import RealClock, SimClock


def test_real_clock_now_is_utc_aware() -> None:
    clock = RealClock()
    now = clock.now
    assert now.tzinfo is not None
    assert now.tzinfo == UTC


def test_sim_clock_manipulation() -> None:
    start_ts = datetime(2025, 1, 1, 9, 30, tzinfo=UTC)
    clock = SimClock(start_ts)
    assert clock.now == start_ts

    next_ts = datetime(2025, 1, 1, 16, 0, tzinfo=UTC)
    clock.set(next_ts)
    assert clock.now == next_ts

    clock.advance(timedelta(days=1))
    assert clock.now == datetime(2025, 1, 2, 16, 0, tzinfo=UTC)


def test_sim_clock_rejects_naive_timestamp() -> None:
    naive_dt = datetime(2025, 1, 1, 10, 0)
    with pytest.raises(ValueError, match="must be timezone-aware UTC"):
        SimClock(naive_dt)

    valid_clock = SimClock(datetime(2025, 1, 1, 10, 0, tzinfo=UTC))
    with pytest.raises(ValueError, match="must be timezone-aware UTC"):
        valid_clock.set(naive_dt)
