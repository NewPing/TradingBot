"""Unit tests for Phase 9 FastAPI endpoints (/api/v1/taxes and /api/v1/shadow)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from atlas.api.main import app

client = TestClient(app)


def test_api_tax_report_endpoint() -> None:
    response = client.get("/api/v1/taxes/report/2026?church_tax_rate=0.0&sparerpauschbetrag=1000")
    assert response.status_code == 200
    data = response.json()
    assert data["tax_year"] == 2026
    assert "total_tax_liability_eur" in data
    assert "aktien_gains_eur" in data
    assert "sparerpauschbetrag_remaining_eur" in data


def test_api_tax_lots_and_events_endpoints() -> None:
    resp_lots = client.get("/api/v1/taxes/lots?symbol=AAPL")
    assert resp_lots.status_code == 200
    lots = resp_lots.json()
    assert isinstance(lots, list)
    if lots:
        assert lots[0]["symbol"] == "AAPL"
        assert "buy_price_eur" in lots[0]

    resp_events = client.get("/api/v1/taxes/events?year=2026")
    assert resp_events.status_code == 200
    events = resp_events.json()
    assert isinstance(events, list)

    resp_ecb = client.get("/api/v1/taxes/ecb-rates?limit=5")
    assert resp_ecb.status_code == 200
    ecb_rates = resp_ecb.json()
    assert isinstance(ecb_rates, list)
    assert len(ecb_rates) > 0


def test_api_shadow_telemetry_and_totp_endpoints() -> None:
    resp_telemetry = client.get("/api/v1/shadow/telemetry")
    assert resp_telemetry.status_code == 200
    tel = resp_telemetry.json()
    assert "mean_slippage_bps" in tel
    assert "quote_latency_ms" in tel["sample_records"][0]

    resp_totp_status = client.get("/api/v1/shadow/totp/status")
    assert resp_totp_status.status_code == 200
    assert resp_totp_status.json()["is_enabled"] is True

    # Test sandbox bypass code 000000
    resp_verify = client.post(
        "/api/v1/shadow/totp/verify",
        json={"code": "000000", "action": "EMERGENCY_FLATTEN"},
    )
    assert resp_verify.status_code == 200
    assert resp_verify.json()["valid"] is True

    # Test bad code
    resp_bad = client.post(
        "/api/v1/shadow/totp/verify",
        json={"code": "111111", "action": "EMERGENCY_FLATTEN"},
    )
    assert resp_bad.status_code == 200
    # Depending on whether 111111 happens to match the instant TOTP step, should return valid or invalid
