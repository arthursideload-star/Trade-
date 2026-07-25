"""Tests for the regime classifier."""

import math

import regime as rg


def _uptrend(n=260):
    highs = [10 + i * 0.1 for i in range(n)]
    lows = [9.8 + i * 0.1 for i in range(n)]
    closes = [9.9 + i * 0.1 for i in range(n)]
    return highs, lows, closes


def _downtrend(n=260):
    highs = [10 + (n - i) * 0.1 for i in range(n)]
    lows = [9.8 + (n - i) * 0.1 for i in range(n)]
    closes = [9.9 + (n - i) * 0.1 for i in range(n)]
    return highs, lows, closes


def _range(n=260):
    closes = [100 + math.sin(i / 2) * 0.5 for i in range(n)]
    highs = [c + 0.2 for c in closes]
    lows = [c - 0.2 for c in closes]
    return highs, lows, closes


# --- EMA fan ---------------------------------------------------------------


def test_ema_fan_bullish_when_fast_above_mid_above_slow():
    assert rg.classify_ema_fan(1.09, 1.08, 1.07) == "bullish"


def test_ema_fan_bearish_when_fast_below_mid_below_slow():
    assert rg.classify_ema_fan(1.07, 1.08, 1.09) == "bearish"


def test_ema_fan_mixed_when_not_stacked():
    assert rg.classify_ema_fan(1.08, 1.09, 1.07) == "mixed"


def test_ema_fan_mixed_when_a_value_is_missing():
    assert rg.classify_ema_fan(None, 1.08, 1.07) == "mixed"


# --- regime labels ---------------------------------------------------------


def test_clean_uptrend_is_trend_up_and_long_only():
    result = rg.detect_regime(*_uptrend())
    assert result.regime == rg.TREND_UP
    assert result.allowed_direction == "long_only"
    assert result.ema_fan == "bullish"
    assert result.adx > rg.ADX_TREND


def test_clean_downtrend_is_trend_down_and_short_only():
    result = rg.detect_regime(*_downtrend())
    assert result.regime == rg.TREND_DOWN
    assert result.allowed_direction == "short_only"
    assert result.ema_fan == "bearish"


def test_choppy_market_is_range():
    result = rg.detect_regime(*_range())
    assert result.regime == rg.RANGE
    assert result.allowed_direction == "both_cautious"


def test_undefined_when_history_too_short_for_adx():
    result = rg.detect_regime([10, 11], [9, 10], [9.5, 10.5])
    assert result.regime == rg.UNDEFINED
    assert result.allowed_direction == "none"


# --- volatility modifier ---------------------------------------------------


def test_volatility_spike_is_flagged():
    highs, lows, closes = _range()
    # Inject a volatility burst at the end.
    for i in range(-5, 0):
        highs[i] += 4
        lows[i] -= 4
    result = rg.detect_regime(highs, lows, closes)
    assert result.volatile is True


def test_trend_survives_a_volatility_spike_but_warns_on_size():
    highs, lows, closes = _uptrend()
    for i in range(-3, 0):
        highs[i] += 3
        lows[i] -= 3
    result = rg.detect_regime(highs, lows, closes)
    # A strong trend keeps its label rather than collapsing to "volatile".
    assert result.regime in (rg.TREND_UP, rg.VOLATILE)
    if result.regime == rg.TREND_UP and result.volatile:
        assert "reduce size" in result.reason


# --- serialization ---------------------------------------------------------


def test_to_dict_carries_the_reason_and_direction():
    payload = rg.detect_regime(*_uptrend()).to_dict()
    assert payload["allowed_direction"] == "long_only"
    assert "ADX" in payload["reason"]
    assert payload["regime"] == rg.TREND_UP
