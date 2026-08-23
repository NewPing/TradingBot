"""Pydantic schemas for the ATLAS Research Loop and Discovery API (Phase 8)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TrialBudgetSummary(BaseModel):
    """Weekly trial budget status."""

    total_trials: int
    trials_this_week: int
    weekly_budget: int
    budget_remaining: int
    budget_pct_used: float
    family: str


class ResearchDaemonStatus(BaseModel):
    """Telemetry status of the autonomous research engine."""

    running: bool
    cycles_completed: int
    last_run_at: datetime | None = None
    active_workers: int
    queued_hypotheses_count: int
    pending_human_review_count: int
    weekly_trial_budget: TrialBudgetSummary


class ResearchHypothesisSchema(BaseModel):
    """Research hypothesis model schema."""

    id: str
    family: str
    generator_type: str
    title: str
    description: str
    base_spec_name: str
    spec_hash: str
    prior_score: float
    status: str
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class GenerateHypothesisRequest(BaseModel):
    """Request to generate hypotheses on-demand."""

    base_spec_name: str = "strategies/core_trend_v1.yaml"
    generator_type: str = "PARAM_REFINEMENT"  # PARAM_REFINEMENT | FEATURE_COMBO | REGIME_VARIANT
    layer: str = "l2"


class ResearchSweepSchema(BaseModel):
    """Parameter/feature sweep record schema."""

    id: str
    hypothesis_id: str | None = None
    family: str
    sweep_type: str
    param_grid: dict[str, Any]
    total_combinations: int
    completed_combinations: int
    best_candidate_params: dict[str, Any] | None = None
    best_metric_name: str
    best_metric_value: float | None = None
    status: str
    created_at: datetime
    completed_at: datetime | None = None


class CreateSweepRequest(BaseModel):
    """Request to execute a parameter sweep."""

    family: str
    param_grid: dict[str, list[Any]]
    hypothesis_id: str | None = None
    base_spec_name: str = "strategies/core_trend_v1.yaml"
    metric_name: str = "sharpe_ratio"


class GateResultSchema(BaseModel):
    """Individual gatekeeper test result."""

    gate_number: int
    name: str
    passed: bool
    score: float
    threshold: float
    operator: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class GatekeeperResultsSchema(BaseModel):
    """Summary of 8 promotion gates."""

    strategy_name: str
    passed_all: bool
    gates_passed: int
    total_gates: int
    verdict: str
    results: list[GateResultSchema]


class ResearchReportSchema(BaseModel):
    """Complete research report record."""

    id: str
    hypothesis_id: str | None = None
    title: str
    family: str
    strategy_spec_name: str
    spec_hash: str
    train_metrics: dict[str, Any]
    val_metrics: dict[str, Any]
    gatekeeper_results: GatekeeperResultsSchema | dict[str, Any]
    gatekeeper_passed: bool
    verdict: str
    report_markdown: str
    human_decision: str
    human_decision_notes: str | None = None
    human_decided_at: datetime | None = None
    created_at: datetime


class CandidateDecisionRequest(BaseModel):
    """Request body for human candidate review approval/rejection."""

    decision_notes: str = Field(default="", description="Human feedback/rationale")
    target_bucket: str = Field(default="CORE", description="Bucket to assign candidate to")


class HoldoutUnlockRequest(BaseModel):
    """Request to manually unlock the holdout partition."""

    family: str
    unlocked_by: str = Field(..., description="Developer/operator identifier")
    reason: str = Field(
        ..., min_length=10, description="Explicit statistical justification for unlocking holdout"
    )
