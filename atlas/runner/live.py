"""Live and paper execution runner daemon."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from atlas.core.bus import Event, EventBus
from atlas.core.clock import Clock, RealClock
from atlas.core.context import MarketContext
from atlas.core.money import Money
from atlas.core.types import (
    BucketId,
    Order,
    OrderType,
    Quantity,
    RunMode,
    Side,
    Symbol,
    TimeInForce,
)
from atlas.data.models import EquityPoint, PositionSnapshot
from atlas.execution.broker import Broker
from atlas.execution.oms import OrderManager
from atlas.portfolio.ledger import BucketLedger
from atlas.risk.killswitch import KillSwitchTrigger
from atlas.risk.manager import RiskManager
from atlas.runner.health import RunnerHealthMonitor
from atlas.runner.recovery import CrashRecoveryManager
from atlas.signals.indicators import compute_atr
from atlas.strategies.builder import (
    build_aggregator,
    build_position_policy,
    build_signal_provider,
)
from atlas.strategies.spec import StrategySpec

logger = logging.getLogger("atlas.runner.live")


class LiveRunnerDaemon:
    """Autonomous execution daemon for Paper and Live trading modes."""

    def __init__(
        self,
        strategy_specs: list[StrategySpec],
        broker: Broker,
        risk_manager: RiskManager,
        ledger: BucketLedger | None = None,
        clock: Clock | None = None,
        context_factory: Callable[[datetime], MarketContext] | None = None,
        event_bus: EventBus | None = None,
        db_session: Session | None = None,
        recovery_manager: CrashRecoveryManager | None = None,
        run_id: str | None = None,
        mode: RunMode = RunMode.PAPER,
    ) -> None:
        self.strategy_specs = strategy_specs
        self.broker = broker
        self.risk = risk_manager
        self.ledger = ledger or BucketLedger()
        self.clock = clock or RealClock()
        self.context_factory = context_factory
        self.bus = event_bus
        self.db = db_session
        self.mode = mode
        self.run_id = run_id or f"run-paper-{uuid.uuid4().hex[:12]}"
        self.recovery = recovery_manager or CrashRecoveryManager(db_session=db_session)
        self.health = RunnerHealthMonitor(event_bus=event_bus)

        self.oms = OrderManager(
            broker=self.broker,
            ledger=self.ledger,
            risk_manager=self.risk,
            event_bus=self.bus,
            db_session=self.db,
        )

    def startup(self) -> None:
        """Initialize runner, rehydrate previous crash state if available, and verify broker."""
        logger.info(
            f"Starting LiveRunnerDaemon in {self.mode.value} mode (run_id={self.run_id})..."
        )
        self.health.start()

        # Check broker connectivity
        if not self.broker.is_healthy():
            logger.warning("Broker health check failed on startup")
            self.risk.kill_switches.trigger(
                KillSwitchTrigger.BROKER_DISCONNECT,
                "Broker connection unhealthy on runner startup",
            )

        # Attempt state recovery
        recovered_ledger, recovered_orders, rec_run_id, _ = self.recovery.recover(self.broker)
        if rec_run_id:
            self.ledger = recovered_ledger
            self.oms.ledger = self.ledger
            self.oms.active_orders = recovered_orders
            logger.info(f"Restored ledger state from previous session (run {rec_run_id})")

    def execute_cycle(
        self,
        current_prices: dict[Symbol, Decimal],
        now: datetime | None = None,
        symbol_sectors: dict[Symbol, str] | None = None,
        symbol_adv: dict[Symbol, Decimal] | None = None,
        symbol_correlations: dict[tuple[Symbol, Symbol], float] | None = None,
    ) -> dict[str, Any]:
        """Execute a single decision and order cycle across all buckets."""
        ts = now or self.clock.now
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)

        try:
            # 1. Update broker heartbeat
            if self.broker.is_healthy():
                self.risk.kill_switches.record_broker_heartbeat(now=ts)
            else:
                self.risk.kill_switches.check_broker_connection(now=ts)

            # 2. Re-value portfolio and evaluate equity kill switches
            tot_eq = self.ledger.total_equity(current_prices)
            self.risk.on_equity_update(tot_eq, now=ts)

            # 3. Handle emergency flatten if triggered
            req_flatten, buckets_to_flatten = self.risk.kill_switches.requires_flatten()
            if req_flatten:
                self._execute_flatten(buckets_to_flatten, current_prices, ts)
                self.health.record_cycle_success(now=ts)
                self._persist_cycle_data(tot_eq, ts, current_prices)
                return {
                    "status": "FLATTENED",
                    "total_equity": str(tot_eq.amount),
                    "open_positions": len(self.ledger.all_positions()),
                }

            # 4. Generate orders if entries are permitted using strategy signals and policies
            created_orders: list[Order] = []
            if self.context_factory is not None:
                ctx = self.context_factory(ts)
                for spec in self.strategy_specs:
                    spec_bucket = (
                        BucketId(
                            spec.bucket.value if hasattr(spec.bucket, "value") else str(spec.bucket)
                        )
                        if hasattr(spec, "bucket")
                        else BucketId.CORE
                    )
                    if not self.risk.kill_switches.allows_entries(spec_bucket):
                        continue

                    signal_providers = [
                        build_signal_provider(sig.provider, sig.params) for sig in spec.signals
                    ]
                    aggregator = build_aggregator(spec)
                    policy = build_position_policy(spec)

                    composite_signals: dict[Symbol, Any] = {}
                    symbols = ctx.universe()
                    if spec.universe.symbols:
                        target_syms = {Symbol(s) for s in spec.universe.symbols}
                        symbols = [s for s in symbols if s in target_syms]

                    for sym in symbols:
                        latest_bar = ctx.latest(sym)
                        if latest_bar is not None:
                            current_prices[sym] = latest_bar.close

                        sym_signals = []
                        for provider in signal_providers:
                            sig = provider.evaluate(ctx, sym)
                            if sig is not None:
                                sym_signals.append(sig)

                        comp = aggregator.combine(sym_signals, ts, sym)
                        if comp is not None:
                            composite_signals[sym] = comp

                    bucket_acc = self.ledger.accounts[spec_bucket]
                    bucket_positions = list(bucket_acc.positions.values())
                    targets = policy.generate_targets(
                        signals=composite_signals,
                        current_positions=bucket_positions,
                        current_prices=current_prices,
                        total_equity=tot_eq,
                        available_cash=bucket_acc.cash,
                    )

                    existing_pos_map = {p.symbol: p.qty for p in bucket_positions}
                    for sym, target_qty in targets.items():
                        curr_qty = existing_pos_map.get(sym, 0)
                        delta_qty = target_qty - curr_qty
                        if delta_qty == 0:
                            continue
                        px = current_prices.get(sym)
                        if px is None or px <= Decimal("0"):
                            continue

                        side = Side.BUY if delta_qty > 0 else Side.SELL

                        # Compute stop price if stop config enabled (long and short awareness)
                        stop_px: Decimal | None = None
                        if hasattr(spec, "stop") and spec.stop:
                            if target_qty > 0 and delta_qty > 0:
                                if spec.stop.type == "atr_trailing":
                                    hist = ctx.bars(sym, lookback=spec.stop.atr_period + 5)
                                    if len(hist) >= spec.stop.atr_period:
                                        atr_val = compute_atr(
                                            highs=hist["high"].to_numpy(),
                                            lows=hist["low"].to_numpy(),
                                            closes=hist["close"].to_numpy(),
                                            period=spec.stop.atr_period,
                                        )
                                        if atr_val is not None and atr_val > 0.0:
                                            stop_distance = Decimal(
                                                str(atr_val * spec.stop.multiple)
                                            )
                                            stop_px = max(Decimal("0.01"), px - stop_distance)
                                elif spec.stop.type == "hard_pct":
                                    pct_down = Decimal(str(spec.stop.pct))
                                    stop_px = px * (Decimal("1.0") - pct_down)
                            elif target_qty < 0 and delta_qty < 0:
                                if spec.stop.type == "atr_trailing":
                                    hist = ctx.bars(sym, lookback=spec.stop.atr_period + 5)
                                    if len(hist) >= spec.stop.atr_period:
                                        atr_val = compute_atr(
                                            highs=hist["high"].to_numpy(),
                                            lows=hist["low"].to_numpy(),
                                            closes=hist["close"].to_numpy(),
                                            period=spec.stop.atr_period,
                                        )
                                        if atr_val is not None and atr_val > 0.0:
                                            stop_distance = Decimal(
                                                str(atr_val * spec.stop.multiple)
                                            )
                                            stop_px = px + stop_distance
                                elif spec.stop.type == "hard_pct":
                                    pct_up = Decimal(str(spec.stop.pct))
                                    stop_px = px * (Decimal("1.0") + pct_up)

                        order = Order(
                            id=f"ord-{uuid.uuid4().hex[:10]}",
                            run_id=self.run_id,
                            strategy_version_id=spec.name,
                            bucket=spec_bucket,
                            symbol=sym,
                            side=side,
                            qty=Quantity(abs(delta_qty)),
                            type=OrderType.MARKET,
                            tif=TimeInForce.DAY,
                            created_ts=ts,
                            limit_px=px,
                            stop_px=stop_px,
                        )
                        try:
                            self.oms.submit_order(
                                order=order,
                                current_prices=current_prices,
                                symbol_sectors=symbol_sectors,
                                symbol_adv=symbol_adv,
                                symbol_correlations=symbol_correlations,
                            )
                            created_orders.append(order)
                        except Exception as err:
                            logger.warning(f"Could not submit order {order.id}: {err}")

                # Ratchet ATR trailing stops on existing positions
                for spec in self.strategy_specs:
                    if hasattr(spec, "stop") and spec.stop and spec.stop.type == "atr_trailing":
                        spec_bucket = (
                            BucketId(
                                spec.bucket.value
                                if hasattr(spec.bucket, "value")
                                else str(spec.bucket)
                            )
                            if hasattr(spec, "bucket")
                            else BucketId.CORE
                        )
                        b_acc = self.ledger.accounts[spec_bucket]
                        for p_sym, pos in list(b_acc.positions.items()):
                            if pos.qty == 0 or pos.stop_px is None:
                                continue
                            hist = ctx.bars(p_sym, lookback=spec.stop.atr_period + 5)
                            if len(hist) >= spec.stop.atr_period:
                                atr_val = compute_atr(
                                    highs=hist["high"].to_numpy(),
                                    lows=hist["low"].to_numpy(),
                                    closes=hist["close"].to_numpy(),
                                    period=spec.stop.atr_period,
                                )
                                if atr_val is not None and atr_val > 0.0:
                                    stop_dist = Decimal(str(atr_val * spec.stop.multiple))
                                    current_px = current_prices.get(p_sym, pos.avg_price)
                                    if pos.qty > 0:
                                        cand_stop = max(Decimal("0.01"), current_px - stop_dist)
                                        new_stop = max(pos.stop_px, cand_stop)
                                    else:
                                        cand_stop = current_px + stop_dist
                                        new_stop = min(pos.stop_px, cand_stop)
                                    b_acc.positions[p_sym] = replace(pos, stop_px=new_stop)

            # 5. Persist state for crash recovery
            self.recovery.persist_state(
                ledger=self.ledger,
                active_orders=self.oms.active_orders,
                run_id=self.run_id,
                strategy_version_id=self.strategy_specs[0].name
                if self.strategy_specs
                else "default",
            )

            # 6. Record cycle snapshot to DB
            self._persist_cycle_data(tot_eq, ts, current_prices)

            self.health.record_cycle_success(now=ts)

            # 7. Broadcast state
            if self.bus is not None:
                self.bus.emit(
                    Event(
                        topic="runner.cycle_complete",
                        data={
                            "ts": ts.isoformat(),
                            "total_equity": str(tot_eq.amount),
                            "cash": str(self.ledger.total_cash().amount),
                            "orders_submitted": len(created_orders),
                            "open_positions": len(self.ledger.all_positions()),
                        },
                    )
                )

            return {
                "status": "OK",
                "ts": ts.isoformat(),
                "total_equity": str(tot_eq.amount),
                "cash": str(self.ledger.total_cash().amount),
                "orders_submitted": len(created_orders),
                "open_positions": len(self.ledger.all_positions()),
            }

        except Exception as err:
            self.health.record_cycle_error(err, now=ts)
            logger.error(f"Error during runner execution cycle: {err}", exc_info=True)
            raise

    def _execute_flatten(
        self,
        buckets_to_flatten: set[BucketId],
        current_prices: dict[Symbol, Decimal],
        ts: datetime,
    ) -> None:
        """Cancel working orders and liquidate positions for designated buckets."""
        # Cancel all open orders in affected buckets
        for oid, order in list(self.oms.active_orders.items()):
            if order.bucket in buckets_to_flatten:
                self.oms.cancel_order(oid)

        # Generate immediate market orders to liquidate positions (sells for long, buys for short)
        for b_id in buckets_to_flatten:
            account = self.ledger.accounts[b_id]
            for sym, pos in list(account.positions.items()):
                if pos.qty == 0:
                    continue
                side = Side.SELL if pos.qty > 0 else Side.BUY
                abs_qty = abs(pos.qty)
                flatten_order = Order(
                    id=f"ord-flatten-{uuid.uuid4().hex[:8]}",
                    run_id=self.run_id,
                    strategy_version_id="emergency_flatten",
                    bucket=b_id,
                    symbol=sym,
                    side=side,
                    qty=Quantity(abs_qty),
                    type=OrderType.MARKET,
                    tif=TimeInForce.IOC,
                    created_ts=ts,
                )
                try:
                    self.oms.submit_order(flatten_order, current_prices=current_prices)
                except Exception as err:
                    logger.error(f"Failed to submit emergency liquidation order for {sym}: {err}")

    def _persist_cycle_data(
        self,
        total_equity: Money,
        ts: datetime,
        current_prices: dict[Symbol, Decimal],
    ) -> None:
        """Persist point-in-time equity curve and position snapshots into DB."""
        if self.db is None:
            return
        try:
            # Save equity point
            per_b_str = {
                b.value: str(self.ledger.bucket_equity(b, current_prices).amount) for b in BucketId
            }
            eq_pt = EquityPoint(
                run_id=self.run_id,
                ts=ts,
                total_equity=total_equity.amount,
                cash=self.ledger.total_cash().amount,
                per_bucket=str(per_b_str),
                drawdown=Decimal("0"),
            )
            self.db.add(eq_pt)

            # Save position snapshots
            for pos in self.ledger.all_positions():
                px = current_prices.get(pos.symbol, pos.avg_price)
                mv = px * pos.qty
                unrealized = (px - pos.avg_price) * pos.qty
                p_snap = PositionSnapshot(
                    run_id=self.run_id,
                    ts=ts,
                    symbol=str(pos.symbol),
                    bucket=pos.bucket.value,
                    qty=pos.qty,
                    avg_price=pos.avg_price,
                    market_value=mv,
                    unrealized_pnl=unrealized,
                )
                self.db.add(p_snap)

            self.db.commit()
        except Exception as err:
            logger.error(f"Failed to persist cycle metrics to DB: {err}")
            self.db.rollback()

    def shutdown(self) -> None:
        """Gracefully shut down daemon."""
        logger.info("Shutting down LiveRunnerDaemon...")
        self.health.stop()
