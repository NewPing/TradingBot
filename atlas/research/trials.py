"""Sacred trial counter and multiple testing correction registry (Phase 3 & Phase 8)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from atlas.data.models import Trial


class TrialTracker:
    """Tracks every strategy iteration/trial for sacred multiple-testing budget accounting."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def record_trial(
        self,
        family: str,
        parameters: dict[str, Any],
        metrics: dict[str, Any],
        outcome: str = "COMPLETED",
        hypothesis_id: str | None = None,
        run_id: str | None = None,
        notes: str = "",
    ) -> Trial:
        """Record an optimization or evaluation trial in the trials ledger."""
        trial = Trial(
            hypothesis_id=hypothesis_id,
            run_id=run_id,
            family=family,
            params=json.dumps(parameters, sort_keys=True),
            metrics=json.dumps(metrics, sort_keys=True),
            outcome=outcome.upper(),
            notes=notes,
            created_at=datetime.now(UTC),
        )
        self.session.add(trial)
        self.session.commit()
        self.session.refresh(trial)
        return trial

    def get_budget_status(
        self, family: str | None = None, weekly_budget: int = 500
    ) -> dict[str, Any]:
        """Get total trial count, trials this week, and budget consumption."""
        now = datetime.now(UTC)
        one_week_ago = now - timedelta(days=7)

        total_stmt = select(func.count(Trial.id))
        if family:
            total_stmt = total_stmt.where(Trial.family == family)
        total_trials = self.session.execute(total_stmt).scalar() or 0

        week_stmt = select(func.count(Trial.id)).where(Trial.created_at >= one_week_ago)
        if family:
            week_stmt = week_stmt.where(Trial.family == family)
        trials_this_week = self.session.execute(week_stmt).scalar() or 0

        budget_remaining = max(0, weekly_budget - trials_this_week)
        budget_pct_used = min(1.0, trials_this_week / weekly_budget) if weekly_budget > 0 else 0.0

        return {
            "total_trials": total_trials,
            "trials_this_week": trials_this_week,
            "weekly_budget": weekly_budget,
            "budget_remaining": budget_remaining,
            "budget_pct_used": round(budget_pct_used * 100, 2),
            "family": family or "all",
        }

    def list_trials(self, family: str | None = None, limit: int = 100) -> list[Trial]:
        """List trial records sorted chronologically descending."""
        stmt = select(Trial)
        if family:
            stmt = stmt.where(Trial.family == family)
        stmt = stmt.order_by(Trial.created_at.desc()).limit(limit)
        return list(self.session.execute(stmt).scalars().all())
