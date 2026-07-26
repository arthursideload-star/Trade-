"""Patterns, levels, setups and the ratio.

Where a detector's whole value is "does it fire on the right shape and stay
quiet on the wrong one", the tests use hand-built candles with the exact
geometry rather than synthetic noise.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from metals import gsr, seasonality
from metals.candles import Candle, CandleSeries, build_series
from metals.levels import (Level, build_level_map, equal_highs_lows,
                           fib_levels, pivot_points, round_number_levels,
                           swing_levels)
from metals.patterns import (detect_sweep, engulfing, fair_value_gaps,
                             inside_bar, marubozu, market_structure_shift,
                             pin_bar, scan)
from metals.setups import CATALOGUE, detect_all
from tests.helpers import make_series, series_from_ohlc

UTC = timezone.utc


class TestCandleGeometry(unittest.TestCase):
    def test_derived_properties(self):
        c = Candle(datetime(2026, 7, 1, tzinfo=UTC), 100.0, 110.0, 95.0, 105.0)
        self.assertAlmostEqual(c.body, 5.0)
        self.assertAlmostEqual(c.range, 15.0)
        self.assertAlmostEqual(c.upper_wick, 5.0)
        self.assertAlmostEqual(c.lower_wick, 5.0)
        self.assertTrue(c.bullish)
        self.assertAlmostEqual(c.body_ratio, 5.0 / 15.0)
        self.assertAlmostEqual(c.close_position, 10.0 / 15.0)

    def test_invalid_ohlc_is_rejected(self):
        with self.assertRaises(ValueError):
            Candle(datetime(2026, 7, 1, tzinfo=UTC), 100.0, 99.0, 95.0, 97.0)

    def test_naive_timestamp_is_rejected(self):
        with self.assertRaises(ValueError):
            Candle(datetime(2026, 7, 1), 100.0, 110.0, 95.0, 105.0)

    def test_series_deduplicates_and_sorts(self):
        base = datetime(2026, 7, 1, tzinfo=UTC)
        candles = [
            Candle(base + timedelta(hours=2), 3, 4, 2, 3),
            Candle(base, 1, 2, 0.5, 1.5),
            Candle(base + timedelta(hours=2), 3, 5, 2, 4),   # duplicate ts
        ]
        s = CandleSeries("XAUUSD", "1h", candles)
        self.assertEqual(len(s), 2)
        self.assertLess(s[0].ts, s[1].ts)
        self.assertAlmostEqual(s[1].high, 5)   # last one wins

    def test_drop_forming_bar(self):
        now = datetime(2026, 7, 1, 10, 30, tzinfo=UTC)
        s = make_series(timeframe="1h", n=5,
                        start=datetime(2026, 7, 1, 6, 0, tzinfo=UTC))
        # Last bar opens 10:00, closes 11:00 -- still forming at 10:30.
        trimmed = s.drop_forming_bar(now)
        self.assertEqual(len(trimmed), len(s) - 1)

    def test_gaps_are_detected(self):
        base = datetime(2026, 7, 1, tzinfo=UTC)
        candles = [
            Candle(base, 1, 2, 0.5, 1.5),
            Candle(base + timedelta(hours=1), 1.5, 2, 1, 1.8),
            Candle(base + timedelta(hours=6), 1.8, 2, 1, 1.9),
        ]
        s = CandleSeries("XAUUSD", "1h", candles)
        self.assertEqual(len(s.gaps()), 1)

    def test_timestamp_coercion_handles_provider_shapes(self):
        rows = [
            {"ts": 1785000000, "open": 1, "high": 2, "low": 0.5, "close": 1.5},
            {"ts": "2026-07-26 12:00:00", "open": 1, "high": 2, "low": 0.5, "close": 1.5},
            {"ts": "2026-07-27T12:00:00Z", "open": 1, "high": 2, "low": 0.5, "close": 1.5},
            {"ts": 1785000000000, "open": 1, "high": 2, "low": 0.5, "close": 1.5},
        ]
        s = build_series("XAUUSD", "1h", rows)
        self.assertEqual(len(s), 3)   # two of the four are the same instant
        for c in s:
            self.assertIsNotNone(c.ts.tzinfo)


class TestPatterns(unittest.TestCase):
    def _pin_series(self) -> CandleSeries:
        rows = [(100, 102, 98, 101)] * 20
        # Bullish pin: long lower wick, small body, closes near the high.
        rows.append((100, 101, 88, 100.5))
        return series_from_ohlc(rows)

    def test_pin_bar_fires_at_a_level(self):
        s = self._pin_series()
        hit = pin_bar(s, -1, atr_value=3.0, level=88.5)
        self.assertIsNotNone(hit)
        self.assertEqual(hit.direction, "bullish")

    def test_pin_bar_is_discounted_away_from_a_level(self):
        s = self._pin_series()
        at_level = pin_bar(s, -1, atr_value=3.0, level=88.5)
        no_level = pin_bar(s, -1, atr_value=3.0, level=None)
        self.assertGreater(at_level.strength, no_level.strength)

    def test_engulfing_requires_closing_beyond_the_prior_extreme(self):
        # Engulfs the body but not the high: must not fire.
        weak = series_from_ohlc([(100, 102, 98, 101)] * 20
                                + [(105, 106, 100, 101.5), (101, 104.5, 100, 104)])
        self.assertIsNone(engulfing(weak, -1, atr_value=2.0, level=102))

        strong = series_from_ohlc([(100, 102, 98, 101)] * 20
                                  + [(105, 106, 100, 101), (101, 107, 100, 106.5)])
        hit = engulfing(strong, -1, atr_value=2.0, level=102)
        self.assertIsNotNone(hit)
        self.assertEqual(hit.direction, "bullish")

    def test_marubozu_is_labelled_momentum_not_reversal(self):
        s = series_from_ohlc([(100, 101, 99, 100)] * 20 + [(100, 108.2, 99.9, 108)])
        hit = marubozu(s, -1, atr_value=3.0)
        self.assertIsNotNone(hit)
        self.assertIn("momentum", hit.description)

    def test_inside_bar(self):
        s = series_from_ohlc([(100, 110, 90, 105)] * 20 + [(102, 106, 96, 104)])
        hit = inside_bar(s, -1)
        self.assertIsNotNone(hit)
        self.assertIn("expansion pending", hit.description)

    def test_scan_returns_ranked_hits(self):
        s = self._pin_series()
        hits = scan(s, level=88.5)
        self.assertTrue(hits)
        strengths = [h.strength for h in hits]
        self.assertEqual(strengths, sorted(strengths, reverse=True))


class TestSweepDetection(unittest.TestCase):
    def test_sweep_fires_when_price_closes_back_inside(self):
        rows = [(100, 102, 98, 100)] * 20
        rows.append((100, 101, 92, 99))     # spikes below 95, closes above
        s = series_from_ohlc(rows)
        hit = detect_sweep(s, level=95.0, direction="bullish",
                           atr_value=3.0)
        self.assertIsNotNone(hit)
        self.assertTrue(hit.close_back_inside)
        self.assertAlmostEqual(hit.penetration, 3.0)

    def test_no_sweep_when_price_stays_outside(self):
        """A break that holds is a breakout, which is the opposite trade.

        This is the single most important distinction in the setup catalogue,
        so it gets an explicit test.
        """
        rows = [(100, 102, 98, 100)] * 20
        rows.append((100, 101, 92, 93))     # closes below the level
        s = series_from_ohlc(rows)
        self.assertIsNone(detect_sweep(s, 95.0, "bullish", atr_value=3.0))

    def test_shallow_penetration_is_ignored(self):
        rows = [(100, 102, 98, 100)] * 20
        rows.append((100, 101, 94.95, 99))   # barely clips the level
        s = series_from_ohlc(rows)
        self.assertIsNone(detect_sweep(s, 95.0, "bullish", atr_value=10.0,
                                       min_penetration_atr=0.10))

    def test_bearish_sweep(self):
        rows = [(100, 102, 98, 100)] * 20
        rows.append((100, 108, 99, 101))
        s = series_from_ohlc(rows)
        hit = detect_sweep(s, level=105.0, direction="bearish", atr_value=3.0)
        self.assertIsNotNone(hit)
        self.assertEqual(hit.direction, "bearish")

    def test_market_structure_shift(self):
        rising = make_series(n=60, drift=1.5, noise=0.4)
        hit = market_structure_shift(rising)
        if hit is not None:
            self.assertEqual(hit.direction, "bullish")

    def test_fair_value_gaps_found_and_fill_tracked(self):
        # 20 leading bars so ATR(14) is defined by the time the gap prints.
        rows = [(100, 101, 99, 100)] * 20
        rows += [(100, 102, 99, 102), (102, 108, 102, 107), (107, 110, 105, 109)]
        rows += [(109, 110, 108, 109)] * 5
        s = series_from_ohlc(rows)
        gaps = fair_value_gaps(s, min_size_atr=0.05)
        self.assertTrue(gaps)
        bullish = [g for g in gaps if g.direction == "bullish"]
        # The impulse leaves two overlapping imbalances: 101-102 and 102-105.
        self.assertEqual(len(bullish), 2)
        widest = max(bullish, key=lambda g: g.high - g.low)
        self.assertAlmostEqual(widest.low, 102.0)
        self.assertAlmostEqual(widest.high, 105.0)
        # Price stalls at 109 afterwards and never trades back into either.
        self.assertFalse(any(g.filled for g in bullish))


class TestLevels(unittest.TestCase):
    def test_gold_round_grid(self):
        levels = round_number_levels("XAUUSD", 4500.0, reach_pct=2.0)
        prices = {l.price for l in levels}
        self.assertIn(4500.0, prices)
        self.assertIn(4450.0, prices)   # 50-grid, inside a 90 USD reach
        # The 100 grid must score higher than the 10 grid.
        major = next(l for l in levels if l.price == 4500.0)
        intermediate = next(l for l in levels if l.price == 4450.0)
        minor = next(l for l in levels if l.price == 4490.0)
        self.assertGreater(major.strength, intermediate.strength)
        self.assertGreater(intermediate.strength, minor.strength)

    def test_round_levels_respect_the_reach_limit(self):
        levels = round_number_levels("XAUUSD", 4500.0, reach_pct=1.0)
        for l in levels:
            self.assertLessEqual(abs(l.price - 4500.0), 45.0 + 1e-9)

    def test_silver_round_grid_is_an_order_of_magnitude_finer(self):
        levels = round_number_levels("XAGUSD", 52.0, reach_pct=6.0)
        prices = {l.price for l in levels}
        self.assertIn(50.0, prices)     # 5-grid
        self.assertIn(52.0, prices)     # 1-grid
        self.assertIn(52.5, prices)     # 0.5-grid
        self.assertNotIn(4500.0, prices)

    def test_swing_levels_score_by_touches(self):
        s = make_series(n=150)
        levels = swing_levels(s)
        self.assertTrue(levels)
        for l in levels:
            self.assertGreaterEqual(l.strength, 0.0)
            self.assertLessEqual(l.strength, 1.0)

    def test_equal_highs_are_detected(self):
        rows = []
        for i in range(6):
            rows += [(100, 100 + i * 0.1, 95, 98), (98, 99, 94, 96),
                     (96, 110.0, 95, 97), (97, 98, 93, 95)]
        s = series_from_ohlc(rows)
        levels = equal_highs_lows(s, tolerance_pct=0.5)
        self.assertTrue(any(l.kind == "equal_highs" for l in levels))

    def test_confluence_zones_cluster_nearby_levels(self):
        from metals.levels import LevelMap
        lm = LevelMap("XAUUSD", 4500.0, [
            Level(4520.0, "round", 0.85),
            Level(4521.0, "swing_high", 0.7),
            Level(4522.0, "prior_day_high", 0.65),
            Level(4400.0, "swing_low", 0.5),
        ])
        zones = lm.confluence_zones(tolerance_pct=0.15)
        self.assertEqual(len(zones), 2)
        strongest = zones[0]
        self.assertEqual(len(strongest.members), 3)
        self.assertGreater(strongest.strength, 0.6)

    def test_pivot_points_arithmetic(self):
        p = pivot_points(110.0, 90.0, 100.0)
        self.assertAlmostEqual(p["P"], 100.0)
        self.assertAlmostEqual(p["R1"], 110.0)
        self.assertAlmostEqual(p["S1"], 90.0)

    def test_golden_pocket_scores_highest(self):
        levels = fib_levels(4400.0, 4500.0, "long")
        gp = [l for l in levels if l.kind in ("fib_0.618", "fib_0.65")]
        other = [l for l in levels if l.kind == "fib_0.236"]
        self.assertTrue(gp)
        self.assertGreater(gp[0].strength, other[0].strength)

    def test_build_level_map_filters_by_distance(self):
        s = make_series(n=200)
        lm = build_level_map("XAUUSD", s.last.close, s, s,
                             datetime(2026, 7, 21, 14, 0, tzinfo=UTC),
                             reach_pct=1.0)
        span = s.last.close * 0.015
        for l in lm.levels:
            self.assertLessEqual(abs(l.price - lm.price), span + 1e-6)

    def test_nearest_and_directional_helpers(self):
        from metals.levels import LevelMap
        lm = LevelMap("XAUUSD", 4500.0, [
            Level(4520.0, "round", 0.8), Level(4480.0, "round", 0.8),
            Level(4600.0, "round", 0.8),
        ])
        self.assertEqual(len(lm.above(2)), 2)
        self.assertEqual(lm.above(1)[0].price, 4520.0)
        self.assertEqual(lm.below(1)[0].price, 4480.0)


class TestSetups(unittest.TestCase):
    def test_catalogue_is_complete_and_documented(self):
        self.assertGreaterEqual(len(CATALOGUE), 12)
        for key, spec in CATALOGUE.items():
            self.assertTrue(spec.name)
            self.assertGreater(len(spec.idea), 60, f"{key} idea is too thin")
            self.assertGreater(len(spec.failure_mode), 40,
                               f"{key} does not say how it fails")
            self.assertTrue(spec.entry_rule)
            self.assertTrue(spec.stop_rule)
            self.assertTrue(spec.target_rule)

    def test_detect_all_is_quiet_on_noise(self):
        """Most bars are not a setup. A detector that fires constantly is
        worse than no detector."""
        s = make_series(n=250, drift=0.0, noise=3.0)
        lm = build_level_map("XAUUSD", s.last.close, s, s)
        signals = detect_all("XAUUSD", s, s, s, lm,
                             datetime(2026, 7, 21, 14, 0, tzinfo=UTC))
        self.assertLessEqual(len(signals), 4)

    def test_signals_have_coherent_geometry(self):
        for seed in range(1, 12):
            s = make_series(n=250, drift=0.8, noise=2.0, seed=seed)
            lm = build_level_map("XAUUSD", s.last.close, s, s)
            for sig in detect_all("XAUUSD", s, s, s, lm,
                                  datetime(2026, 7, 21, 14, 0, tzinfo=UTC)):
                if sig.direction == "long":
                    self.assertGreater(sig.target, sig.entry,
                                       f"{sig.setup_id}: long target below entry")
                else:
                    self.assertLess(sig.target, sig.entry,
                                    f"{sig.setup_id}: short target above entry")
                self.assertGreaterEqual(sig.confidence, 0.0)
                self.assertLessEqual(sig.confidence, 0.95)
                self.assertTrue(sig.failure_mode)

    def test_detector_failure_does_not_abort_the_scan(self):
        s = make_series(n=250)
        lm = build_level_map("XAUUSD", s.last.close, s, s)
        # An empty M15 series would break a naive detector.
        empty = CandleSeries("XAUUSD", "15m", [])
        signals = detect_all("XAUUSD", s, s, empty, lm,
                             datetime(2026, 7, 21, 14, 0, tzinfo=UTC))
        self.assertIsInstance(signals, list)


class TestGoldSilverRatio(unittest.TestCase):
    def test_ratio_arithmetic(self):
        self.assertAlmostEqual(gsr.compute_ratio(4500.0, 50.0), 90.0)
        with self.assertRaises(ValueError):
            gsr.compute_ratio(4500.0, 0.0)

    def test_band_classification(self):
        self.assertEqual(gsr.classify(95.0), "extreme_high")
        self.assertEqual(gsr.classify(82.0), "high")
        self.assertEqual(gsr.classify(65.0), "normal")
        self.assertEqual(gsr.classify(52.0), "low")
        self.assertEqual(gsr.classify(40.0), "extreme_low")

    def test_series_aligns_on_timestamp_not_index(self):
        base = datetime(2026, 7, 1, tzinfo=UTC)
        gold = CandleSeries("XAUUSD", "1d", [
            Candle(base + timedelta(days=i), 4500, 4510, 4490, 4500 + i)
            for i in range(5)
        ])
        # Silver is missing day 2 -- a naive zip would misalign everything after.
        silver = CandleSeries("XAGUSD", "1d", [
            Candle(base + timedelta(days=i), 50, 51, 49, 50.0)
            for i in (0, 1, 3, 4)
        ])
        values = gsr.ratio_series(gold, silver)
        self.assertEqual(len(values), 4)
        self.assertAlmostEqual(values[0], 4500 / 50.0)
        self.assertAlmostEqual(values[2], 4503 / 50.0)

    def test_no_overlap_raises_a_clear_error(self):
        base = datetime(2026, 7, 1, tzinfo=UTC)
        gold = CandleSeries("XAUUSD", "1d",
                            [Candle(base, 4500, 4510, 4490, 4500)])
        silver = CandleSeries("XAGUSD", "1d",
                              [Candle(base + timedelta(days=30), 50, 51, 49, 50)])
        with self.assertRaises(ValueError) as ctx:
            gsr.analyse(gold, silver)
        self.assertIn("overlapping", str(ctx.exception))

    def test_rising_ratio_reads_as_defensive(self):
        base = datetime(2026, 7, 1, tzinfo=UTC)
        gold = CandleSeries("XAUUSD", "1d", [
            Candle(base + timedelta(days=i),
                   open=4000 + i * 20, high=4010 + i * 20,
                   low=3990 + i * 20, close=4005 + i * 20)
            for i in range(60)
        ])
        silver = CandleSeries("XAGUSD", "1d", [
            Candle(base + timedelta(days=i), 50, 52, 48, 50.0)
            for i in range(60)
        ])
        state = gsr.analyse(gold, silver)
        self.assertEqual(state.trend_20, "rising")
        self.assertEqual(state.regime, "defensive")
        self.assertEqual(state.leader, "gold")

    def test_metal_selection_follows_the_ratio(self):
        rising = gsr.RatioState(85.0, 1.0, 90.0, "rising", "high", "defensive")
        falling = gsr.RatioState(60.0, -1.0, 20.0, "falling", "normal", "cyclical")
        self.assertEqual(gsr.which_metal(rising, "long")[0], "XAUUSD")
        self.assertEqual(gsr.which_metal(falling, "long")[0], "XAGUSD")
        self.assertEqual(gsr.which_metal(rising, "short")[0], "XAGUSD")

    def test_pair_trade_note_only_at_extremes(self):
        normal = gsr.RatioState(65.0, 0.0, 50.0, "flat", "normal", "mixed")
        extreme = gsr.RatioState(95.0, 2.5, 98.0, "rising", "extreme_high",
                                 "defensive")
        self.assertIsNone(gsr.pair_trade_note(normal))
        note = gsr.pair_trade_note(extreme)
        self.assertIsNotNone(note)
        self.assertIn("Reasons", note)


class TestSeasonality(unittest.TestCase):
    def test_every_month_is_covered_for_both_metals(self):
        for m in range(1, 13):
            self.assertIn(m, seasonality.GOLD_MONTHS)
            self.assertIn(m, seasonality.SILVER_MONTHS)

    def test_weight_stays_negligible(self):
        from datetime import date
        r = seasonality.read("XAUUSD", date(2026, 1, 15))
        self.assertLessEqual(r.confidence_weight, 0.10)
        self.assertIn("breaks ties", r.explain())

    def test_summer_doldrums_window(self):
        from datetime import date
        self.assertTrue(seasonality.summer_doldrums(date(2026, 7, 15)))
        self.assertFalse(seasonality.summer_doldrums(date(2026, 3, 15)))

    def test_silver_and_gold_can_differ(self):
        from datetime import date
        gold = seasonality.read("XAUUSD", date(2026, 5, 15))
        silver = seasonality.read("XAGUSD", date(2026, 5, 15))
        self.assertNotEqual(gold.score, silver.score)


if __name__ == "__main__":
    unittest.main()
