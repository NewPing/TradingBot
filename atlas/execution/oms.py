"""Order Management System (OMS): Execution routing, order lifecycle, and fill reconciliation."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from atlas.core.bus import Event, EventBus
from atlas.core.types import (
    BrokerOrderRef,
    Fill,
    Order,
    OrderStatus,
    Position,
    Symbol,
)
from atlas.data.models import FillRecord, OrderRecord
from atlas.execution.broker import Broker
from atlas.portfolio.ledger import BucketLedger
from atlas.risk.manager import RiskManager

logger = logging.getLogger("atlas.execution.oms")


class OrderManager:
    """Central Order Management System coordinating risk validation, routing, and ledger sync."""

    def __init__(
        self,
        broker: Broker,
        ledger: BucketLedger,
        risk_manager: RiskManager,
        event_bus: EventBus | None = None,
        db_session: Session | None = None,
    ) -> None:
        self.broker = broker
        self.ledger = ledger
        self.risk = risk_manager
        self.bus = event_bus
        self.db = db_session

        self.active_orders: dict[str, Order] = {}
        self.order_history: dict[str, Order] = {}
        self.fills_history: list[Fill] = []
        self.broker_ref_map: dict[str, str] = {}  # broker_ref -> order_id

        # Register fill callback with the broker
        self.broker.on_fill(self.process_fill)

    def submit_order(
        self,
        order: Order,
        current_prices: dict[Symbol, Decimal],
        symbol_sectors: dict[Symbol, str] | None = None,
        symbol_adv: dict[Symbol, Decimal] | None = None,
        symbol_correlations: dict[tuple[Symbol, Symbol], float] | None = None,
        critical_data_symbols: set[Symbol] | None = None,
    ) -> BrokerOrderRef:
        """Validate an order against risk rules and submit to broker."""
        # 1. Risk Manager validation
        try:
            self.risk.validate_order(
                order=order,
                ledger=self.ledger,
                current_prices=current_prices,
                symbol_sectors=symbol_sectors,
                symbol_adv=symbol_adv,
                symbol_correlations=symbol_correlations,
                critical_data_symbols=critical_data_symbols,
            )
        except Exception as err:
            rejected_order = replace(order, status=OrderStatus.REJECTED)
            self.order_history[order.id] = rejected_order
            self.risk.kill_switches.record_order_result(False, order.bucket)
            self._persist_order(rejected_order)
            logger.warning(f"Order {order.id} rejected by risk manager: {err}")
            raise

        # 2. Submit to broker
        try:
            broker_ref = self.broker.submit(order)
            submitted_order = replace(order, status=OrderStatus.SUBMITTED)
            self.active_orders[order.id] = submitted_order
            self.order_history[order.id] = submitted_order
            self.broker_ref_map[str(broker_ref)] = order.id
            self.risk.kill_switches.record_order_result(True, order.bucket)
            self._persist_order(submitted_order, broker_ref=str(broker_ref))

            if self.bus is not None:
                self.bus.emit(
                    Event(
                        topic="order.submitted",
                        data={
                            "order_id": order.id,
                            "symbol": order.symbol,
                            "side": order.side.value,
                            "qty": order.qty,
                            "bucket": order.bucket.value,
                        },
                    )
                )

            return broker_ref
        except Exception as err:
            rejected_order = replace(order, status=OrderStatus.REJECTED)
            self.order_history[order.id] = rejected_order
            self.risk.kill_switches.record_order_result(False, order.bucket)
            self._persist_order(rejected_order)
            logger.error(f"Broker submission failed for order {order.id}: {err}")
            raise

    def process_fill(self, fill: Fill) -> None:
        """Process fill event from broker, update ledger and order status."""
        order_id = self.broker_ref_map.get(str(fill.order_id), fill.order_id)
        order = self.active_orders.get(order_id) or self.order_history.get(order_id)
        if order is None:
            logger.warning(f"Received fill for unknown order_id / ref: {fill.order_id}")
            return

        # Execute fill in bucket ledger
        self.ledger.execute_fill(
            fill=fill,
            bucket=order.bucket,
            side=order.side,
            symbol=order.symbol,
            stop_px=order.stop_px,
        )

        self.fills_history.append(fill)

        # Update order status
        filled_order = replace(order, status=OrderStatus.FILLED)
        self.order_history[order.id] = filled_order
        self.active_orders.pop(order.id, None)

        self._persist_order(filled_order)
        self._persist_fill(fill)

        if self.bus is not None:
            self.bus.emit(
                Event(
                    topic="fill.completed",
                    data={
                        "order_id": fill.order_id,
                        "symbol": order.symbol,
                        "side": order.side.value,
                        "qty": fill.qty,
                        "price": str(fill.price),
                        "bucket": order.bucket.value,
                        "ts": fill.ts.isoformat(),
                    },
                )
            )

    def cancel_order(self, order_id: str) -> None:
        """Cancel an open order."""
        order = self.active_orders.get(order_id)
        if order is None:
            return

        # Find broker reference
        broker_ref = None
        for ref_str, o_id in self.broker_ref_map.items():
            if o_id == order_id:
                broker_ref = BrokerOrderRef(ref_str)
                break

        if broker_ref:
            self.broker.cancel(broker_ref)

        canceled_order = replace(order, status=OrderStatus.CANCELED)
        self.order_history[order_id] = canceled_order
        self.active_orders.pop(order_id, None)
        self._persist_order(canceled_order)

    def cancel_all_working_orders(self) -> int:
        """Cancel all pending/active orders across all buckets."""
        count = 0
        order_ids = list(self.active_orders.keys())
        for oid in order_ids:
            self.cancel_order(oid)
            count += 1
        return count

    def get_open_positions(self) -> list[Position]:
        """Return all open positions from ledger."""
        return self.ledger.all_positions()

    def _persist_order(self, order: Order, broker_ref: str | None = None) -> None:
        """Persist or update order record in database."""
        if self.db is None:
            return
        try:
            existing = self.db.get(OrderRecord, order.id)
            if existing:
                existing.status = order.status.value
                existing.updated_ts = datetime.now(UTC)
                if broker_ref:
                    existing.broker_ref = broker_ref
            else:
                record = OrderRecord(
                    id=order.id,
                    run_id=order.run_id,
                    strategy_version_id=order.strategy_version_id,
                    bucket=order.bucket.value,
                    symbol=str(order.symbol),
                    side=order.side.value,
                    qty=order.qty,
                    order_type=order.type.value,
                    tif=order.tif.value,
                    limit_px=order.limit_px,
                    stop_px=order.stop_px,
                    status=order.status.value,
                    broker_ref=broker_ref,
                    created_ts=order.created_ts,
                    updated_ts=order.created_ts,
                )
                self.db.add(record)
            self.db.commit()
        except Exception as err:
            logger.error(f"Failed to persist order {order.id}: {err}")
            self.db.rollback()

    def _persist_fill(self, fill: Fill) -> None:
        """Persist fill record in database."""
        if self.db is None:
            return
        try:
            record = FillRecord(
                order_id=fill.order_id,
                ts=fill.ts,
                qty=fill.qty,
                price=fill.price,
                commission=fill.commission.amount,
                fees=fill.fees.amount,
                slippage_est=fill.slippage_est.amount,
                venue=fill.venue,
            )
            self.db.add(record)
            self.db.commit()
        except Exception as err:
            logger.error(f"Failed to persist fill for order {fill.order_id}: {err}")
            self.db.rollback()
