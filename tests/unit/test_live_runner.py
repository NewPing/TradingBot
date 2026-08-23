"""Unit tests for LiveRunnerDaemon, recovery manager, and health monitoring."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from atlas.backtest.broker import SimBroker
from atlas.core.bus import EventBus
from atlas.core.money import Money
from atlas.core.types import RunMode, Symbol
from atlas.portfolio.ledger import BucketLedger
from atlas.risk.manager import RiskManager
from atlas.runner.health import RunnerHealthMonitor
from atlas.runner.live import LiveRunnerDaemon
from atlas.runner.recovery import CrashRecoveryManager


def test_runner_health_monitor() -> None:
    bus = EventBus()
    health = RunnerHealthMonitor(event_bus=bus)

    health.start()
    assert health.status().is_running

    health.record_cycle_success()
    assert health.status().total_cycles == 1
    assert health.status().consecutive_errors == 0

    health.record_cycle_error(RuntimeError("Test cycle error"))
    assert health.status().consecutive_errors == 1
    assert health.status().last_error == "Test cycle error"

    health.stop()
    assert not health.status().is_running


def test_crash_recovery_roundtrip(tmp_path: Path) -> None:
    state_file = tmp_path / "runner_state.json"
    recovery = CrashRecoveryManager(state_file_path=state_file)

    ledger = BucketLedger()
    ledger.deposit(Money(Decimal("100000.00"), "USD"))

    recovery.persist_state(
        ledger=ledger,
        active_orders={},
        run_id="run-test-recovery",
        strategy_version_id="strat-v1",
    )

    broker = SimBroker()
    rec_ledger, rec_orders, rec_run_id, rec_strat_id = recovery.recover(broker)

    assert rec_run_id == "run-test-recovery"
    assert rec_strat_id == "strat-v1"
    assert rec_ledger.total_cash() == Money(Decimal("100000.00"), "USD")


def test_live_runner_daemon_emergency_flatten(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    broker = SimBroker()
    ledger = BucketLedger()
    ledger.deposit(Money(Decimal("100000.00"), "USD"))
    risk = RiskManager()
    recovery = CrashRecoveryManager(state_file_path=state_file)

    daemon = LiveRunnerDaemon(
        strategy_specs=[],
        broker=broker,
        risk_manager=risk,
        ledger=ledger,
        recovery_manager=recovery,
        mode=RunMode.PAPER,
    )

    daemon.startup()
    # Trigger emergency manual halt
    risk.emergency_flatten(detail="Test manual halt")

    prices = {Symbol("SPY"): Decimal("400.00")}
    cycle_res = daemon.execute_cycle(current_prices=prices)

    assert cycle_res["status"] == "FLATTENED"
    daemon.shutdown()
