"""Alpaca Paper Trading Broker implementation conforming to Broker protocol."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from atlas.core.config import Settings, get_settings
from atlas.core.money import Money
from atlas.core.types import (
    AccountState,
    BrokerOrderRef,
    BucketId,
    Fill,
    Order,
    OrderType,
    Position,
    Quantity,
    Side,
    Symbol,
)

logger = logging.getLogger("atlas.execution.alpaca")


class AlpacaPaperBroker:
    """Live paper trading broker adapter using Alpaca Paper Trading API."""

    def __init__(
        self,
        api_key: str | None = None,
        secret_key: str | None = None,
        base_url: str | None = None,
        settings: Settings | None = None,
    ) -> None:
        cfg = settings or get_settings()
        self.api_key = api_key or cfg.alpaca_api_key_id or ""
        self.secret_key = secret_key or cfg.alpaca_api_secret or ""
        self.base_url = (
            base_url or cfg.alpaca_base_url or "https://paper-api.alpaca.markets"
        ).rstrip("/")

        self._fill_callbacks: list[Callable[[Fill], None]] = []
        self._mock_orders: dict[str, Order] = {}
        self._mock_positions: dict[Symbol, Position] = {}
        self._mock_cash = Money(Decimal("100000.00"), "USD")
        self._is_mock = not bool(self.api_key and self.secret_key)
        if self._is_mock:
            logger.info(
                "AlpacaPaperBroker running in local mock/offline mode (no credentials provided)"
            )

    @property
    def is_mock(self) -> bool:
        return self._is_mock

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        """Perform HTTP request against Alpaca REST API."""
        if self._is_mock:
            return None

        url = f"{self.base_url}{path}"
        headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json",
            "User-Agent": "ATLAS-Trading-System/1.0",
        }
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8")
            logger.error(f"Alpaca API HTTP {err.code} on {path}: {body}")
            raise RuntimeError(f"Alpaca API error {err.code}: {body}") from err
        except Exception as err:
            logger.error(f"Alpaca connection error on {path}: {err}")
            raise

    def is_healthy(self) -> bool:
        """Check API connection status."""
        if self._is_mock:
            return True
        try:
            res = self._request("GET", "/v2/account")
            return res is not None and res.get("status") == "ACTIVE"
        except Exception:
            return False

    def submit(self, order: Order) -> BrokerOrderRef:
        """Submit an order to Alpaca paper venue."""
        if self._is_mock:
            self._mock_orders[order.id] = order
            return BrokerOrderRef(order.id)

        alpaca_side = "buy" if order.side == Side.BUY else "sell"
        alpaca_type = "market"
        if order.type == OrderType.LIMIT:
            alpaca_type = "limit"
        elif order.type == OrderType.STOP:
            alpaca_type = "stop"
        elif order.type == OrderType.STOP_LIMIT:
            alpaca_type = "stop_limit"

        body: dict[str, Any] = {
            "symbol": str(order.symbol),
            "qty": str(order.qty),
            "side": alpaca_side,
            "type": alpaca_type,
            "time_in_force": order.tif.value.lower(),
            "client_order_id": order.id,
        }
        if order.type in (OrderType.LIMIT, OrderType.STOP_LIMIT) and order.limit_px is not None:
            body["limit_price"] = str(order.limit_px)
        if order.type in (OrderType.STOP, OrderType.STOP_LIMIT) and order.stop_px is not None:
            body["stop_price"] = str(order.stop_px)

        res = self._request("POST", "/v2/orders", body)
        alpaca_id = res.get("id", order.id)
        return BrokerOrderRef(alpaca_id)

    def cancel(self, ref: BrokerOrderRef) -> None:
        """Cancel an open order."""
        if self._is_mock:
            self._mock_orders.pop(str(ref), None)
            return

        try:
            self._request("DELETE", f"/v2/orders/{ref}")
        except Exception as err:
            logger.warning(f"Failed to cancel order {ref}: {err}")

    def positions(self) -> list[Position]:
        """Fetch current open positions."""
        if self._is_mock:
            return list(self._mock_positions.values())

        res = self._request("GET", "/v2/positions")
        positions_list: list[Position] = []
        now = datetime.now(UTC)

        for p in res:
            qty_int = int(Decimal(p["qty"]))
            avg_entry = Decimal(p["avg_entry_price"])
            unrealized_amt = Decimal(p["unrealized_pl"])
            pos = Position(
                symbol=Symbol(p["symbol"]),
                bucket=BucketId.CORE,
                qty=Quantity(qty_int),
                avg_price=avg_entry,
                opened_ts=now,
                unrealized=Money(unrealized_amt, "USD"),
                realized=Money.zero("USD"),
            )
            positions_list.append(pos)
        return positions_list

    def account(self) -> AccountState:
        """Fetch current account state."""
        now = datetime.now(UTC)
        if self._is_mock:
            return AccountState(
                ts=now,
                total_equity=self._mock_cash,
                cash=self._mock_cash,
                buying_power=self._mock_cash,
                per_bucket_equity={b: Money.zero("USD") for b in BucketId},
            )

        res = self._request("GET", "/v2/account")
        equity = Money(Decimal(res["equity"]), "USD")
        cash = Money(Decimal(res["cash"]), "USD")
        bp = Money(Decimal(res["buying_power"]), "USD")

        per_b = {
            BucketId.CORE: equity * Decimal("0.50"),
            BucketId.SWING: equity * Decimal("0.30"),
            BucketId.MOONSHOT: equity * Decimal("0.15"),
            BucketId.CASH: equity * Decimal("0.05"),
        }

        return AccountState(
            ts=now,
            total_equity=equity,
            cash=cash,
            buying_power=bp,
            per_bucket_equity=per_b,
        )

    def on_fill(self, cb: Callable[[Fill], None]) -> None:
        """Register a callback for fill reports."""
        self._fill_callbacks.append(cb)

    def dispatch_fill(self, fill: Fill) -> None:
        """Notify all registered fill subscribers."""
        for cb in self._fill_callbacks:
            try:
                cb(fill)
            except Exception as err:
                logger.error(f"Error in fill callback: {err}")
