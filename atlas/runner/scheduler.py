"""Job scheduler for periodic market hours execution and maintenance."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from atlas.core.calendar import is_trading_day
from atlas.core.types import Symbol
from atlas.runner.live import LiveRunnerDaemon

logger = logging.getLogger("atlas.runner.scheduler")


class RunnerScheduler:
    """Coordinates periodic job triggers with NYSE calendar hours."""

    def __init__(
        self,
        daemon: LiveRunnerDaemon,
        poll_interval_seconds: int = 60,
    ) -> None:
        self.daemon = daemon
        self.poll_interval_seconds = poll_interval_seconds
        self._is_active = False

    def tick(
        self,
        current_prices: dict[Symbol, Decimal],
        now: datetime | None = None,
        symbol_sectors: dict[Symbol, str] | None = None,
        symbol_adv: dict[Symbol, Decimal] | None = None,
        symbol_correlations: dict[tuple[Symbol, Symbol], float] | None = None,
    ) -> None:
        """Run a single scheduler evaluation tick."""
        ts = now or datetime.now(UTC)
        if not is_trading_day(ts):
            logger.debug(f"Date {ts.date()} is not a trading day; skipping cycle.")
            return

        # Execute decision cycle
        self.daemon.execute_cycle(
            current_prices=current_prices,
            now=ts,
            symbol_sectors=symbol_sectors,
            symbol_adv=symbol_adv,
            symbol_correlations=symbol_correlations,
        )
