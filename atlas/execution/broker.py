"""Broker protocol and interface definitions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from atlas.core.types import AccountState, BrokerOrderRef, Fill, Order, Position


class Broker(Protocol):
    """Protocol implemented by all broker adapters (SimBroker, AlpacaPaperBroker, IBKRBroker)."""

    def submit(self, order: Order) -> BrokerOrderRef:
        """Submit an order for execution."""
        ...

    def cancel(self, ref: BrokerOrderRef) -> None:
        """Cancel a pending order."""
        ...

    def positions(self) -> list[Position]:
        """Return list of currently open positions."""
        ...

    def account(self) -> AccountState:
        """Return current account balances and total equity."""
        ...

    def on_fill(self, cb: Callable[[Fill], None]) -> None:
        """Register a callback to receive fill reports."""
        ...

    def is_healthy(self) -> bool:
        """Return True if connection to venue/broker is healthy."""
        ...
