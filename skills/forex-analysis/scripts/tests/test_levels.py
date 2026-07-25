"""Tests for support/resistance level detection."""

import levels as lv


# --- pip size --------------------------------------------------------------


def test_pip_size_is_smaller_for_non_jpy_pairs():
    assert lv.pip_size("EUR/USD") == 0.0001


def test_pip_size_is_larger_for_jpy_pairs():
    assert lv.pip_size("USD/JPY") == 0.01


# --- swing detection -------------------------------------------------------


def test_swing_high_is_the_local_peak():
    highs = [1, 2, 3, 2, 1]
    assert lv.find_swing_highs(highs, window=2) == [2]


def test_swing_low_is_the_local_trough():
    lows = [3, 2, 1, 2, 3]
    assert lv.find_swing_lows(lows, window=2) == [2]


def test_no_swing_on_a_monotonic_series():
    assert lv.find_swing_highs([1, 2, 3, 4, 5], window=2) == []


def test_fully_flat_window_is_not_a_swing():
    # With no bar strictly higher than any other, there is no turning point.
    assert lv.find_swing_highs([3, 3, 3, 3, 3], window=2) == []


def test_plateau_above_its_surroundings_counts_as_one_swing():
    # A flat top that still sits above the outer bars is a genuine level.
    assert lv.find_swing_highs([1, 3, 3, 3, 1], window=2) == [2]


# --- clustering ------------------------------------------------------------


def test_nearby_prices_merge_into_one_level_with_touch_count():
    levels = lv.cluster_levels([1.1000, 1.1001, 1.1002], "resistance", tolerance=0.0005)
    assert len(levels) == 1
    assert levels[0].touches == 3


def test_distant_prices_stay_separate():
    levels = lv.cluster_levels([1.1000, 1.2000], "support", tolerance=0.0005)
    assert len(levels) == 2


def test_clusters_are_ordered_by_strength():
    levels = lv.cluster_levels([1.10, 1.10, 1.10, 1.20], "resistance", tolerance=0.0005)
    assert levels[0].touches == 3  # strongest first


def test_empty_input_yields_no_levels():
    assert lv.cluster_levels([], "support", tolerance=0.0005) == []


# --- pivots ----------------------------------------------------------------


def test_pivot_is_the_average_of_hlc():
    p = lv.pivot_points(1.11, 1.09, 1.10)
    assert p["pivot"] == round((1.11 + 1.09 + 1.10) / 3, 6)


def test_pivot_r1_above_and_s1_below():
    p = lv.pivot_points(1.11, 1.09, 1.10)
    assert p["r1"] > p["pivot"] > p["s1"]


# --- full analysis ---------------------------------------------------------


def _wave(cycles=6, amp=0.01, base=1.10):
    """A repeating triangle so the same highs and lows recur as real levels."""
    highs, lows, closes = [], [], []
    for _ in range(cycles):
        for step in [0, 1, 2, 3, 2, 1]:
            c = base + amp * step / 3
            closes.append(c)
            highs.append(c + 0.0002)
            lows.append(c - 0.0002)
    return highs, lows, closes


def test_analyze_finds_support_below_and_resistance_above():
    highs, lows, closes = _wave()
    # Put the current price in the middle of the range.
    closes[-1] = 1.105
    report = lv.analyze_levels(highs, lows, closes, "EUR/USD")
    assert report.nearest_support is not None
    assert report.nearest_resistance is not None
    assert report.nearest_support.price < 1.105 < report.nearest_resistance.price


def test_analyze_reports_distances_in_pips():
    highs, lows, closes = _wave()
    report = lv.analyze_levels(highs, lows, closes, "EUR/USD")
    if report.nearest_support:
        assert report.distance_to_support_pips >= 0


def test_analyze_includes_a_pivot():
    highs, lows, closes = _wave()
    assert lv.analyze_levels(highs, lows, closes, "EUR/USD").pivot is not None


def test_to_dict_is_json_friendly():
    highs, lows, closes = _wave()
    payload = lv.analyze_levels(highs, lows, closes, "EUR/USD").to_dict()
    assert "supports" in payload and "resistances" in payload
    assert "pivot" in payload


# --- is_at_level -----------------------------------------------------------


def test_is_at_level_true_close_to_a_level():
    highs, lows, closes = _wave()
    report = lv.analyze_levels(highs, lows, closes, "EUR/USD")
    a_level = (report.supports + report.resistances)[0].price
    assert lv.is_at_level(a_level, report, "EUR/USD", proximity_pips=10) is True


def test_is_at_level_false_far_from_any_level():
    highs, lows, closes = _wave()
    report = lv.analyze_levels(highs, lows, closes, "EUR/USD")
    assert lv.is_at_level(2.0, report, "EUR/USD", proximity_pips=10) is False
