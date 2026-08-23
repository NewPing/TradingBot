"""Unit tests verifying audit remediation fixes across simulation, fees, risk limits, and metrics."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal

import pytest

from atlas.backtest.broker import SimBroker
from atlas.backtest.costs import DefaultCostModelV1
from atlas.backtest.metrics import compute_metrics
from atlas.core.calendar import get_trading_days
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
from atlas.research.stats import monte_carlo_trade_shuffle
from atlas.risk.limits import HardLimitsValidator


def test_entry_fee_deduction_in_simbroker() -> None:
    """Verify opening commissions and regulatory fees are strictly deducted from realized PnL on close."""
    cost_model = DefaultCostModelV1(broker_commission_type="ibkr")
    broker = SimBroker(initial_capital=Money(Decimal("10000.00"), "USD"), cost_model=cost_model)
    sym = Symbol("TEST")

    # Day 1: Buy 10 shares at $100. Entry fee = $2.00
    buy_order = Order(
        id="ord_buy_1",
        run_id="run_1",
        strategy_version_id="v1",
        bucket=BucketId.CORE,
        symbol=sym,
        side=Side.BUY,
        qty=10,
        type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        created_ts=datetime(2024, 1, 2, 16, 0, tzinfo=UTC),
    )
    broker.submit(buy_order)

    day2_bar = Bar(
        symbol=sym,
        ts=datetime(2024, 1, 3, 21, 0, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("105.00"),
        low=Decimal("99.00"),
        close=Decimal("104.00"),
        volume=100000,
    )
    # Fills buy order
    bars_map1 = {sym: day2_bar}
    broker.process_pending_orders(
        current_ts=datetime(2024, 1, 3, 21, 0, tzinfo=UTC),
        current_bars=bars_map1,
    )

    pos = broker.get_position(sym)
    assert pos is not None
    assert pos.open_fees.amount > Decimal("0")  # Recorded entry friction

    # Day 3: Sell 10 shares at $110.
    sell_order = Order(
        id="ord_sell_1",
        run_id="run_1",
        strategy_version_id="v1",
        bucket=BucketId.CORE,
        symbol=sym,
        side=Side.SELL,
        qty=10,
        type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        created_ts=datetime(2024, 1, 3, 16, 0, tzinfo=UTC),
    )
    broker.submit(sell_order)

    day4_bar = Bar(
        symbol=sym,
        ts=datetime(2024, 1, 4, 21, 0, tzinfo=UTC),
        open=Decimal("110.00"),
        high=Decimal("112.00"),
        low=Decimal("109.00"),
        close=Decimal("111.00"),
        volume=100000,
    )
    bars_map2 = {sym: day4_bar}
    fills = broker.process_pending_orders(
        current_ts=datetime(2024, 1, 4, 21, 0, tzinfo=UTC),
        current_bars=bars_map2,
    )
    assert len(fills) == 1

    # Cash difference must equal gross price gain minus total entry & exit costs
    expected_cash_gain = broker.cash.amount - Decimal("10000.00")
    assert broker.realized_pnl.amount == expected_cash_gain
    assert broker.get_position(sym) is None


def test_entry_fee_deduction_in_bucket_ledger() -> None:
    """Verify BucketLedger accurately deducts entry fees from realized PnL on position exits."""
    ledger = BucketLedger(currency="USD")
    ledger.deposit(Money(Decimal("10000.00"), "USD"))
    sym = Symbol("TEST")

    # Buy fill with $5 fee
    buy_fill = Fill(
        order_id="buy_1",
        ts=datetime(2024, 1, 2, 21, 0, tzinfo=UTC),
        qty=10,
        price=Decimal("100.00"),
        commission=Money(Decimal("3.00"), "USD"),
        fees=Money(Decimal("2.00"), "USD"),
        slippage_est=Money.zero("USD"),
        venue="SIM",
        symbol=sym,
        side=Side.BUY,
    )
    ledger.execute_fill(buy_fill, BucketId.CORE, Side.BUY, sym)

    pos = ledger.accounts[BucketId.CORE].positions[sym]
    assert pos.open_fees == Money(Decimal("5.00"), "USD")

    # Sell fill at $110 with $4 fee
    sell_fill = Fill(
        order_id="sell_1",
        ts=datetime(2024, 1, 3, 21, 0, tzinfo=UTC),
        qty=10,
        price=Decimal("110.00"),
        commission=Money(Decimal("2.00"), "USD"),
        fees=Money(Decimal("2.00"), "USD"),
        slippage_est=Money.zero("USD"),
        venue="SIM",
        symbol=sym,
        side=Side.SELL,
    )
    ledger.execute_fill(sell_fill, BucketId.CORE, Side.SELL, sym)

    # Gross profit = $100. Total fees = $5 entry + $4 exit = $9. Net realized PnL = $91.
    acc = ledger.accounts[BucketId.CORE]
    assert acc.realized_pnl == Money(Decimal("91.00"), "USD")


def test_session_cutoff_simulation_awareness() -> None:
    """Verify session cutoff does not reject simulated orders at 16:00 ET / 21:00 UTC."""
    validator = HardLimitsValidator(session_cutoff_minutes=10)
    ledger = BucketLedger(currency="USD")
    ledger.deposit(Money(Decimal("100000.00"), "USD"))
    sym = Symbol("SPY")

    # Order created at 21:00 UTC (16:00 EST in winter)
    winter_ts = datetime(2024, 1, 15, 21, 0, tzinfo=UTC)
    order = Order(
        id="ord_winter",
        run_id="run_sim",
        strategy_version_id="v1",
        bucket=BucketId.CORE,
        symbol=sym,
        side=Side.BUY,
        qty=10,
        type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        created_ts=winter_ts,
    )

    prices_map = {sym: Decimal("450.00")}

    # Simulated order should pass
    results_sim = validator.validate_order(
        order=order,
        ledger=ledger,
        current_prices=prices_map,
        is_simulated=True,
    )
    assert all(r.passed for r in results_sim)

    # Order at 16:00 ET (at close) should also pass even with is_simulated=False
    results_close = validator.validate_order(
        order=order,
        ledger=ledger,
        current_prices=prices_map,
        is_simulated=False,
    )
    assert all(r.passed for r in results_close)

    # Live order at 15:55 ET (5 minutes before close) should be rejected
    intraday_ts = datetime(2024, 1, 15, 20, 55, tzinfo=UTC)  # 15:55 EST
    live_order = Order(
        id="ord_live_late",
        run_id="run_live",
        strategy_version_id="v1",
        bucket=BucketId.CORE,
        symbol=sym,
        side=Side.BUY,
        qty=10,
        type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        created_ts=intraday_ts,
    )
    results_live = validator.validate_order(
        order=live_order,
        ledger=ledger,
        current_prices=prices_map,
        is_simulated=False,
    )
    assert any(r.rule_name == "SESSION_CUTOFF" and not r.passed for r in results_live)


def test_market_exposure_full_horizon_calculation() -> None:
    """Verify exposure_pct extends to end of backtest for held positions without late fills."""
    start_d = date(2024, 1, 2)
    end_d = date(2024, 1, 31)
    dates = get_trading_days(start_d, end_d)

    equity_series = [100000.0 + i * 100 for i in range(len(dates))]

    # Single buy fill on day 1
    buy_fill = Fill(
        order_id="buy_day1",
        ts=datetime.combine(dates[0], time(21, 0), tzinfo=UTC),
        qty=100,
        price=Decimal("100.00"),
        commission=Money.zero("USD"),
        fees=Money.zero("USD"),
        slippage_est=Money.zero("USD"),
        venue="SIM",
        symbol=Symbol("AAPL"),
        side=Side.BUY,
    )

    metrics = compute_metrics(
        equity_series=equity_series,
        initial_capital=100000.0,
        fills=[buy_fill],
        timestamps=dates,
    )

    # Since AAPL was held from Day 1 through the end of the month, exposure must be 100%
    assert metrics.exposure_pct == pytest.approx(1.0, abs=1e-2)


def test_monte_carlo_daily_returns_bootstrapping() -> None:
    """Verify Monte Carlo resampling supports daily return vectors without path distortion."""
    daily_returns = [0.001, -0.0005, 0.002, -0.001, 0.0015] * 50
    mc = monte_carlo_trade_shuffle(
        trade_pct_returns=[],
        n_sims=500,
        initial_capital=100_000.0,
        daily_returns=daily_returns,
        seed=123,
    )

    assert mc["prob_profit"] > 0.0
    assert mc["p5_cagr"] <= mc["p50_cagr"] <= mc["p95_cagr"]
    assert mc["p5_max_dd"] <= mc["p50_max_dd"] <= mc["p95_max_dd"]
