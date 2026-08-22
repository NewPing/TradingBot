"""Unit tests for MarketContext lookahead enforcement."""

from datetime import UTC, datetime

import pytest

from atlas.core.clock import SimClock
from atlas.core.context import BaseMarketContext
from atlas.core.errors import LookaheadError


def test_base_context_lookahead_detection() -> None:
    current_time = datetime(2025, 1, 15, 16, 0, tzinfo=UTC)
    future_time = datetime(2025, 1, 16, 9, 30, tzinfo=UTC)
    past_time = datetime(2025, 1, 14, 16, 0, tzinfo=UTC)

    clock = SimClock(current_time)
    ctx = BaseMarketContext(clock)

    assert ctx.now == current_time

    # Past time is allowed
    ctx._assert_no_future_access(past_time)

    # Current time is allowed
    ctx._assert_no_future_access(current_time)

    # Future time must raise LookaheadError
    with pytest.raises(LookaheadError, match="in the future relative to current time"):
        ctx._assert_no_future_access(future_time)
