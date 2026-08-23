"""Unit tests for Live/Paper and Risk API router endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from atlas.api.main import app
from atlas.data.db import get_engine
from atlas.data.models import Base

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db() -> None:
    Base.metadata.create_all(get_engine())


def test_api_live_state() -> None:
    response = client.get("/api/v1/live/state")
    assert response.status_code == 200
    data = response.json()
    assert "total_equity" in data
    assert "cash" in data
    assert "buckets" in data
    assert len(data["buckets"]) >= 4


def test_api_live_positions_and_orders() -> None:
    resp_pos = client.get("/api/v1/live/positions")
    assert resp_pos.status_code == 200
    assert isinstance(resp_pos.json(), list)

    resp_ord = client.get("/api/v1/live/orders")
    assert resp_ord.status_code == 200
    assert isinstance(resp_ord.json(), list)

    resp_fills = client.get("/api/v1/live/fills")
    assert resp_fills.status_code == 200
    assert isinstance(resp_fills.json(), list)


def test_api_risk_status_and_emergency_controls() -> None:
    # 1. Check initial status
    resp = client.get("/api/v1/risk/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "is_halted" in data
    assert "active_switches" in data

    # 2. Trigger emergency flatten
    resp_flat = client.post(
        "/api/v1/risk/emergency-flatten",
        json={"reason": "Test API Emergency Flatten"},
    )
    assert resp_flat.status_code == 200
    flat_data = resp_flat.json()
    assert flat_data["is_halted"] is True
    assert len(flat_data["active_switches"]) >= 1

    # 3. Reset kill switch
    resp_reset = client.post(
        "/api/v1/risk/reset",
        json={"trigger": "MANUAL_EMERGENCY", "resolved_by": "test_operator"},
    )
    assert resp_reset.status_code == 200
    reset_data = resp_reset.json()
    assert reset_data["is_halted"] is False
