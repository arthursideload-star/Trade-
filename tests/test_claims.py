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
from datetime import datetime, timedelta, timezone

from metals import simulate
from metals.candles import resample
from metals.claims import (ASSUMED_EUR_USD, CLAIMS, ASIA_HOURS_UTC,
                           OVERLAP_HOURS_UTC, find, margin_required,
                           measure_account_sizes,
                           POINT_USD_OZ, measure_reversion_dependence,
                           measure_walk_forward,
                           measure_win_rate_is_not_an_edge,
                           stops_level_usd, swap_on_one_position,
                           target_is_placeable, WALK_FORWARD_RED_FLAG,
                           WalkForwardFinding)
from metals.dayrange import (ROLLOVER_HOUR_UTC, TRIPLE_SWAP_WEEKDAY,
                             DayRangeConfig, in_news_blackout, lots_for,
                             run, sweep)
from metals.risk import MAX_RISK_PER_TRADE_PCT, NEWS_BLACKOUT_MINUTES
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


class TestTheRiskCeiling(unittest.TestCase):
    """max_risk_pct: decline the setup rather than shrink the position.

    On a small gold account the position cannot be shrunk below 0.01 lot, so
    the only control left is which setups to accept. These tests pin the
    mechanics and, in the last one, the trade-off that makes it a real
    decision rather than a free improvement.
    """

    EQUITY = 400 * ASSUMED_EUR_USD

    def _cfg(self, cap):
        return DayRangeConfig(start_equity=self.EQUITY, lot=0.01,
                              risk_pct=None, max_risk_pct=cap)

    def test_without_a_ceiling_nothing_is_declined(self):
        r = run(self._cfg(None), seed=71, bars=8_000)
        self.assertEqual(r.skipped_stop_too_wide, 0)

    def test_a_ceiling_declines_setups_and_says_how_many(self):
        r = run(self._cfg(4.0), seed=71, bars=8_000)
        self.assertGreater(r.skipped_stop_too_wide, 0)

    def test_a_tighter_ceiling_declines_more(self):
        loose = run(self._cfg(10.0), seed=71, bars=8_000)
        tight = run(self._cfg(2.5), seed=71, bars=8_000)
        self.assertGreater(tight.skipped_stop_too_wide,
                           loose.skipped_stop_too_wide)
        self.assertLess(tight.trades, loose.trades)

    def test_no_trade_taken_exceeds_the_ceiling(self):
        """The property the whole thing exists for."""
        cap = 4.0
        cfg = self._cfg(cap)
        r = run(cfg, seed=71, bars=8_000)
        self.assertGreater(r.trades, 0)
        for target in r.target_distances:
            stop = target * cfg.stop_fraction / cfg.take_fraction
            risked_pct = stop * cfg.lot * 100 / self.EQUITY * 100
            self.assertLessEqual(round(risked_pct, 6), cap + 1e-6)

    def test_the_ceiling_trades_return_away_for_a_better_worst_case(self):
        """What the ceiling actually buys, stated only as far as the data
        goes.

        An earlier version of this test asserted that a tighter ceiling
        costs expectancy per trade. Measured across 40 markets the
        expectancy bands overlap completely (+0.10..+0.30 against
        +0.00..+0.35), so that difference was never established -- the test
        was pinning noise and duly broke the moment rule R2 shifted it.

        Monotone and robust are the median and the worst case: the ceiling
        gives up return and improves the bad tail.
        """
        loose = sweep(self._cfg(10.0), markets=24, bars=1_440,
                      seed_base=600_000)
        tight = sweep(self._cfg(2.5), markets=24, bars=1_440,
                      seed_base=600_000)
        self.assertGreater(loose.mean_trades, tight.mean_trades)
        self.assertGreater(loose.median_return_pct, tight.median_return_pct)
        self.assertGreater(tight.worst_return_pct, loose.worst_return_pct)

    def test_a_ceiling_above_the_daily_limit_makes_it_a_one_trade_limit(self):
        """The coupling between max_risk_pct and R2, measured directly
        rather than inferred from expectancy.

        With no ceiling a single trade can risk far more than the 3% daily
        limit, so one loser ends the day. Bringing the ceiling below the
        daily limit takes two or more. Measured share of bars spent stopped
        out on risk: 17.9% with no ceiling, 12.1% at 4%, 4.3% at 2.5%,
        1.4% at 2% -- the cliff sits where the ceiling crosses under 3%.
        """
        import statistics
        loose = sweep(self._cfg(10.0), markets=24, bars=1_440,
                      seed_base=600_000)
        tight = sweep(self._cfg(2.0), markets=24, bars=1_440,
                      seed_base=600_000)
        loose_bars = statistics.fmean(r.days_stopped_out_of_risk
                                      for r in loose.runs)
        tight_bars = statistics.fmean(r.days_stopped_out_of_risk
                                      for r in tight.runs)
        self.assertGreater(loose_bars, tight_bars * 3,
                           "a ceiling above the daily limit should trip it "
                           "far more often; if this ever narrows, the "
                           "coupling has changed")


class TestC11Swap(unittest.TestCase):
    """Overnight financing, which the model did not charge at all before."""

    def test_long_pays_and_short_receives(self):
        """The asymmetry is the whole point: it is the cost of carrying
        metal, so it does not cancel between directions."""
        self.assertLess(swap_on_one_position(0.10, 1, long=True), 0)
        self.assertGreater(swap_on_one_position(0.10, 1, long=False), 0)

    def test_it_scales_with_lots_and_nights(self):
        one = swap_on_one_position(0.10, 1)
        self.assertAlmostEqual(swap_on_one_position(0.10, 30), one * 30)
        self.assertAlmostEqual(swap_on_one_position(0.20, 1), one * 2)

    def test_holding_a_position_a_month_costs_a_real_share_of_a_small_account(self):
        """0.10 lot long for 30 nights against a 400 euro account."""
        cost = abs(swap_on_one_position(0.10, 30))
        self.assertGreater(cost / (400 * ASSUMED_EUR_USD), 0.40)

    def test_the_run_charges_it_and_records_it(self):
        cfg = DayRangeConfig()
        r = run(cfg, seed=11, bars=20_000)
        free = run(replace(cfg, swap_long_usd_per_lot=0.0,
                           swap_short_usd_per_lot=0.0), seed=11, bars=20_000)
        self.assertGreater(r.nights_held, 0)
        self.assertEqual(free.swap_paid_usd, 0.0)
        self.assertNotEqual(r.end_equity, free.end_equity)

    def test_it_does_not_touch_the_r_multiples(self):
        """Financing is rent, not a trading result. Charging it against a
        trade's R would make the strategy look worse at picking direction
        when what actually happened is that it held for longer."""
        cfg = DayRangeConfig()
        r = run(cfg, seed=11, bars=20_000)
        free = run(replace(cfg, swap_long_usd_per_lot=0.0,
                           swap_short_usd_per_lot=0.0), seed=11, bars=20_000)
        self.assertEqual(r.r_multiples, free.r_multiples)

    def test_a_time_stop_reduces_the_nights_carried(self):
        """The finding worth keeping: an exit rule is also a cost control."""
        quick = run(DayRangeConfig(time_stop_bars=60), seed=21, bars=20_000)
        slow = run(DayRangeConfig(time_stop_bars=60, stop_fraction=50.0),
                   seed=21, bars=20_000)
        self.assertLessEqual(quick.nights_held, slow.nights_held)

    def test_wednesday_is_charged_three_times(self):
        self.assertEqual(TRIPLE_SWAP_WEEKDAY, 2)

    def test_the_rollover_hour_matches_the_broker_timezone_used_elsewhere(self):
        """The backtest already assumes GMT+3 server time; a different
        rollover hour here would silently model a different broker."""
        self.assertEqual(ROLLOVER_HOUR_UTC, 21)


class TestC14WhatTheEdgeStandsOn(unittest.TestCase):
    """The sharpest caveat this project has produced.

    "The simulator is too easy" is vague. This names the parameter: turn
    `MarketParams.reversion` off and most of the measured edge goes with
    it, because the strategy buys the edge of the range and sells toward
    the middle, and that dial is what pulls price back to the middle.
    """

    @classmethod
    def setUpClass(cls):
        cls.finding = measure_reversion_dependence(markets=10, bars=10_000)

    def test_most_of_the_edge_lives_on_the_reversion_dial(self):
        self.assertGreater(self.finding.share_of_edge_from_reversion, 0.5,
                           "if the edge survived the dial being switched "
                           "off, it would be coming from the chart rather "
                           "than from the generator's design")

    def test_a_trending_market_costs_more_than_a_flat_one(self):
        """The claim as the trade press states it: these systems work until
        the market runs one way."""
        for reversion in (self.finding.default_reversion, 0.0):
            with self.subTest(reversion=reversion):
                self.assertGreater(self.finding.at(reversion, 0.0),
                                   self.finding.at(reversion, 0.00001))

    def test_the_worst_case_is_reversion_off_and_a_trend_on(self):
        worst = self.finding.at(0.0, 0.00001)
        best = self.finding.at(self.finding.default_reversion, 0.0)
        self.assertLess(worst, best)
        self.assertLess(worst, 0.0)

    def test_the_default_is_read_from_the_simulator_not_hardcoded(self):
        from metals import simulate
        self.assertEqual(self.finding.default_reversion,
                         simulate.MarketParams().reversion)


class TestClosePositionDetectsReversion(unittest.TestCase):
    """The statistic that lets real data answer C14 directly.

    C14 established that ~85% of the measured edge rests on
    `simulate.MarketParams.reversion`. That makes one empirical question
    decisive: does real gold revert intraday at that strength? This needs
    only OHLC, so it can be run on the downloaded history without tick data
    -- but only if it can actually tell the two worlds apart, which is what
    these tests check.
    """

    @staticmethod
    def _pooled(reversion, markets=6, seed_base=890_000):
        from metals.claims import ClosePositionStats, close_position_stats
        positions = []
        for i in range(markets):
            params = simulate.MarketParams(start_price=4_100.0,
                                           reversion=reversion)
            s = simulate.generate(bars=20_000, timeframe="1m",
                                  seed=seed_base + i, params=params)
            positions.extend(close_position_stats(s).positions)
        return ClosePositionStats(positions)

    def test_reversion_produces_more_mid_range_closes(self):
        strong = self._pooled(simulate.MarketParams().reversion)
        none = self._pooled(0.0)
        self.assertGreater(strong.share_closing_mid, none.share_closing_mid)
        self.assertLess(strong.mean_distance_from_middle,
                        none.mean_distance_from_middle)

    def test_it_groups_by_trading_date_not_by_counting_bars(self):
        """Gold feeds gap at the daily break and over weekends, so counted
        days drift out of alignment and stop being days."""
        from datetime import datetime, timedelta, timezone

        from metals.candles import Candle, CandleSeries
        from metals.claims import close_position_stats
        from metals.dayrange import ROLLOVER_HOUR_UTC

        bars, start = [], datetime(2026, 1, 5, 0, tzinfo=timezone.utc)
        for day in range(3):
            for i in range(30):
                ts = start + timedelta(days=day, minutes=i)
                price = 100.0 + i
                bars.append(Candle(ts=ts, open=price, high=price + 1,
                                   low=price - 1, close=price, volume=1.0))
        stats = close_position_stats(CandleSeries("XAUUSD", "1m", bars))
        self.assertEqual(stats.days, 3)
        self.assertLess(ROLLOVER_HOUR_UTC, 24)

    def test_a_stub_session_is_not_counted_as_a_day(self):
        from datetime import datetime, timedelta, timezone

        from metals.candles import Candle, CandleSeries
        from metals.claims import close_position_stats

        start = datetime(2026, 1, 5, 0, tzinfo=timezone.utc)
        bars = [Candle(ts=start + timedelta(minutes=i), open=100.0,
                       high=101.0, low=99.0, close=100.0, volume=1.0)
                for i in range(5)]
        self.assertEqual(close_position_stats(
            CandleSeries("XAUUSD", "1m", bars)).days, 0)

    def test_an_empty_series_gives_zero_rather_than_dividing(self):
        from metals.claims import ClosePositionStats
        empty = ClosePositionStats([])
        self.assertEqual(empty.days, 0)
        self.assertEqual(empty.share_closing_mid, 0.0)
        self.assertEqual(empty.mean_distance_from_middle, 0.0)


class TestDocumentsDoNotFreezeEachOthersNumbers(unittest.TestCase):
    """One document quoting another's moving figure rots silently.

    REPO-AUDIT.md carried "die +0,176 R aus PAPIER-LAUF.md" for several
    days. By the time anyone looked, PAPIER-LAUF.md contained no such
    number and the live figure was +0.192 R -- the citation was wrong, and
    nothing anywhere could notice, because prose has no compiler.

    The rule this enforces is narrow on purpose: a document may state a
    measurement it owns, and may point at where another one lives, but may
    not copy a number out of a sibling and call it current.
    """

    import pathlib
    DOCS = sorted(pathlib.Path("docs").glob("*.md"))

    def test_no_document_quotes_an_r_figure_out_of_another(self):
        import re

        pattern = re.compile(
            r"[+-]?\d+[.,]\d+\s*R\s+aus\s+\[?[A-ZÄÖÜ][A-ZÄÖÜa-zäöü-]*\.md")
        offenders = []
        for path in self.DOCS:
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if line.lstrip().startswith("*"):
                    continue          # the note explaining the old mistake
                if pattern.search(line):
                    offenders.append(f"{path}:{n}: {line.strip()[:80]}")
        self.assertEqual(offenders, [], "\n".join(
            ["a moving figure was copied between documents; name the command "
             "that produces it instead:"] + offenders))

    def test_the_command_that_produces_the_live_figure_is_real(self):
        from metals.cli import build_parser
        build_parser().parse_args(["paper", "--evidence"])


class TestTheAccountSizeDocumentStaysTrue(unittest.TestCase):
    """docs/KONTOGROESSE.md is the answer to 'is 400 euro enough'.

    It is the document most likely to be read on its own and acted on, so
    the arithmetic it quotes is checked against the code, and the honesty
    clauses are checked for still being there. A later edit that quietly
    drops the uncertainty band should fail a test, not a review.
    """

    @classmethod
    def setUpClass(cls):
        import pathlib
        cls.text = pathlib.Path("docs/KONTOGROESSE.md").read_text(encoding="utf-8")

    def test_the_margin_figure_it_quotes_is_the_one_the_code_computes(self):
        self.assertIn("205", self.text)
        self.assertAlmostEqual(margin_required(4_100.0, 0.01, 20.0), 205.0,
                               places=0)

    def test_it_states_the_uncertainty_on_the_ruin_rate(self):
        """0 of 20 runs is not 'it does not blow up'."""
        self.assertIn("Wilson", self.text)
        self.assertIn("16,1", self.text)

    def test_it_does_not_promise_a_return(self):
        for phrase in ("garantiert", "sicherer Gewinn", "risikofrei",
                       "du wirst verdienen"):
            self.assertNotIn(phrase, self.text.lower())

    def test_it_names_the_simulator_caveat(self):
        self.assertIn("simulate.py", self.text)
        self.assertIn("nicht nachgewiesen", self.text.lower())

    def test_it_explains_the_percentage_illusion(self):
        """The single most misreadable number in the document: +44.7% on a
        small account is the same trade sequence as +1.8% on a large one."""
        self.assertIn("dieselbe Handelsfolge", self.text)

    def test_the_forced_risk_scales_inversely_with_the_account(self):
        """The doc's core table is 31 USD divided by the account. Checked
        as arithmetic so the table cannot drift away from the code."""
        f = measure_account_sizes(equities_eur=(100, 400), markets=4,
                                  bars=8_000)
        small, large = f.at(100), f.at(400)
        assert small is not None and large is not None
        self.assertAlmostEqual(small.forced_risk_pct,
                               large.forced_risk_pct * 4, places=3)


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


class TestTheEaExitScheme(unittest.TestCase):
    """A11 could only estimate what the EA's exit costs. It can be measured.

    The estimate blended two rows of a target sweep and landed on "roughly
    20% less". The measurement says otherwise, and it also says the blame
    was on the wrong component.
    """

    BASE = DayRangeConfig()

    def test_the_ea_scheme_takes_a_partial_and_the_plain_one_does_not(self):
        ea = run(replace(self.BASE, ea_exit=True), seed=91, bars=15_000)
        plain = run(self.BASE, seed=91, bars=15_000)
        self.assertGreater(ea.partials_taken, 0)
        self.assertEqual(plain.partials_taken, 0)

    def test_r_is_measured_against_the_risk_the_trade_opened_with(self):
        """The trap in a break-even stop: if R used the *current* stop,
        every runner that ends at break-even would divide by zero, and a
        partial would credit the remainder with the whole trade's risk."""
        r = run(replace(self.BASE, ea_exit=True), seed=91, bars=15_000)
        self.assertTrue(r.r_multiples)
        for value in r.r_multiples:
            self.assertLess(abs(value), 10.0,
                            "an R multiple in double digits means the risk "
                            "denominator collapsed")

    def test_banked_profit_is_counted_once(self):
        """Taken at the partial and again at the close would inflate every
        winning trade by the size of its own first target."""
        cfg = replace(self.BASE, ea_exit=True)
        r = run(cfg, seed=91, bars=15_000)
        self.assertGreater(r.trades, 0)
        # End equity must equal start plus the sum of trade P&L, and trade
        # P&L is r_multiple * risk. A double count breaks that identity.
        self.assertLess(abs(r.end_equity - r.start_equity), r.start_equity,
                        "a session cannot gain or lose more than the account")

    def test_the_time_stop_costs_more_than_the_exit_structure(self):
        """The finding that redirects the fix.

        A11 blamed the split exit. Measured separately, the 45-minute time
        stop is the larger loss by itself -- the day-range setup aims at the
        far end of the day's range, which does not happen inside 45 minutes.
        """
        base = sweep(self.BASE, markets=12, bars=15_000, seed_base=950_000)
        short_stop = sweep(replace(self.BASE, time_stop_bars=45), markets=12,
                           bars=15_000, seed_base=950_000)
        split_exit = sweep(replace(self.BASE, ea_exit=True), markets=12,
                           bars=15_000, seed_base=950_000)
        self.assertLess(short_stop.mean_expectancy_r, base.mean_expectancy_r)
        self.assertLess(split_exit.mean_expectancy_r, base.mean_expectancy_r)
        self.assertLess(short_stop.mean_expectancy_r,
                        split_exit.mean_expectancy_r,
                        "the time stop must be the bigger of the two, which "
                        "is what makes raising it the fix")

    def test_the_ea_refuses_the_combination_it_cannot_survive(self):
        """The guard is in MQL5 and cannot be compiled here, so the test
        checks the source says what it must."""
        import pathlib
        src = pathlib.Path("mt5/Experts/GoldScalpAssistant.mq5").read_text(
            encoding="utf-8")
        self.assertIn("DR_MIN_TIME_STOP_MINUTES 240", src)
        self.assertIn("INIT_PARAMETERS_INCORRECT", src)
        self.assertIn("InpUseDayRange && InpTimeStopMinutes", src)


class TestTheUnsplittablePosition(unittest.TestCase):
    """A minimum-lot account cannot take a partial at all.

    60% of 0.01 lot is 0.006, which rounds down to nothing, and the
    remainder would be under the broker minimum too. The EA's fallback is to
    close the position in full at the first target -- so on a small account
    the runner never exists and every trade caps at first_target_r. This is
    not an edge case there; it is the only case.
    """

    def test_a_minimum_lot_position_is_never_split(self):
        cfg = replace(DayRangeConfig(), ea_exit=True, lot=0.01,
                      start_equity=1_928.0)
        r = run(cfg, seed=91, bars=15_000)
        self.assertEqual(r.partials_taken, 0)
        self.assertGreater(r.unsplittable_closes, 0)

    def test_a_larger_position_is_split(self):
        cfg = replace(DayRangeConfig(), ea_exit=True, lot=0.10,
                      start_equity=20_000.0)
        r = run(cfg, seed=91, bars=15_000)
        self.assertGreater(r.partials_taken, 0)
        self.assertEqual(r.unsplittable_closes, 0)

    def test_the_python_model_follows_the_ea_and_closes_in_full(self):
        """The EA closes the whole position at the first target when it
        cannot be split. An engine that instead let it run would model a
        strategy the expert does not trade."""
        import pathlib
        src = pathlib.Path("mt5/Experts/GoldScalpAssistant.mq5").read_text(
            encoding="utf-8")
        self.assertIn("a partial is not possible", src)
        self.assertIn("Closing in full", src)

    def test_no_exit_scheme_is_distinguishable_at_this_sample(self):
        """The result that stops a recommendation being made.

        Measured over ~1,200 trades each, the three schemes come out at
        +0.060R, +0.069R and +0.093R -- and every 95% band overlaps every
        other. The ranking is suggestive and nothing more, which is why the
        EA guard addresses the time stop (a several-times-larger effect on
        the same footing) and leaves the exit structure alone.
        """
        from metals.journal import mean_interval
        base = DayRangeConfig()
        variants = {
            "split": replace(base, ea_exit=True, lot=0.10,
                             start_equity=20_000.0),
            "full_at_half": replace(base, ea_exit=True, lot=0.01,
                                    start_equity=1_928.0),
            "single_target": replace(base, lot=0.01, start_equity=1_928.0),
        }
        bands = {}
        for name, cfg in variants.items():
            s = sweep(cfg, markets=12, bars=15_000, seed_base=960_000)
            rs = [x for r in s.runs for x in r.r_multiples]
            bands[name] = mean_interval(rs)
        lo_best, hi_best = bands["single_target"]
        lo_worst, hi_worst = bands["split"]
        self.assertLess(lo_best, hi_worst,
                        "if the bands ever separate, the ranking becomes a "
                        "finding and this test should be rewritten to say so")


class TestTheUnsplittableCloseIsNotTrailed(unittest.TestCase):
    """A position the EA closes outright must not also be trailed.

    The first version of the model let the trail run on it, so the engine
    sometimes exited at a *better* trailed stop than the first target -- a
    path the expert never takes. It inflated the measured expectancy from
    +0.093R down to a wrong +0.069R in the published table before it was
    caught.
    """

    CFG = replace(DayRangeConfig(), ea_exit=True, lot=0.01,
                  start_equity=1_928.0)

    def test_no_trade_exceeds_the_first_target(self):
        r = run(self.CFG, seed=91, bars=15_000)
        self.assertGreater(r.unsplittable_closes, 0)
        self.assertLessEqual(max(r.r_multiples),
                             self.CFG.first_target_r + 1e-6,
                             "an R above the first target means the trail ran "
                             "on a position the EA had already closed")

    def test_it_holds_across_several_markets(self):
        for seed in (91, 92, 93, 94):
            r = run(self.CFG, seed=seed, bars=12_000)
            if r.r_multiples:
                self.assertLessEqual(max(r.r_multiples),
                                     self.CFG.first_target_r + 1e-6, seed)

    def test_a_splittable_position_may_exceed_it(self):
        """The runner is supposed to reach further -- that is its purpose."""
        cfg = replace(DayRangeConfig(), ea_exit=True, lot=0.10,
                      start_equity=20_000.0)
        r = run(cfg, seed=91, bars=15_000)
        self.assertGreater(r.partials_taken, 0)
        self.assertGreater(max(r.r_multiples), cfg.first_target_r)


class TestTheFirstTargetSweepStaysMeaningful(unittest.TestCase):
    """On a minimum-lot account every trade closes at first_target_r, so
    that value is the one dial that matters. Sweeping it is worthwhile --
    and a sweep that quietly includes rows testing nothing is worse than no
    sweep, because it reads like six comparable measurements.

    Above the strategy's own target the EA path never activates: the plain
    take-profit fires first and the row is just the baseline wearing a
    different label.
    """

    BASE = replace(DayRangeConfig(), ea_exit=True, lot=0.01,
                   start_equity=1_928.0, time_stop_bars=240)

    def test_a_target_below_the_strategy_target_actually_binds(self):
        for r_target in (0.25, 0.50, 0.75):
            r = run(replace(self.BASE, first_target_r=r_target),
                    seed=970_001, bars=15_000)
            self.assertGreater(r.unsplittable_closes, 0, r_target)
            self.assertLessEqual(max(r.r_multiples), r_target + 1e-6, r_target)

    def test_a_target_above_it_is_degenerate_and_must_not_be_read(self):
        """1.5R never binds: take_fraction 0.5 of the predicted move is
        1.0R, and that target is reached first. The row is the baseline."""
        r = run(replace(self.BASE, first_target_r=1.5), seed=970_001,
                bars=15_000)
        self.assertEqual(r.unsplittable_closes, 0)
        plain = run(replace(DayRangeConfig(), lot=0.01,
                            start_equity=1_928.0, time_stop_bars=240),
                    seed=970_001, bars=15_000)
        self.assertEqual(r.trades, plain.trades)
        self.assertEqual(r.end_equity, plain.end_equity)

    def test_the_win_rate_falls_as_the_target_moves_away(self):
        """The one relationship that is clean here, and the sanity check on
        the whole sweep: a nearer target is reached more often."""
        near = sweep(replace(self.BASE, first_target_r=0.25), markets=10,
                     bars=15_000, seed_base=970_000)
        far = sweep(replace(self.BASE, first_target_r=0.75), markets=10,
                    bars=15_000, seed_base=970_000)
        self.assertGreater(near.mean_win_rate, far.mean_win_rate)

    def test_no_first_target_in_range_is_shown_to_beat_the_default(self):
        """Measured: 0.25 gives +0.083R, 0.50 gives +0.104R, 0.75 gives
        +0.119R, and every 95% band overlaps every other. There is no basis
        to move InpFirstTargetR off 0.5, and this test exists so that
        "0.75 looked best" cannot quietly become a change."""
        from metals.journal import mean_interval
        bands = {}
        for r_target in (0.25, 0.50, 0.75):
            s = sweep(replace(self.BASE, first_target_r=r_target), markets=12,
                      bars=15_000, seed_base=970_000)
            rs = [x for run_ in s.runs for x in run_.r_multiples]
            bands[r_target] = mean_interval(rs)
        self.assertLess(bands[0.75][0], bands[0.25][1],
                        "if these ever separate, the default deserves a "
                        "second look and this test should say so")


class TestTheWeekendFlatRule(unittest.TestCase):
    """M5: flat by Friday 19:00 UTC.

    The third rule found living in metals/risk.py while the code that
    actually trades knew nothing about it -- after R1 (position sizing, A1)
    and R4 (news blackout, A7). Same shape every time.

    As with R4, the simulator cannot argue for it: it skips closed hours, so
    a position carried over a weekend simply resumes at the next bar with no
    gap. These tests check the rule is obeyed, not that it pays.
    """

    def test_the_rule_is_on_by_default(self):
        """M5 is a hard metal rule, not a preference. A default of off would
        make it advice."""
        self.assertTrue(DayRangeConfig().weekend_flat)

    def test_friday_evening_is_inside_the_window(self):
        from metals.dayrange import past_weekend_flat
        from metals.risk import WEEKEND_FLAT_HOUR_UTC
        friday = datetime(2026, 7, 31, WEEKEND_FLAT_HOUR_UTC, 0,
                          tzinfo=timezone.utc)
        self.assertEqual(friday.weekday(), 4)
        self.assertTrue(past_weekend_flat(friday))
        self.assertFalse(past_weekend_flat(friday - timedelta(hours=1)))

    def test_other_weekdays_are_never_inside_it(self):
        from metals.dayrange import past_weekend_flat
        for day in range(27, 31):          # Mon-Thu of that week
            ts = datetime(2026, 7, day, 23, 0, tzinfo=timezone.utc)
            self.assertFalse(past_weekend_flat(ts), ts)

    def test_positions_are_closed_and_the_exit_is_named(self):
        r = run(DayRangeConfig(), seed=980_001, bars=20_000)
        self.assertGreater(r.exits.get("weekend_flat", 0), 0)

    def test_nothing_is_opened_after_the_cutoff(self):
        """A closed position that is reopened ten minutes later has not been
        made flat."""
        from metals.dayrange import past_weekend_flat
        cfg = DayRangeConfig()
        r = run(cfg, seed=980_001, bars=20_000)
        self.assertGreater(r.trades, 0)
        # With the rule off the run must differ, or it is not being applied.
        off = run(replace(cfg, weekend_flat=False), seed=980_001, bars=20_000)
        self.assertNotEqual(r.end_equity, off.end_equity)
        self.assertEqual(off.exits.get("weekend_flat", 0), 0)

    def test_the_simulator_cannot_show_the_benefit_and_that_is_expected(self):
        """Measured +0.1051R with the rule against +0.1071R without, bands
        almost identical. The rule stands on documented gap behaviour, not
        on this number, and the test records that the number is a wash so
        nobody later reads it as an argument against M5."""
        with_rule = sweep(DayRangeConfig(), markets=10, bars=20_000,
                          seed_base=980_000)
        without = sweep(replace(DayRangeConfig(), weekend_flat=False),
                        markets=10, bars=20_000, seed_base=980_000)
        self.assertLess(
            abs(with_rule.mean_expectancy_r - without.mean_expectancy_r), 0.05,
            "if the simulator ever showed a real difference here it would be "
            "an artefact, because it has no weekend gaps at all")


class TestRuleCoverageIsChecked(unittest.TestCase):
    """The structural fix behind A1, A7 and A15.

    Three hard rules were found missing from the trading engine one at a
    time, each by somebody reading the source. That is not a process. Every
    rule in the risk layer now needs an entry saying it is implemented or
    why it does not apply, and this test fails when one does not have it.
    """

    def test_every_hard_rule_has_a_coverage_entry(self):
        from metals.dayrange import uncovered_rules
        self.assertEqual(uncovered_rules(), [],
                         "a rule exists in metals.risk.RULES with no entry in "
                         "dayrange.RULE_COVERAGE -- decide whether the engine "
                         "implements it or why it cannot, and write it down")

    def test_every_entry_has_a_status_and_a_reason(self):
        from metals.dayrange import RULE_COVERAGE
        for rule, (status, reason) in RULE_COVERAGE.items():
            self.assertIn(status, ("implemented", "n/a"), rule)
            self.assertTrue(reason.strip(), rule)

    def test_a_not_applicable_reason_is_a_sentence_not_a_shrug(self):
        """'n/a' with no argument is how a forgotten rule hides. Anything
        this short is a placeholder rather than a reason."""
        from metals.dayrange import RULE_COVERAGE
        for rule, (status, reason) in RULE_COVERAGE.items():
            if status == "n/a":
                self.assertGreater(len(reason), 40, rule)

    def test_the_table_does_not_describe_rules_that_do_not_exist(self):
        from metals.dayrange import RULE_COVERAGE
        from metals.risk import RULES
        self.assertEqual(set(RULE_COVERAGE) - set(RULES), set())


class TestR2DailyLossLimit(unittest.TestCase):
    """The fourth rule, and the first one the coverage table found rather
    than a person."""

    def test_it_is_on_by_default(self):
        self.assertTrue(DayRangeConfig().daily_loss_limit)

    def test_it_holds_entries_back_and_counts_that(self):
        r = run(DayRangeConfig(), seed=990_001, bars=20_000)
        off = run(replace(DayRangeConfig(), daily_loss_limit=False),
                  seed=990_001, bars=20_000)
        self.assertGreater(r.days_stopped_out_of_risk, 0)
        self.assertEqual(off.days_stopped_out_of_risk, 0)

    def test_the_day_is_bounded_by_the_broker_rollover(self):
        """Resetting at midnight UTC would refill the budget in the middle
        of the New York session, which is where the losses that trigger it
        happen."""
        import inspect
        from metals import dayrange
        src = inspect.getsource(dayrange.run)
        self.assertIn("ROLLOVER_HOUR_UTC", src)
        self.assertIn("day_start_equity", src)

    def test_the_simulator_penalises_the_rule_and_that_is_expected(self):
        """Measured: +0.100R with the limit against +0.113R without, and the
        worst market goes from +0.86% to -2.78%.

        Read carelessly that says the safety rule makes things worse. What
        it actually says is that this simulator hands the strategy a real
        edge, so interrupting it after a bad day costs the recovery. A daily
        limit is insurance against the case where the edge is absent -- the
        case nobody here has ruled out for real gold -- and a market that
        pays you to keep trading cannot price insurance.
        """
        with_rule = sweep(DayRangeConfig(), markets=10, bars=20_000,
                          seed_base=990_000)
        without = sweep(replace(DayRangeConfig(), daily_loss_limit=False),
                        markets=10, bars=20_000, seed_base=990_000)
        self.assertLessEqual(with_rule.mean_expectancy_r,
                             without.mean_expectancy_r + 1e-9)


class TestTheTrainingLogKnowsItsOwnRegime(unittest.TestCase):
    """The training log accumulates across engine changes.

    slippage_fraction was already recorded per iteration. R2 and M5 were
    added to the engine later, so an iteration run before them is not
    comparable with one run after -- and summarise() pools everything. The
    log turned out to be split already: three iterations at slippage 0 and
    three at 0.5, invisible until asked.
    """

    def test_the_regime_label_names_every_rule_that_can_differ(self):
        from metals.train import regime_of
        label = regime_of({"slippage_fraction": 0.5,
                           "daily_loss_limit": True, "weekend_flat": True})
        self.assertIn("Slippage 0.5", label)
        self.assertIn("R2 an", label)
        self.assertIn("M5 an", label)

    def test_an_old_entry_reads_as_the_rules_it_actually_ran_without(self):
        """An iteration from before the field existed really did run with
        the rule off. Defaulting it to on would rewrite history."""
        from metals.train import regime_of
        self.assertIn("R2 aus", regime_of({"slippage_fraction": 0.5}))
        self.assertIn("M5 aus", regime_of({"slippage_fraction": 0.5}))

    def test_two_regimes_produce_different_labels(self):
        from metals.train import regime_of
        a = regime_of({"slippage_fraction": 0.0, "daily_loss_limit": False,
                       "weekend_flat": False})
        b = regime_of({"slippage_fraction": 0.5, "daily_loss_limit": True,
                       "weekend_flat": True})
        self.assertNotEqual(a, b)

    def test_a_boundary_winner_is_recognised(self):
        """Five of the first six iterations picked the lowest or highest
        value on their grid. That means the sweep ran out of range rather
        than finding a peak, and the report has to say so."""
        from metals.train import Iteration
        edge = Iteration(index=0, dial="take_fraction", seed_base=0,
                         markets=4, bars=100, best_value=1.0,
                         results=[{"value": v} for v in (0.3, 0.5, 0.75, 1.0)])
        self.assertTrue(edge.winner_is_on_the_grid_edge)
        inner = Iteration(index=0, dial="take_fraction", seed_base=0,
                          markets=4, bars=100, best_value=0.5,
                          results=[{"value": v} for v in (0.3, 0.5, 0.75, 1.0)])
        self.assertFalse(inner.winner_is_on_the_grid_edge)

    def test_an_iteration_without_results_is_not_called_a_boundary_hit(self):
        from metals.train import Iteration
        empty = Iteration(index=0, dial="x", seed_base=0, markets=1, bars=1)
        self.assertFalse(empty.winner_is_on_the_grid_edge)

    def test_the_real_log_is_flagged_as_mixed(self):
        """Not a hypothetical: the log on disk spans two cost models."""
        from metals.train import load_log, regime_of, summarise
        log = load_log()
        if len({regime_of(e) for e in log}) > 1:
            self.assertIn("mischt Regelwerke", summarise())
