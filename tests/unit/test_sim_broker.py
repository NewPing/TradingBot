"""Unit tests for SimBroker execution, fill timing, and position accounting."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from atlas.backtest.broker import SimBroker
from atlas.core.money import Money
from atlas.core.types import (
    Bar,
    BucketId,
    Fill,
    Order,
    OrderType,
    Side,
    Symbol,
    TimeInForce,
)


def make_test_bar(
    symbol: Symbol,
    ts: datetime,
    open_px: Decimal,
    high_px: Decimal,
    low_px: Decimal,
    close_px: Decimal,
) -> Bar:
    return Bar(
        symbol=symbol,
        ts=ts,
        open=open_px,
        high=high_px,
        low=low_px,
        close=close_px,
        volume=1_000_000,
    )


def test_t_plus_one_fill_discipline() -> None:
    broker = SimBroker(initial_capital=Money(Decimal("100000.00"), "USD"))
    t0 = datetime(2022, 1, 3, 21, 0, tzinfo=UTC)
    t1 = datetime(2022, 1, 4, 21, 0, tzinfo=UTC)

    order = Order(
        id="ord_1",
        run_id="run_1",
        strategy_version_id="1.0",
        bucket=BucketId.CORE,
        symbol=Symbol("AAPL"),
        side=Side.BUY,
        qty=100,
        type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        created_ts=t0,
    )

    broker.submit(order)

    # If we evaluate fills at bar t0 -> CANNOT fill (same timestamp)
    bar_t0 = make_test_bar(
        Symbol("AAPL"), t0, Decimal("150"), Decimal("155"), Decimal("149"), Decimal("152")
    )
    fills_t0 = broker.process_pending_orders(t0, {Symbol("AAPL"): bar_t0})
    assert len(fills_t0) == 0
    assert len(broker.positions()) == 0

    # On bar t1 -> strictly executes
    bar_t1 = make_test_bar(
        Symbol("AAPL"), t1, Decimal("153"), Decimal("156"), Decimal("151"), Decimal("154")
    )
    fills_t1 = broker.process_pending_orders(t1, {Symbol("AAPL"): bar_t1})
    assert len(fills_t1) == 1
    assert fills_t1[0].qty == 100
    assert len(broker.positions()) == 1

    pos = broker.get_position(Symbol("AAPL"))
    assert pos is not None
    assert pos.qty == 100
    assert broker.cash < Money(Decimal("100000.00"), "USD")


def test_sell_order_realizes_pnl() -> None:
    broker = SimBroker(initial_capital=Money(Decimal("100000.00"), "USD"))
    t0 = datetime(2022, 1, 3, 21, 0, tzinfo=UTC)
    t1 = datetime(2022, 1, 4, 21, 0, tzinfo=UTC)
    t2 = datetime(2022, 1, 5, 21, 0, tzinfo=UTC)

    # Buy 100 AAPL
    buy_order = Order(
        id="buy_1",
        run_id="r1",
        strategy_version_id="1.0",
        bucket=BucketId.CORE,
        symbol=Symbol("AAPL"),
        side=Side.BUY,
        qty=100,
        type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        created_ts=t0,
    )
    broker.submit(buy_order)
    bar_t1 = make_test_bar(
        Symbol("AAPL"), t1, Decimal("100"), Decimal("105"), Decimal("99"), Decimal("102")
    )
    broker.process_pending_orders(t1, {Symbol("AAPL"): bar_t1})

    # Now submit Sell 100 AAPL at t1
    sell_order = Order(
        id="sell_1",
        run_id="r1",
        strategy_version_id="1.0",
        bucket=BucketId.CORE,
        symbol=Symbol("AAPL"),
        side=Side.SELL,
        qty=100,
        type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        created_ts=t1,
    )
    broker.submit(sell_order)

    # Executes on t2 at higher price 120
    bar_t2 = make_test_bar(
        Symbol("AAPL"), t2, Decimal("120"), Decimal("125"), Decimal("119"), Decimal("122")
    )
    fills_t2 = broker.process_pending_orders(t2, {Symbol("AAPL"): bar_t2})

    assert len(fills_t2) == 1
    assert len(broker.positions()) == 0  # Closed position
    # Net profit ~$2,000 minus fees
    assert broker.cash > Money(Decimal("100000.00"), "USD")


def test_stop_loss_trigger() -> None:
    broker = SimBroker(initial_capital=Money(Decimal("100000.00"), "USD"))
    t0 = datetime(2022, 1, 3, 21, 0, tzinfo=UTC)
    t1 = datetime(2022, 1, 4, 21, 0, tzinfo=UTC)
    t2 = datetime(2022, 1, 5, 21, 0, tzinfo=UTC)

    # Buy with stop price at $90
    buy_order = Order(
        id="buy_stop",
        run_id="r1",
        strategy_version_id="1.0",
        bucket=BucketId.SWING,
        symbol=Symbol("TSLA"),
        side=Side.BUY,
        qty=50,
        type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        created_ts=t0,
        stop_px=Decimal("90.00"),
    )
    broker.submit(buy_order)
    bar_t1 = make_test_bar(
        Symbol("TSLA"), t1, Decimal("100"), Decimal("102"), Decimal("98"), Decimal("101")
    )
    broker.process_pending_orders(t1, {Symbol("TSLA"): bar_t1})

    # On t2, stock crashes to low of $85 (breaching $90 stop)
    bar_t2 = make_test_bar(
        Symbol("TSLA"), t2, Decimal("95"), Decimal("96"), Decimal("85"), Decimal("88")
    )
    stop_fills = broker.process_stops(t2, {Symbol("TSLA"): bar_t2})

    assert len(stop_fills) == 1
    assert len(broker.positions()) == 0


def test_broker_cancel_and_callbacks() -> None:
    broker = SimBroker(initial_capital=Money(Decimal("100000.00"), "USD"))
    assert broker.is_healthy() is True

    callback_fills: list[Fill] = []
    broker.on_fill(lambda f: callback_fills.append(f))

    t0 = datetime(2022, 1, 3, 21, 0, tzinfo=UTC)
    order = Order(
        id="ord_cancel",
        run_id="r1",
        strategy_version_id="1.0",
        bucket=BucketId.CORE,
        symbol=Symbol("AAPL"),
        side=Side.BUY,
        qty=10,
        type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        created_ts=t0,
    )
    ref = broker.submit(order)
    assert len(broker._pending_orders) == 1

    broker.cancel(ref)
    assert len(broker._pending_orders) == 0


def test_limit_order_execution() -> None:
    broker = SimBroker(initial_capital=Money(Decimal("100000.00"), "USD"))
    t0 = datetime(2022, 1, 3, 21, 0, tzinfo=UTC)
    t1 = datetime(2022, 1, 4, 21, 0, tzinfo=UTC)

    # Buy Limit at $95
    order = Order(
        id="ord_limit",
        run_id="r1",
        strategy_version_id="1.0",
        bucket=BucketId.CORE,
        symbol=Symbol("AAPL"),
        side=Side.BUY,
        qty=10,
        type=OrderType.LIMIT,
        limit_px=Decimal("95.00"),
        tif=TimeInForce.DAY,
        created_ts=t0,
    )
    broker.submit(order)

    # Bar with low $98 does not trigger
    bar_high = make_test_bar(
        Symbol("AAPL"), t1, Decimal("100"), Decimal("105"), Decimal("98"), Decimal("102")
    )
    fills1 = broker.process_pending_orders(t1, {Symbol("AAPL"): bar_high})
    assert len(fills1) == 0

    # Next bar with low $93 triggers limit
    t2 = datetime(2022, 1, 5, 21, 0, tzinfo=UTC)
    bar_low = make_test_bar(
        Symbol("AAPL"), t2, Decimal("96"), Decimal("97"), Decimal("93"), Decimal("94")
    )
    fills2 = broker.process_pending_orders(t2, {Symbol("AAPL"): bar_low})
    assert len(fills2) == 1
    assert fills2[0].price <= Decimal("95.50")
