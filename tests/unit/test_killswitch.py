"""Unit tests for KillSwitchManager and automated circuit breakers."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from atlas.core.money import Money
from atlas.core.types import BucketId
from atlas.risk.killswitch import (
    KillSwitchManager,
    KillSwitchTrigger,
)


def test_daily_loss_kill_switch_trigger() -> None:
    mgr = KillSwitchManager()
    mgr.session_open_equity = Decimal("100000.00")
    mgr.peak_equity = Decimal("100000.00")

    # Drop to $97,500 (-2.5% loss > -2.0% threshold)
    current_eq = Money(Decimal("97500.00"), "USD")
    triggered = mgr.evaluate_equity(current_eq)

    assert len(triggered) == 1
    assert triggered[0].trigger == KillSwitchTrigger.DAILY_LOSS
    assert mgr.is_triggered()
    assert not mgr.allows_entries()

    # Reset daily loss on new session
    mgr.new_session(Decimal("97500.00"))
    assert not mgr.is_triggered()
    assert mgr.allows_entries()


def test_drawdown_kill_switches() -> None:
    mgr = KillSwitchManager()
    mgr.peak_equity = Decimal("100000.00")
    mgr.session_open_equity = Decimal("90000.00")

    # Drop to $84,000 (-16% drawdown > -15%)
    eq1 = Money(Decimal("84000.00"), "USD")
    trig1 = mgr.evaluate_equity(eq1)
    assert any(t.trigger == KillSwitchTrigger.DRAWDOWN_15 for t in trig1)

    req_flat, b_flat = mgr.requires_flatten()
    assert req_flat
    assert BucketId.MOONSHOT in b_flat

    # Drop to $74,000 (-26% drawdown > -25%)
    eq2 = Money(Decimal("74000.00"), "USD")
    trig2 = mgr.evaluate_equity(eq2)
    assert any(t.trigger == KillSwitchTrigger.DRAWDOWN_25 for t in trig2)

    req_flat2, b_flat2 = mgr.requires_flatten()
    assert req_flat2
    assert BucketId.CORE in b_flat2
    assert BucketId.SWING in b_flat2


def test_order_reject_rate_kill_switch() -> None:
    mgr = KillSwitchManager()

    # Submit 7 successes, 3 failures (30% reject rate over 10 orders > 20%)
    for _ in range(7):
        mgr.record_order_result(True, BucketId.CORE)
    for _ in range(3):
        active = mgr.record_order_result(False, BucketId.CORE)

    assert active is not None
    assert active.trigger == KillSwitchTrigger.ORDER_REJECT_RATE
    assert active.affected_bucket == BucketId.CORE
    assert not mgr.allows_entries(BucketId.CORE)
    # SWING is still allowed
    assert mgr.allows_entries(BucketId.SWING)


def test_broker_disconnect_kill_switch() -> None:
    mgr = KillSwitchManager()
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    mgr.record_broker_heartbeat(now=t0)

    # Check 30 seconds later (ok)
    t1 = datetime(2026, 1, 1, 12, 0, 30, tzinfo=UTC)
    assert mgr.check_broker_connection(now=t1, timeout_seconds=60) is None

    # Check 70 seconds later (> 60s timeout)
    t2 = datetime(2026, 1, 1, 12, 1, 10, tzinfo=UTC)
    active = mgr.check_broker_connection(now=t2, timeout_seconds=60)
    assert active is not None
    assert active.trigger == KillSwitchTrigger.BROKER_DISCONNECT
    assert mgr.is_triggered()

    # Auto-recovery on heartbeat
    t3 = datetime(2026, 1, 1, 12, 1, 15, tzinfo=UTC)
    mgr.record_broker_heartbeat(now=t3)
    assert not mgr.is_triggered()
