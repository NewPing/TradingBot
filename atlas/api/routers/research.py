"""FastAPI router for Phase 8: The Autonomous Research Loop and Strategy Discovery."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.api.schemas.research import (
    CandidateDecisionRequest,
    CreateSweepRequest,
    GenerateHypothesisRequest,
    HoldoutUnlockRequest,
    ResearchDaemonStatus,
    ResearchHypothesisSchema,
    ResearchReportSchema,
    ResearchSweepSchema,
)
from atlas.data.db import get_db, get_session_factory
from atlas.data.models import (
    ResearchHypothesis,
    ResearchReport,
    ResearchSweep,
)
from atlas.research.daemon import ResearchDaemon
from atlas.research.holdout import HoldoutGuard
from atlas.research.hypothesis import HypothesisGenerator
from atlas.research.sweep import SweepEngine
from atlas.strategies.spec import StrategySpec

router = APIRouter(prefix="/api/v1/research", tags=["research"])

# Singleton daemon instance
_daemon_instance: ResearchDaemon | None = None


def get_research_daemon() -> ResearchDaemon:
    """Retrieve or initialize the research daemon singleton."""
    global _daemon_instance
    if _daemon_instance is None:
        _daemon_instance = ResearchDaemon(session_factory=get_session_factory())
    return _daemon_instance


@router.get("/status", response_model=ResearchDaemonStatus)
def get_status(daemon: ResearchDaemon = Depends(get_research_daemon)) -> Any:
    """Get research daemon telemetry, active workers, and trial budget status."""
    return daemon.get_status()


@router.post("/daemon/start")
async def start_daemon(daemon: ResearchDaemon = Depends(get_research_daemon)) -> dict[str, str]:
    """Start the autonomous research background loop."""
    await daemon.start()
    return {"status": "Research daemon started"}


@router.post("/daemon/stop")
async def stop_daemon(daemon: ResearchDaemon = Depends(get_research_daemon)) -> dict[str, str]:
    """Stop the autonomous research background loop."""
    await daemon.stop()
    return {"status": "Research daemon stopped"}


@router.post("/daemon/step")
def step_daemon(daemon: ResearchDaemon = Depends(get_research_daemon)) -> dict[str, Any]:
    """Execute a single research loop cycle synchronously."""
    return daemon.run_iteration_sync()


@router.get("/hypotheses", response_model=list[ResearchHypothesisSchema])
def list_hypotheses(
    family: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> Any:
    """List generated research hypotheses."""
    stmt = select(ResearchHypothesis).order_by(ResearchHypothesis.created_at.desc())
    if family:
        stmt = stmt.where(ResearchHypothesis.family == family)
    stmt = stmt.limit(limit)

    results = db.execute(stmt).scalars().all()
    out = []
    for h in results:
        out.append(
            ResearchHypothesisSchema(
                id=h.id,
                family=h.family,
                generator_type=h.generator_type,
                title=h.title,
                description=h.description,
                base_spec_name=h.base_spec_name,
                spec_hash=h.spec_hash,
                prior_score=float(h.prior_score),
                status=h.status,
                rejection_reason=h.rejection_reason,
                created_at=h.created_at,
                updated_at=h.updated_at,
            )
        )
    return out


@router.post("/hypotheses/generate", response_model=ResearchHypothesisSchema)
def generate_hypothesis(
    req: GenerateHypothesisRequest,
    db: Session = Depends(get_db),
) -> Any:
    """Generate a new candidate hypothesis on-demand."""
    generator = HypothesisGenerator()
    try:
        base_spec = StrategySpec.from_yaml(req.base_spec_name)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to load base spec '{req.base_spec_name}': {e}",
        ) from e

    if req.generator_type == "FEATURE_COMBO":
        data = generator.generate_feature_combination(base_spec, layer=req.layer)
    elif req.generator_type == "REGIME_VARIANT":
        data = generator.generate_regime_variant(base_spec)
    else:
        data = generator.generate_parameter_refinement(base_spec)

    hyp = ResearchHypothesis(
        id=data["id"],
        family=data["family"],
        generator_type=data["generator_type"],
        title=data["title"],
        description=data["description"],
        base_spec_name=data["base_spec_name"],
        proposed_spec=data["proposed_spec"],
        spec_hash=data["spec_hash"],
        prior_score=data["prior_score"],
        status="QUEUED",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(hyp)
    db.commit()
    db.refresh(hyp)

    return ResearchHypothesisSchema(
        id=hyp.id,
        family=hyp.family,
        generator_type=hyp.generator_type,
        title=hyp.title,
        description=hyp.description,
        base_spec_name=hyp.base_spec_name,
        spec_hash=hyp.spec_hash,
        prior_score=float(hyp.prior_score),
        status=hyp.status,
        rejection_reason=hyp.rejection_reason,
        created_at=hyp.created_at,
        updated_at=hyp.updated_at,
    )


@router.get("/sweeps", response_model=list[ResearchSweepSchema])
def list_sweeps(
    family: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> Any:
    """List exploration sweeps."""
    stmt = select(ResearchSweep).order_by(ResearchSweep.created_at.desc())
    if family:
        stmt = stmt.where(ResearchSweep.family == family)
    stmt = stmt.limit(limit)

    results = db.execute(stmt).scalars().all()
    out = []
    for s in results:
        out.append(
            ResearchSweepSchema(
                id=s.id,
                hypothesis_id=s.hypothesis_id,
                family=s.family,
                sweep_type=s.sweep_type,
                param_grid=json.loads(s.param_grid) if s.param_grid else {},
                total_combinations=s.total_combinations,
                completed_combinations=s.completed_combinations,
                best_candidate_params=json.loads(s.best_candidate_params)
                if s.best_candidate_params
                else None,
                best_metric_name=s.best_metric_name,
                best_metric_value=float(s.best_metric_value)
                if s.best_metric_value is not None
                else None,
                status=s.status,
                created_at=s.created_at,
                completed_at=s.completed_at,
            )
        )
    return out


@router.post("/sweeps", response_model=ResearchSweepSchema)
def create_sweep(
    req: CreateSweepRequest,
    db: Session = Depends(get_db),
) -> Any:
    """Create and immediately execute a parameter sweep."""
    sweep_engine = SweepEngine(db)
    sweep = sweep_engine.create_grid_sweep(
        family=req.family,
        param_grid=req.param_grid,
        hypothesis_id=req.hypothesis_id,
        metric_name=req.metric_name,
    )
    base_spec = StrategySpec.from_yaml(req.base_spec_name)
    sweep = sweep_engine.execute_sweep_sync(sweep.id, base_spec)

    return ResearchSweepSchema(
        id=sweep.id,
        hypothesis_id=sweep.hypothesis_id,
        family=sweep.family,
        sweep_type=sweep.sweep_type,
        param_grid=json.loads(sweep.param_grid) if sweep.param_grid else {},
        total_combinations=sweep.total_combinations,
        completed_combinations=sweep.completed_combinations,
        best_candidate_params=json.loads(sweep.best_candidate_params)
        if sweep.best_candidate_params
        else None,
        best_metric_name=sweep.best_metric_name,
        best_metric_value=float(sweep.best_metric_value)
        if sweep.best_metric_value is not None
        else None,
        status=sweep.status,
        created_at=sweep.created_at,
        completed_at=sweep.completed_at,
    )


@router.get("/reports", response_model=list[ResearchReportSchema])
def list_reports(
    family: str | None = None,
    verdict: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> Any:
    """List research reports."""
    stmt = select(ResearchReport).order_by(ResearchReport.created_at.desc())
    if family:
        stmt = stmt.where(ResearchReport.family == family)
    if verdict:
        stmt = stmt.where(ResearchReport.verdict == verdict)
    stmt = stmt.limit(limit)

    results = db.execute(stmt).scalars().all()
    out = []
    for r in results:
        out.append(
            ResearchReportSchema(
                id=r.id,
                hypothesis_id=r.hypothesis_id,
                title=r.title,
                family=r.family,
                strategy_spec_name=r.strategy_spec_name,
                spec_hash=r.spec_hash,
                train_metrics=json.loads(r.train_metrics) if r.train_metrics else {},
                val_metrics=json.loads(r.val_metrics) if r.val_metrics else {},
                gatekeeper_results=json.loads(r.gatekeeper_results) if r.gatekeeper_results else {},
                gatekeeper_passed=r.gatekeeper_passed,
                verdict=r.verdict,
                report_markdown=r.report_markdown,
                human_decision=r.human_decision,
                human_decision_notes=r.human_decision_notes,
                human_decided_at=r.human_decided_at,
                created_at=r.created_at,
            )
        )
    return out


@router.get("/reports/{report_id}", response_model=ResearchReportSchema)
def get_report(report_id: str, db: Session = Depends(get_db)) -> Any:
    """Retrieve single research report by ID."""
    report = db.get(ResearchReport, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    return ResearchReportSchema(
        id=report.id,
        hypothesis_id=report.hypothesis_id,
        title=report.title,
        family=report.family,
        strategy_spec_name=report.strategy_spec_name,
        spec_hash=report.spec_hash,
        train_metrics=json.loads(report.train_metrics) if report.train_metrics else {},
        val_metrics=json.loads(report.val_metrics) if report.val_metrics else {},
        gatekeeper_results=json.loads(report.gatekeeper_results)
        if report.gatekeeper_results
        else {},
        gatekeeper_passed=report.gatekeeper_passed,
        verdict=report.verdict,
        report_markdown=report.report_markdown,
        human_decision=report.human_decision,
        human_decision_notes=report.human_decision_notes,
        human_decided_at=report.human_decided_at,
        created_at=report.created_at,
    )


@router.get("/queue", response_model=list[ResearchReportSchema])
def get_review_queue(db: Session = Depends(get_db)) -> Any:
    """Retrieve candidates awaiting human review in the Promotion Queue."""
    stmt = (
        select(ResearchReport)
        .where(ResearchReport.human_decision == "PENDING_REVIEW")
        .where(ResearchReport.gatekeeper_passed.is_(True))
        .order_by(ResearchReport.created_at.desc())
    )
    results = db.execute(stmt).scalars().all()
    out = []
    for r in results:
        out.append(
            ResearchReportSchema(
                id=r.id,
                hypothesis_id=r.hypothesis_id,
                title=r.title,
                family=r.family,
                strategy_spec_name=r.strategy_spec_name,
                spec_hash=r.spec_hash,
                train_metrics=json.loads(r.train_metrics) if r.train_metrics else {},
                val_metrics=json.loads(r.val_metrics) if r.val_metrics else {},
                gatekeeper_results=json.loads(r.gatekeeper_results) if r.gatekeeper_results else {},
                gatekeeper_passed=r.gatekeeper_passed,
                verdict=r.verdict,
                report_markdown=r.report_markdown,
                human_decision=r.human_decision,
                human_decision_notes=r.human_decision_notes,
                human_decided_at=r.human_decided_at,
                created_at=r.created_at,
            )
        )
    return out


@router.post("/queue/{report_id}/approve")
def approve_candidate(
    report_id: str,
    req: CandidateDecisionRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Human one-click promotion of candidate strategy to CANDIDATE/PAPER stage."""
    report = db.get(ResearchReport, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    report.human_decision = "APPROVED"
    report.human_decision_notes = req.decision_notes
    report.human_decided_at = datetime.now(UTC)

    # If hypothesis is linked, mark it as PROMOTED
    if report.hypothesis_id:
        hyp = db.get(ResearchHypothesis, report.hypothesis_id)
        if hyp:
            hyp.status = "PROMOTED"

    db.commit()
    return {"status": "APPROVED", "report_id": report_id}


@router.post("/queue/{report_id}/reject")
def reject_candidate(
    report_id: str,
    req: CandidateDecisionRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Human rejection of candidate strategy."""
    report = db.get(ResearchReport, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    report.human_decision = "REJECTED"
    report.human_decision_notes = req.decision_notes
    report.human_decided_at = datetime.now(UTC)

    if report.hypothesis_id:
        hyp = db.get(ResearchHypothesis, report.hypothesis_id)
        if hyp:
            hyp.status = "REJECTED"
            hyp.rejection_reason = f"Human rejection: {req.decision_notes}"

    db.commit()
    return {"status": "REJECTED", "report_id": report_id}


@router.post("/holdout/unlock")
def unlock_holdout_partition(
    req: HoldoutUnlockRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Record manual authorization to unlock holdout partition (§8.3 Invariant)."""
    try:
        log_entry = HoldoutGuard.record_unlock(
            session=db,
            family=req.family,
            unlocked_by=req.unlocked_by,
            reason=req.reason,
        )
        return {
            "status": "UNLOCKED",
            "family": req.family,
            "unlocked_by": req.unlocked_by,
            "unlocked_at": log_entry.unlocked_at.isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
