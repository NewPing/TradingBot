"""Unit tests for Research Loop components: HoldoutGuard, HypothesisGenerator, SweepEngine, Reporter, and Daemon."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from atlas.core.types import BucketId
from atlas.data.models import Base
from atlas.research.daemon import ResearchDaemon
from atlas.research.holdout import HoldoutGuard, HoldoutPartitionLockedError
from atlas.research.hypothesis import HypothesisGenerator
from atlas.research.sweep import SweepEngine
from atlas.strategies.spec import SignalConfig, StrategySpec, UniverseFilterConfig


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def dummy_spec() -> StrategySpec:
    return StrategySpec(
        name="test_core_spec",
        family="core_trend",
        version="1.0.0",
        bucket=BucketId.CORE,
        universe=UniverseFilterConfig(symbols=["SPY", "QQQ"]),
        signals=[
            SignalConfig(
                provider="l1_trend_filter",
                weight=0.5,
                params={"period": 20, "threshold": 0.05},
            ),
            SignalConfig(
                provider="l1_trend_filter",
                weight=0.5,
                params={"period": 50, "threshold": 0.02},
            ),
        ],
    )


def test_holdout_guard_blocks_locked_partition() -> None:
    """HoldoutGuard must raise HoldoutPartitionLockedError when date touches 2023 without authorization."""
    with pytest.raises(HoldoutPartitionLockedError):
        HoldoutGuard.validate_date_range(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 6, 30),
            family="core_trend",
            allow_holdout=False,
        )

    # Train partition should pass without error
    HoldoutGuard.validate_date_range(
        start_date=date(2005, 1, 1),
        end_date=date(2018, 12, 31),
        family="core_trend",
        allow_holdout=False,
    )


def test_holdout_guard_unlock_audit(db_session: Session) -> None:
    """HoldoutGuard unlock records audit log entry with justification."""
    log = HoldoutGuard.record_unlock(
        session=db_session,
        family="core_trend",
        unlocked_by="lead_quant",
        reason="Final promotion verification against holdout partition after 8-gate pass.",
    )
    assert log.id is not None
    assert log.family == "core_trend"
    assert log.unlocked_by == "lead_quant"


def test_hypothesis_generator(dummy_spec: StrategySpec) -> None:
    """Test formulation across hypothesis generator modalities."""
    gen = HypothesisGenerator()

    # 1. Parameter Refinement
    ref = gen.generate_parameter_refinement(dummy_spec)
    assert ref["generator_type"] == "PARAM_REFINEMENT"
    assert ref["spec_hash"] != ""
    assert ref["family"] == "core_trend"

    # 2. Feature Combo L2
    feat = gen.generate_feature_combination(dummy_spec, layer="l2")
    assert feat["generator_type"] == "FEATURE_COMBO"
    assert "l2_cross_sectional_momentum" in feat["proposed_spec"]

    # 3. Regime Variant
    reg = gen.generate_regime_variant(dummy_spec)
    assert reg["generator_type"] == "REGIME_VARIANT"
    assert "l2_regime_detector" in reg["proposed_spec"]

    # 4. Genetic Recombination
    crossover = gen.generate_genetic_recombination(dummy_spec, dummy_spec)
    assert crossover["generator_type"] == "GENETIC_RECOMBINATION"


def test_sweep_engine(db_session: Session, dummy_spec: StrategySpec) -> None:
    """Test sweep creation, grid evaluation, and trial logging."""
    engine = SweepEngine(db_session)
    sweep = engine.create_grid_sweep(
        family="core_trend",
        param_grid={"fast": [10, 20], "slow": [50, 100]},
        metric_name="sharpe_ratio",
    )
    assert sweep.total_combinations == 4
    assert sweep.status == "PENDING"

    executed = engine.execute_sweep_sync(sweep.id, dummy_spec)
    assert executed.status == "COMPLETED"
    assert executed.completed_combinations == 4
    assert executed.best_metric_value is not None


def test_research_daemon_cycle(db_session: Session) -> None:
    """Test single synchronous research cycle execution."""

    def session_factory() -> Session:
        return db_session

    daemon = ResearchDaemon(session_factory=session_factory, weekly_trial_budget=500)

    res = daemon.run_iteration_sync()
    assert res["status"] in ["COMPLETED", "NO_BASE_STRATEGIES_AVAILABLE"]
    if res["status"] == "COMPLETED":
        assert "hypothesis_id" in res
        assert "report_id" in res
