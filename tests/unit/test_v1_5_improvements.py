"""Unit tests for ATLAS v1.5 improvements (multi-horizon metrics, real data verification, uncapped budget, screener)."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from atlas.backtest.broker import SimBroker
from atlas.backtest.metrics import compute_metrics, compute_multi_horizon_metrics
from atlas.core.money import Money
from atlas.core.types import (
    Bar,
    BucketId,
    Fill,
    Order,
    OrderStatus,
    OrderType,
    Position,
    Quantity,
    Side,
    Symbol,
    TimeInForce,
)
from atlas.data.models import Base
from atlas.data.validate import DataValidator
from atlas.portfolio.policies import TopNLongOnlyPolicy
from atlas.research.trials import TrialTracker
from atlas.risk.killswitch import KillSwitchManager, KillSwitchTrigger


def test_compute_multi_horizon_metrics() -> None:
    """Verify multi-horizon calculation generates standard institutional horizons with SPY comparison."""
    start_d = date(2023, 1, 3)
    timestamps = [start_d + timedelta(days=i) for i in range(500)]
    initial_cap = 100_000.0
    equity_series = [initial_cap * (1.0 + 0.0004 * i) for i in range(500)]
    bm_series = [initial_cap * (1.0 + 0.0002 * i) for i in range(500)]

    horizons = compute_multi_horizon_metrics(
        timestamps=timestamps,
        equity_series=equity_series,
        initial_capital=initial_cap,
        benchmark_equity=bm_series,
    )

    assert len(horizons) > 0
    horizon_labels = [h.horizon for h in horizons]
    assert "ALL" in horizon_labels
    assert "1Y" in horizon_labels
    assert "YTD" in horizon_labels

    all_horizon = next(h for h in horizons if h.horizon == "ALL")
    assert all_horizon.starting_capital == pytest.approx(100_000.0, rel=1e-2)
    assert all_horizon.ending_equity > all_horizon.starting_capital
    assert all_horizon.net_profit_usd > 0
    assert all_horizon.strategy_return_pct > 0
    assert all_horizon.benchmark_ending_equity > all_horizon.benchmark_starting_equity
    assert all_horizon.alpha >= 0.0


def test_real_data_verification() -> None:
    """Verify DataValidator.verify_real_market_data accurately validates real market bars."""
    valid_bars = [
        Bar(
            symbol=Symbol("SPY"),
            ts=datetime(2024, 1, 15, 16, 0, tzinfo=UTC),
            open=Decimal("475.00"),
            high=Decimal("478.50"),
            low=Decimal("474.20"),
            close=Decimal("477.80"),
            volume=45000000,
            adj_factor=Decimal("1.0"),
            vwap=Decimal("476.50"),
            source="tiingo",
        )
    ]
    assert DataValidator.verify_real_market_data(valid_bars) is True
    assert DataValidator.verify_real_market_data([]) is False


def test_uncapped_trial_budget_v1_5() -> None:
    """Verify v1.5 uncapped trial budget accounting allows unlimited exploratory iterations."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)

    tracker = TrialTracker(session)

    # Record 10 trials
    for i in range(10):
        tracker.record_trial(
            family="core_trend",
            parameters={"sma_period": 200 + i},
            metrics={"sharpe": 1.25 + 0.01 * i},
        )

    # Weekly budget = 0 (unlimited)
    status = tracker.get_budget_status(family="core_trend", weekly_budget=0)
    assert status["total_trials"] == 10
    assert status["trials_this_week"] == 10
    assert status["is_unlimited"] is True
    assert status["budget_remaining"] > 1000
    assert status["budget_pct_used"] == 0.0


def test_multi_horizon_fifo_lot_matching_across_windows() -> None:
    """Verify multi-horizon FIFO matching doesn't convert prior-window buys into short positions."""
    # Trade 1: Bought in 2022, sold in 2023
    f1 = Fill(
        order_id="ord_1",
        ts=datetime(2022, 6, 1, 16, 0, tzinfo=UTC),
        qty=100,
        price=Decimal("100.00"),
        commission=Money.zero("USD"),
        fees=Money.zero("USD"),
        slippage_est=Money.zero("USD"),
        venue="SIM",
        symbol=Symbol("AAPL"),
        side=Side.BUY,
    )
    f2 = Fill(
        order_id="ord_2",
        ts=datetime(2023, 6, 1, 16, 0, tzinfo=UTC),
        qty=100,
        price=Decimal("150.00"),
        commission=Money.zero("USD"),
        fees=Money.zero("USD"),
        slippage_est=Money.zero("USD"),
        venue="SIM",
        symbol=Symbol("AAPL"),
        side=Side.SELL,
    )

    timestamps = [date(2022, 1, 1) + timedelta(days=i) for i in range(600)]
    equity = [100000.0 + i * 100.0 for i in range(600)]

    horizons = compute_multi_horizon_metrics(
        timestamps=timestamps,
        equity_series=equity,
        initial_capital=100000.0,
        fills=[f1, f2],
    )

    h_1y = next((h for h in horizons if h.horizon == "1Y"), None)
    assert h_1y is not None
    # 1Y window should capture the trade that exited in 2023 as 1 winning trade
    assert h_1y.total_trades == 1
    assert h_1y.win_rate == 1.0


def test_calmar_ratio_zero_drawdown() -> None:
    """Verify Calmar ratio returns 999.99 instead of 0.0 when CAGR > 0 and drawdown is zero."""
    metrics = compute_metrics(
        equity_series=[100000.0, 101000.0, 102000.0, 103000.0],
        initial_capital=100000.0,
        fills=[],
    )
    assert metrics.max_drawdown == 0.0
    assert metrics.cagr > 0.0
    assert metrics.calmar_ratio == 999.99


def test_top_n_policy_cross_bucket_isolation() -> None:
    """Verify TopN policy in CORE bucket does not liquidate SWING positions."""
    policy = TopNLongOnlyPolicy(n=2, bucket=BucketId.CORE)
    pos_core = Position(
        symbol=Symbol("AAPL"),
        bucket=BucketId.CORE,
        qty=Quantity(10),
        avg_price=Decimal("150.00"),
        opened_ts=datetime.now(UTC),
        unrealized=Money.zero("USD"),
        realized=Money.zero("USD"),
    )
    pos_swing = Position(
        symbol=Symbol("TSLA"),
        bucket=BucketId.SWING,
        qty=Quantity(20),
        avg_price=Decimal("200.00"),
        opened_ts=datetime.now(UTC),
        unrealized=Money.zero("USD"),
        realized=Money.zero("USD"),
    )

    # Empty signals -> CORE positions targeted for exit, but SWING untouched
    targets = policy.generate_targets(
        signals={},
        current_positions=[pos_core, pos_swing],
        current_prices={Symbol("AAPL"): Decimal("150.00"), Symbol("TSLA"): Decimal("200.00")},
        total_equity=Money(Decimal("100000.00"), "USD"),
        available_cash=Money(Decimal("50000.00"), "USD"),
    )

    assert targets.get(Symbol("AAPL")) == Quantity(0)
    assert Symbol("TSLA") not in targets  # SWING position not touched!


def test_broker_short_flip_realized_pnl_reset() -> None:
    """Verify that when flipping long to short, the new short position starts with 0 realized PnL."""
    broker = SimBroker(initial_capital=Money(Decimal("100000.00"), "USD"))
    # Open long 10 shares at $100
    ord_buy = Order(
        id="ord_b1",
        run_id="run_1",
        strategy_version_id="strat_1",
        bucket=BucketId.SWING,
        symbol=Symbol("SPY"),
        side=Side.BUY,
        qty=10,
        type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        created_ts=datetime(2024, 1, 1, 16, 0, tzinfo=UTC),
        status=OrderStatus.NEW,
    )
    broker.submit(ord_buy)
    bar1 = Bar(
        symbol=Symbol("SPY"),
        ts=datetime(2024, 1, 2, 16, 0, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("105.00"),
        low=Decimal("99.00"),
        close=Decimal("102.00"),
        volume=1000000,
        adj_factor=Decimal("1.0"),
    )
    broker.process_pending_orders(datetime(2024, 1, 2, 16, 0, tzinfo=UTC), {Symbol("SPY"): bar1})

    # Sell 20 shares at $110 (close 10 long with profit, open 10 short)
    ord_sell = Order(
        id="ord_s1",
        run_id="run_1",
        strategy_version_id="strat_1",
        bucket=BucketId.SWING,
        symbol=Symbol("SPY"),
        side=Side.SELL,
        qty=20,
        type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        created_ts=datetime(2024, 1, 2, 16, 0, tzinfo=UTC),
        status=OrderStatus.NEW,
    )
    broker.submit(ord_sell)
    bar2 = Bar(
        symbol=Symbol("SPY"),
        ts=datetime(2024, 1, 3, 16, 0, tzinfo=UTC),
        open=Decimal("110.00"),
        high=Decimal("115.00"),
        low=Decimal("109.00"),
        close=Decimal("112.00"),
        volume=1000000,
        adj_factor=Decimal("1.0"),
    )
    broker.process_pending_orders(datetime(2024, 1, 3, 16, 0, tzinfo=UTC), {Symbol("SPY"): bar2})

    pos = broker.get_position(Symbol("SPY"))
    assert pos is not None
    assert pos.qty == -10
    # New short position lot should start with 0 realized PnL
    assert pos.realized == Money.zero("USD")
    # But broker aggregate realized PnL should reflect the profit from closing the long
    assert broker.realized_pnl > Money.zero("USD")


def test_rolling_5_session_loss_kill_switch() -> None:
    """Verify rolling 5-session loss triggers over sessions across weekends."""
    mgr = KillSwitchManager()
    mgr.new_session(Decimal("100000.00"))
    mgr.new_session(Decimal("99000.00"))
    mgr.new_session(Decimal("98000.00"))
    mgr.new_session(Decimal("97000.00"))
    mgr.new_session(Decimal("96000.00"))

    # Session 5 drops to $94,000 (-6% vs session 1)
    switches = mgr.evaluate_equity(Money(Decimal("94000.00"), "USD"))
    triggers = [s.trigger for s in switches]
    assert KillSwitchTrigger.ROLLING_5D_LOSS in triggers


def test_sim_broker_short_margin_check() -> None:
    """Verify that excessive short sell orders are clamped/canceled when margin is insufficient."""
    broker = SimBroker(initial_capital=Money(Decimal("10000.00"), "USD"))
    # Attempt to short 10,000 shares of $100 stock ($1,000,000 notional on a $10k account)
    ord_short = Order(
        id="ord_short_huge",
        run_id="run_1",
        strategy_version_id="strat_1",
        bucket=BucketId.SWING,
        symbol=Symbol("AAPL"),
        side=Side.SELL,
        qty=10000,
        type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        created_ts=datetime(2024, 1, 1, 16, 0, tzinfo=UTC),
        status=OrderStatus.NEW,
    )
    broker.submit(ord_short)
    bar = Bar(
        symbol=Symbol("AAPL"),
        ts=datetime(2024, 1, 2, 16, 0, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("99.00"),
        close=Decimal("100.00"),
        volume=1000000,
        adj_factor=Decimal("1.0"),
    )
    fills = broker.process_pending_orders(
        datetime(2024, 1, 2, 16, 0, tzinfo=UTC), {Symbol("AAPL"): bar}
    )
    assert len(fills) == 1
    # Effective qty should be clamped to available margin (approx 20k / 101 ~= 198 shares max)
    assert fills[0].qty < 10000
    assert fills[0].qty <= 200


def test_sim_broker_margin_debit_interest() -> None:
    """Verify SimBroker charges margin interest when cash balance is negative."""
    broker = SimBroker(initial_capital=Money(Decimal("10000.00"), "USD"))
    # Artificially set cash to negative -$10,000
    broker._cash = Money(Decimal("-10000.00"), "USD")
    borrow_fee, cash_yield = broker.apply_daily_carry(
        margin_rate_annual=Decimal("0.06"),
        cash_yield_annual=Decimal("0.04"),
    )
    # Cash should decrease further due to margin interest
    assert broker.cash.amount < Decimal("-10000.00")
    assert cash_yield.amount == Decimal("0.00")


def test_top_n_policy_conviction_weighting() -> None:
    """Verify TopNLongOnlyPolicy allocates capital based on signal conviction when weight_by='conviction'."""
    from atlas.core.types import Signal, SignalLayer

    policy = TopNLongOnlyPolicy(
        n=2, weight_by="conviction", bucket=BucketId.CORE, max_position_pct=Decimal("0.60")
    )
    sig1 = Signal(
        provider="sig1",
        layer=SignalLayer.L1_TECHNICAL,
        symbol=Symbol("AAPL"),
        ts=datetime(2024, 1, 1, 16, 0, tzinfo=UTC),
        score=0.8,
        confidence=0.9,
    )
    sig2 = Signal(
        provider="sig2",
        layer=SignalLayer.L1_TECHNICAL,
        symbol=Symbol("MSFT"),
        ts=datetime(2024, 1, 1, 16, 0, tzinfo=UTC),
        score=0.4,
        confidence=0.5,
    )
    targets = policy.generate_targets(
        signals={Symbol("AAPL"): sig1, Symbol("MSFT"): sig2},
        current_positions=[],
        current_prices={Symbol("AAPL"): Decimal("100.00"), Symbol("MSFT"): Decimal("100.00")},
        total_equity=Money(Decimal("100000.00"), "USD"),
        available_cash=Money(Decimal("100000.00"), "USD"),
    )
    assert targets[Symbol("AAPL")] > targets[Symbol("MSFT")]
