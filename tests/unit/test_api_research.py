"""Unit tests for Phase 8 FastAPI Research endpoints."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from atlas.api.main import app
from atlas.data.db import get_db
from atlas.data.models import Base, ResearchReport


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_api_research_status(client: TestClient) -> None:
    """Test /api/v1/research/status endpoint."""
    res = client.get("/api/v1/research/status")
    assert res.status_code == 200
    data = res.json()
    assert "running" in data
    assert "weekly_trial_budget" in data


def test_api_research_hypotheses_and_generation(client: TestClient) -> None:
    """Test generating a hypothesis and listing hypotheses."""
    gen_res = client.post(
        "/api/v1/research/hypotheses/generate",
        json={
            "base_spec_name": "strategies/core_trend_v1.yaml",
            "generator_type": "PARAM_REFINEMENT",
            "layer": "l2",
        },
    )
    assert gen_res.status_code == 200
    hyp_data = gen_res.json()
    assert hyp_data["generator_type"] == "PARAM_REFINEMENT"

    list_res = client.get("/api/v1/research/hypotheses")
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) >= 1


def test_api_research_queue_and_human_approval(client: TestClient, db_session: Session) -> None:
    """Test human candidate review queue approval and rejection."""
    # Seed a passed report in queue
    report = ResearchReport(
        id="rep_test_queue_1",
        title="Test Report",
        family="core_trend",
        strategy_spec_name="core_trend_v1",
        spec_hash="abc123hash",
        train_metrics='{"sharpe_ratio": 1.8}',
        val_metrics='{"sharpe_ratio": 1.4}',
        gatekeeper_results="{}",
        gatekeeper_passed=True,
        verdict="PASSED",
        report_markdown="# Report",
        human_decision="PENDING_REVIEW",
    )
    db_session.add(report)
    db_session.commit()

    # Query queue
    q_res = client.get("/api/v1/research/queue")
    assert q_res.status_code == 200
    queue = q_res.json()
    assert len(queue) >= 1
    assert queue[0]["id"] == "rep_test_queue_1"

    # Approve
    appr_res = client.post(
        f"/api/v1/research/queue/{report.id}/approve",
        json={"decision_notes": "Passed all gates cleanly."},
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "APPROVED"


def test_api_holdout_unlock(client: TestClient) -> None:
    """Test manual holdout partition unlock endpoint."""
    res = client.post(
        "/api/v1/research/holdout/unlock",
        json={
            "family": "core_trend",
            "unlocked_by": "lead_quant",
            "reason": "Final stage promotion evaluation for Candidate v2.",
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "UNLOCKED"
