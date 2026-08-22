"""Unit tests for API /health and /version endpoints."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from atlas import __version__
from atlas.api.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == __version__
    assert "timestamp" in data
    assert data["environment"] in ("dev", "research", "live")


def test_version_endpoint(client: TestClient) -> None:
    response = client.get("/version")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == __version__
    assert data["phase"] == 0
    assert data["allow_live"] is False
