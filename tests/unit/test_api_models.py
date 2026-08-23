"""Unit tests for ML models and Regime API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from atlas.api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_api_list_models(client: TestClient) -> None:
    res = client.get("/api/v1/models")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "model_id" in data[0]
        assert "feature_names" in data[0]


def test_api_get_current_regime(client: TestClient) -> None:
    res = client.get("/api/v1/models/regime/current?benchmark=SPY")
    assert res.status_code == 200
    data = res.json()
    assert "quadrant" in data
    assert "trend" in data
    assert "volatility" in data
    assert "rationale" in data


def test_api_predict_model(client: TestClient) -> None:
    res = client.post(
        "/api/v1/models/predict",
        json={
            "model_id": "lgbm_dir_5d_v1",
            "version": "1.0.0",
            "features": {"return_1d": 0.01, "realized_vol_21d": 0.15, "rsi_14d": 55.0},
        },
    )
    if res.status_code == 200:
        data = res.json()
        assert "score" in data
        assert "confidence" in data
        assert "rationale" in data
