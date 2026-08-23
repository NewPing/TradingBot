"""Base SignalProvider protocol and base implementations."""

from __future__ import annotations

from typing import Protocol

from atlas.core.context import MarketContext
from atlas.core.types import Signal, SignalLayer, Symbol


class SignalProvider(Protocol):
    """Protocol implemented by all alpha and risk signal generators."""

    @property
    def id(self) -> str:
        """Unique identifier for this provider."""
        ...

    @property
    def version(self) -> str:
        """Semver string for this provider version."""
        ...

    @property
    def layer(self) -> SignalLayer:
        """Signal layer hierarchy level (L1..L4)."""
        ...

    def warmup_bars(self) -> int:
        """Minimum historical bars required to compute a valid signal."""
        ...

    def evaluate(self, ctx: MarketContext, symbol: Symbol) -> Signal | None:
        """Generate a point-in-time alpha signal for symbol.

        Must only access ctx at or before ctx.now.
        """
        ...
