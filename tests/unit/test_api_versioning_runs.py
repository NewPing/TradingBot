"""Integration tests for Phase 3 FastAPI endpoints (versions, runs, compare, trials, signals)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from atlas.api.main import app
from atlas.backtest.registry import RunRegistry
from atlas.data.db import get_db
from atlas.data.models import Base


@pytest.fixture
def client_with_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_versions_endpoints(client_with_db):
    spec_yaml = """
name: Trend Test Strategy v1.0.0
family: trend_test
version: 1.0.0
bucket: CORE
description: Trend following test
"""
    # 1. Create version
    res = client_with_db.post(
        "/api/v1/versions",
        json={"spec_yaml": spec_yaml, "notes": "API test version"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["id"] == "trend_test_1.0.0"
    assert data["family"] == "trend_test"

    # 2. List versions
    res = client_with_db.get("/api/v1/versions")
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # 3. Get single version
    res = client_with_db.get("/api/v1/versions/trend_test_1.0.0")
    assert res.status_code == 200
    assert res.json()["id"] == "trend_test_1.0.0"

    # 4. Update status
    res = client_with_db.patch(
        "/api/v1/versions/trend_test_1.0.0/status",
        json={"status": "CANDIDATE", "notes": "Passed validation gate"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "CANDIDATE"

    # 5. Get lineage
    res = client_with_db.get("/api/v1/versions/trend_test_1.0.0/lineage")
    assert res.status_code == 200
    assert res.json()["current"]["id"] == "trend_test_1.0.0"


def test_trials_and_signals_endpoints(client_with_db):
    # Trial budget (unlimited in v1.5)
    res = client_with_db.get("/api/v1/trials/budget")
    assert res.status_code == 200
    data = res.json()
    assert "weekly_budget" in data
    assert data.get("is_unlimited") is True

    # Parameterized budget
    res_param = client_with_db.get("/api/v1/trials/budget?weekly_budget=500")
    assert res_param.status_code == 200
    assert res_param.json()["weekly_budget"] == 500

    # Signals explore
    res = client_with_db.get("/api/v1/signals/explore?symbol=SPY")
    assert res.status_code == 200
    sig_data = res.json()
    assert sig_data["symbol"] == "SPY"
    assert "available_indicators" in sig_data


def test_runs_and_compare_endpoints(client_with_db):
    # Register strategy version
    spec_yaml = """
name: Compare API Test v1
family: comp_api
version: 1.0.0
"""
    res = client_with_db.post("/api/v1/versions", json={"spec_yaml": spec_yaml})
    assert res.status_code == 201

    # Insert mock runs directly via RunRegistry in test session
    db_gen = app.dependency_overrides[get_db]()
    session = next(db_gen)

    now = datetime.now(UTC)
    reg = RunRegistry(session)
    reg.record_run(
        run_id="run_api_1",
        strategy_version_id="comp_api_1.0.0",
        mode="BACKTEST",
        start_ts=now,
        end_ts=now + timedelta(days=1),
        data_snapshot_id="snap_test",
        spec_hash="hash1",
        cost_model_hash="cost1",
        summary_metrics={"cagr": 0.15, "sharpe": 1.5, "max_drawdown": 0.05},
        equity_curve=[{"ts": now, "equity": 100000, "cash": 100000, "drawdown": 0}],
        trades=[
            {
                "trade_id": "T1",
                "symbol": "SPY",
                "direction": "LONG",
                "entry_time": now,
                "exit_time": now,
                "entry_price": 500.0,
                "exit_price": 505.0,
                "quantity": 10,
                "pnl": 50.0,
                "pnl_net": 48.0,
                "return_pct": 0.01,
                "fees": 1.0,
                "slippage": 1.0,
                "exit_reason": "TAKE_PROFIT",
            }
        ],
    )
    reg.record_run(
        run_id="run_api_2",
        strategy_version_id="comp_api_1.0.0",
        mode="BACKTEST",
        start_ts=now,
        end_ts=now + timedelta(days=1),
        data_snapshot_id="snap_test",
        spec_hash="hash1",
        cost_model_hash="cost1",
        summary_metrics={"cagr": 0.20, "sharpe": 1.8, "max_drawdown": 0.06},
    )

    # 1. List runs
    res = client_with_db.get("/api/v1/runs")
    assert res.status_code == 200
    assert len(res.json()) == 2

    # 2. Get run detail
    res = client_with_db.get("/api/v1/runs/run_api_1")
    assert res.status_code == 200
    assert res.json()["id"] == "run_api_1"

    # 3. Get run metrics
    res = client_with_db.get("/api/v1/runs/run_api_1/metrics")
    assert res.status_code == 200
    assert res.json()["sharpe"] == 1.5

    # 4. Get run equity
    res = client_with_db.get("/api/v1/runs/run_api_1/equity")
    assert res.status_code == 200
    assert len(res.json()) == 1

    # 5. Get run trades
    res = client_with_db.get("/api/v1/runs/run_api_1/trades")
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["symbol"] == "SPY"

    # 6. Compare runs POST
    res = client_with_db.post("/api/v1/compare", json={"run_ids": ["run_api_1", "run_api_2"]})
    assert res.status_code == 200
    comp_data = res.json()
    assert len(comp_data["runs"]) == 2
    assert comp_data["metrics_diff"]["sharpe"]["run_api_1"] == 1.5
    assert comp_data["metrics_diff"]["sharpe"]["run_api_2"] == 1.8

    # 7. Compare runs GET
    res = client_with_db.get("/api/v1/compare?run_ids=run_api_1,run_api_2")
    assert res.status_code == 200
    assert len(res.json()["runs"]) == 2
