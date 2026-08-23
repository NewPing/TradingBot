"""FastAPI router for Risk Management, Kill Switches, and Emergency Controls."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from atlas.api.schemas.risk import (
    ActiveKillSwitchResponse,
    EmergencyFlattenRequest,
    KillSwitchResetRequest,
    RiskStatusResponse,
)
from atlas.data.db import get_db
from atlas.risk.killswitch import KILL_SWITCH_REGISTRY, KillSwitchTrigger
from atlas.risk.manager import RiskManager

router = APIRouter(prefix="/api/v1/risk", tags=["Risk Management"])

# Global runtime risk manager instance
_global_risk_manager: RiskManager | None = None


def get_risk_manager(db: Annotated[Session, Depends(get_db)]) -> RiskManager:
    global _global_risk_manager
    if _global_risk_manager is None:
        _global_risk_manager = RiskManager(db_session=db)
    else:
        _global_risk_manager.kill_switches.db = db
    return _global_risk_manager


@router.get("/status", response_model=RiskStatusResponse)
def get_risk_status(
    risk: Annotated[RiskManager, Depends(get_risk_manager)],
) -> RiskStatusResponse:
    """Get active risk status, tripped kill switches, and entry permissions."""
    active_list: list[ActiveKillSwitchResponse] = []
    for s in risk.kill_switches.active_switches.values():
        cfg = KILL_SWITCH_REGISTRY.get(s.trigger)
        reset_type = cfg.reset_type.value if cfg else "HUMAN"
        active_list.append(
            ActiveKillSwitchResponse(
                trigger=s.trigger.value,
                action=s.action.value,
                detail=s.detail,
                triggered_at=s.triggered_at,
                affected_bucket=s.affected_bucket.value if s.affected_bucket else None,
                reset_type=reset_type,
            )
        )

    allows_entries = {
        b.value: risk.kill_switches.allows_entries(b) for b in risk.order_counts_today
    }

    return RiskStatusResponse(
        is_halted=risk.kill_switches.is_triggered(),
        active_switches=active_list,
        allows_entries=allows_entries,
        daily_order_counts={b.value: c for b, c in risk.order_counts_today.items()},
        peak_equity=float(risk.kill_switches.peak_equity),
        session_open_equity=float(risk.kill_switches.session_open_equity),
    )


@router.post("/reset", response_model=RiskStatusResponse)
def reset_kill_switch(
    payload: KillSwitchResetRequest,
    risk: Annotated[RiskManager, Depends(get_risk_manager)],
) -> RiskStatusResponse:
    """Manually reset a tripped kill switch."""
    try:
        trigger_enum = KillSwitchTrigger(payload.trigger)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown kill switch trigger: {payload.trigger}",
        ) from exc

    success = risk.reset_kill_switch(trigger_enum, resolved_by=payload.resolved_by)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Kill switch '{payload.trigger}' is not currently active",
        )

    return get_risk_status(risk)


@router.post("/emergency-flatten", response_model=RiskStatusResponse)
def emergency_flatten(
    payload: EmergencyFlattenRequest,
    risk: Annotated[RiskManager, Depends(get_risk_manager)],
) -> RiskStatusResponse:
    """Operator emergency halt: triggers full-stop or bucket flatten."""
    from atlas.core.types import BucketId

    bucket_enum = None
    if payload.bucket:
        try:
            bucket_enum = BucketId(payload.bucket)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid bucket: {payload.bucket}",
            ) from exc

    risk.emergency_flatten(bucket=bucket_enum, detail=payload.reason)
    return get_risk_status(risk)
