"""Deterministic backtesting engine strictly enforcing t+1 execution and zero lookahead."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal

import polars as pl

from atlas.backtest.broker import SimBroker, order_tif_day
from atlas.backtest.costs import DefaultCostModelV1
from atlas.backtest.metrics import PerformanceMetrics, compute_metrics
from atlas.core.calendar import get_trading_days
from atlas.core.clock import SimClock
from atlas.core.context import HistoricalMarketContext
from atlas.core.money import Money
from atlas.core.types import (
    Bar,
    Fill,
    Order,
    OrderStatus,
    OrderType,
    Side,
    Signal,
    Symbol,
)
from atlas.risk.limits import HardLimitsValidator
from atlas.risk.manager import RiskManager
from atlas.signals.indicators import compute_atr, compute_realized_volatility
from atlas.strategies.builder import (
    build_aggregator,
    build_cost_model,
    build_position_policy,
    build_signal_provider,
)
from atlas.strategies.spec import StrategySpec


@dataclass(frozen=True, slots=True)
class DailySnapshot:
    """Record of portfolio state at the end of a trading session."""

    ts: datetime
    equity: float
    cash: float
    holdings_value: float
    num_positions: int


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Complete result artifact produced by a backtest run."""

    spec: StrategySpec
    spec_hash: str
    start_date: date
    end_date: date
    initial_capital: Money
    final_equity: Money
    metrics: PerformanceMetrics
    equity_curve: list[DailySnapshot]
    orders: list[Order]
    fills: list[Fill]
    signals: list[Signal]

    def equity_dataframe(self) -> pl.DataFrame:
        """Export equity curve as a Polars DataFrame."""
        return pl.DataFrame(
            {
                "ts": [s.ts for s in self.equity_curve],
                "equity": [s.equity for s in self.equity_curve],
                "cash": [s.cash for s in self.equity_curve],
                "holdings_value": [s.holdings_value for s in self.equity_curve],
                "num_positions": [s.num_positions for s in self.equity_curve],
            }
        )


class BacktestEngine:
    """Backtest engine running the single-threaded deterministic event loop."""

    def __init__(
        self,
        spec: StrategySpec,
        data: pl.DataFrame | dict[Symbol, pl.DataFrame],
        initial_capital: Money | None = None,
        cost_model: DefaultCostModelV1 | None = None,
        risk_manager: RiskManager | None = None,
    ) -> None:
        self.spec = spec
        self.data = data
        self.initial_capital = initial_capital or Money(Decimal("100000.00"), "USD")
        self.cost_model = cost_model or build_cost_model(spec)
        if risk_manager is None:
            pos_pct_dec = Decimal(str(spec.policy.max_position_pct))
            max_sym_pct = pos_pct_dec if pos_pct_dec > Decimal("0.10") else Decimal("0.10")
            limits = HardLimitsValidator(
                max_single_symbol_pct=max_sym_pct,
                max_gross_exposure_pct=Decimal("1.00"),
            )
            self.risk_manager = RiskManager(limits_validator=limits)
        else:
            self.risk_manager = risk_manager

        # Build signal providers, aggregator, policy
        self.signal_providers = [
            build_signal_provider(sig.provider, sig.params) for sig in spec.signals
        ]
        self.aggregator = build_aggregator(spec)
        self.policy = build_position_policy(spec)

    def _should_rebalance(
        self,
        current_date: date,
        all_trading_days: list[date],
        day_index: int,
        has_rebalanced_once: bool,
    ) -> bool:
        """Determine if strategy should generate rebalance orders on this trading day."""
        sched = self.spec.rebalance.schedule.lower()

        if sched == "buy_and_hold":
            return not has_rebalanced_once
        elif sched == "daily":
            return True
        elif sched == "weekly_monday":
            # True if first trading day of the week
            return current_date.weekday() == 0 or (
                day_index > 0 and all_trading_days[day_index - 1].weekday() > current_date.weekday()
            )
        elif sched == "monthly_last_trading_day":
            # True if last trading day of the month
            if day_index == len(all_trading_days) - 1:
                return True
            next_day = all_trading_days[day_index + 1]
            return next_day.month != current_date.month
        elif sched == "monthly_first_trading_day":
            if day_index == 0:
                return True
            prev_day = all_trading_days[day_index - 1]
            return prev_day.month != current_date.month
        else:
            # Default to monthly
            if day_index == len(all_trading_days) - 1:
                return True
            next_day = all_trading_days[day_index + 1]
            return next_day.month != current_date.month

    def run(
        self,
        start_date: date,
        end_date: date,
        benchmark_symbol: Symbol | None = None,
    ) -> BacktestResult:
        """Execute backtest over the date range [start_date, end_date]."""
        trading_days = get_trading_days(start_date, end_date)
        if not trading_days:
            raise ValueError(f"No valid trading sessions found between {start_date} and {end_date}")

        # Initialize simulation clock at first trading day 09:30 UTC
        start_ts = datetime.combine(trading_days[0], time(16, 0), tzinfo=UTC)
        clock = SimClock(start_ts)
        context = HistoricalMarketContext(clock=clock, bars_df=self.data)
        broker = SimBroker(initial_capital=self.initial_capital, cost_model=self.cost_model)

        daily_snapshots: list[DailySnapshot] = []
        all_orders: list[Order] = []
        all_signals: list[Signal] = []
        has_rebalanced_once = False

        run_id = f"run_{uuid.uuid4().hex[:8]}"

        for idx, current_day in enumerate(trading_days):
            # Session close timestamp
            session_ts = datetime.combine(current_day, time(21, 0), tzinfo=UTC)
            clock.set(session_ts)

            # 1. Fetch latest bars available at current session
            symbols = context.universe()
            # If spec specifies target symbols, filter by them
            if self.spec.universe.symbols:
                target_syms = {Symbol(s) for s in self.spec.universe.symbols}
                symbols = [s for s in symbols if s in target_syms]

            current_bars: dict[Symbol, Bar] = {}
            daily_vols: dict[Symbol, Decimal] = {}
            annualized_vols: dict[Symbol, Decimal] = {}
            advs: dict[Symbol, Decimal] = {}
            atrs: dict[Symbol, Decimal] = {}

            for sym in symbols:
                bar = context.latest(sym)
                if bar is not None and bar.ts.date() == current_day:
                    current_bars[sym] = bar
                    # Compute realized vol, ATR, and ADV with standardized warmup lookback
                    hist = context.bars(sym, lookback=max(100, self.spec.stop.atr_period * 5))
                    if len(hist) >= 5:
                        closes = hist["close"].to_numpy()
                        v = compute_realized_volatility(closes, period=min(20, len(hist) - 1))
                        if v is not None:
                            annualized_vols[sym] = Decimal(str(v))
                            daily_vols[sym] = Decimal(str(v / (252.0**0.5)))
                        vols = hist["volume"].to_numpy()
                        mean_vol = float(vols.mean())
                        advs[sym] = Decimal(str(mean_vol * float(bar.close)))
                    if len(hist) >= self.spec.stop.atr_period:
                        atr_val = compute_atr(
                            highs=hist["high"].to_numpy(),
                            lows=hist["low"].to_numpy(),
                            closes=hist["close"].to_numpy(),
                            period=self.spec.stop.atr_period,
                        )
                        if atr_val is not None and atr_val > 0.0:
                            atrs[sym] = Decimal(str(atr_val))

            # Mark-to-market unrealized on existing positions for accurate session baseline
            broker.update_positions_unrealized(current_bars)
            account_curr = broker.account()
            self.risk_manager.kill_switches.new_session(account_curr.total_equity.amount)
            self.risk_manager.order_counts_today = dict.fromkeys(
                self.risk_manager.order_counts_today.keys(), 0
            )

            # 2. Process yesterday's pending orders (Fills on t+1 bar)
            broker.process_pending_orders(
                current_ts=session_ts,
                current_bars=current_bars,
                daily_vols=daily_vols,
                advs=advs,
            )

            # 3. Process stop-losses on current bar against established stop_px from prior session
            broker.process_stops(
                current_ts=session_ts,
                current_bars=current_bars,
                daily_vols=daily_vols,
                advs=advs,
            )

            # 4. Ratchet trailing stops at end-of-session on held positions for next session
            if self.spec.stop.type == "atr_trailing":
                broker.update_trailing_stops(
                    current_bars=current_bars,
                    atrs=atrs,
                    atr_multiple=self.spec.stop.multiple,
                )

            # 5. Apply overnight short borrow fees and idle cash yield
            broker.apply_daily_carry(
                current_bars=current_bars,
                borrow_rate_annual=self.cost_model.borrow_rate_annual,
                cash_yield_annual=self.cost_model.cash_yield_annual,
            )

            # 5. Update mark-to-market unrealized PnL & Risk Manager equity check
            broker.update_positions_unrealized(current_bars)
            account = broker.account()
            self.risk_manager.on_equity_update(account.total_equity, now=session_ts)

            # 6. Check if today is a rebalance day
            if self._should_rebalance(current_day, trading_days, idx, has_rebalanced_once):
                has_rebalanced_once = True
                composite_signals: dict[Symbol, Signal] = {}

                for sym in symbols:
                    sym_signals: list[Signal] = []
                    for provider in self.signal_providers:
                        sig = provider.evaluate(context, sym)
                        if sig is not None:
                            sym_signals.append(sig)
                            all_signals.append(sig)

                    composite = self.aggregator.combine(sym_signals, session_ts, sym)
                    if composite is not None:
                        composite_signals[sym] = composite

                # Generate target quantities from policy
                account = broker.account()
                current_positions = broker.positions()
                current_prices = {s: b.close for s, b in current_bars.items()}

                targets = self.policy.generate_targets(
                    signals=composite_signals,
                    current_positions=current_positions,
                    current_prices=current_prices,
                    total_equity=account.total_equity,
                    available_cash=account.cash,
                    realized_vols=annualized_vols,
                )

                # Generate orders for deltas between current and target
                existing_pos_map = {p.symbol: p.qty for p in current_positions}

                for sym, target_qty in targets.items():
                    curr_qty = existing_pos_map.get(sym, 0)
                    delta_qty = target_qty - curr_qty

                    if delta_qty == 0:
                        continue

                    bar = current_bars.get(sym)
                    if bar is None:
                        continue

                    side = Side.BUY if delta_qty > 0 else Side.SELL
                    qty_to_trade = abs(delta_qty)

                    # Check kill switches before entering new risk
                    if not self.risk_manager.kill_switches.allows_entries(self.spec.bucket) and (
                        (side == Side.BUY and curr_qty >= 0)
                        or (side == Side.SELL and curr_qty <= 0)
                    ):
                        continue

                    # Compute stop price if stop config enabled (long and short awareness)
                    stop_px: Decimal | None = None
                    if target_qty > 0 and delta_qty > 0:  # Long entry or position increase
                        if self.spec.stop.type == "atr_trailing":
                            hist = context.bars(
                                sym, lookback=max(100, self.spec.stop.atr_period * 5)
                            )
                            if len(hist) >= self.spec.stop.atr_period:
                                atr_val = compute_atr(
                                    highs=hist["high"].to_numpy(),
                                    lows=hist["low"].to_numpy(),
                                    closes=hist["close"].to_numpy(),
                                    period=self.spec.stop.atr_period,
                                )
                                if atr_val is not None and atr_val > 0.0:
                                    stop_distance = Decimal(str(atr_val * self.spec.stop.multiple))
                                    stop_px = max(Decimal("0.01"), bar.close - stop_distance)
                        elif self.spec.stop.type == "hard_pct":
                            pct_down = Decimal(str(self.spec.stop.pct))
                            stop_px = bar.close * (Decimal("1.0") - pct_down)
                    elif target_qty < 0 and delta_qty < 0:  # Short entry or position increase
                        if self.spec.stop.type == "atr_trailing":
                            hist = context.bars(
                                sym, lookback=max(100, self.spec.stop.atr_period * 5)
                            )
                            if len(hist) >= self.spec.stop.atr_period:
                                atr_val = compute_atr(
                                    highs=hist["high"].to_numpy(),
                                    lows=hist["low"].to_numpy(),
                                    closes=hist["close"].to_numpy(),
                                    period=self.spec.stop.atr_period,
                                )
                                if atr_val is not None and atr_val > 0.0:
                                    stop_distance = Decimal(str(atr_val * self.spec.stop.multiple))
                                    stop_px = bar.close + stop_distance
                        elif self.spec.stop.type == "hard_pct":
                            pct_up = Decimal(str(self.spec.stop.pct))
                            stop_px = bar.close * (Decimal("1.0") + pct_up)

                    order = Order(
                        id=f"ord_{sym}_{session_ts.strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}",
                        run_id=run_id,
                        strategy_version_id=self.spec.version,
                        bucket=self.spec.bucket,
                        symbol=sym,
                        side=side,
                        qty=qty_to_trade,
                        type=OrderType.MARKET,
                        tif=order_tif_day(),
                        created_ts=session_ts,
                        stop_px=stop_px,
                        status=OrderStatus.NEW,
                    )

                    # Centralized risk validation enforcing parity with live OMS
                    try:
                        current_ledger = broker.to_ledger(current_prices)
                        self.risk_manager.validate_order(
                            order=order,
                            ledger=current_ledger,
                            current_prices=current_prices,
                            symbol_adv=advs,
                            is_simulated=True,
                        )
                    except Exception:
                        continue

                    broker.submit(order)
                    all_orders.append(order)

            # 6. Record daily snapshot
            account = broker.account()
            holdings_val = float(account.total_equity.amount - account.cash.amount)
            snapshot = DailySnapshot(
                ts=session_ts,
                equity=float(account.total_equity.amount),
                cash=float(account.cash.amount),
                holdings_value=holdings_val,
                num_positions=len(broker.positions()),
            )
            daily_snapshots.append(snapshot)

        # Compute benchmark equity if benchmark symbol requested
        bm_equity: list[float] | None = None
        if benchmark_symbol is not None:
            bm_df = context.bars(benchmark_symbol, lookback=len(trading_days) + 10)
            if not bm_df.is_empty():
                bm_bars_by_date = {
                    r["ts"].date(): float(r["close"]) for r in bm_df.iter_rows(named=True)
                }
                bm_prices: list[float] = []
                for d in trading_days:
                    px = bm_bars_by_date.get(d)
                    if px is not None:
                        bm_prices.append(px)
                    elif bm_prices:
                        bm_prices.append(bm_prices[-1])
                    else:
                        bm_prices.append(1.0)
                if bm_prices:
                    first_px = bm_prices[0]
                    bm_equity = [
                        (p / first_px) * float(self.initial_capital.amount) for p in bm_prices
                    ]

        # Compute full performance metrics
        equity_values = [s.equity for s in daily_snapshots]
        snap_ts = [s.ts for s in daily_snapshots]
        metrics = compute_metrics(
            equity_series=equity_values,
            initial_capital=float(self.initial_capital.amount),
            fills=broker.fills,
            benchmark_equity=bm_equity,
            timestamps=snap_ts,
        )

        final_eq = Money(
            Decimal(
                str(daily_snapshots[-1].equity if daily_snapshots else self.initial_capital.amount)
            ),
            "USD",
        )

        return BacktestResult(
            spec=self.spec,
            spec_hash=self.spec.spec_hash(),
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_equity=final_eq,
            metrics=metrics,
            equity_curve=daily_snapshots,
            orders=all_orders,
            fills=broker.fills,
            signals=all_signals,
        )
