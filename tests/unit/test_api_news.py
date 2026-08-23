"""Unit tests for FastAPI News and Narrative endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from atlas.api.main import app

client = TestClient(app)


def test_get_news_feed() -> None:
    resp = client.get("/api/v1/news/feed")
    assert resp.status_code == 200
    data = resp.json()
    assert "articles" in data
    assert len(data["articles"]) > 0
    assert "score" in data["articles"][0]


def test_get_symbol_sentiment() -> None:
    resp = client.get("/api/v1/news/sentiment/NVDA")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "NVDA"
    assert "composite_sentiment" in data
    assert "narrative_momentum" in data


def test_get_prompt_templates() -> None:
    resp = client.get("/api/v1/news/prompts")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["version"] == "v1.0"


def test_get_news_stats() -> None:
    resp = client.get("/api/v1/news/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "llm_model" in data
    assert "p95_latency_ms" in data


def test_post_score_news_on_demand() -> None:
    payload = {
        "symbols": ["AAPL"],
        "title": "Apple launches breakthrough hardware and records revenue beat",
        "summary": "Record hardware revenue driven by strong upgrade cycles.",
    }
    resp = client.post("/api/v1/news/score", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["sentiment_score"] > 0.0
    assert data["impact"] == "BULLISH"
    assert "latency_ms" in data
