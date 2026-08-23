"""Unit tests for OMS (Order Management System) and Broker execution routing."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from atlas.backtest.broker import SimBroker
from atlas.core.bus import EventBus
from atlas.core.money import Money
from atlas.core.types import (
    BucketId,
    Fill,
    Order,
    OrderStatus,
    OrderType,
    Quantity,
    Side,
    Symbol,
    TimeInForce,
)
from atlas.execution.alpaca_broker import AlpacaPaperBroker
from atlas.execution.oms import OrderManager
from atlas.portfolio.ledger import BucketLedger
from atlas.risk.manager import RiskManager


def test_oms_order_lifecycle_with_sim_broker() -> None:
    broker = SimBroker()
    ledger = BucketLedger()
    ledger.deposit(Money(Decimal("100000.00"), "USD"))
    risk = RiskManager()
    bus = EventBus()

    oms = OrderManager(
        broker=broker,
        ledger=ledger,
        risk_manager=risk,
        event_bus=bus,
    )

    order = Order(
        id="ord-oms-1",
        run_id="run-test",
        strategy_version_id="strat-v1",
        bucket=BucketId.CORE,
        symbol=Symbol("AAPL"),
        side=Side.BUY,
        qty=Quantity(20),
        type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        created_ts=datetime(2026, 1, 15, 14, 0, tzinfo=UTC),
    )

    prices = {Symbol("AAPL"): Decimal("150.00")}

    # 1. Submit order
    ref = oms.submit_order(order, current_prices=prices)
    assert ref is not None
    assert "ord-oms-1" in oms.active_orders
    assert oms.active_orders["ord-oms-1"].status == OrderStatus.SUBMITTED

    # 2. Simulate broker fill callback
    fill = Fill(
        order_id="ord-oms-1",
        ts=datetime(2026, 1, 16, 9, 30, tzinfo=UTC),
        qty=Quantity(20),
        price=Decimal("150.50"),
        commission=Money(Decimal("1.00"), "USD"),
        fees=Money(Decimal("0.10"), "USD"),
        slippage_est=Money.zero("USD"),
        venue="SIM",
    )
    oms.process_fill(fill)

    # 3. Verify order marked filled & position recorded in ledger
    assert "ord-oms-1" not in oms.active_orders
    assert oms.order_history["ord-oms-1"].status == OrderStatus.FILLED
    assert len(oms.get_open_positions()) == 1
    pos = oms.get_open_positions()[0]
    assert pos.symbol == Symbol("AAPL")
    assert pos.qty == 20


def test_alpaca_paper_broker_mock_mode() -> None:
    broker = AlpacaPaperBroker()
    assert broker.is_mock
    assert broker.is_healthy()

    order = Order(
        id="ord-alpaca-1",
        run_id="run-test",
        strategy_version_id="strat-v1",
        bucket=BucketId.CORE,
        symbol=Symbol("SPY"),
        side=Side.BUY,
        qty=Quantity(10),
        type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        created_ts=datetime(2026, 1, 15, 14, 0, tzinfo=UTC),
    )

    ref = broker.submit(order)
    assert ref == "ord-alpaca-1"
    account = broker.account()
    assert account.total_equity == Money(Decimal("100000.00"), "USD")
