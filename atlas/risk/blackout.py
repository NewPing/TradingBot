"""Earnings calendar blackout risk guard.

Prevents new position entries in high-beta/MOONSHOT or SWING buckets within N days
prior to scheduled earnings releases to eliminate binary event risk.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from atlas.core.context import MarketContext
from atlas.core.types import BucketId, Order, Side, Symbol
from atlas.risk.limits import RiskCheckResult


class EarningsBlackoutGuard:
    """Blocks entry orders in symbols with scheduled earnings announcements."""

    def __init__(
        self,
        blackout_days_pre: int = 2,
        protected_buckets: Sequence[BucketId] | None = None,
    ) -> None:
        self.blackout_days_pre = blackout_days_pre
        self.protected_buckets = set(protected_buckets or [BucketId.MOONSHOT, BucketId.SWING])

    def is_in_blackout(
        self,
        ctx: MarketContext,
        symbol: Symbol,
    ) -> tuple[bool, datetime | None]:
        """Check if symbol has an upcoming earnings event within blackout window."""
        upcoming = ctx.upcoming_earnings(symbol, lookahead_days=self.blackout_days_pre)
        if upcoming is not None:
            return True, upcoming
        return False, None

    def validate_order(
        self,
        order: Order,
        ctx: MarketContext,
    ) -> RiskCheckResult:
        """Evaluate order against earnings blackout window."""
        # Exits/SELL orders are always allowed during blackout to de-risk
        if order.side == Side.SELL:
            return RiskCheckResult(
                passed=True,
                rule_name="EARNINGS_BLACKOUT_GUARD",
                reason="Sell order allowed to reduce risk",
            )

        if order.bucket in self.protected_buckets:
            in_blackout, earnings_date = self.is_in_blackout(ctx, order.symbol)
            if in_blackout and earnings_date is not None:
                return RiskCheckResult(
                    passed=False,
                    rule_name="EARNINGS_BLACKOUT_ACTIVE",
                    reason=(
                        f"New entry blocked for {order.symbol} in bucket {order.bucket}: "
                        f"Earnings announcement scheduled within {self.blackout_days_pre} days ({earnings_date.strftime('%Y-%m-%d')})"
                    ),
                )

        return RiskCheckResult(passed=True, rule_name="EARNINGS_BLACKOUT_GUARD")
