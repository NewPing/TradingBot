"""Unit tests for StrategyVersionRegistry and immutability enforcement."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from atlas.core.errors import SpecImmutabilityError
from atlas.data.models import Base, Run
from atlas.strategies.registry import StrategyVersionRegistry
from atlas.strategies.spec import StrategySpec


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_register_and_get_spec(db_session):
    registry = StrategyVersionRegistry(db_session)
    spec_yaml = """
name: Core Trend Strategy v1.0.0
family: core_trend
version: 1.0.0
bucket: CORE
description: 200 SMA trend following
signals:
  - provider: sma_trend
    weight: 1.0
    params:
      period: 200
"""
    spec = StrategySpec.from_yaml(spec_yaml)
    record = registry.register_spec(spec, raw_yaml=spec_yaml, notes="Initial version")

    assert record.id == "core_trend_1.0.0"
    assert record.family == "core_trend"
    assert record.version == "1.0.0"
    assert record.status == "RESEARCH"

    # Fetch
    fetched = registry.get("core_trend_1.0.0")
    assert fetched is not None
    assert fetched.spec_hash == record.spec_hash

    # Re-register identical spec returns same record
    same_record = registry.register_spec(spec, raw_yaml=spec_yaml)
    assert same_record.id == record.id


def test_immutability_violation_raises_error(db_session):
    registry = StrategyVersionRegistry(db_session)
    spec_yaml_1 = """
name: Core Trend Strategy v1.0.0
family: core_trend
version: 1.0.0
signals:
  - provider: sma_trend
    params:
      period: 200
"""
    spec1 = StrategySpec.from_yaml(spec_yaml_1)
    registry.register_spec(spec1)

    # Mutate spec parameters while keeping same version string
    spec_yaml_mutated = """
name: Core Trend Strategy v1.0.0
family: core_trend
version: 1.0.0
signals:
  - provider: sma_trend
    params:
      period: 50
"""
    spec_mutated = StrategySpec.from_yaml(spec_yaml_mutated)

    # Must raise SpecImmutabilityError
    with pytest.raises(SpecImmutabilityError, match="differing spec hash"):
        registry.register_spec(spec_mutated)


def test_immutability_with_existing_runs(db_session):
    registry = StrategyVersionRegistry(db_session)
    spec_yaml = """
name: Swing Mean Reversion v1.0.0
family: swing_meanrev
version: 1.0.0
signals:
  - provider: rsi_reversion
"""
    spec = StrategySpec.from_yaml(spec_yaml)
    version = registry.register_spec(spec)

    # Add a run referencing this version
    run = Run(
        id="run_123",
        strategy_version_id=version.id,
        mode="BACKTEST",
        start_ts=version.created_at,
        end_ts=version.created_at,
        data_snapshot_id="snapshot_20240101",
        git_sha="abcdef1234567890",
        spec_hash=version.spec_hash,
        cost_model_hash="cost_model_v1",
        seed=42,
        status="COMPLETED",
    )
    db_session.add(run)
    db_session.commit()

    # Attempt to change spec
    mutated_spec = StrategySpec.from_yaml("""
name: Swing Mean Reversion v1.0.0
family: swing_meanrev
version: 1.0.0
signals:
  - provider: rsi_reversion
    params:
      oversold: 20
""")
    with pytest.raises(
        SpecImmutabilityError, match="referenced by execution runs and is immutable"
    ):
        registry.register_spec(mutated_spec)


def test_lineage_tracking(db_session):
    registry = StrategyVersionRegistry(db_session)

    # Root version v1.0.0
    spec_v1 = StrategySpec.from_yaml("""
name: Trend Following v1.0.0
family: trend_follow
version: 1.0.0
""")
    v1 = registry.register_spec(spec_v1)

    # Child version v1.1.0 with parent_id
    spec_v2 = StrategySpec.from_yaml(f"""
name: Trend Following v1.1.0
family: trend_follow
version: 1.1.0
parent_id: {v1.id}
""")
    v2 = registry.register_spec(spec_v2)

    # Grandchild version v1.2.0
    spec_v3 = StrategySpec.from_yaml(f"""
name: Trend Following v1.2.0
family: trend_follow
version: 1.2.0
parent_id: {v2.id}
""")
    v3 = registry.register_spec(spec_v3)

    # Check lineage of v3
    lineage_v3 = registry.get_lineage(v3.id)
    assert lineage_v3["current"]["id"] == v3.id
    assert len(lineage_v3["ancestors"]) == 2
    assert lineage_v3["ancestors"][0]["id"] == v2.id
    assert lineage_v3["ancestors"][1]["id"] == v1.id
    assert len(lineage_v3["children"]) == 0

    # Check lineage of v1
    lineage_v1 = registry.get_lineage(v1.id)
    assert len(lineage_v1["ancestors"]) == 0
    assert len(lineage_v1["children"]) == 1
    assert lineage_v1["children"][0]["id"] == v2.id


def test_status_update(db_session):
    registry = StrategyVersionRegistry(db_session)
    spec = StrategySpec.from_yaml("""
name: Test Strategy v1.0.0
family: test_strat
version: 1.0.0
""")
    v = registry.register_spec(spec)
    assert v.status == "RESEARCH"

    updated = registry.update_status(v.id, "CANDIDATE", notes="Passed walkforward testing")
    assert updated.status == "CANDIDATE"
    assert "Passed walkforward" in updated.notes

    with pytest.raises(ValueError, match="Invalid status"):
        registry.update_status(v.id, "NON_EXISTENT_STATUS")
