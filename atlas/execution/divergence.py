"""Real-time execution slippage and shadow divergence telemetry monitor (Phase 9)."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from atlas.core.types import Side, Symbol
from atlas.data.models import ShadowExecutionLog

logger = logging.getLogger("atlas.execution.divergence")


@dataclass
class DivergenceTelemetry:
    """Statistical summary of execution slippage and quote delay divergence."""

    total_shadow_trades: int = 0
    mean_slippage_bps: Decimal = Decimal("0.00")
    max_slippage_bps: Decimal = Decimal("0.00")
    p95_slippage_bps: Decimal = Decimal("0.00")
    mean_quote_latency_ms: Decimal = Decimal("0.00")
    p95_quote_latency_ms: Decimal = Decimal("0.00")
    positive_slippage_trades: int = 0  # Fills worse than decision price
    zero_or_better_trades: int = 0  # Fills equal or price improved
    sample_records: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_shadow_trades": self.total_shadow_trades,
            "mean_slippage_bps": float(self.mean_slippage_bps),
            "max_slippage_bps": float(self.max_slippage_bps),
            "p95_slippage_bps": float(self.p95_slippage_bps),
            "mean_quote_latency_ms": float(self.mean_quote_latency_ms),
            "p95_quote_latency_ms": float(self.p95_quote_latency_ms),
            "positive_slippage_trades": self.positive_slippage_trades,
            "zero_or_better_trades": self.zero_or_better_trades,
            "sample_records": self.sample_records,
        }


class DivergenceMonitor:
    """Monitors and records real-time divergence between theoretical model prices and broker quotes."""

    def __init__(self, session: Session | None = None) -> None:
        self.session = session
        self._memory_logs: list[ShadowExecutionLog] = []

    def record_shadow_fill(
        self,
        run_id: str,
        symbol: Symbol | str,
        side: Side | str,
        quantity: int,
        model_price: Decimal,
        simulated_fill_price: Decimal,
        broker_bid: Decimal | None = None,
        broker_ask: Decimal | None = None,
        broker_mid: Decimal | None = None,
        quote_latency_ms: Decimal = Decimal("0.0"),
        routing_venue: str = "SHADOW_SIM",
        timestamp: datetime | None = None,
    ) -> ShadowExecutionLog:
        """Log a shadow execution record with slippage and latency metrics."""
        ts = timestamp or datetime.now(UTC)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)

        side_str = side.value if isinstance(side, Side) else str(side)
        sym_str = str(symbol)

        # Calculate slippage in Basis Points (bps = 1/100th of 1%)
        # Slippage is (fill - model) / model * 10,000 for BUY, or (model - fill) / model * 10,000 for SELL
        if model_price > Decimal("0"):
            if side_str == "BUY":
                slippage_bps = ((simulated_fill_price - model_price) / model_price) * Decimal(
                    "10000.0"
                )
            else:
                slippage_bps = ((model_price - simulated_fill_price) / model_price) * Decimal(
                    "10000.0"
                )
        else:
            slippage_bps = Decimal("0.0")

        slippage_bps = slippage_bps.quantize(Decimal("0.0001"), ROUND_HALF_UP)
        latency = quote_latency_ms.quantize(Decimal("0.01"), ROUND_HALF_UP)

        log_id = f"shd_{uuid.uuid4().hex[:12]}"
        log_entry = ShadowExecutionLog(
            id=log_id,
            run_id=run_id,
            symbol=sym_str,
            timestamp=ts,
            side=side_str,
            quantity=quantity,
            model_price_usd=model_price.quantize(Decimal("0.0001"), ROUND_HALF_UP),
            broker_bid_usd=broker_bid.quantize(Decimal("0.0001"), ROUND_HALF_UP)
            if broker_bid
            else None,
            broker_ask_usd=broker_ask.quantize(Decimal("0.0001"), ROUND_HALF_UP)
            if broker_ask
            else None,
            broker_mid_usd=broker_mid.quantize(Decimal("0.0001"), ROUND_HALF_UP)
            if broker_mid
            else None,
            simulated_fill_price_usd=simulated_fill_price.quantize(
                Decimal("0.0001"), ROUND_HALF_UP
            ),
            slippage_bps=slippage_bps,
            quote_latency_ms=latency,
            routing_venue=routing_venue,
            created_at=datetime.now(UTC),
        )

        if self.session is not None:
            self.session.add(log_entry)
            self.session.commit()
        else:
            self._memory_logs.append(log_entry)

        return log_entry

    def get_telemetry(self, run_id: str | None = None, limit: int = 50) -> DivergenceTelemetry:
        """Compute aggregate divergence metrics and fetch recent sample logs."""
        logs: list[ShadowExecutionLog]
        if self.session is not None:
            stmt = select(ShadowExecutionLog)
            if run_id:
                stmt = stmt.where(ShadowExecutionLog.run_id == run_id)
            stmt = stmt.order_by(desc(ShadowExecutionLog.timestamp)).limit(limit)
            logs = list(self.session.execute(stmt).scalars().all())
        else:
            filtered = [
                item for item in self._memory_logs if run_id is None or item.run_id == run_id
            ]
            logs = sorted(filtered, key=lambda item: item.timestamp, reverse=True)[:limit]

        if not logs:
            return DivergenceTelemetry()

        signed_slippages = [Decimal(str(entry.slippage_bps)) for entry in logs]
        latencies = [Decimal(str(entry.quote_latency_ms)) for entry in logs]

        sorted_slip = sorted(signed_slippages)
        sorted_lat = sorted(latencies)

        mean_slip = sum(signed_slippages, Decimal("0.0")) / Decimal(len(signed_slippages))
        max_slip = max(signed_slippages)
        p95_idx = int(len(sorted_slip) * 0.95)
        p95_slip = sorted_slip[min(p95_idx, len(sorted_slip) - 1)]

        mean_lat = sum(latencies, Decimal("0.0")) / Decimal(len(latencies))
        p95_lat = sorted_lat[min(p95_idx, len(sorted_lat) - 1)]

        pos_slip_count = sum(
            1 for entry in logs if Decimal(str(entry.slippage_bps)) > Decimal("0.0")
        )
        zero_or_better = len(logs) - pos_slip_count

        sample_records = [
            {
                "id": entry.id,
                "run_id": entry.run_id,
                "symbol": entry.symbol,
                "timestamp": entry.timestamp.isoformat()
                if hasattr(entry.timestamp, "isoformat")
                else str(entry.timestamp),
                "side": entry.side,
                "quantity": entry.quantity,
                "model_price_usd": float(entry.model_price_usd),
                "simulated_fill_price_usd": float(entry.simulated_fill_price_usd),
                "slippage_bps": float(entry.slippage_bps),
                "quote_latency_ms": float(entry.quote_latency_ms),
                "routing_venue": entry.routing_venue,
            }
            for entry in logs[:20]
        ]

        return DivergenceTelemetry(
            total_shadow_trades=len(logs),
            mean_slippage_bps=mean_slip.quantize(Decimal("0.01"), ROUND_HALF_UP),
            max_slippage_bps=max_slip.quantize(Decimal("0.01"), ROUND_HALF_UP),
            p95_slippage_bps=p95_slip.quantize(Decimal("0.01"), ROUND_HALF_UP),
            mean_quote_latency_ms=mean_lat.quantize(Decimal("0.01"), ROUND_HALF_UP),
            p95_quote_latency_ms=p95_lat.quantize(Decimal("0.01"), ROUND_HALF_UP),
            positive_slippage_trades=pos_slip_count,
            zero_or_better_trades=zero_or_better,
            sample_records=sample_records,
        )
