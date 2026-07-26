"""Indicator correctness.

Verified against hand-computed values rather than against another library, so
the tests state what the right answer is instead of asserting that two
implementations agree.
"""

from __future__ import annotations

import unittest

from metals.indicators import (adx, atr, atr_percent, bollinger,
                               bollinger_bandwidth, ema, macd, rolling_correlation,
                               rsi, sma, squeeze_on, stdev, stochastic,
                               swing_points, true_range, volume_ratio,
                               wilder_ma, zscore)
from tests.helpers import make_series


class TestMovingAverages(unittest.TestCase):
    def test_sma_warmup_and_value(self):
        values = [1, 2, 3, 4, 5, 6]
        result = sma(values, 3)
        self.assertEqual(result[:2], [None, None])
        self.assertAlmostEqual(result[2], 2.0)   # (1+2+3)/3
        self.assertAlmostEqual(result[5], 5.0)   # (4+5+6)/3
        self.assertEqual(len(result), len(values))

    def test_sma_shorter_than_period_is_all_none(self):
        self.assertEqual(sma([1, 2], 5), [None, None])

    def test_ema_seeds_with_sma(self):
        values = [1, 2, 3, 4, 5]
        result = ema(values, 3)
        self.assertAlmostEqual(result[2], 2.0)  # SMA seed
        # k = 2/(3+1) = 0.5; next = 4*0.5 + 2*0.5 = 3.0
        self.assertAlmostEqual(result[3], 3.0)
        self.assertAlmostEqual(result[4], 4.0)

    def test_wilder_smoothing(self):
        values = [2, 4, 6, 8]
        result = wilder_ma(values, 2)
        self.assertAlmostEqual(result[1], 3.0)          # seed (2+4)/2
        self.assertAlmostEqual(result[2], (3 * 1 + 6) / 2)
        self.assertAlmostEqual(result[3], ((3 * 1 + 6) / 2 * 1 + 8) / 2)

    def test_period_must_be_positive(self):
        with self.assertRaises(ValueError):
            sma([1, 2, 3], 0)
        with self.assertRaises(ValueError):
            ema([1, 2, 3], -1)


class TestVolatility(unittest.TestCase):
    def test_true_range_uses_previous_close(self):
        highs = [10, 12, 11]
        lows = [8, 11, 9]
        closes = [9, 11.5, 10]
        tr = true_range(highs, lows, closes)
        self.assertAlmostEqual(tr[0], 2.0)          # first bar: high - low
        # bar 1: max(12-11, |12-9|, |11-9|) = 3
        self.assertAlmostEqual(tr[1], 3.0)
        # bar 2: max(11-9, |11-11.5|, |9-11.5|) = 2.5
        self.assertAlmostEqual(tr[2], 2.5)

    def test_atr_is_positive_and_finite(self):
        s = make_series(n=100)
        result = atr(s.highs, s.lows, s.closes, 14)
        self.assertIsNone(result[10])
        self.assertIsNotNone(result[-1])
        self.assertGreater(result[-1], 0)

    def test_atr_percent_normalises_across_price_levels(self):
        """Gold at 4500 and a hypothetical gold at 450 with the same relative
        moves must produce the same ATR percentage."""
        big = make_series(n=100, start_price=4500.0, noise=4.0)
        small = make_series(n=100, start_price=450.0, noise=0.4)
        pct_big = atr_percent(big.highs, big.lows, big.closes, 14)[-1]
        pct_small = atr_percent(small.highs, small.lows, small.closes, 14)[-1]
        self.assertAlmostEqual(pct_big, pct_small, places=1)

    def test_stdev_matches_population_formula(self):
        values = [2, 4, 4, 4, 5, 5, 7, 9]
        result = stdev(values, 8)
        self.assertAlmostEqual(result[-1], 2.0)


class TestBands(unittest.TestCase):
    def test_bollinger_is_symmetric_around_the_mean(self):
        values = [10] * 10 + [12] * 10
        up, mid, lo = bollinger(values, 20, 2.0)
        self.assertIsNotNone(mid[-1])
        self.assertAlmostEqual(mid[-1], 11.0)
        self.assertAlmostEqual(up[-1] - mid[-1], mid[-1] - lo[-1])

    def test_bandwidth_is_zero_on_a_flat_series(self):
        values = [100.0] * 30
        bw = bollinger_bandwidth(values, 20)
        self.assertAlmostEqual(bw[-1], 0.0)

    def test_squeeze_detects_compression(self):
        s = make_series(n=80, noise=0.05)      # very tight
        sq = squeeze_on(s.highs, s.lows, s.closes, 20)
        self.assertIn(True, [v for v in sq if v is not None])


class TestMomentum(unittest.TestCase):
    def test_rsi_is_100_on_a_pure_uptrend(self):
        values = list(range(1, 40))
        result = rsi(values, 14)
        self.assertAlmostEqual(result[-1], 100.0)

    def test_rsi_is_low_on_a_pure_downtrend(self):
        values = list(range(40, 1, -1))
        result = rsi(values, 14)
        self.assertLess(result[-1], 1.0)

    def test_rsi_stays_within_bounds(self):
        s = make_series(n=200)
        for v in rsi(s.closes, 14):
            if v is not None:
                self.assertGreaterEqual(v, 0.0)
                self.assertLessEqual(v, 100.0)

    def test_macd_alignment(self):
        s = make_series(n=200)
        line, signal, hist = macd(s.closes)
        self.assertEqual(len(line), len(s))
        self.assertEqual(len(signal), len(s))
        self.assertEqual(len(hist), len(s))
        self.assertIsNotNone(line[-1])
        self.assertIsNotNone(signal[-1])
        self.assertAlmostEqual(hist[-1], line[-1] - signal[-1])

    def test_stochastic_bounds(self):
        s = make_series(n=120)
        k, d = stochastic(s.highs, s.lows, s.closes)
        for series in (k, d):
            for v in series:
                if v is not None:
                    self.assertGreaterEqual(v, 0.0)
                    self.assertLessEqual(v, 100.0)


class TestTrendStrength(unittest.TestCase):
    def test_adx_rises_in_a_strong_trend(self):
        trending = make_series(n=200, drift=2.0, noise=0.5)
        choppy = make_series(n=200, drift=0.0, noise=4.0)
        a_trend, _, _ = adx(trending.highs, trending.lows, trending.closes)
        a_chop, _, _ = adx(choppy.highs, choppy.lows, choppy.closes)
        self.assertIsNotNone(a_trend[-1])
        self.assertIsNotNone(a_chop[-1])
        self.assertGreater(a_trend[-1], a_chop[-1])

    def test_di_lines_favour_the_trend_direction(self):
        up = make_series(n=200, drift=2.0, noise=0.5)
        _, plus_di, minus_di = adx(up.highs, up.lows, up.closes)
        self.assertGreater(plus_di[-1], minus_di[-1])


class TestCorrelationAndZScore(unittest.TestCase):
    def test_perfect_positive_correlation(self):
        a = list(range(50))
        b = [2 * x + 1 for x in a]
        result = rolling_correlation(a, b, 20)
        self.assertAlmostEqual(result[-1], 1.0, places=6)

    def test_perfect_negative_correlation(self):
        a = list(range(50))
        b = [-3 * x for x in a]
        result = rolling_correlation(a, b, 20)
        self.assertAlmostEqual(result[-1], -1.0, places=6)

    def test_flat_series_yields_no_correlation(self):
        a = list(range(50))
        b = [7.0] * 50
        self.assertIsNone(rolling_correlation(a, b, 20)[-1])

    def test_zscore_of_a_known_outlier(self):
        values = [10.0] * 99 + [20.0]
        z = zscore(values, 100)
        self.assertIsNotNone(z[-1])
        self.assertGreater(z[-1], 5.0)


class TestVolume(unittest.TestCase):
    def test_volume_ratio_flags_a_surge(self):
        vols = [100.0] * 25 + [400.0]
        result = volume_ratio(vols, 20)
        self.assertGreater(result[-1], 2.0)

    def test_missing_volume_does_not_crash(self):
        vols = [None] * 30
        result = volume_ratio(vols, 20)
        self.assertTrue(all(v is None for v in result[-5:]))


class TestSwingPoints(unittest.TestCase):
    def test_finds_an_obvious_pivot(self):
        highs = [1, 2, 5, 2, 1, 1, 1]
        lows = [0, 0, 0, 0, 0, 0, 0]
        sh, sl = swing_points(highs, lows, 2, 2)
        self.assertIn(2, sh)

    def test_last_bars_never_contain_a_confirmed_swing(self):
        s = make_series(n=100)
        sh, sl = swing_points(s.highs, s.lows, 2, 2)
        for idx in sh + sl:
            self.assertLessEqual(idx, len(s) - 3)


if __name__ == "__main__":
    unittest.main()
