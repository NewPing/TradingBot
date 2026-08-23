"""State persistence and crash recovery for live/paper execution daemon."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from atlas.core.types import (
    BucketId,
    Order,
    OrderStatus,
    OrderType,
    Quantity,
    Side,
    Symbol,
    TimeInForce,
)
from atlas.execution.broker import Broker
from atlas.portfolio.ledger import BucketLedger

logger = logging.getLogger("atlas.runner.recovery")


class CrashRecoveryManager:
    """Handles snapshotting and reconstructing runner state during clean or ungraceful restarts."""

    def __init__(
        self,
        state_file_path: Path | str = "data/runner_state.json",
        db_session: Session | None = None,
    ) -> None:
        self.state_file_path = Path(state_file_path)
        self.db = db_session

    def persist_state(
        self,
        ledger: BucketLedger,
        active_orders: dict[str, Order],
        run_id: str,
        strategy_version_id: str,
    ) -> None:
        """Serialize and save runner state to disk atomically."""
        state = {
            "saved_at": datetime.now(UTC).isoformat(),
            "run_id": run_id,
            "strategy_version_id": strategy_version_id,
            "ledger": ledger.to_dict(),
            "active_orders": {
                oid: {
                    "id": o.id,
                    "run_id": o.run_id,
                    "strategy_version_id": o.strategy_version_id,
                    "bucket": o.bucket.value,
                    "symbol": str(o.symbol),
                    "side": o.side.value,
                    "qty": o.qty,
                    "type": o.type.value,
                    "tif": o.tif.value,
                    "created_ts": o.created_ts.isoformat(),
                    "limit_px": str(o.limit_px) if o.limit_px is not None else None,
                    "stop_px": str(o.stop_px) if o.stop_px is not None else None,
                    "status": o.status.value,
                }
                for oid, o in active_orders.items()
            },
        }

        self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.state_file_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        temp_path.replace(self.state_file_path)
        logger.debug(f"Runner state persisted to {self.state_file_path}")

    def load_state(self) -> dict[str, Any] | None:
        """Load and return persisted runner state if available."""
        if not self.state_file_path.exists():
            return None
        try:
            content = self.state_file_path.read_text(encoding="utf-8")
            data = json.loads(content)
            if isinstance(data, dict):
                return data
            return None
        except Exception as err:
            logger.error(f"Failed to read state file {self.state_file_path}: {err}")
            return None

    def recover(
        self, broker: Broker
    ) -> tuple[BucketLedger, dict[str, Order], str | None, str | None]:
        """Reconstruct ledger, orders, and reconcile with broker."""
        data = self.load_state()
        if not data:
            ledger = BucketLedger()
            return ledger, {}, None, None

        run_id = data.get("run_id")
        strategy_version_id = data.get("strategy_version_id")
        ledger = BucketLedger.from_dict(data["ledger"])

        active_orders: dict[str, Order] = {}
        for oid, o_data in data.get("active_orders", {}).items():
            created_ts = datetime.fromisoformat(o_data["created_ts"])
            if created_ts.tzinfo is None:
                created_ts = created_ts.replace(tzinfo=UTC)
            order = Order(
                id=o_data["id"],
                run_id=o_data["run_id"],
                strategy_version_id=o_data["strategy_version_id"],
                bucket=BucketId(o_data["bucket"]),
                symbol=Symbol(o_data["symbol"]),
                side=Side(o_data["side"]),
                qty=Quantity(o_data["qty"]),
                type=OrderType(o_data["type"]),
                tif=TimeInForce(o_data["tif"]),
                created_ts=created_ts,
                limit_px=None,
                stop_px=None,
                status=OrderStatus(o_data["status"]),
            )
            active_orders[oid] = order

        # Reconciliation check with broker
        try:
            broker_positions = {p.symbol: p.qty for p in broker.positions()}
            ledger_positions = {p.symbol: p.qty for p in ledger.all_positions()}

            for sym, b_qty in broker_positions.items():
                l_qty = ledger_positions.get(sym, 0)
                if b_qty != l_qty:
                    logger.warning(
                        f"Reconciliation divergence for {sym}: broker has {b_qty}, "
                        f"ledger has {l_qty}"
                    )
        except Exception as err:
            logger.warning(f"Could not perform broker reconciliation on recovery: {err}")

        logger.info(
            f"Successfully recovered runner state for run {run_id} ({len(active_orders)} active orders)"
        )
        return ledger, active_orders, run_id, strategy_version_id
