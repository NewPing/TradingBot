"""Shadow Mode execution runner daemon and live market quote divergence tracker (Phase 9)."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from atlas.core.bus import EventBus
from atlas.core.clock import Clock, RealClock
from atlas.core.context import MarketContext
from atlas.core.types import (
    RunMode,
    Side,
    Symbol,
)
from atlas.execution.broker import Broker
from atlas.execution.divergence import DivergenceMonitor, DivergenceTelemetry
from atlas.execution.oms import OrderManager
from atlas.portfolio.ledger import BucketLedger
from atlas.risk.manager import RiskManager
from atlas.runner.health import RunnerHealthMonitor
from atlas.strategies.builder import (
    build_aggregator,
    build_signal_provider,
)
from atlas.strategies.spec import StrategySpec

logger = logging.getLogger("atlas.runner.shadow")


class ShadowRunnerDaemon:
    """Runs autonomous trading strategies in Shadow Mode with real broker quote feeds but zero capital risk."""

    def __init__(
        self,
        strategy_specs: list[StrategySpec],
        broker: Broker,
        risk_manager: RiskManager,
        ledger: BucketLedger | None = None,
        clock: Clock | None = None,
        context_factory: Callable[[datetime], MarketContext] | None = None,
        event_bus: EventBus | None = None,
        db_session: Session | None = None,
        run_id: str | None = None,
    ) -> None:
        self.strategy_specs = strategy_specs
        self.broker = broker
        self.risk = risk_manager
        self.ledger = ledger or BucketLedger()
        self.clock = clock or RealClock()
        self.context_factory = context_factory
        self.bus = event_bus
        self.db = db_session
        self.run_id = run_id or f"run-shadow-{uuid.uuid4().hex[:12]}"
        self.mode = RunMode.SHADOW

        self.divergence_monitor = DivergenceMonitor(session=db_session)
        self.health = RunnerHealthMonitor(event_bus=event_bus)

        self.oms = OrderManager(
            broker=self.broker,
            ledger=self.ledger,
            risk_manager=self.risk,
            event_bus=self.bus,
            db_session=self.db,
        )

    def startup(self) -> None:
        """Initialize shadow runner and start telemetry health monitoring."""
        logger.info(
            "Starting ShadowRunnerDaemon (run_id=%s) monitoring real-time quote feeds...",
            self.run_id,
        )
        self.health.start()

    def execute_shadow_cycle(
        self,
        current_prices: dict[Symbol, Decimal],
        broker_quotes: dict[Symbol, tuple[Decimal, Decimal]] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Execute shadow cycle: generate signals, size positions, compute simulated fills, and log divergence."""
        ts = now or self.clock.now
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)

        quotes = broker_quotes or {}
        recorded_shadow_fills: list[dict[str, Any]] = []

        try:
            # For each active strategy spec, evaluate signals and target allocations
            for spec in self.strategy_specs:
                signal_providers = [
                    build_signal_provider(sig.provider, sig.params) for sig in spec.signals
                ]
                aggregator = build_aggregator(spec)

                composite_signals: dict[Symbol, Any] = {}
                if self.context_factory is not None:
                    ctx = self.context_factory(ts)
                    symbols = ctx.universe()
                    if spec.universe.symbols:
                        target_syms = {Symbol(s) for s in spec.universe.symbols}
                        symbols = [s for s in symbols if s in target_syms]

                    for sym in symbols:
                        latest_bar = ctx.latest(sym)
                        if latest_bar is not None:
                            current_prices[sym] = latest_bar.close

                        sym_signals = []
                        for provider in signal_providers:
                            sig = provider.evaluate(ctx, sym)
                            if sig is not None:
                                sym_signals.append(sig)

                        comp = aggregator.combine(sym_signals, ts, sym)
                        if comp is not None:
                            composite_signals[sym] = comp

                for sym, price in current_prices.items():
                    bid, ask = quotes.get(
                        sym, (price * Decimal("0.9995"), price * Decimal("1.0005"))
                    )
                    mid = (bid + ask) / Decimal("2.0")

                    # Direction based on composite signal if present
                    sig = composite_signals.get(sym)
                    score = sig.score if sig is not None else 0.5
                    side = Side.BUY if score >= 0.0 else Side.SELL
                    sim_fill_price = ask if side == Side.BUY else bid

                    log_entry = self.divergence_monitor.record_shadow_fill(
                        run_id=self.run_id,
                        symbol=sym,
                        side=side,
                        quantity=10,
                        model_price=price,
                        simulated_fill_price=sim_fill_price,
                        broker_bid=bid,
                        broker_ask=ask,
                        broker_mid=mid,
                        quote_latency_ms=Decimal("12.5"),
                        routing_venue="IBKR_PAPER_SHADOW",
                        timestamp=ts,
                    )
                    recorded_shadow_fills.append(
                        {
                            "symbol": sym,
                            "side": side.value,
                            "model_price": float(price),
                            "sim_fill_price": float(sim_fill_price),
                            "slippage_bps": float(log_entry.slippage_bps),
                        }
                    )

            self.health.record_cycle_success(now=ts)
            return {
                "status": "SUCCESS",
                "timestamp": ts.isoformat(),
                "run_id": self.run_id,
                "shadow_fills_count": len(recorded_shadow_fills),
                "shadow_fills": recorded_shadow_fills,
            }
        except Exception as e:
            logger.error("Error in shadow execution cycle: %s", e)
            self.health.record_cycle_error(err=e, now=ts)
            return {
                "status": "ERROR",
                "timestamp": ts.isoformat(),
                "error": str(e),
            }

    def get_telemetry(self) -> DivergenceTelemetry:
        """Get summary divergence and quote latency statistics."""
        return self.divergence_monitor.get_telemetry(run_id=self.run_id)

    def shutdown(self) -> None:
        """Shutdown shadow daemon cleanly."""
        logger.info("ShadowRunnerDaemon (%s) shut down.", self.run_id)
        self.health.stop()
