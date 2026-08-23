"""Unit tests for short-selling execution, borrowing costs, ledger accounting, and stops."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from atlas.backtest.broker import SimBroker
from atlas.backtest.costs import DefaultCostModelV1
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
from atlas.portfolio.ledger import BucketLedger


def test_borrow_cost_calculation() -> None:
    cost_model = DefaultCostModelV1(borrow_rate_annual=Decimal("0.03"))
    # Short notional of $100,000 for 1 day: (100,000 * 0.03) / 252 = $11.9047...
    daily_fee = cost_model.calculate_daily_borrow_fee(Decimal("100000.00"))
    assert daily_fee.amount > Decimal("11.00")
    assert daily_fee.amount < Decimal("12.00")


def test_bucket_ledger_short_execution_and_covering() -> None:
    ledger = BucketLedger()
    ledger.deposit(Money(Decimal("10000.00"), "USD"))

    swing_acc = ledger.accounts[BucketId.SWING]
    initial_cash = swing_acc.cash

    # 1. Execute short SELL 10 shares of TSLA at $200
    fill_short = Fill(
        order_id="ord_short_1",
        ts=datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
        qty=10,
        price=Decimal("200.00"),
        commission=Money.zero("USD"),
        fees=Money.zero("USD"),
        slippage_est=Money.zero("USD"),
        venue="SIM",
    )

    pos = ledger.execute_fill(
        fill=fill_short,
        bucket=BucketId.SWING,
        side=Side.SELL,
        symbol=Symbol("TSLA"),
        stop_px=Decimal("220.00"),
        allow_short=True,
    )

    assert pos is not None
    assert pos.qty == -10
    assert pos.avg_price == Decimal("200.00")
    assert swing_acc.cash == initial_cash + Money(Decimal("2000.00"), "USD")

    # Mark to market at $180 (gain of $20/share * 10 = $200)
    prices_down = {Symbol("TSLA"): Decimal("180.00")}
    assert swing_acc.unrealized_pnl(prices_down) == Money(Decimal("200.00"), "USD")

    # 2. Cover short at $180
    fill_cover = Fill(
        order_id="ord_cover_1",
        ts=datetime(2026, 4, 2, 10, 0, tzinfo=UTC),
        qty=10,
        price=Decimal("180.00"),
        commission=Money.zero("USD"),
        fees=Money.zero("USD"),
        slippage_est=Money.zero("USD"),
        venue="SIM",
    )

    pos_covered = ledger.execute_fill(
        fill=fill_cover,
        bucket=BucketId.SWING,
        side=Side.BUY,
        symbol=Symbol("TSLA"),
        allow_short=True,
    )

    assert pos_covered is None
    assert Symbol("TSLA") not in swing_acc.positions
    assert swing_acc.realized_pnl == Money(Decimal("200.00"), "USD")


def test_sim_broker_short_stops() -> None:
    broker = SimBroker(initial_capital=Money(Decimal("10000.00"), "USD"))
    t0 = datetime(2026, 4, 1, 9, 30, tzinfo=UTC)

    # Submit SELL order to open short
    order = Order(
        id="ord_short_tsla",
        run_id="run_1",
        strategy_version_id="strat_1",
        bucket=BucketId.SWING,
        symbol=Symbol("TSLA"),
        side=Side.SELL,
        qty=10,
        type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        created_ts=t0,
        stop_px=Decimal("220.00"),
    )
    broker.submit(order)

    # Process fill on t+1 at open $200
    t1 = datetime(2026, 4, 2, 9, 30, tzinfo=UTC)
    bars_t1 = {
        Symbol("TSLA"): Bar(
            symbol=Symbol("TSLA"),
            ts=t1,
            open=Decimal("200.00"),
            high=Decimal("205.00"),
            low=Decimal("198.00"),
            close=Decimal("202.00"),
            volume=100000,
        )
    }
    broker.process_pending_orders(t1, bars_t1)

    pos = broker.get_position(Symbol("TSLA"))
    assert pos is not None
    assert pos.qty == -10
    assert pos.stop_px == Decimal("220.00")

    # t+2: Price rallies to high $225 -> Stop loss breached on short!
    t2 = datetime(2026, 4, 3, 9, 30, tzinfo=UTC)
    bars_t2 = {
        Symbol("TSLA"): Bar(
            symbol=Symbol("TSLA"),
            ts=t2,
            open=Decimal("215.00"),
            high=Decimal("225.00"),  # > stop_px (220.00)
            low=Decimal("214.00"),
            close=Decimal("223.00"),
            volume=150000,
        )
    }

    stop_fills = broker.process_stops(t2, bars_t2)
    assert len(stop_fills) == 1
    assert broker.get_position(Symbol("TSLA")) is None  # Closed by stop buy to cover
