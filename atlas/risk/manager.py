"""Centralized Risk Manager combining hard limits, kill switches, and emergency controls."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from atlas.core.errors import KillSwitchTriggeredError, RiskLimitExceededError
from atlas.core.money import Money
from atlas.core.types import BucketId, Order, Side, Symbol
from atlas.portfolio.ledger import BucketLedger
from atlas.risk.killswitch import (
    ActiveKillSwitch,
    KillSwitchManager,
    KillSwitchTrigger,
)
from atlas.risk.limits import HardLimitsValidator, RiskCheckResult


class RiskManager:
    """Master centralized risk manager for backtest, paper, and live environments."""

    def __init__(
        self,
        limits_validator: HardLimitsValidator | None = None,
        kill_switch_manager: KillSwitchManager | None = None,
        db_session: Session | None = None,
    ) -> None:
        self.limits = limits_validator or HardLimitsValidator()
        self.kill_switches = kill_switch_manager or KillSwitchManager(db_session=db_session)
        self.order_counts_today: dict[BucketId, int] = dict.fromkeys(BucketId, 0)

    def validate_order(
        self,
        order: Order,
        ledger: BucketLedger,
        current_prices: dict[Symbol, Decimal],
        symbol_sectors: dict[Symbol, str] | None = None,
        symbol_adv: dict[Symbol, Decimal] | None = None,
        symbol_correlations: dict[tuple[Symbol, Symbol], float] | None = None,
        critical_data_symbols: set[Symbol] | None = None,
    ) -> list[RiskCheckResult]:
        """Validate proposed order against kill switch status and §6.3 hard limits."""
        # 1. Kill switch state check
        if order.side == Side.BUY and not self.kill_switches.allows_entries(order.bucket):
            active_reasons = [
                f"{k.trigger.value}: {k.detail}"
                for k in self.kill_switches.active_switches.values()
            ]
            raise KillSwitchTriggeredError(
                f"Order rejected: active kill switch blocks entries in bucket {order.bucket}. "
                f"Triggers: {'; '.join(active_reasons)}"
            )

        # 2. Hard limits validation
        results = self.limits.validate_order(
            order=order,
            ledger=ledger,
            current_prices=current_prices,
            symbol_sectors=symbol_sectors,
            symbol_adv=symbol_adv,
            order_counts_today=self.order_counts_today,
            symbol_correlations=symbol_correlations,
            critical_data_symbols=critical_data_symbols,
        )

        failures = [r for r in results if not r.passed]
        if failures:
            reasons = "; ".join(f"[{f.rule_name}] {f.reason}" for f in failures)
            raise RiskLimitExceededError(f"Order rejected by risk manager: {reasons}")

        if order.side == Side.BUY:
            self.order_counts_today[order.bucket] = self.order_counts_today.get(order.bucket, 0) + 1

        return results

    def on_equity_update(
        self,
        current_equity: Money,
        now: datetime | None = None,
    ) -> list[ActiveKillSwitch]:
        """Process portfolio equity update and evaluate loss/drawdown kill switches."""
        return self.kill_switches.evaluate_equity(current_equity, now=now)

    def emergency_flatten(
        self,
        bucket: BucketId | None = None,
        detail: str = "Manual emergency flatten invoked",
        now: datetime | None = None,
    ) -> ActiveKillSwitch:
        """Trigger emergency manual halt and position flatten."""
        trigger = (
            KillSwitchTrigger.DRAWDOWN_15
            if bucket == BucketId.MOONSHOT
            else KillSwitchTrigger.MANUAL_EMERGENCY
        )
        return self.kill_switches.trigger(
            trigger=trigger,
            detail=detail,
            affected_bucket=bucket,
            now=now,
        )

    def reset_kill_switch(
        self,
        trigger: KillSwitchTrigger,
        resolved_by: str = "operator",
        now: datetime | None = None,
    ) -> bool:
        """Reset an active kill switch."""
        return self.kill_switches.reset(trigger, resolved_by=resolved_by, now=now)

    def get_status(self) -> dict[str, Any]:
        """Return full risk and kill switch operational status."""
        return {
            "is_halted": self.kill_switches.is_triggered(),
            "allows_entries": {b.value: self.kill_switches.allows_entries(b) for b in BucketId},
            "active_switches": [
                {
                    "trigger": s.trigger.value,
                    "action": s.action.value,
                    "detail": s.detail,
                    "triggered_at": s.triggered_at.isoformat(),
                    "affected_bucket": s.affected_bucket.value if s.affected_bucket else None,
                }
                for s in self.kill_switches.active_switches.values()
            ],
            "peak_equity": str(self.kill_switches.peak_equity),
            "session_open_equity": str(self.kill_switches.session_open_equity),
            "daily_order_counts": {b.value: c for b, c in self.order_counts_today.items()},
        }
