"""Tests for the fetch_candles command line entry point."""

import json

import pytest

import fetch_candles
import twelvedata_client as td


def _series(interval="15min", warnings=None, from_cache=False):
    return td.CandleSeries(
        symbol="EUR/USD",
        interval=interval,
        candles=[
            td.Candle("2026-07-25 14:30:00", 1.0840, 1.0850, 1.0830, 1.0845),
            td.Candle("2026-07-25 14:45:00", 1.0845, 1.0860, 1.0844, 1.0858),
        ],
        currency_base="Euro",
        currency_quote="US Dollar",
        from_cache=from_cache,
        warnings=warnings or [],
    )


# --- interval parsing ------------------------------------------------------


def test_parse_intervals_normalizes_the_plan_vocabulary():
    assert fetch_candles.parse_intervals("5m,15m,1h,4h") == ["5min", "15min", "1h", "4h"]


def test_parse_intervals_handles_whitespace_and_duplicates():
    assert fetch_candles.parse_intervals(" 15m , 15min,1h ") == ["15min", "1h"]


def test_parse_intervals_rejects_an_unsupported_entry():
    with pytest.raises(td.TwelveDataError, match="Unsupported interval"):
        fetch_candles.parse_intervals("15m,3m")


def test_parse_intervals_rejects_empty_input():
    with pytest.raises(td.TwelveDataError):
        fetch_candles.parse_intervals("  ,  ")


# --- text output -----------------------------------------------------------


def test_format_text_shows_pair_interval_and_latest_close():
    text = fetch_candles.format_text([_series()])

    assert "EUR/USD" in text
    assert "15min" in text
    assert "1.0858" in text


def test_format_text_marks_cached_results():
    assert "cache" in fetch_candles.format_text([_series(from_cache=True)])


def test_format_text_surfaces_warnings():
    text = fetch_candles.format_text([_series(warnings=["duplicate timestamps: x"])])

    assert "WARNING: duplicate timestamps" in text


def test_format_text_renders_missing_volume_as_dash():
    assert " V -" in fetch_candles.format_text([_series()])


# --- main ------------------------------------------------------------------


def _run(monkeypatch, capsys, argv, fetch=None):
    monkeypatch.setattr("sys.argv", ["fetch_candles.py", *argv])
    monkeypatch.setattr(td, "fetch_candles", fetch or (lambda **kwargs: _series()))
    code = fetch_candles.main()
    return code, capsys.readouterr()


def test_main_writes_a_single_object_for_one_interval(monkeypatch, capsys):
    code, captured = _run(monkeypatch, capsys, ["--symbol", "EUR/USD", "--interval", "15min"])

    assert code == 0
    payload = json.loads(captured.out)
    assert payload["symbol"] == "EUR/USD"
    assert payload["count"] == 2


def test_main_writes_a_list_for_several_intervals(monkeypatch, capsys):
    code, captured = _run(monkeypatch, capsys, ["--symbol", "EUR/USD", "--interval", "15m,1h"])

    assert code == 0
    payload = json.loads(captured.out)
    assert isinstance(payload, list)
    assert len(payload) == 2


def test_main_output_declares_the_candle_order(monkeypatch, capsys):
    """Downstream sprints must not have to guess the direction."""
    _, captured = _run(monkeypatch, capsys, ["--symbol", "EUR/USD", "--interval", "15min"])

    assert json.loads(captured.out)["order"] == "ascending (oldest first)"


def test_main_reports_rate_limit_with_exit_code_2(monkeypatch, capsys):
    def limited(**kwargs):
        raise td.RateLimitError("API credits exhausted")

    code, captured = _run(monkeypatch, capsys, ["--symbol", "EUR/USD"], fetch=limited)

    assert code == 2
    assert "Rate limit" in captured.err


def test_main_reports_other_errors_with_exit_code_1(monkeypatch, capsys):
    def failing(**kwargs):
        raise td.TwelveDataError("Invalid API key")

    code, captured = _run(monkeypatch, capsys, ["--symbol", "EUR/USD"], fetch=failing)

    assert code == 1
    assert "Invalid API key" in captured.err


def test_main_rejects_a_bad_interval_before_calling_the_api(monkeypatch, capsys):
    def fail(**kwargs):
        raise AssertionError("must not reach the API")

    code, captured = _run(monkeypatch, capsys, ["--symbol", "EUR/USD", "--interval", "7m"], fail)

    assert code == 1
    assert "Unsupported interval" in captured.err


def test_main_keeps_stdout_clean_for_piping(monkeypatch, capsys):
    """Progress goes to stderr so stdout stays valid JSON."""
    _, captured = _run(monkeypatch, capsys, ["--symbol", "EUR/USD", "--interval", "15min"])

    json.loads(captured.out)
    assert "Fetching" in captured.err


def test_main_can_write_to_a_file(monkeypatch, capsys, tmp_path):
    target = tmp_path / "candles.json"

    code, _ = _run(
        monkeypatch, capsys, ["--symbol", "EUR/USD", "--interval", "15min", "-o", str(target)]
    )

    assert code == 0
    assert json.loads(target.read_text(encoding="utf-8"))["symbol"] == "EUR/USD"
