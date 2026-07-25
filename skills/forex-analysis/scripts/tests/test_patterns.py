"""Tests for candlestick patterns and failed-breakout detection."""

import levels as levels_mod
import patterns as pt


# --- single-bar geometry ---------------------------------------------------


def test_hammer_has_long_lower_wick_and_small_body():
    # open 1.1050, close 1.1052 (tiny body near top), low 1.1000 (long lower wick)
    c = pt.Candle(open=1.1050, high=1.1053, low=1.1000, close=1.1052)
    assert pt.is_hammer(c) is True


def test_not_a_hammer_when_body_is_large():
    c = pt.Candle(open=1.1000, high=1.1055, low=1.0995, close=1.1050)
    assert pt.is_hammer(c) is False


def test_shooting_star_has_long_upper_wick():
    c = pt.Candle(open=1.1002, high=1.1050, low=1.1000, close=1.1001)
    assert pt.is_shooting_star(c) is True


def test_doji_has_a_tiny_body():
    c = pt.Candle(open=1.1000, high=1.1020, low=1.0980, close=1.1001)
    assert pt.is_doji(c) is True


def test_doji_false_for_a_decisive_bar():
    c = pt.Candle(open=1.1000, high=1.1050, low=1.0999, close=1.1048)
    assert pt.is_doji(c) is False


# --- two-bar patterns ------------------------------------------------------


def test_bullish_engulfing():
    prev = pt.Candle(open=1.1020, high=1.1025, low=1.1000, close=1.1005)  # down
    cur = pt.Candle(open=1.1000, high=1.1035, low=1.0998, close=1.1030)  # up, engulfs
    assert pt.is_bullish_engulfing(prev, cur) is True


def test_bearish_engulfing():
    prev = pt.Candle(open=1.1000, high=1.1030, low=1.0998, close=1.1025)  # up
    cur = pt.Candle(open=1.1028, high=1.1030, low=1.0995, close=1.0999)  # down, engulfs
    assert pt.is_bearish_engulfing(prev, cur) is True


def test_engulfing_requires_the_second_body_to_be_larger():
    prev = pt.Candle(open=1.1020, high=1.1025, low=1.1000, close=1.1005)
    small = pt.Candle(open=1.1006, high=1.1012, low=1.1004, close=1.1010)
    assert pt.is_bullish_engulfing(prev, small) is False


# --- three-bar stars -------------------------------------------------------


def test_morning_star_is_bullish_reversal():
    a = pt.Candle(open=1.1050, high=1.1052, low=1.1010, close=1.1015)  # strong down
    b = pt.Candle(open=1.1012, high=1.1016, low=1.1008, close=1.1011)  # small
    c = pt.Candle(open=1.1014, high=1.1045, low=1.1013, close=1.1040)  # strong up
    assert pt.is_morning_star(a, b, c) is True


def test_evening_star_is_bearish_reversal():
    a = pt.Candle(open=1.1010, high=1.1050, low=1.1008, close=1.1045)  # strong up
    b = pt.Candle(open=1.1046, high=1.1050, low=1.1042, close=1.1047)  # small
    c = pt.Candle(open=1.1044, high=1.1046, low=1.1010, close=1.1015)  # strong down
    assert pt.is_evening_star(a, b, c) is True


# --- detect_patterns dispatch ----------------------------------------------


def test_detect_finds_a_hammer_on_the_last_bar():
    opens = [1.10, 1.1050]
    highs = [1.1010, 1.1053]
    lows = [1.0990, 1.1000]
    closes = [1.1005, 1.1052]
    names = {p.name for p in pt.detect_patterns(highs, lows, opens, closes)}
    assert "hammer" in names


def test_detect_empty_for_no_bars():
    assert pt.detect_patterns([], [], [], []) == []


# --- the "only at a level" rule --------------------------------------------


def _report_with_support(price):
    return levels_mod.LevelReport(
        supports=[levels_mod.Level(price=price, kind="support", touches=3)],
        resistances=[],
        nearest_support=None,
        nearest_resistance=None,
        distance_to_support_pips=None,
        distance_to_resistance_pips=None,
        pivot=None,
    )


def test_pattern_at_a_level_is_kept():
    # Hammer whose low (1.1000) sits right on a support at 1.1000.
    opens = [1.1050]
    highs = [1.1053]
    lows = [1.1000]
    closes = [1.1052]
    report = _report_with_support(1.1000)
    kept = pt.patterns_at_level(highs, lows, opens, closes, report, "EUR/USD", proximity_pips=10)
    assert any(p.name == "hammer" and p.at_level for p in kept)


def test_pattern_far_from_any_level_is_dropped():
    # Same hammer, but the only support is 200 pips away.
    opens = [1.1050]
    highs = [1.1053]
    lows = [1.1000]
    closes = [1.1052]
    report = _report_with_support(1.0800)
    kept = pt.patterns_at_level(highs, lows, opens, closes, report, "EUR/USD", proximity_pips=10)
    assert kept == []


# --- failed breakout -------------------------------------------------------


def _report_with_resistance(price):
    return levels_mod.LevelReport(
        supports=[],
        resistances=[levels_mod.Level(price=price, kind="resistance", touches=3)],
        nearest_support=None,
        nearest_resistance=None,
        distance_to_support_pips=None,
        distance_to_resistance_pips=None,
        pivot=None,
    )


def test_failed_break_above_resistance_is_bearish():
    # High pokes above 1.1000 resistance by 5 pips, closes back below.
    opens = [1.0990]
    highs = [1.1005]
    lows = [1.0988]
    closes = [1.0995]
    report = _report_with_resistance(1.1000)
    fb = pt.detect_failed_breakout(highs, lows, opens, closes, report, "EUR/USD", sweep_pips=3)
    assert fb is not None
    assert fb.direction == "bearish"
    assert fb.level_price == 1.1000


def test_failed_break_below_support_is_bullish():
    opens = [1.1010]
    highs = [1.1012]
    lows = [1.0995]  # 5 pips below the 1.1000 support
    closes = [1.1005]  # reclaimed
    report = _report_with_support(1.1000)
    fb = pt.detect_failed_breakout(highs, lows, opens, closes, report, "EUR/USD", sweep_pips=3)
    assert fb is not None
    assert fb.direction == "bullish"


def test_clean_break_is_not_a_failed_breakout():
    # High pokes above and CLOSES above -> a real break, not a trap.
    opens = [1.0995]
    highs = [1.1010]
    lows = [1.0993]
    closes = [1.1008]
    report = _report_with_resistance(1.1000)
    fb = pt.detect_failed_breakout(highs, lows, opens, closes, report, "EUR/USD", sweep_pips=3)
    assert fb is None


def test_small_poke_below_sweep_threshold_is_ignored():
    # High only 1 pip above resistance; below the 3-pip sweep requirement.
    opens = [1.0998]
    highs = [1.1001]
    lows = [1.0996]
    closes = [1.0999]
    report = _report_with_resistance(1.1000)
    fb = pt.detect_failed_breakout(highs, lows, opens, closes, report, "EUR/USD", sweep_pips=3)
    assert fb is None
