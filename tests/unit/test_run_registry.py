"""Unit tests for RunRegistry, reproducibility metadata, and TrialTracker."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from atlas.backtest.registry import RunRegistry
from atlas.data.models import Base
from atlas.research.trials import TrialTracker
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


def test_record_and_retrieve_run(db_session):
    ver_reg = StrategyVersionRegistry(db_session)
    spec = StrategySpec.from_yaml("name: Run Test v1\nfamily: run_test\nversion: 1.0.0")
    version = ver_reg.register_spec(spec)

    run_reg = RunRegistry(db_session)
    now = datetime.now(UTC)

    equity_curve = [
        {"ts": now, "equity": 100000, "cash": 100000, "drawdown": 0},
        {"ts": now + timedelta(days=1), "equity": 105000, "cash": 50000, "drawdown": 0},
        {"ts": now + timedelta(days=2), "equity": 102000, "cash": 50000, "drawdown": 0.0285},
    ]

    trades = [
        {
            "trade_id": "T001",
            "symbol": "SPY",
            "direction": "LONG",
            "entry_time": now,
            "exit_time": now + timedelta(days=2),
            "entry_price": 500.0,
            "exit_price": 520.0,
            "quantity": 100,
            "pnl": 2000.0,
            "pnl_net": 1995.0,
            "return_pct": 0.04,
            "fees": 2.5,
            "slippage": 2.5,
            "exit_reason": "SIGNAL",
        }
    ]

    summary_metrics = {
        "cagr": 0.152,
        "sharpe": 1.45,
        "sortino": 2.10,
        "max_drawdown": 0.085,
        "calmar": 1.78,
        "win_rate": 0.65,
        "profit_factor": 1.85,
        "expectancy_pct": 0.012,
        "total_trades": 1,
    }

    run = run_reg.record_run(
        run_id="run_test_001",
        strategy_version_id=version.id,
        mode="BACKTEST",
        start_ts=now,
        end_ts=now + timedelta(days=2),
        data_snapshot_id="snapshot_20240101",
        spec_hash=version.spec_hash,
        cost_model_hash="costs.default_v1",
        seed=42,
        summary_metrics=summary_metrics,
        equity_curve=equity_curve,
        trades=trades,
        status="COMPLETED",
    )

    assert run.id == "run_test_001"
    assert run.git_sha != ""
    assert "atlas" in run.lib_versions

    # Retrieve equity points
    eq_points = run_reg.get_equity_curve("run_test_001")
    assert len(eq_points) == 3
    assert float(eq_points[1].total_equity) == 105000.0

    # Retrieve trades
    tr_list = run_reg.get_trades("run_test_001")
    assert len(tr_list) == 1
    assert tr_list[0].symbol == "SPY"
    assert float(tr_list[0].pnl_net) == 1995.0


def test_compare_multiple_runs(db_session):
    ver_reg = StrategyVersionRegistry(db_session)
    spec1 = StrategySpec.from_yaml("name: Comp Test 1\nfamily: comp_test\nversion: 1.0.0")
    spec2 = StrategySpec.from_yaml("name: Comp Test 2\nfamily: comp_test\nversion: 2.0.0")
    v1 = ver_reg.register_spec(spec1)
    v2 = ver_reg.register_spec(spec2)

    run_reg = RunRegistry(db_session)
    now = datetime.now(UTC)

    run_reg.record_run(
        run_id="run_comp_1",
        strategy_version_id=v1.id,
        mode="BACKTEST",
        start_ts=now,
        end_ts=now + timedelta(days=1),
        data_snapshot_id="snap_1",
        spec_hash=v1.spec_hash,
        cost_model_hash="costs.default_v1",
        summary_metrics={"cagr": 0.12, "sharpe": 1.20, "max_drawdown": 0.10},
    )

    run_reg.record_run(
        run_id="run_comp_2",
        strategy_version_id=v2.id,
        mode="BACKTEST",
        start_ts=now,
        end_ts=now + timedelta(days=1),
        data_snapshot_id="snap_1",
        spec_hash=v2.spec_hash,
        cost_model_hash="costs.default_v1",
        summary_metrics={"cagr": 0.18, "sharpe": 1.65, "max_drawdown": 0.08},
    )

    comparison = run_reg.compare_runs(["run_comp_1", "run_comp_2"])
    assert len(comparison["runs"]) == 2
    assert comparison["metrics_diff"]["sharpe"]["run_comp_1"] == 1.20
    assert comparison["metrics_diff"]["sharpe"]["run_comp_2"] == 1.65
    assert comparison["metrics_diff"]["cagr"]["run_comp_2"] == 0.18


def test_trial_tracker_budget(db_session):
    tracker = TrialTracker(db_session)

    # Record 5 trials
    for i in range(5):
        tracker.record_trial(
            family="core_trend",
            parameters={"period": 100 + i * 20},
            metrics={"sharpe": 1.0 + i * 0.1},
            notes=f"Sweep trial {i}",
        )

    status = tracker.get_budget_status(family="core_trend", weekly_budget=500)
    assert status["total_trials"] == 5
    assert status["trials_this_week"] == 5
    assert status["budget_remaining"] == 495
    assert status["budget_pct_used"] == 1.0

    trials = tracker.list_trials(family="core_trend")
    assert len(trials) == 5
