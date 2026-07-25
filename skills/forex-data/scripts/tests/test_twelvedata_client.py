"""Tests for the Twelve Data client."""

import pytest

import twelvedata_client as td


def _payload(values, meta=None):
    return {
        "meta": meta
        or {
            "symbol": "EUR/USD",
            "interval": "15min",
            "currency_base": "Euro",
            "currency_quote": "US Dollar",
        },
        "values": values,
        "status": "ok",
    }


def _value(datetime_, open_="1.0840", high="1.0850", low="1.0830", close="1.0845", **extra):
    entry = {"datetime": datetime_, "open": open_, "high": high, "low": low, "close": close}
    entry.update(extra)
    return entry


# --- symbol and interval normalization -------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("EUR/USD", "EUR/USD"),
        ("eur/usd", "EUR/USD"),
        ("EURUSD", "EUR/USD"),
        ("eurusd", "EUR/USD"),
        ("EUR-USD", "EUR/USD"),
        ("  usd/jpy  ", "USD/JPY"),
    ],
)
def test_normalize_symbol_accepts_common_spellings(raw, expected):
    assert td.normalize_symbol(raw) == expected


@pytest.mark.parametrize("raw", ["BTC/USD", "EUR/XXX", "nonsense"])
def test_normalize_symbol_rejects_unsupported_pairs(raw):
    with pytest.raises(td.TwelveDataError, match="Unsupported pair"):
        td.normalize_symbol(raw)


@pytest.mark.parametrize(
    "raw,expected",
    [("5m", "5min"), ("5min", "5min"), ("15m", "15min"), ("1h", "1h"), ("4H", "4h")],
)
def test_normalize_interval_accepts_plan_vocabulary(raw, expected):
    """The plan documents write 5m/15m/1h/4h; the API wants 5min/15min."""
    assert td.normalize_interval(raw) == expected


@pytest.mark.parametrize("raw", ["3m", "1week", ""])
def test_normalize_interval_rejects_unsupported(raw):
    with pytest.raises(td.TwelveDataError, match="Unsupported interval"):
        td.normalize_interval(raw)


# --- parsing ---------------------------------------------------------------


def test_parse_returns_candles_oldest_first_even_when_api_sends_newest_first():
    """Twelve Data answers newest first by default; indicators need the reverse."""
    payload = _payload(
        [
            _value("2026-07-25 15:00:00", close="1.0860"),
            _value("2026-07-25 14:45:00", close="1.0850"),
            _value("2026-07-25 14:30:00", close="1.0840"),
        ]
    )

    series = td.parse_time_series(payload, "EUR/USD", "15min")

    assert [c.datetime for c in series.candles] == [
        "2026-07-25 14:30:00",
        "2026-07-25 14:45:00",
        "2026-07-25 15:00:00",
    ]
    assert series.candles[-1].close == 1.0860


def test_parse_keeps_volume_none_when_feed_reports_none():
    """Forex has no exchange volume; a fabricated 0.0 would read as real data."""
    series = td.parse_time_series(_payload([_value("2026-07-25 14:30:00")]), "EUR/USD", "15min")

    assert series.candles[0].volume is None


def test_parse_reads_volume_when_present():
    payload = _payload([_value("2026-07-25 14:30:00", volume="1234")])

    series = td.parse_time_series(payload, "EUR/USD", "15min")

    assert series.candles[0].volume == 1234.0


def test_parse_converts_price_strings_to_floats():
    series = td.parse_time_series(_payload([_value("2026-07-25 14:30:00")]), "EUR/USD", "15min")
    candle = series.candles[0]

    assert (candle.open, candle.high, candle.low, candle.close) == (1.0840, 1.0850, 1.0830, 1.0845)


def test_parse_carries_metadata():
    series = td.parse_time_series(_payload([_value("2026-07-25 14:30:00")]), "EUR/USD", "15min")

    assert series.currency_base == "Euro"
    assert series.currency_quote == "US Dollar"


def test_parse_raises_on_api_error_status():
    payload = {"status": "error", "code": 401, "message": "Invalid API key"}

    with pytest.raises(td.TwelveDataError, match="Invalid API key"):
        td.parse_time_series(payload, "EUR/USD", "15min")


def test_parse_raises_rate_limit_error_on_code_429():
    payload = {"status": "error", "code": 429, "message": "API credits exhausted"}

    with pytest.raises(td.RateLimitError):
        td.parse_time_series(payload, "EUR/USD", "15min")


def test_parse_raises_on_empty_values_and_mentions_market_hours():
    with pytest.raises(td.TwelveDataError, match="market may be closed"):
        td.parse_time_series(_payload([]), "EUR/USD", "15min")


def test_parse_raises_on_non_numeric_price():
    payload = _payload([_value("2026-07-25 14:30:00", close="n/a")])

    with pytest.raises(td.TwelveDataError, match="not a number"):
        td.parse_time_series(payload, "EUR/USD", "15min")


# --- validation ------------------------------------------------------------


def test_validate_flags_high_below_low():
    candles = [td.Candle("2026-07-25 14:30:00", 1.084, 1.080, 1.085, 1.084)]

    assert any("below low" in w for w in td.validate_candles(candles))


def test_validate_flags_close_outside_high_low_range():
    candles = [td.Candle("2026-07-25 14:30:00", 1.084, 1.085, 1.083, 1.090)]

    assert any("outside the high-low range" in w for w in td.validate_candles(candles))


def test_validate_flags_duplicate_timestamps():
    candles = [
        td.Candle("2026-07-25 14:30:00", 1.084, 1.085, 1.083, 1.084),
        td.Candle("2026-07-25 14:30:00", 1.084, 1.085, 1.083, 1.084),
    ]

    assert any("duplicate timestamps" in w for w in td.validate_candles(candles))


def test_validate_accepts_clean_candles():
    candles = [td.Candle("2026-07-25 14:30:00", 1.084, 1.085, 1.083, 1.0845)]

    assert td.validate_candles(candles) == []


def test_warnings_reach_the_series():
    payload = _payload([_value("2026-07-25 14:30:00", high="1.0800", low="1.0900")])

    series = td.parse_time_series(payload, "EUR/USD", "15min")

    assert series.warnings


# --- fetching --------------------------------------------------------------


def test_fetch_requests_ascending_order_and_normalized_parameters(tmp_path):
    seen = {}

    def fake_get(url):
        seen["url"] = url
        return _payload([_value("2026-07-25 14:30:00")])

    td.fetch_candles(
        symbol="eurusd",
        interval="15m",
        outputsize=300,
        api_key="key",
        cache_dir=tmp_path,
        http_get=fake_get,
    )

    url = seen["url"]
    assert "order=ASC" in url
    assert "symbol=EUR%2FUSD" in url
    assert "interval=15min" in url
    assert "outputsize=300" in url
    assert "timezone=UTC" in url


def test_fetch_defaults_to_300_candles_for_ema200_warmup(tmp_path):
    seen = {}

    def fake_get(url):
        seen["url"] = url
        return _payload([_value("2026-07-25 14:30:00")])

    td.fetch_candles(
        symbol="EUR/USD", interval="1h", api_key="key", cache_dir=tmp_path, http_get=fake_get
    )

    assert f"outputsize={td.DEFAULT_OUTPUTSIZE}" in seen["url"]
    assert td.DEFAULT_OUTPUTSIZE >= 250


def test_fetch_second_call_is_served_from_cache(tmp_path):
    calls = []

    def fake_get(url):
        calls.append(url)
        return _payload([_value("2026-07-25 14:30:00")])

    kwargs = dict(
        symbol="EUR/USD", interval="15min", api_key="key", cache_dir=tmp_path, http_get=fake_get
    )
    first = td.fetch_candles(**kwargs)
    second = td.fetch_candles(**kwargs)

    assert len(calls) == 1
    assert first.from_cache is False
    assert second.from_cache is True
    assert [c.datetime for c in second.candles] == [c.datetime for c in first.candles]


def test_fetch_with_cache_disabled_always_calls_the_api(tmp_path):
    calls = []

    def fake_get(url):
        calls.append(url)
        return _payload([_value("2026-07-25 14:30:00")])

    kwargs = dict(
        symbol="EUR/USD",
        interval="15min",
        api_key="key",
        cache_dir=tmp_path,
        use_cache=False,
        http_get=fake_get,
    )
    td.fetch_candles(**kwargs)
    td.fetch_candles(**kwargs)

    assert len(calls) == 2


def test_fetch_rejects_out_of_range_outputsize(tmp_path):
    with pytest.raises(td.TwelveDataError, match="outputsize must be"):
        td.fetch_candles(
            symbol="EUR/USD",
            interval="15min",
            outputsize=99999,
            api_key="key",
            cache_dir=tmp_path,
            http_get=lambda url: _payload([]),
        )


def test_fetch_validates_symbol_before_spending_a_credit(tmp_path):
    def fail(url):
        raise AssertionError("must not reach the API")

    with pytest.raises(td.TwelveDataError, match="Unsupported pair"):
        td.fetch_candles(
            symbol="BTC/USD", interval="15min", api_key="key", cache_dir=tmp_path, http_get=fail
        )


# --- api key ---------------------------------------------------------------


def test_get_api_key_prefers_explicit_value(monkeypatch):
    monkeypatch.setenv("TWELVEDATA_API_KEY", "from-env")

    assert td.get_api_key("explicit") == "explicit"


def test_get_api_key_falls_back_to_environment(monkeypatch):
    monkeypatch.setenv("TWELVEDATA_API_KEY", "from-env")

    assert td.get_api_key() == "from-env"


def test_get_api_key_error_names_the_variable(monkeypatch):
    monkeypatch.delenv("TWELVEDATA_API_KEY", raising=False)

    with pytest.raises(td.TwelveDataError, match="TWELVEDATA_API_KEY"):
        td.get_api_key()
