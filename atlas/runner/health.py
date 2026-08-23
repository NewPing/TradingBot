"""Runner health monitoring, heartbeat tracking, and operational alerting."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from atlas.core.bus import Event, EventBus

logger = logging.getLogger("atlas.runner.health")


@dataclass
class HeartbeatStatus:
    is_running: bool
    last_cycle_ts: datetime | None
    uptime_seconds: float
    total_cycles: int
    consecutive_errors: int
    last_error: str | None


class RunnerHealthMonitor:
    """Monitors live runner loop execution health and dispatches operational alerts."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self.bus = event_bus
        self.start_time: datetime | None = None
        self.is_running: bool = False
        self.last_cycle_ts: datetime | None = None
        self.total_cycles: int = 0
        self.consecutive_errors: int = 0
        self.last_error: str | None = None
        self.alerts_log: list[dict[str, Any]] = []

    def start(self) -> None:
        self.start_time = datetime.now(UTC)
        self.is_running = True
        self.record_alert("INFO", "Runner daemon started")

    def stop(self) -> None:
        self.is_running = False
        self.record_alert("INFO", "Runner daemon stopped")

    def record_cycle_success(self, now: datetime | None = None) -> None:
        self.last_cycle_ts = now or datetime.now(UTC)
        self.total_cycles += 1
        self.consecutive_errors = 0

    def record_cycle_error(self, err: Exception, now: datetime | None = None) -> None:
        self.consecutive_errors += 1
        self.last_error = str(err)
        self.record_alert(
            "ERROR",
            f"Runner cycle error ({self.consecutive_errors} consecutive): {err}",
            now=now,
        )

    def record_alert(
        self, severity: str, message: str, now: datetime | None = None
    ) -> dict[str, Any]:
        ts = now or datetime.now(UTC)
        alert = {
            "ts": ts.isoformat(),
            "severity": severity,
            "message": message,
        }
        self.alerts_log.append(alert)
        if len(self.alerts_log) > 100:
            self.alerts_log.pop(0)

        logger.log(
            logging.ERROR if severity == "ERROR" else logging.INFO,
            f"[{severity}] {message}",
        )

        if self.bus is not None:
            self.bus.emit(
                Event(
                    topic="runner.alert",
                    data=alert,
                )
            )

        return alert

    def status(self) -> HeartbeatStatus:
        uptime = 0.0
        if self.start_time and self.is_running:
            uptime = (datetime.now(UTC) - self.start_time).total_seconds()

        return HeartbeatStatus(
            is_running=self.is_running,
            last_cycle_ts=self.last_cycle_ts,
            uptime_seconds=uptime,
            total_cycles=self.total_cycles,
            consecutive_errors=self.consecutive_errors,
            last_error=self.last_error,
        )
