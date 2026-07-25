"""Tests for the technical indicators."""

import math

import pytest

import indicators as ind


# --- SMA -------------------------------------------------------------------


def test_sma_matches_hand_computation():
    assert ind.sma([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]


def test_sma_is_none_before_enough_history():
    result = ind.sma([1, 2, 3], 3)
    assert result[:2] == [None, None]
    assert result[2] == 2.0


def test_sma_rejects_zero_period():
    with pytest.raises(ValueError):
        ind.sma([1, 2, 3], 0)


# --- EMA -------------------------------------------------------------------


def test_ema_is_seeded_with_the_simple_average():
    # seed = mean(1,2,3) = 2 at index 2
    result = ind.ema([1, 2, 3, 4, 10], 3)
    assert result[2] == 2.0


def test_ema_reacts_to_a_jump_more_than_sma():
    values = [1, 2, 3, 4, 10]
    ema_last = ind.ema(values, 3)[-1]
    # idx3 = (4-2)*0.5+2 = 3 ; idx4 = (10-3)*0.5+3 = 6.5
    assert ema_last == pytest.approx(6.5)


def test_ema_none_when_series_shorter_than_period():
    assert ind.ema([1, 2], 5) == [None, None]


# --- Wilder RMA ------------------------------------------------------------


def test_wilder_rma_seed_is_simple_mean():
    result = ind.wilder_rma([2, 2, 2, 2, 2], 3)
    assert result[2] == 2.0
    assert result[-1] == pytest.approx(2.0)


# --- RSI -------------------------------------------------------------------


def test_rsi_is_100_when_every_bar_closes_higher():
    closes = list(range(1, 30))
    rsi = ind.rsi(closes, 14)
    assert ind.last_defined(rsi) == pytest.approx(100.0)


def test_rsi_is_low_when_every_bar_closes_lower():
    closes = list(range(30, 1, -1))
    rsi = ind.rsi(closes, 14)
    assert ind.last_defined(rsi) == pytest.approx(0.0)


def test_rsi_stays_within_bounds():
    closes = [math.sin(i / 3) * 5 + 100 for i in range(80)]
    for value in ind.rsi(closes, 14):
        if value is not None:
            assert 0.0 <= value <= 100.0


def test_rsi_first_value_lands_at_index_period():
    closes = [100 + (i % 3) for i in range(40)]
    rsi = ind.rsi(closes, 14)
    assert rsi[13] is None
    assert rsi[14] is not None


# --- ATR -------------------------------------------------------------------


def test_atr_of_constant_range_equals_that_range():
    highs = [11] * 20
    lows = [10] * 20
    closes = [10.5] * 20
    assert ind.last_defined(ind.atr(highs, lows, closes, 14)) == pytest.approx(1.0)


def test_true_range_first_bar_uses_high_low():
    tr = ind.true_range([11, 12], [10, 11], [10.5, 11.5])
    assert tr[0] == 1.0


def test_true_range_accounts_for_gaps():
    # Gap up: prev close 10, this bar high 15 low 14 -> range from prev close is 5
    tr = ind.true_range([11, 15], [10, 14], [10, 14.5])
    assert tr[1] == pytest.approx(5.0)


# --- MACD ------------------------------------------------------------------


def test_macd_histogram_is_line_minus_signal():
    closes = [100 + math.sin(i / 4) * 3 for i in range(80)]
    result = ind.macd(closes)
    for line, signal, hist in zip(result["macd"], result["signal"], result["histogram"]):
        if hist is not None:
            assert hist == pytest.approx(line - signal)


def test_macd_rejects_fast_not_smaller_than_slow():
    with pytest.raises(ValueError):
        ind.macd([1.0] * 50, fast=26, slow=12)


# --- Bollinger -------------------------------------------------------------


def test_bollinger_bands_are_symmetric_around_the_mean():
    closes = [100 + math.sin(i / 5) * 2 for i in range(60)]
    bands = ind.bollinger_bands(closes, 20, 2.0)
    for upper, middle, lower in zip(bands["upper"], bands["middle"], bands["lower"]):
        if middle is not None:
            assert middle - lower == pytest.approx(upper - middle)


def test_bollinger_width_is_zero_for_a_flat_series():
    closes = [100.0] * 30
    bands = ind.bollinger_bands(closes, 20, 2.0)
    assert bands["upper"][-1] == pytest.approx(bands["lower"][-1])


# --- Stochastic ------------------------------------------------------------


def test_stochastic_is_100_at_the_top_of_the_range():
    highs = [10 + i * 0.1 for i in range(20)]
    lows = [9 + i * 0.1 for i in range(20)]
    closes = list(highs)  # close at the high each bar
    stoch = ind.stochastic(highs, lows, closes, 14, 3)
    assert ind.last_defined(stoch["k"]) == pytest.approx(100.0)


def test_stochastic_k_is_none_for_a_flat_window():
    highs = [10.0] * 20
    lows = [10.0] * 20
    closes = [10.0] * 20
    stoch = ind.stochastic(highs, lows, closes, 14, 3)
    assert stoch["k"][-1] is None


# --- ADX -------------------------------------------------------------------


def test_adx_is_high_in_a_strong_uptrend():
    highs = [10 + i for i in range(60)]
    lows = [9 + i for i in range(60)]
    closes = [9.5 + i for i in range(60)]
    result = ind.adx(highs, lows, closes, 14)
    assert ind.last_defined(result["adx"]) > 40


def test_adx_plus_di_dominates_in_an_uptrend():
    highs = [10 + i for i in range(60)]
    lows = [9 + i for i in range(60)]
    closes = [9.5 + i for i in range(60)]
    result = ind.adx(highs, lows, closes, 14)
    assert ind.last_defined(result["plus_di"]) > ind.last_defined(result["minus_di"])


def test_adx_minus_di_dominates_in_a_downtrend():
    highs = [70 - i for i in range(60)]
    lows = [69 - i for i in range(60)]
    closes = [69.5 - i for i in range(60)]
    result = ind.adx(highs, lows, closes, 14)
    assert ind.last_defined(result["minus_di"]) > ind.last_defined(result["plus_di"])


def test_adx_values_stay_within_bounds():
    highs = [10 + math.sin(i / 3) for i in range(80)]
    lows = [9 + math.sin(i / 3) for i in range(80)]
    closes = [9.5 + math.sin(i / 3) for i in range(80)]
    result = ind.adx(highs, lows, closes, 14)
    for value in result["adx"]:
        if value is not None:
            assert 0.0 <= value <= 100.0


# --- helpers ---------------------------------------------------------------


def test_last_defined_finds_the_final_number():
    assert ind.last_defined([None, 1.0, 2.0, None]) == 2.0


def test_last_defined_returns_none_for_all_none():
    assert ind.last_defined([None, None]) is None
