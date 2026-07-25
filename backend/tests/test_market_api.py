"""Tests for the dashboard API, including its delegation to the skill client."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_SKILL_SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "forex-data" / "scripts"
if str(_SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SKILL_SCRIPTS))

import twelvedata_client as td  # noqa: E402

from backend.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Keep tests off the real cache directory."""
    monkeypatch.setenv("FOREX_CACHE_DIR", str(tmp_path))


@pytest.fixture
def api_payload(monkeypatch):
    """Replace the HTTP layer of the skill client, newest candle first."""
    payload = {
        "meta": {
            "symbol": "EUR/USD",
            "interval": "15min",
            "currency_base": "Euro",
            "currency_quote": "US Dollar",
        },
        "values": [
            {
                "datetime": "2026-07-25 14:45:00",
                "open": "1.0845",
                "high": "1.0860",
                "low": "1.0844",
                "close": "1.0858",
            },
            {
                "datetime": "2026-07-25 14:30:00",
                "open": "1.0840",
                "high": "1.0850",
                "low": "1.0830",
                "close": "1.0845",
            },
        ],
        "status": "ok",
    }
    monkeypatch.setattr(td, "_http_get_json", lambda url: payload)
    return payload


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_pairs_lists_pairs_and_intervals_shortest_first():
    body = client.get("/api/market/pairs").json()

    assert "EUR/USD" in body["pairs"]
    assert body["intervals"] == ["5min", "15min", "1h", "4h"]


def test_candles_flow_through_and_arrive_oldest_first(api_payload):
    """End to end: HTTP layer -> skill client -> API response."""
    response = client.get("/api/market/candles", params={"symbol": "EUR/USD"})

    assert response.status_code == 200
    body = response.json()
    assert [c["datetime"] for c in body["candles"]] == [
        "2026-07-25 14:30:00",
        "2026-07-25 14:45:00",
    ]
    assert body["order"] == "ascending (oldest first)"


def test_candles_report_missing_volume_as_null(api_payload):
    body = client.get("/api/market/candles", params={"symbol": "EUR/USD"}).json()

    assert body["candles"][0]["volume"] is None


def test_candles_accept_a_symbol_without_slash(api_payload):
    response = client.get("/api/market/candles", params={"symbol": "EURUSD"})

    assert response.status_code == 200
    assert response.json()["symbol"] == "EUR/USD"


def test_unsupported_pair_is_rejected(api_payload):
    response = client.get("/api/market/candles", params={"symbol": "BTC/USD"})

    assert response.status_code == 502
    assert "Unsupported pair" in response.json()["detail"]


def test_unsupported_interval_is_rejected(api_payload):
    response = client.get(
        "/api/market/candles", params={"symbol": "EUR/USD", "interval": "7min"}
    )

    assert response.status_code == 502
    assert "Unsupported interval" in response.json()["detail"]


def test_rate_limit_is_reported_as_429(monkeypatch):
    def limited(url):
        raise td.RateLimitError("API credits exhausted")

    monkeypatch.setattr(td, "_http_get_json", limited)

    response = client.get("/api/market/candles", params={"symbol": "EUR/USD"})

    assert response.status_code == 429


def test_price_returns_the_latest_close_with_its_timestamp(api_payload):
    body = client.get("/api/market/price", params={"symbol": "EUR/USD"}).json()

    assert body["price"] == 1.0858
    assert body["as_of"] == "2026-07-25 14:45:00"
