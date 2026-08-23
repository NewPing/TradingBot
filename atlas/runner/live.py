"""Live and paper execution runner daemon."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
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

            # 4. Generate orders if entries are permitted
            created_orders: list[Order] = []
            if self.context_factory is not None:
                ctx = self.context_factory(ts)
                for spec in self.strategy_specs:
                    spec_bucket = (
                        BucketId(spec.family.upper())
                        if spec.family.upper() in BucketId.__members__
                        else BucketId.CORE
                    )
                    if not self.risk.kill_switches.allows_entries(spec_bucket):
                        continue

                    # Strategy evaluation loop
                    for symbol in ctx.universe():
                        latest_bar = ctx.latest(symbol)
                        if latest_bar is None:
                            continue

                        px = latest_bar.close
                        current_prices[symbol] = px

                        # Check if already held
                        existing_pos = self.ledger.accounts[spec_bucket].positions.get(symbol)
                        if (
                            existing_pos is None
                            and len(self.ledger.accounts[spec_bucket].positions) < 5
                        ):
                            # Sizing calculation
                            bucket_cash = self.ledger.accounts[spec_bucket].cash
                            target_notional = bucket_cash * Decimal("0.15")
                            if px > Decimal("0") and target_notional.amount >= px:
                                target_qty = int(target_notional.amount // px)
                                if target_qty > 0:
                                    order = Order(
                                        id=f"ord-{uuid.uuid4().hex[:10]}",
                                        run_id=self.run_id,
                                        strategy_version_id=spec.name,
                                        bucket=spec_bucket,
                                        symbol=symbol,
                                        side=Side.BUY,
                                        qty=Quantity(target_qty),
                                        type=OrderType.MARKET,
                                        tif=TimeInForce.DAY,
                                        created_ts=ts,
                                        limit_px=px,
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

        # Generate immediate market sell orders to liquidate positions
        for b_id in buckets_to_flatten:
            account = self.ledger.accounts[b_id]
            for sym, pos in list(account.positions.items()):
                if pos.qty > 0:
                    sell_order = Order(
                        id=f"ord-flatten-{uuid.uuid4().hex[:8]}",
                        run_id=self.run_id,
                        strategy_version_id="emergency_flatten",
                        bucket=b_id,
                        symbol=sym,
                        side=Side.SELL,
                        qty=pos.qty,
                        type=OrderType.MARKET,
                        tif=TimeInForce.IOC,
                        created_ts=ts,
                    )
                    try:
                        self.oms.submit_order(sell_order, current_prices=current_prices)
                    except Exception as err:
                        logger.error(
                            f"Failed to submit emergency liquidation order for {sym}: {err}"
                        )

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
