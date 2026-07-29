"""The research claims, and the machinery that measures them.

These tests do not assert that a claim is true. Most of them assert that the
*measurement* is honest -- that the win-rate search really can move the win
rate, that the spread really is charged, that the timeframe comparison really
sees the same market at three resolutions. A test that asserted "the session
filter helps" would have to be rewritten the day the measurement said
otherwise, which is precisely backwards.

The one exception is C1, which is asserted as a result, because it is not an
empirical claim about gold at all. It is arithmetic: moving the target closer
and the stop further away must raise the win rate without creating an edge.
If that ever failed, the P&L accounting would be broken.
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from metals import simulate
from metals.candles import resample
from metals.claims import (ASSUMED_EUR_USD, CLAIMS, ASIA_HOURS_UTC,
                           OVERLAP_HOURS_UTC, find, margin_required,
                           measure_account_sizes,
                           measure_win_rate_is_not_an_edge)
from metals.dayrange import DayRangeConfig, lots_for, run, sweep
from metals.risk import MAX_RISK_PER_TRADE_PCT
from metals.specs import get_spec


class TestTheCatalogue(unittest.TestCase):
    def test_every_claim_names_a_source_and_a_kind(self):
        kinds = {"vendor", "editorial", "regulatory", "academic"}
        for c in CLAIMS:
            self.assertTrue(c.text, c.id)
            self.assertTrue(c.source, c.id)
            self.assertIn(c.kind, kinds, c.id)

    def test_ids_are_unique(self):
        ids = [c.id for c in CLAIMS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_no_vendor_claim_is_recorded_as_established(self):
        """The project rule: marketing figures are hypotheses, not facts.

        A vendor claim may be testable, and may even turn out to be true --
        but it must never sit in the catalogue as something already settled.
        """
        for c in CLAIMS:
            if c.kind == "vendor":
                self.assertTrue(
                    c.testable,
                    f"{c.id} is a vendor claim carried without a way to check it")

    def test_the_untestable_ones_say_why(self):
        for c in CLAIMS:
            if not c.testable:
                self.assertTrue(c.note, f"{c.id} is untestable without saying why")

    def test_find_raises_on_an_unknown_id(self):
        self.assertEqual(find("C1").kind, "vendor")
        with self.assertRaises(KeyError):
            find("C999")


class TestC1WinRateIsADial(unittest.TestCase):
    """The finding that makes every '90% win rate' thumbnail uninformative."""

    def test_a_high_win_rate_can_be_manufactured_without_an_edge(self):
        f = measure_win_rate_is_not_an_edge(markets=8, bars=8_000)
        self.assertGreater(f.best_win_rate, f.baseline_win_rate)
        self.assertGreater(f.best_win_rate, 0.80,
                           "the search should be able to buy a headline number")
        self.assertTrue(f.buying_a_win_rate_costs_expectancy,
                        "a manufactured win rate must not also improve "
                        "expectancy -- if it does, the P&L accounting is wrong")

    def test_the_configuration_it_found_is_the_expected_shape(self):
        """Near target, distant stop. If it found something else, the
        mechanism is not what the finding claims it is."""
        f = measure_win_rate_is_not_an_edge(markets=8, bars=8_000)
        self.assertLess(f.its_take, f.its_stop)


class TestRiskSizing(unittest.TestCase):
    """A1: the audit finding. A fixed lot is how small accounts die."""

    OZ = get_spec("XAUUSD").contract_size_oz

    def test_without_a_risk_percent_the_fixed_lot_is_used(self):
        cfg = DayRangeConfig(lot=0.07)
        self.assertEqual(lots_for(cfg, 10_000, 12.0, self.OZ), 0.07)

    def test_the_lot_follows_from_the_stop(self):
        """1% of 20,000 is 200 dollars; a 10-dollar stop on 100 ounces per
        lot means 0.20 lot risks exactly that."""
        cfg = DayRangeConfig(risk_pct=1.0)
        self.assertAlmostEqual(lots_for(cfg, 20_000, 10.0, self.OZ), 0.20)

    def test_a_wider_stop_gives_a_smaller_position(self):
        cfg = DayRangeConfig(risk_pct=1.0)
        near = lots_for(cfg, 20_000, 5.0, self.OZ)
        far = lots_for(cfg, 20_000, 20.0, self.OZ)
        self.assertGreater(near, far)

    def test_the_risk_percent_is_capped_by_the_hard_rule(self):
        """The config may only ever be more conservative than R1.

        This is the project rule that risk limits live in code: a caller
        asking for 10% gets 1%, silently and always.
        """
        greedy = DayRangeConfig(risk_pct=10.0)
        capped = DayRangeConfig(risk_pct=MAX_RISK_PER_TRADE_PCT)
        self.assertEqual(lots_for(greedy, 20_000, 10.0, self.OZ),
                         lots_for(capped, 20_000, 10.0, self.OZ))

    def test_an_account_too_small_for_the_minimum_lot_gets_zero(self):
        """Not the broker minimum, not an exception -- zero.

        Rounding up to 0.01 here would be the single most expensive line in
        the project: it turns "this trade does not fit" into "risk 4% of the
        account".
        """
        cfg = DayRangeConfig(risk_pct=1.0)
        self.assertEqual(lots_for(cfg, 200.0, 15.0, self.OZ), 0.0)

    def test_the_lot_is_floored_never_rounded_up(self):
        cfg = DayRangeConfig(risk_pct=1.0)
        # 1% of 1,000 = 10 dollars; a 7-dollar stop allows 0.0142... lot.
        self.assertAlmostEqual(lots_for(cfg, 1_000, 7.0, self.OZ), 0.01)

    def test_refused_trades_are_counted_not_dropped(self):
        cfg = DayRangeConfig(risk_pct=1.0, start_equity=216.0)
        r = run(cfg, seed=11, bars=8_000)
        self.assertGreater(r.signals, 0)
        self.assertEqual(r.trades, 0)
        self.assertEqual(r.skipped_too_small, r.signals)
        self.assertEqual(r.signals_acted_on, 0.0)

    def test_a_large_account_acts_on_what_it_sees(self):
        cfg = DayRangeConfig(risk_pct=1.0, start_equity=50_000.0)
        r = run(cfg, seed=11, bars=8_000)
        self.assertGreater(r.trades, 0)
        self.assertEqual(r.skipped_too_small, 0)


class TestAccountSizes(unittest.TestCase):
    def test_small_accounts_are_reported_as_refusing_trades(self):
        f = measure_account_sizes(equities_eur=(200, 5_000), markets=4,
                                  bars=8_000)
        small = f.at(200)
        large = f.at(5_000)
        assert small is not None and large is not None
        self.assertLess(small.share_of_signals_taken,
                        large.share_of_signals_taken,
                        "the small account must act on a smaller share of "
                        "its own signals")
        self.assertFalse(small.rule_permits_trading)

    def test_the_forced_risk_is_what_the_minimum_lot_dictates(self):
        """The number the whole account-size question reduces to.

        Halving the account doubles the share of it that one minimum-lot
        position puts at risk. Nothing about the strategy changes.
        """
        f = measure_account_sizes(equities_eur=(200, 400), markets=4,
                                  bars=8_000)
        small, large = f.at(200), f.at(400)
        assert small is not None and large is not None
        self.assertAlmostEqual(small.forced_risk_pct,
                               large.forced_risk_pct * 2, places=4)

    def test_the_minimum_lot_run_actually_trades_where_the_rule_refuses(self):
        """The honest forecast for a small account: it does trade, because
        the broker allows it. That is the problem, not the reassurance."""
        f = measure_account_sizes(equities_eur=(400,), markets=4, bars=8_000)
        row = f.at(400)
        assert row is not None
        self.assertGreater(row.minlot_trades, row.disciplined_trades)

    def test_the_smallest_viable_account_is_derived_not_guessed(self):
        f = measure_account_sizes(equities_eur=(1_000,), markets=4, bars=8_000)
        oz = get_spec("XAUUSD").contract_size_oz
        expected_usd = 0.01 * oz * f.mean_stop_usd / (MAX_RISK_PER_TRADE_PCT / 100)
        self.assertAlmostEqual(f.smallest_viable_eur,
                               expected_usd / ASSUMED_EUR_USD, places=4)

    def test_the_euro_rate_is_an_assumption_that_is_written_down(self):
        self.assertGreater(ASSUMED_EUR_USD, 1.0)
        self.assertLess(ASSUMED_EUR_USD, 1.3)


class TestSessionAndTimeframeMachinery(unittest.TestCase):
    def test_the_session_filter_actually_restricts_entries(self):
        cfg = DayRangeConfig(trade_hours_utc=OVERLAP_HOURS_UTC)
        r = run(cfg, seed=21, bars=12_000)
        unrestricted = run(DayRangeConfig(), seed=21, bars=12_000)
        self.assertLess(r.signals, unrestricted.signals)

    def test_the_two_session_windows_do_not_overlap(self):
        self.assertFalse(set(OVERLAP_HOURS_UTC) & set(ASIA_HOURS_UTC))

    def test_resampling_preserves_the_extremes(self):
        """The M5 bar must contain the M1 bars it was built from, or the
        timeframe comparison is comparing two different markets."""
        s = simulate.generate(bars=1_000, timeframe="1m", seed=31)
        five = resample(s, 5)
        self.assertEqual(len(five), 200)
        for k, bar in enumerate(five.candles):
            group = s.candles[k * 5:(k + 1) * 5]
            self.assertEqual(bar.open, group[0].open)
            self.assertEqual(bar.close, group[-1].close)
            self.assertEqual(bar.high, max(b.high for b in group))
            self.assertEqual(bar.low, min(b.low for b in group))

    def test_an_incomplete_final_group_is_dropped(self):
        s = simulate.generate(bars=1_002, timeframe="1m", seed=32)
        self.assertEqual(len(resample(s, 5)), 200)

    def test_resampling_by_one_is_the_identity(self):
        s = simulate.generate(bars=100, timeframe="1m", seed=33)
        self.assertIs(resample(s, 1), s)

    def test_an_unnameable_timeframe_is_refused(self):
        s = simulate.generate(bars=100, timeframe="1m", seed=34)
        with self.assertRaises(ValueError):
            resample(s, 7)          # 7 minutes is not a timeframe we name

    def test_the_day_window_scales_with_the_timeframe(self):
        """Otherwise 'the day's range' silently becomes five days on M5."""
        cfg = DayRangeConfig(bars_per_day=288)
        self.assertEqual(cfg.bars_per_day * 5, DayRangeConfig().bars_per_day)


class TestC10TheArithmetic(unittest.TestCase):
    def test_margin_for_a_tenth_of_a_lot_exceeds_the_advertised_minimum(self):
        """Vendor pages say 1,000 USD is enough for 0.01-0.10 lot gold.

        At the leverage EU retail clients are actually allowed, 0.10 lot
        needs more than twice that in margin alone -- before any adverse
        move at all.
        """
        need = margin_required(4_100.0, 0.10, 20.0)
        self.assertGreater(need, 2_000.0)

    def test_the_minimum_lot_is_within_reach_of_a_small_account(self):
        self.assertLess(margin_required(4_100.0, 0.01, 20.0), 250.0)

    def test_leverage_moves_the_requirement_proportionally(self):
        a = margin_required(4_100.0, 0.10, 20.0)
        b = margin_required(4_100.0, 0.10, 100.0)
        self.assertAlmostEqual(a / b, 5.0)


class TestSpreadIsReallyCharged(unittest.TestCase):
    def test_a_wider_spread_lowers_expectancy(self):
        cheap = sweep(DayRangeConfig(spread_usd_oz=0.0), markets=6, bars=8_000)
        dear = sweep(DayRangeConfig(spread_usd_oz=1.20), markets=6, bars=8_000)
        self.assertGreater(cheap.mean_expectancy_r, dear.mean_expectancy_r)

    def test_the_target_distance_is_recorded(self):
        """The number that explains why the spread barely matters here."""
        r = run(DayRangeConfig(), seed=41, bars=8_000)
        self.assertGreater(r.mean_target_usd, 1.0,
                           "a target of under a dollar would make this a tick "
                           "scalper, which is a different strategy")
        self.assertEqual(len(r.target_distances), r.trades - r.exits.get("x", 0))


class TestNothingChangedForTheDefaultConfiguration(unittest.TestCase):
    """The new dials must not have moved any previously measured result."""

    def test_the_defaults_still_describe_m1_and_all_hours(self):
        cfg = DayRangeConfig()
        self.assertEqual(cfg.bars_per_day, 1_440)
        self.assertEqual(cfg.trade_hours_utc, ())
        self.assertIsNone(cfg.risk_pct)

    def test_the_default_run_is_unchanged_by_the_new_fields(self):
        a = run(DayRangeConfig(), seed=11, bars=8_000)
        b = run(replace(DayRangeConfig(), risk_pct=None), seed=11, bars=8_000)
        self.assertEqual(a.trades, b.trades)
        self.assertEqual(a.end_equity, b.end_equity)


if __name__ == "__main__":
    unittest.main()
