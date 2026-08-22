"""Clock abstractions for simulation and live execution parity."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    """Protocol for time sources in ATLAS."""

    @property
    def now(self) -> datetime:
        """Current time (tz-aware UTC)."""
        ...


class RealClock:
    """Real-time clock tracking actual wall-clock UTC time."""

    @property
    def now(self) -> datetime:
        return datetime.now(UTC)


class SimClock:
    """Deterministic simulation clock manipulated by backtest event loop."""

    def __init__(self, initial_time: datetime) -> None:
        if initial_time.tzinfo is None:
            raise ValueError("SimClock initial_time must be timezone-aware UTC")
        self._current_time = initial_time

    @property
    def now(self) -> datetime:
        return self._current_time

    def set(self, ts: datetime) -> None:
        """Set the simulation time. Must be tz-aware UTC."""
        if ts.tzinfo is None:
            raise ValueError("Simulation timestamp must be timezone-aware UTC")
        self._current_time = ts

    def advance(self, delta: timedelta) -> None:
        """Advance simulation time by delta."""
        self._current_time += delta
