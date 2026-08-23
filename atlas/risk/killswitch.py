"""Kill switches and emergency circuit breaker controls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.core.money import Money
from atlas.core.types import BucketId
from atlas.data.models import KillSwitchEventRecord


class KillSwitchTrigger(StrEnum):
    DAILY_LOSS = "DAILY_LOSS"
    ROLLING_5D_LOSS = "ROLLING_5D_LOSS"
    DRAWDOWN_15 = "DRAWDOWN_15"
    DRAWDOWN_25 = "DRAWDOWN_25"
    DATA_STALENESS = "DATA_STALENESS"
    BROKER_DISCONNECT = "BROKER_DISCONNECT"
    ORDER_REJECT_RATE = "ORDER_REJECT_RATE"
    LIVE_SHADOW_DIVERGENCE = "LIVE_SHADOW_DIVERGENCE"
    UNHANDLED_EXCEPTION = "UNHANDLED_EXCEPTION"
    MANUAL_EMERGENCY = "MANUAL_EMERGENCY"


class KillSwitchAction(StrEnum):
    HALT_ENTRIES = "HALT_ENTRIES"
    HALT_ALL_ENTRIES = "HALT_ALL_ENTRIES"
    FLATTEN_MOONSHOT = "FLATTEN_MOONSHOT"
    FLATTEN_ALL_FULL_STOP = "FLATTEN_ALL_FULL_STOP"
    CANCEL_WORKING_ORDERS = "CANCEL_WORKING_ORDERS"
    HALT_BUCKET = "HALT_BUCKET"


class ResetType(StrEnum):
    AUTOMATIC_NEXT_SESSION = "AUTOMATIC_NEXT_SESSION"
    AUTOMATIC_ON_RECOVERY = "AUTOMATIC_ON_RECOVERY"
    HUMAN = "HUMAN"
    HUMAN_POST_MORTEM = "HUMAN_POST_MORTEM"


@dataclass(frozen=True, slots=True)
class KillSwitchConfig:
    trigger: KillSwitchTrigger
    action: KillSwitchAction
    reset_type: ResetType
    threshold_description: str


KILL_SWITCH_REGISTRY: dict[KillSwitchTrigger, KillSwitchConfig] = {
    KillSwitchTrigger.DAILY_LOSS: KillSwitchConfig(
        trigger=KillSwitchTrigger.DAILY_LOSS,
        action=KillSwitchAction.HALT_ENTRIES,
        reset_type=ResetType.AUTOMATIC_NEXT_SESSION,
        threshold_description="-2% of total equity daily loss",
    ),
    KillSwitchTrigger.ROLLING_5D_LOSS: KillSwitchConfig(
        trigger=KillSwitchTrigger.ROLLING_5D_LOSS,
        action=KillSwitchAction.HALT_ALL_ENTRIES,
        reset_type=ResetType.HUMAN,
        threshold_description="-5% rolling 5-day loss",
    ),
    KillSwitchTrigger.DRAWDOWN_15: KillSwitchConfig(
        trigger=KillSwitchTrigger.DRAWDOWN_15,
        action=KillSwitchAction.FLATTEN_MOONSHOT,
        reset_type=ResetType.HUMAN,
        threshold_description="-15% drawdown from peak equity",
    ),
    KillSwitchTrigger.DRAWDOWN_25: KillSwitchConfig(
        trigger=KillSwitchTrigger.DRAWDOWN_25,
        action=KillSwitchAction.FLATTEN_ALL_FULL_STOP,
        reset_type=ResetType.HUMAN_POST_MORTEM,
        threshold_description="-25% drawdown from peak equity",
    ),
    KillSwitchTrigger.DATA_STALENESS: KillSwitchConfig(
        trigger=KillSwitchTrigger.DATA_STALENESS,
        action=KillSwitchAction.HALT_ENTRIES,
        reset_type=ResetType.AUTOMATIC_ON_RECOVERY,
        threshold_description="> 2 expected bars missing or stale",
    ),
    KillSwitchTrigger.BROKER_DISCONNECT: KillSwitchConfig(
        trigger=KillSwitchTrigger.BROKER_DISCONNECT,
        action=KillSwitchAction.CANCEL_WORKING_ORDERS,
        reset_type=ResetType.AUTOMATIC_ON_RECOVERY,
        threshold_description="Broker connection lost for > 60 seconds",
    ),
    KillSwitchTrigger.ORDER_REJECT_RATE: KillSwitchConfig(
        trigger=KillSwitchTrigger.ORDER_REJECT_RATE,
        action=KillSwitchAction.HALT_BUCKET,
        reset_type=ResetType.HUMAN,
        threshold_description="> 20% order rejection rate over trailing 10 orders",
    ),
    KillSwitchTrigger.LIVE_SHADOW_DIVERGENCE: KillSwitchConfig(
        trigger=KillSwitchTrigger.LIVE_SHADOW_DIVERGENCE,
        action=KillSwitchAction.HALT_ALL_ENTRIES,
        reset_type=ResetType.HUMAN,
        threshold_description="> 0.5% equity divergence vs shadow over 5 days",
    ),
    KillSwitchTrigger.UNHANDLED_EXCEPTION: KillSwitchConfig(
        trigger=KillSwitchTrigger.UNHANDLED_EXCEPTION,
        action=KillSwitchAction.FLATTEN_ALL_FULL_STOP,
        reset_type=ResetType.HUMAN,
        threshold_description="Unhandled loop exception encountered",
    ),
    KillSwitchTrigger.MANUAL_EMERGENCY: KillSwitchConfig(
        trigger=KillSwitchTrigger.MANUAL_EMERGENCY,
        action=KillSwitchAction.FLATTEN_ALL_FULL_STOP,
        reset_type=ResetType.HUMAN,
        threshold_description="Manual emergency operator halt",
    ),
}


@dataclass
class ActiveKillSwitch:
    trigger: KillSwitchTrigger
    action: KillSwitchAction
    detail: str
    triggered_at: datetime
    affected_bucket: BucketId | None = None


class KillSwitchManager:
    """Manages trigger monitoring, active kill states, and operator resets."""

    def __init__(self, db_session: Session | None = None) -> None:
        self.db = db_session
        self.active_switches: dict[KillSwitchTrigger, ActiveKillSwitch] = {}
        self.peak_equity: Decimal = Decimal("0")
        self.session_open_equity: Decimal = Decimal("0")
        self.rolling_equity_history: list[tuple[datetime, Decimal]] = []
        self.rolling_session_equities: list[Decimal] = []
        self.trailing_order_statuses: list[bool] = []  # True = filled/accepted, False = rejected
        self.last_broker_heartbeat: datetime | None = None
        self.stale_bar_count: int = 0

    def trigger(
        self,
        trigger: KillSwitchTrigger,
        detail: str,
        affected_bucket: BucketId | None = None,
        now: datetime | None = None,
    ) -> ActiveKillSwitch:
        """Trigger a kill switch and record audit log."""
        ts = now or datetime.now(UTC)
        cfg = KILL_SWITCH_REGISTRY[trigger]
        active = ActiveKillSwitch(
            trigger=trigger,
            action=cfg.action,
            detail=detail,
            triggered_at=ts,
            affected_bucket=affected_bucket,
        )
        self.active_switches[trigger] = active

        if self.db is not None:
            record = KillSwitchEventRecord(
                ts=ts,
                trigger=trigger.value,
                action=cfg.action.value,
                detail=detail,
                is_active=True,
                auto_resolved=False,
            )
            self.db.add(record)
            self.db.commit()

        return active

    def reset(
        self,
        trigger: KillSwitchTrigger,
        resolved_by: str = "operator",
        now: datetime | None = None,
    ) -> bool:
        """Reset an active kill switch."""
        if trigger not in self.active_switches:
            return False

        ts = now or datetime.now(UTC)
        del self.active_switches[trigger]

        if self.db is not None:
            stmt = (
                select(KillSwitchEventRecord)
                .where(KillSwitchEventRecord.trigger == trigger.value)
                .where(KillSwitchEventRecord.is_active.is_(True))
            )
            records = self.db.execute(stmt).scalars().all()
            for rec in records:
                rec.is_active = False
                rec.resolved_by = resolved_by
                rec.resolved_at = ts
            self.db.commit()

        return True

    def is_triggered(self) -> bool:
        """Return True if any kill switch is currently active."""
        return len(self.active_switches) > 0

    def allows_entries(self, bucket: BucketId | None = None) -> bool:
        """Check if new position entries are allowed."""
        for active in self.active_switches.values():
            if active.action in (
                KillSwitchAction.HALT_ENTRIES,
                KillSwitchAction.HALT_ALL_ENTRIES,
                KillSwitchAction.FLATTEN_ALL_FULL_STOP,
                KillSwitchAction.FLATTEN_MOONSHOT,
            ):
                if (
                    active.action == KillSwitchAction.FLATTEN_MOONSHOT
                    and bucket != BucketId.MOONSHOT
                ):
                    continue
                return False
            if active.action == KillSwitchAction.HALT_BUCKET and (
                bucket is None or active.affected_bucket == bucket
            ):
                return False
        return True

    def requires_flatten(self) -> tuple[bool, set[BucketId]]:
        """Return (requires_flatten, set_of_buckets_to_flatten)."""
        buckets_to_flatten: set[BucketId] = set()
        for active in self.active_switches.values():
            if active.action == KillSwitchAction.FLATTEN_ALL_FULL_STOP:
                return True, {BucketId.CORE, BucketId.SWING, BucketId.MOONSHOT}
            if active.action == KillSwitchAction.FLATTEN_MOONSHOT:
                buckets_to_flatten.add(BucketId.MOONSHOT)
        return len(buckets_to_flatten) > 0, buckets_to_flatten

    def evaluate_equity(
        self,
        current_equity: Money,
        now: datetime | None = None,
    ) -> list[ActiveKillSwitch]:
        """Evaluate portfolio equity against loss limits and drawdown thresholds."""
        ts = now or datetime.now(UTC)
        triggered: list[ActiveKillSwitch] = []
        eq_amt = current_equity.amount

        if eq_amt <= Decimal("0"):
            return triggered

        if self.peak_equity == Decimal("0") or eq_amt > self.peak_equity:
            self.peak_equity = eq_amt

        if self.session_open_equity == Decimal("0"):
            self.session_open_equity = eq_amt

        # 1. Daily loss threshold (-2%)
        daily_return = (eq_amt - self.session_open_equity) / self.session_open_equity
        if daily_return <= Decimal("-0.02"):
            triggered.append(
                self.trigger(
                    KillSwitchTrigger.DAILY_LOSS,
                    f"Daily loss of {daily_return:.2%} breached -2.00% limit",
                    now=ts,
                )
            )

        # 2. Drawdown thresholds (-15%, -25%)
        drawdown = (eq_amt - self.peak_equity) / self.peak_equity
        if drawdown <= Decimal("-0.25"):
            triggered.append(
                self.trigger(
                    KillSwitchTrigger.DRAWDOWN_25,
                    f"Peak drawdown {drawdown:.2%} breached -25.00% catastrophic limit",
                    now=ts,
                )
            )
        elif drawdown <= Decimal("-0.15"):
            triggered.append(
                self.trigger(
                    KillSwitchTrigger.DRAWDOWN_15,
                    f"Peak drawdown {drawdown:.2%} breached -15.00% limit",
                    now=ts,
                )
            )

        # Track history for rolling 5-session loss
        self.rolling_equity_history.append((ts, eq_amt))
        if not self.rolling_session_equities:
            self.rolling_session_equities.append(self.session_open_equity)

        oldest_eq = self.rolling_session_equities[0]
        if oldest_eq > Decimal("0"):
            rolling_ret = (eq_amt - oldest_eq) / oldest_eq
            if rolling_ret <= Decimal("-0.05"):
                triggered.append(
                    self.trigger(
                        KillSwitchTrigger.ROLLING_5D_LOSS,
                        f"Rolling 5-day loss {rolling_ret:.2%} breached -5.00% limit",
                        now=ts,
                    )
                )

        return triggered

    def record_order_result(
        self, success: bool, bucket: BucketId, now: datetime | None = None
    ) -> ActiveKillSwitch | None:
        """Record order acceptance or rejection for reject rate circuit breaker."""
        self.trailing_order_statuses.append(success)
        if len(self.trailing_order_statuses) > 10:
            self.trailing_order_statuses.pop(0)

        if len(self.trailing_order_statuses) == 10:
            failures = sum(1 for s in self.trailing_order_statuses if not s)
            reject_rate = failures / 10.0
            if reject_rate > 0.20:
                return self.trigger(
                    KillSwitchTrigger.ORDER_REJECT_RATE,
                    f"Order reject rate {reject_rate:.1%} over 10 orders exceeded 20%",
                    affected_bucket=bucket,
                    now=now,
                )
        return None

    def record_broker_heartbeat(self, now: datetime | None = None) -> None:
        """Update last seen broker heartbeat timestamp."""
        self.last_broker_heartbeat = now or datetime.now(UTC)
        if KillSwitchTrigger.BROKER_DISCONNECT in self.active_switches:
            self.reset(KillSwitchTrigger.BROKER_DISCONNECT, resolved_by="auto_heartbeat", now=now)

    def check_broker_connection(
        self, now: datetime | None = None, timeout_seconds: int = 60
    ) -> ActiveKillSwitch | None:
        """Check if broker heartbeat is stale beyond 60s."""
        ts = now or datetime.now(UTC)
        if self.last_broker_heartbeat is not None:
            elapsed = (ts - self.last_broker_heartbeat).total_seconds()
            if elapsed > timeout_seconds:
                return self.trigger(
                    KillSwitchTrigger.BROKER_DISCONNECT,
                    f"Broker disconnect: no heartbeat for {int(elapsed)}s (> {timeout_seconds}s)",
                    now=ts,
                )
        return None

    def record_data_bars(
        self, missing_bars_count: int, now: datetime | None = None
    ) -> ActiveKillSwitch | None:
        """Check for stale market data feed."""
        self.stale_bar_count = missing_bars_count
        if missing_bars_count > 2:
            return self.trigger(
                KillSwitchTrigger.DATA_STALENESS,
                f"Data staleness: {missing_bars_count} expected bars missing (> 2)",
                now=now,
            )
        elif missing_bars_count == 0 and KillSwitchTrigger.DATA_STALENESS in self.active_switches:
            self.reset(KillSwitchTrigger.DATA_STALENESS, resolved_by="auto_recovery", now=now)
        return None

    def new_session(self, open_equity: Decimal) -> None:
        """Reset session-level daily loss metrics on market open."""
        self.session_open_equity = open_equity
        if open_equity > Decimal("0"):
            self.rolling_session_equities.append(open_equity)
            if len(self.rolling_session_equities) > 5:
                self.rolling_session_equities.pop(0)
        # Auto-reset daily loss on new session
        if KillSwitchTrigger.DAILY_LOSS in self.active_switches:
            self.reset(KillSwitchTrigger.DAILY_LOSS, resolved_by="session_roll")
