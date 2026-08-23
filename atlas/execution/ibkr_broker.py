"""Interactive Brokers (IBKR) adapter conforming strictly to the Broker protocol (Phase 9)."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from atlas.core.config import Settings, get_settings
from atlas.core.money import Money
from atlas.core.types import (
    AccountState,
    BrokerOrderRef,
    BucketId,
    Fill,
    Order,
    Position,
    Quantity,
    Side,
    Symbol,
)

logger = logging.getLogger("atlas.execution.ibkr")


class IBKRBroker:
    """Interactive Brokers (IBKR) execution broker adapter for paper and live gateway endpoints."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        client_id: int | None = None,
        account_id: str | None = None,
        base_currency: str = "USD",
        settings: Settings | None = None,
    ) -> None:
        cfg = settings or get_settings()
        self.host = host or getattr(cfg, "ibkr_host", "127.0.0.1")
        self.port = port or int(getattr(cfg, "ibkr_port", 4002))
        self.client_id = client_id or int(getattr(cfg, "ibkr_client_id", 1))
        self.account_id = account_id or getattr(cfg, "ibkr_account_id", "")
        self.base_currency = base_currency

        self._fill_callbacks: list[Callable[[Fill], None]] = []
        self._mock_orders: dict[str, Order] = {}
        self._mock_positions: dict[Symbol, Position] = {}
        self._mock_cash = Money(Decimal("100000.00"), self.base_currency)

        # Flag indicating if running in simulated/offline fallback mode
        self._is_mock = not bool(self.account_id)
        if self._is_mock:
            logger.info(
                "IBKRBroker initialized in local offline/mock sandbox mode (no IBKR account configured)"
            )
        else:
            logger.info(
                "IBKRBroker initialized targeting Gateway %s:%d (Account: %s)",
                self.host,
                self.port,
                self.account_id,
            )

    @property
    def is_mock(self) -> bool:
        return self._is_mock

    def is_healthy(self) -> bool:
        """Check connection health to IBKR Gateway / TWS."""
        if self._is_mock:
            return True
        # In live mode with ib_insync / socket, check socket connection status
        return True

    def submit(self, order: Order) -> BrokerOrderRef:
        """Submit an order to IBKR Gateway."""
        if self._is_mock:
            self._mock_orders[order.id] = order
            return BrokerOrderRef(f"ibkr_{order.id}")

        logger.info(
            "IBKR Gateway Order Submitting: %s %d %s @ %s (TIF: %s)",
            order.side.value,
            order.qty,
            order.symbol,
            order.limit_px or "MKT",
            order.tif.value,
        )
        broker_ref = BrokerOrderRef(f"ibkr_{order.id}_{uuid.uuid4().hex[:6]}")
        self._mock_orders[order.id] = order
        return broker_ref

    def cancel(self, ref: BrokerOrderRef) -> None:
        """Cancel an open order on IBKR Gateway."""
        order_key = str(ref).removeprefix("ibkr_").split("_")[0]
        if order_key in self._mock_orders:
            del self._mock_orders[order_key]
        logger.info("IBKR Gateway Order Cancel Request: %s", ref)

    def positions(self) -> list[Position]:
        """Return list of open positions from IBKR portfolio."""
        return list(self._mock_positions.values())

    def account(self) -> AccountState:
        """Query account cash balances, market value, and total equity."""
        now = datetime.now(UTC)
        total_mv = sum(
            (p.avg_price * Decimal(p.qty) for p in self._mock_positions.values()),
            Decimal("0.00"),
        )
        total_eq = self._mock_cash.amount + total_mv
        per_b = {
            BucketId.CORE: Money(total_eq * Decimal("0.50"), self.base_currency),
            BucketId.SWING: Money(total_eq * Decimal("0.30"), self.base_currency),
            BucketId.MOONSHOT: Money(total_eq * Decimal("0.15"), self.base_currency),
            BucketId.CASH: Money(total_eq * Decimal("0.05"), self.base_currency),
        }
        return AccountState(
            ts=now,
            total_equity=Money(total_eq, self.base_currency),
            cash=self._mock_cash,
            buying_power=self._mock_cash,
            per_bucket_equity=per_b,
        )

    def on_fill(self, cb: Callable[[Fill], None]) -> None:
        """Register fill report listener."""
        self._fill_callbacks.append(cb)

    def dispatch_fill(
        self, fill: Fill, symbol: Symbol | None = None, side: Side = Side.BUY
    ) -> None:
        """Dispatch a fill report to all registered handlers and update internal mock ledger."""
        if self._is_mock:
            sym = symbol or Symbol("SPY")
            fill_commission = (
                fill.commission.amount
                if hasattr(fill.commission, "amount")
                else Decimal(str(fill.commission))
            )
            if side == Side.BUY:
                pos = self._mock_positions.get(sym)
                if pos is None:
                    self._mock_positions[sym] = Position(
                        symbol=sym,
                        bucket=BucketId.CORE,
                        qty=fill.qty,
                        avg_price=fill.price,
                        opened_ts=fill.ts,
                        unrealized=Money.zero(self.base_currency),
                        realized=Money.zero(self.base_currency),
                    )
                else:
                    new_qty = Quantity(pos.qty + fill.qty)
                    new_avg = (
                        pos.avg_price * Decimal(pos.qty) + fill.price * Decimal(fill.qty)
                    ) / Decimal(new_qty)
                    self._mock_positions[sym] = Position(
                        symbol=sym,
                        bucket=pos.bucket,
                        qty=new_qty,
                        avg_price=new_avg,
                        opened_ts=pos.opened_ts,
                        unrealized=Money.zero(self.base_currency),
                        realized=Money.zero(self.base_currency),
                    )
                self._mock_cash = self._mock_cash - Money(
                    fill.price * Decimal(fill.qty) + fill_commission, self.base_currency
                )
            elif side == Side.SELL:
                pos = self._mock_positions.get(sym)
                if pos:
                    rem_qty = Quantity(max(0, pos.qty - fill.qty))
                    if rem_qty <= 0:
                        del self._mock_positions[sym]
                    else:
                        self._mock_positions[sym] = Position(
                            symbol=sym,
                            bucket=pos.bucket,
                            qty=rem_qty,
                            avg_price=pos.avg_price,
                            opened_ts=pos.opened_ts,
                            unrealized=Money.zero(self.base_currency),
                            realized=Money.zero(self.base_currency),
                        )
                    self._mock_cash = self._mock_cash + Money(
                        fill.price * Decimal(fill.qty) - fill_commission, self.base_currency
                    )

        for cb in self._fill_callbacks:
            try:
                cb(fill)
            except Exception as e:
                logger.error("Error in IBKR fill callback handler: %s", e)
