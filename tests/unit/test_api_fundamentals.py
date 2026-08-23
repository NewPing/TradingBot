"""Tests for FastAPI fundamentals and earnings calendar endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from atlas.api.main import app

client = TestClient(app)


def test_get_symbol_fundamentals_endpoint() -> None:
    res = client.get("/api/v1/fundamentals/AAPL")
    assert res.status_code == 200
    data = res.json()
    assert data["symbol"] == "AAPL"
    assert "quality_score" in data
    assert "value_score" in data
    assert "roic" in data
    assert "sloan_accrual" in data
    assert "rationale" in data


def test_get_earnings_calendar_endpoint() -> None:
    res = client.get("/api/v1/fundamentals/earnings/calendar?blackout_days_pre=2")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) > 0
    first = data[0]
    assert "symbol" in first
    assert "event_date" in first
    assert "blackout_status" in first
    assert "days_until_event" in first


def test_get_fundamental_screener_endpoint() -> None:
    res = client.get("/api/v1/fundamentals/screener/universe")
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "items" in data
    assert data["total"] > 0
    item = data["items"][0]
    assert "symbol" in item
    assert "quality_score" in item
    assert "value_score" in item
    assert "roic" in item
    assert "sector_zscore_quality" in item
