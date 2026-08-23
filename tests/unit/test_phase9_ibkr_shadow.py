"""Unit tests for IBKR Broker, Shadow Runner Daemon, Divergence Monitor, and TOTP Authenticator (Phase 9)."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from decimal import Decimal

from atlas.core.money import Money
from atlas.core.totp import TOTPAuthenticator
from atlas.core.types import (
    BucketId,
    Fill,
    Order,
    OrderType,
    Side,
    Symbol,
    TimeInForce,
)
from atlas.execution.divergence import DivergenceMonitor
from atlas.execution.ibkr_broker import IBKRBroker
from atlas.risk.manager import RiskManager
from atlas.runner.shadow import ShadowRunnerDaemon
from atlas.strategies.spec import StrategySpec


def test_totp_authenticator_generation_and_verification() -> None:
    totp = TOTPAuthenticator()
    code = totp.generate_code()
    assert len(code) == 6
    assert code.isdigit()

    # Code should verify as valid
    assert totp.verify_code(code) is True

    # Bad code should fail
    assert totp.verify_code("999999" if code != "999999" else "123456") is False

    # Check drift tolerance
    past_time = time.time() - 25
    past_code = totp.generate_code(timestamp=past_time)
    assert totp.verify_code(past_code, drift_steps=1) is True


def test_ibkr_broker_mock_protocol_compliance() -> None:
    broker = IBKRBroker()
    assert broker.is_healthy() is True
    assert broker.is_mock is True

    now = datetime.now(UTC)
    order = Order(
        id="ord_ibkr_1",
        run_id="run_1",
        strategy_version_id="strat_v1",
        bucket=BucketId.CORE,
        symbol=Symbol("SPY"),
        side=Side.BUY,
        qty=25,
        type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        created_ts=now,
    )

    ref = broker.submit(order)
    assert str(ref).startswith("ibkr_")

    # Dispatch fill
    received_fills: list[Fill] = []
    broker.on_fill(lambda f: received_fills.append(f))

    fill = Fill(
        order_id="ord_ibkr_1",
        ts=now,
        qty=25,
        price=Decimal("550.00"),
        commission=Money(Decimal("1.00"), "USD"),
        fees=Money.zero("USD"),
        slippage_est=Money.zero("USD"),
        venue="IBKR_PAPER",
    )
    broker.dispatch_fill(fill, symbol=Symbol("SPY"), side=Side.BUY)

    assert len(received_fills) == 1
    assert len(broker.positions()) == 1
    assert broker.positions()[0].symbol == Symbol("SPY")
    assert broker.positions()[0].qty == 25

    # Account state
    acc = broker.account()
    assert acc.cash.amount < Decimal("100000.00")
    assert acc.total_equity.amount == Decimal("100000.00") - Decimal("1.00")


def test_divergence_monitor_slippage_calculation() -> None:
    monitor = DivergenceMonitor()
    run_id = "test_run_shadow"

    # Buy trade: model price 100, fill price 100.05 -> Slippage = (100.05 - 100)/100 * 10,000 = 5.0 bps
    entry1 = monitor.record_shadow_fill(
        run_id=run_id,
        symbol="SPY",
        side=Side.BUY,
        quantity=10,
        model_price=Decimal("100.00"),
        simulated_fill_price=Decimal("100.05"),
        quote_latency_ms=Decimal("15.2"),
    )
    assert entry1.slippage_bps == Decimal("5.0000")

    # Sell trade: model price 100, fill price 99.98 -> Slippage = (100 - 99.98)/100 * 10,000 = 2.0 bps
    entry2 = monitor.record_shadow_fill(
        run_id=run_id,
        symbol="QQQ",
        side=Side.SELL,
        quantity=10,
        model_price=Decimal("100.00"),
        simulated_fill_price=Decimal("99.98"),
        quote_latency_ms=Decimal("8.4"),
    )
    assert entry2.slippage_bps == Decimal("2.0000")

    telemetry = monitor.get_telemetry(run_id=run_id)
    assert telemetry.total_shadow_trades == 2
    assert telemetry.mean_slippage_bps == Decimal("3.50")
    assert telemetry.max_slippage_bps == Decimal("5.00")
    assert telemetry.positive_slippage_trades == 2


def test_shadow_runner_daemon_execution() -> None:
    broker = IBKRBroker()
    risk = RiskManager()
    spec = StrategySpec(
        name="test_strat",
        family="core_trend",
        version="v1.0.0",
        author="quant",
        description="test spec",
        bucket=BucketId.CORE,
        signals=[],
    )

    shadow_runner = ShadowRunnerDaemon(
        strategy_specs=[spec],
        broker=broker,
        risk_manager=risk,
    )
    shadow_runner.startup()

    prices = {Symbol("SPY"): Decimal("550.00"), Symbol("QQQ"): Decimal("480.00")}
    result = shadow_runner.execute_shadow_cycle(current_prices=prices)

    assert result["status"] == "SUCCESS"
    assert result["shadow_fills_count"] == 2

    telemetry = shadow_runner.get_telemetry()
    assert telemetry.total_shadow_trades == 2
    shadow_runner.shutdown()
