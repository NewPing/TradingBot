"""Cryptographic holdout partition guard and authorization tracker (Phase 8).

Strictly enforces partition isolation (§8.3):
- Train: 2005-01-01 -> 2018-12-31 (unlimited fitting)
- Validation: 2019-01-01 -> 2022-12-31 (single-pass validation, logs trial)
- Holdout: 2023-01-01 -> present-90d (STRICTLY LOCKED; requires manual human unlock)
- Live-Forward: present-90d -> present (paper trading only)
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from atlas.core.errors import AtlasError
from atlas.data.models import HoldoutAccessLog


class HoldoutPartitionLockedError(AtlasError):
    """Raised when an automated backtest or sweep attempts to touch the locked holdout partition."""

    pass


class HoldoutGuard:
    """Guards the holdout partition against unauthorized automated access or data snooping."""

    HOLDOUT_START = date(2023, 1, 1)

    @classmethod
    def get_holdout_end(cls) -> date:
        """Holdout partition ends 90 days before today."""
        today = datetime.now(UTC).date()
        return today - timedelta(days=90)

    @classmethod
    def validate_date_range(
        cls,
        start_date: date,
        end_date: date,
        family: str,
        allow_holdout: bool = False,
    ) -> None:
        """Verify date range does not violate the locked holdout partition."""
        holdout_end = cls.get_holdout_end()

        # Check if date range overlaps with [HOLDOUT_START, holdout_end]
        overlaps_holdout = not (end_date < cls.HOLDOUT_START or start_date > holdout_end)

        if overlaps_holdout and not allow_holdout:
            raise HoldoutPartitionLockedError(
                f"Evaluation range {start_date} to {end_date} touches the locked Holdout "
                f"partition ({cls.HOLDOUT_START} to {holdout_end}) for family '{family}'. "
                f"Automated sweeps and research runs are strictly restricted to Train (2005-2018) "
                f"or Validation (2019-2022). Human CLI unlock is required to evaluate against holdout."
            )

    @classmethod
    def record_unlock(
        cls,
        session: Session,
        family: str,
        unlocked_by: str,
        reason: str,
        run_id: str | None = None,
    ) -> HoldoutAccessLog:
        """Record human authorization in the holdout access audit ledger."""
        if not reason or len(reason.strip()) < 10:
            raise ValueError(
                "A substantial justification (>10 characters) is required to unlock holdout."
            )

        log_entry = HoldoutAccessLog(
            family=family,
            unlocked_by=unlocked_by,
            reason=reason.strip(),
            run_id=run_id,
            unlocked_at=datetime.now(UTC),
        )
        session.add(log_entry)
        session.commit()
        session.refresh(log_entry)
        return log_entry
