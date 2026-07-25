"""End-to-end tests for the analyze CLI with a stubbed data feed."""

import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "forex-data" / "scripts"))

import analyze  # noqa: E402
import twelvedata_client as td  # noqa: E402


def _uptrend_payload(n=260):
    """A clean rising market so the analysis has a defined regime and levels."""
    values = []
    price = 1.0800
    for i in range(n):
        price = 1.0800 + i * 0.0005 + math.sin(i / 5) * 0.0008
        values.append(
            {
                "datetime": f"2026-07-{1 + i // 96:02d} {(i % 96) * 15 // 60:02d}:00:00",
                "open": f"{price - 0.0003:.5f}",
                "high": f"{price + 0.0006:.5f}",
                "low": f"{price - 0.0006:.5f}",
                "close": f"{price:.5f}",
            }
        )
    return {
        "meta": {
            "symbol": "EUR/USD",
            "interval": "15min",
            "currency_base": "Euro",
            "currency_quote": "US Dollar",
        },
        "values": values,
        "status": "ok",
    }


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("FOREX_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("TWELVEDATA_API_KEY", "test")


@pytest.fixture
def stub_feed(monkeypatch):
    monkeypatch.setattr(td, "_http_get_json", lambda url: _uptrend_payload())


def _run(monkeypatch, capsys, argv):
    monkeypatch.setattr("sys.argv", ["analyze.py", *argv])
    code = analyze.main()
    return code, capsys.readouterr()


def test_analyze_single_timeframe_produces_full_block(monkeypatch, capsys, stub_feed):
    code, captured = _run(monkeypatch, capsys, ["--symbol", "EUR/USD", "--interval", "15min"])

    assert code == 0
    payload = json.loads(captured.out)
    assert payload["symbol"] == "EUR/USD"
    block = payload["timeframes"][0]
    assert block["interval"] == "15min"
    assert "indicators" in block
    assert "regime" in block
    assert "levels" in block
    assert "patterns_at_level" in block


def test_indicators_are_populated(monkeypatch, capsys, stub_feed):
    _, captured = _run(monkeypatch, capsys, ["--symbol", "EUR/USD", "--interval", "15min"])
    indicators = json.loads(captured.out)["timeframes"][0]["indicators"]

    assert indicators["rsi_14"] is not None
    assert indicators["ema_200"] is not None  # 260 candles is enough for EMA200
    assert indicators["adx_14"] is not None


def test_regime_is_classified_not_undefined(monkeypatch, capsys, stub_feed):
    _, captured = _run(monkeypatch, capsys, ["--symbol", "EUR/USD", "--interval", "15min"])
    regime = json.loads(captured.out)["timeframes"][0]["regime"]

    assert regime["regime"] != "undefined"
    assert regime["allowed_direction"] in ("long_only", "short_only", "both_cautious", "reduced_size")


def test_default_covers_all_four_timeframes(monkeypatch, capsys, stub_feed):
    _, captured = _run(monkeypatch, capsys, ["--symbol", "EUR/USD"])
    payload = json.loads(captured.out)

    assert len(payload["timeframes"]) == 4


def test_text_format_is_human_readable(monkeypatch, capsys, stub_feed):
    _, captured = _run(
        monkeypatch, capsys, ["--symbol", "EUR/USD", "--interval", "15min", "--format", "text"]
    )

    assert "Analysis EUR/USD" in captured.out
    assert "Regime:" in captured.out


def test_stdout_is_valid_json_progress_on_stderr(monkeypatch, capsys, stub_feed):
    _, captured = _run(monkeypatch, capsys, ["--symbol", "EUR/USD", "--interval", "15min"])

    json.loads(captured.out)  # must not raise
    assert "Analyzing" in captured.err


def test_rate_limit_exits_with_code_2(monkeypatch, capsys):
    def limited(url):
        raise td.RateLimitError("credits exhausted")

    monkeypatch.setattr(td, "_http_get_json", limited)
    code, captured = _run(monkeypatch, capsys, ["--symbol", "EUR/USD", "--interval", "15min"])

    assert code == 2
    assert "Rate limit" in captured.err
