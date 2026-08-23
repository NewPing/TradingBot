"""Strategy version registry with strict immutability enforcement and lineage tracking."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.core.errors import SpecImmutabilityError, StrategyVersionNotFoundError
from atlas.data.models import Run, StrategyVersion
from atlas.strategies.spec import StrategySpec


class StrategyVersionRegistry:
    """Registry managing immutable strategy specifications, versions, and lineage."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def register_spec(
        self,
        spec: StrategySpec,
        raw_yaml: str | None = None,
        notes: str = "",
        status: str = "RESEARCH",
        git_sha: str | None = None,
    ) -> StrategyVersion:
        """Register a strategy specification into the version registry.

        If a version with the same ID already exists:
          - If spec_hash is identical: returns existing record.
          - If spec_hash differs: raises SpecImmutabilityError.
        """
        version_id = (
            f"{spec.family}_{spec.version}" if spec.version not in spec.family else spec.family
        )
        # Canonical spec hash
        spec_hash = spec.spec_hash()

        # Check existing version
        existing = self.session.execute(
            select(StrategyVersion).where(StrategyVersion.id == version_id)
        ).scalar_one_or_none()

        if existing is not None:
            if existing.spec_hash == spec_hash:
                return existing

            # Spec has changed! Check if any runs exist
            has_runs = (
                self.session.execute(
                    select(Run.id).where(Run.strategy_version_id == version_id)
                ).first()
                is not None
            )

            if has_runs:
                raise SpecImmutabilityError(
                    f"Strategy version '{version_id}' is referenced by execution runs and is immutable. "
                    f"Create a new version (e.g. version: '1.0.1') with parent_id='{version_id}'."
                )
            else:
                raise SpecImmutabilityError(
                    f"Strategy version '{version_id}' already registered with differing spec hash "
                    f"({existing.spec_hash[:8]} vs {spec_hash[:8]}). Modify version string instead."
                )

        # Check parent lineage if parent_id is specified
        canonical_parent_id = spec.parent_id
        if spec.parent_id:
            parent_candidates = [
                spec.parent_id,
                spec.parent_id.replace(":", "_"),
                spec.parent_id.replace("_v1", "_1.0.0"),
                spec.parent_id.replace("_v2", "_2.0.0"),
                spec.parent_id.replace("_v3", "_3.0.0"),
                spec.parent_id.replace("_v4", "_4.0.0"),
                spec.parent_id.replace("_l2", "_2.0.0"),
                spec.parent_id.replace("_l3", "_3.0.0"),
                spec.parent_id.replace("_l4", "_4.0.0"),
                f"{spec.family}_{spec.parent_id}",
            ]
            parent = self.session.execute(
                select(StrategyVersion).where(StrategyVersion.id.in_(parent_candidates))
            ).scalar_one_or_none()
            if parent is not None:
                canonical_parent_id = parent.id
            elif spec.parent_id:
                # If still not found, check if family matches
                fam_parent = self.session.execute(
                    select(StrategyVersion).where(StrategyVersion.family == spec.parent_id)
                ).first()
                if fam_parent is not None:
                    canonical_parent_id = fam_parent[0].id
                else:
                    raise StrategyVersionNotFoundError(
                        f"Parent strategy version '{spec.parent_id}' does not exist in registry."
                    )

        yaml_content = raw_yaml if raw_yaml is not None else spec.model_dump_json(indent=2)
        record = StrategyVersion(
            id=version_id,
            family=spec.family,
            version=spec.version,
            spec_yaml=yaml_content,
            spec_hash=spec_hash,
            git_sha=git_sha,
            parent_id=canonical_parent_id,
            status=status,
            notes=notes or spec.description,
            created_at=datetime.now(UTC),
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def get(self, version_id: str) -> StrategyVersion | None:
        """Get strategy version by unique ID."""
        return self.session.execute(
            select(StrategyVersion).where(StrategyVersion.id == version_id)
        ).scalar_one_or_none()

    def get_or_raise(self, version_id: str) -> StrategyVersion:
        """Get strategy version by ID or raise StrategyVersionNotFoundError."""
        version = self.get(version_id)
        if version is None:
            raise StrategyVersionNotFoundError(f"Strategy version '{version_id}' not found.")
        return version

    def list_all(self, family: str | None = None) -> list[StrategyVersion]:
        """List all strategy versions, optionally filtered by strategy family."""
        stmt = select(StrategyVersion)
        if family:
            stmt = stmt.where(StrategyVersion.family == family)
        stmt = stmt.order_by(
            StrategyVersion.family, StrategyVersion.version, StrategyVersion.created_at.desc()
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_lineage(self, version_id: str) -> dict[str, Any]:
        """Get ancestral lineage tree and direct child versions for a strategy version."""
        current = self.get_or_raise(version_id)

        # Ancestors
        ancestors: list[dict[str, Any]] = []
        curr_parent_id = current.parent_id
        while curr_parent_id:
            parent = self.get(curr_parent_id)
            if not parent:
                break
            ancestors.append(
                {
                    "id": parent.id,
                    "family": parent.family,
                    "version": parent.version,
                    "status": parent.status,
                    "spec_hash": parent.spec_hash,
                    "created_at": parent.created_at.isoformat(),
                }
            )
            curr_parent_id = parent.parent_id

        # Children
        children_records = (
            self.session.execute(
                select(StrategyVersion).where(StrategyVersion.parent_id == version_id)
            )
            .scalars()
            .all()
        )
        children = [
            {
                "id": child.id,
                "family": child.family,
                "version": child.version,
                "status": child.status,
                "spec_hash": child.spec_hash,
                "created_at": child.created_at.isoformat(),
            }
            for child in children_records
        ]

        return {
            "current": {
                "id": current.id,
                "family": current.family,
                "version": current.version,
                "status": current.status,
                "spec_hash": current.spec_hash,
                "created_at": current.created_at.isoformat(),
            },
            "ancestors": ancestors,
            "children": children,
        }

    def update_status(
        self, version_id: str, new_status: str, notes: str | None = None
    ) -> StrategyVersion:
        """Update promotion/lifecycle status of a strategy version."""
        valid_statuses = {"RESEARCH", "CANDIDATE", "PAPER", "SHADOW", "LIVE", "REJECTED", "RETIRED"}
        if new_status.upper() not in valid_statuses:
            raise ValueError(f"Invalid status '{new_status}'. Allowed: {sorted(valid_statuses)}")

        version = self.get_or_raise(version_id)
        version.status = new_status.upper()
        if notes:
            version.notes = f"{version.notes}\n[{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}] {notes}".strip()
        self.session.commit()
        self.session.refresh(version)
        return version

    def sync_directory(self, strategies_dir: Path) -> list[StrategyVersion]:
        """Discover and register all YAML specifications in a directory with multi-pass dependency resolution."""
        if not strategies_dir.exists():
            return []

        yaml_files = sorted(strategies_dir.glob("*.yaml"))
        registered_dict: dict[str, StrategyVersion] = {}

        # Multi-pass registration (pass 1: roots/parents, pass 2-3: children & derivatives)
        for _pass in range(3):
            for yaml_file in yaml_files:
                try:
                    with yaml_file.open(encoding="utf-8") as f:
                        raw_yaml = f.read()
                    spec = StrategySpec.from_yaml(raw_yaml)
                    version_record = self.register_spec(spec=spec, raw_yaml=raw_yaml)
                    registered_dict[version_record.id] = version_record
                except Exception:
                    # Retry in next pass if parent was not yet registered
                    continue

        return list(registered_dict.values())
