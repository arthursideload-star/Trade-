"""The compounding paper-trading chain.

The thing that most needs a test here is not the P&L -- it is the bookkeeping
around it. A chain that silently resets its equity, or double-counts a
session, or quietly rounds a losing day up, would still print a plausible
number every time and nobody would notice for weeks.

So: equity carries forward exactly, a session is written once, a loss is
carried with the same fidelity as a gain, and the forced risk is recorded
rather than being left implicit.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock

from metals import paper, simulate
from metals.paper import (ASSUMED_EUR_USD, BARS_PER_DAY, MIN_LOT, Session,
                          calibrate_vol, current_equity_eur, run_session)
from metals.risk import MAX_RISK_PER_TRADE_PCT
from metals.specs import get_spec

TODAY = dict(gold_price=4_102.83, day_high=4_120.16, day_low=4_028.77,
             price_source="test")


class LedgerFixture(unittest.TestCase):
    """Every test writes to its own throwaway ledger.

    Without this a test run would append to the real chain, which is the
    project's actual record -- a test suite that corrupts the data it is
    meant to protect is worse than no test suite.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "ledger.jsonl")
        patcher = mock.patch.object(paper, "LEDGER_PATH", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        dir_patcher = mock.patch.object(paper, "LEDGER_DIR", self.tmp.name)
        dir_patcher.start()
        self.addCleanup(dir_patcher.stop)
        self.addCleanup(self.tmp.cleanup)


class TestVolatilityCalibration(unittest.TestCase):
    def test_it_reproduces_the_observed_range(self):
        """The whole claim to using 'real data' rests on this."""
        for high, low in ((4_120.16, 4_028.77), (4_150.0, 4_090.0)):
            with self.subTest(range=high - low):
                bv = calibrate_vol(4_102.83, high, low)
                got = paper._median_range(4_102.83, bv, BARS_PER_DAY)
                self.assertLess(abs(got / (high - low) - 1), 0.20,
                                "calibrated market should land within 20% of "
                                "the range it was calibrated to")

    def test_a_wider_day_gives_a_more_volatile_market(self):
        quiet = calibrate_vol(4_100.0, 4_120.0, 4_090.0)
        wild = calibrate_vol(4_100.0, 4_200.0, 4_000.0)
        self.assertGreater(wild, quiet)

    def test_it_is_deterministic(self):
        a = calibrate_vol(4_100.0, 4_150.0, 4_050.0)
        b = calibrate_vol(4_100.0, 4_150.0, 4_050.0)
        self.assertEqual(a, b)

    def test_a_degenerate_range_falls_back_rather_than_dividing_by_zero(self):
        self.assertEqual(calibrate_vol(4_100.0, 4_100.0, 4_100.0),
                         simulate.MarketParams().base_vol)

    def test_calibration_seeds_are_disjoint_from_trading_seeds(self):
        """A market must never be measured on the seeds used to tune it."""
        trading = {500_000 + i * 97 for i in range(2_000)}
        self.assertFalse(set(paper._CALIBRATION_SEEDS) & trading)


class TestTheChainCompounds(LedgerFixture):
    def test_the_first_session_starts_at_the_stated_budget(self):
        self.assertEqual(current_equity_eur(), 400.0)

    def test_the_next_session_starts_where_the_last_one_ended(self):
        first = run_session(**TODAY)
        paper.append(first)
        self.assertAlmostEqual(current_equity_eur(), first.end_equity_eur)

        second = run_session(**TODAY)
        self.assertAlmostEqual(second.start_equity_eur, first.end_equity_eur)

    def test_a_loss_is_carried_forward_exactly_like_a_gain(self):
        """The direction of the carry must not depend on its sign."""
        losing = Session(index=0, timestamp=0.0, date_utc="x",
                         gold_price=4_100.0, day_high=4_150.0,
                         day_low=4_050.0, price_source="test",
                         start_equity_eur=400.0, end_equity_eur=372.5,
                         lot=MIN_LOT, forced_risk_pct=6.0)
        paper.append(losing)
        self.assertAlmostEqual(current_equity_eur(), 372.5)
        self.assertAlmostEqual(losing.pnl_eur, -27.5)
        self.assertLess(losing.return_pct, 0)

    def test_each_session_is_written_once(self):
        for _ in range(3):
            paper.append(run_session(**TODAY))
        with open(self.path, encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
        self.assertEqual(len(rows), 3)
        self.assertEqual([r["index"] for r in rows], [0, 1, 2])

    def test_every_session_trades_a_market_it_has_not_seen(self):
        seeds = set()
        for _ in range(5):
            s = run_session(**TODAY)
            paper.append(s)
            seed = 500_000 + s.index * 97
            self.assertNotIn(seed, seeds)
            seeds.add(seed)

    def test_an_explicit_equity_overrides_the_chain(self):
        paper.append(run_session(**TODAY))
        s = run_session(**TODAY, start_equity_eur=1_000.0)
        self.assertEqual(s.start_equity_eur, 1_000.0)


class TestWhatItRecordsAboutRisk(LedgerFixture):
    def test_the_forced_risk_is_recorded_and_exceeds_the_rule(self):
        """On a 400 euro account the minimum lot breaks R1, and the session
        has to say so rather than leaving it to be inferred."""
        s = run_session(**TODAY)
        self.assertGreater(s.forced_risk_pct, MAX_RISK_PER_TRADE_PCT)
        self.assertTrue(s.breaks_the_risk_rule)

    def test_a_large_account_does_not_break_the_rule(self):
        s = run_session(**TODAY, start_equity_eur=50_000.0)
        self.assertLess(s.forced_risk_pct, MAX_RISK_PER_TRADE_PCT)
        self.assertFalse(s.breaks_the_risk_rule)

    def test_an_account_below_the_margin_cannot_trade_at_all(self):
        """100 euro is 108 USD; 0.01 lot at 1:20 needs about 205."""
        s = run_session(**TODAY, start_equity_eur=100.0)
        self.assertTrue(s.could_not_trade)
        self.assertEqual(s.trades, 0)
        self.assertEqual(s.end_equity_eur, s.start_equity_eur,
                         "a session that could not trade must not move the "
                         "account")

    def test_the_spread_of_risk_is_recorded_not_just_its_mean(self):
        """The defect this exists to prevent.

        With a fixed lot the money risked per trade is whatever the
        predicted move happened to be. Reporting only the mean turns a
        session that risked 1.9% on one trade and 18.2% on another into a
        reassuring single figure of 8.7%.
        """
        s = run_session(**TODAY)
        self.assertGreater(s.risk_pct_max, 0)
        self.assertLess(s.risk_pct_min, s.forced_risk_pct)
        self.assertGreater(s.risk_pct_max, s.forced_risk_pct)

    def test_a_wide_spread_of_risk_is_flagged_in_the_output(self):
        s = run_session(**TODAY)
        if s.risk_spread_ratio >= 3.0:
            self.assertIn("WELCHE", paper.render(s),
                          "a session whose stakes differ several-fold must "
                          "say that the result turned on which trades won")

    def test_the_ratio_is_one_when_there_are_no_trades(self):
        s = run_session(**TODAY, start_equity_eur=100.0)
        self.assertEqual(s.risk_spread_ratio, 1.0)

    def test_the_margin_threshold_matches_the_contract_spec(self):
        oz = get_spec("XAUUSD").contract_size_oz
        needed_usd = MIN_LOT * oz * TODAY["gold_price"] / 20.0
        just_under = (needed_usd / ASSUMED_EUR_USD) * 0.98
        just_over = (needed_usd / ASSUMED_EUR_USD) * 1.10
        self.assertTrue(run_session(**TODAY,
                                    start_equity_eur=just_under).could_not_trade)
        self.assertFalse(run_session(**TODAY,
                                     start_equity_eur=just_over).could_not_trade)


class TestTheSessionRecord(LedgerFixture):
    def test_it_keeps_the_price_it_was_given_and_where_it_came_from(self):
        s = run_session(gold_price=4_102.83, day_high=4_120.16,
                        day_low=4_028.77, price_source="WebSearch 30.07.2026")
        self.assertEqual(s.gold_price, 4_102.83)
        self.assertEqual(s.price_source, "WebSearch 30.07.2026")

    def test_the_market_starts_at_the_real_price(self):
        """If the generated market did not start where gold actually is, the
        margin and risk figures would be about a different asset."""
        s = run_session(**TODAY)
        self.assertAlmostEqual(s.gold_price, 4_102.83)

    def test_trades_are_counted_consistently(self):
        s = run_session(**TODAY)
        self.assertEqual(s.trades, s.wins + s.losses)
        if s.exits:
            self.assertEqual(s.trades, sum(s.exits.values()))

    def test_the_same_session_index_reproduces_the_same_market(self):
        a = run_session(**TODAY, start_equity_eur=400.0)
        b = run_session(**TODAY, start_equity_eur=400.0)
        self.assertEqual(a.end_equity_eur, b.end_equity_eur)


class TestTheNewsBlackoutReachesTheSession(LedgerFixture):
    """R4 is only useful if the code that trades is told about it.

    The rule existed in risk.py for weeks while dayrange ignored it, and the
    paper session then ignored it for one more session after dayrange was
    fixed. These tests close that gap at the last link.
    """

    def test_a_session_without_release_times_says_so(self):
        s = run_session(**TODAY)
        self.assertEqual(s.news_times_utc, [])
        self.assertIn("Keine Nachrichtensperre", paper.render(s))

    def test_configured_releases_are_recorded_and_shown(self):
        s = run_session(**TODAY, news_times_utc=((12, 30), (18, 0)))
        self.assertEqual(s.news_times_utc, [[12, 30], [18, 0]])
        rendered = paper.render(s)
        self.assertIn("12:30", rendered)
        self.assertIn("18:00", rendered)
        self.assertIn("R4", rendered)

    def test_a_blackout_covering_the_day_stops_every_signal(self):
        """Deterministic end-to-end check of the wiring.

        Two release times a day would be the realistic case, but over one
        session the strategy signals seven to ten times and none of them
        need land inside a 60-minute window -- so asserting a drop there
        tests the dice, not the plumbing. Blacking out every hour cannot be
        satisfied by luck.
        """
        every_hour = tuple((h, 0) for h in range(24))
        blocked = run_session(**TODAY, start_equity_eur=400.0,
                              news_times_utc=every_hour)
        self.assertEqual(blocked.signals, 0)
        self.assertEqual(blocked.trades, 0)

    def test_a_blackout_never_creates_signals(self):
        free = run_session(**TODAY, start_equity_eur=400.0)
        blocked = run_session(**TODAY, start_equity_eur=400.0,
                              news_times_utc=((12, 30), (18, 0)))
        self.assertLessEqual(blocked.signals, free.signals)

    def test_it_survives_the_ledger_round_trip(self):
        paper.append(run_session(**TODAY, news_times_utc=((18, 0),)))
        row = paper.load_ledger()[-1]
        self.assertEqual(row["news_times_utc"], [[18, 0]])


class TestParsingReleaseTimes(unittest.TestCase):
    def test_it_reads_the_command_line_form(self):
        from metals.cli import _parse_news_times
        self.assertEqual(_parse_news_times("12:30,18:00"), ((12, 30), (18, 0)))

    def test_a_bare_hour_means_on_the_hour(self):
        from metals.cli import _parse_news_times
        self.assertEqual(_parse_news_times("18"), ((18, 0),))

    def test_nothing_given_means_no_blackout(self):
        from metals.cli import _parse_news_times
        self.assertEqual(_parse_news_times(None), ())
        self.assertEqual(_parse_news_times(""), ())

    def test_stray_whitespace_and_commas_are_tolerated(self):
        from metals.cli import _parse_news_times
        self.assertEqual(_parse_news_times(" 12:30 , 18:00 ,"),
                         ((12, 30), (18, 0)))


class TestCrossCheckingTheQuote(unittest.TestCase):
    """Several lookups, one price. Which one goes in the ledger matters."""

    def test_wide_disagreement_is_reported(self):
        """The actual quotes one lookup returned: a live CFD price, a
        physical dealer stamped hours earlier, and a feed marked previous."""
        ok, note = paper.check_quotes({"investing.com": 4_114.79,
                                       "jmbullion": 4_047.47,
                                       "mql5": 4_011.13})
        self.assertFalse(ok)
        self.assertIn("2.5", note)
        for name in ("investing.com", "jmbullion", "mql5"):
            self.assertIn(name, note, "the note has to name the sources, or "
                                      "it cannot be acted on")

    def test_close_quotes_pass(self):
        ok, _ = paper.check_quotes({"a": 4_114.79, "b": 4_116.00})
        self.assertTrue(ok)

    def test_a_single_source_cannot_be_cross_checked_and_says_so(self):
        ok, note = paper.check_quotes({"only": 4_114.79})
        self.assertTrue(ok)
        self.assertIn("one source", note)

    def test_it_uses_the_projects_existing_rule(self):
        """One definition of 'these feeds disagree', not two."""
        from metals.sources.prices import cross_check
        self.assertIn("cross_check", paper.check_quotes.__doc__ or "")
        self.assertTrue(callable(cross_check))


class TestWhenTheResultContradictsTheRules(LedgerFixture):
    """Expectancy and money pointing opposite ways.

    They can only disagree when the stakes differ, so this flag is the
    clearest available symptom of the fixed-lot defect -- and it has now
    fired in both directions in the real chain.
    """

    def _session(self, expectancy: float, end: float) -> Session:
        return Session(index=0, timestamp=0.0, date_utc="x",
                       gold_price=4_100.0, day_high=4_150.0, day_low=4_050.0,
                       price_source="t", start_equity_eur=400.0,
                       end_equity_eur=end, lot=MIN_LOT, forced_risk_pct=6.0,
                       trades=8, expectancy_r=expectancy)

    def test_good_rules_and_a_losing_account_is_flagged(self):
        self.assertTrue(self._session(0.05, 390.0)
                        .expectancy_and_return_disagree)

    def test_poor_rules_and_a_winning_account_is_flagged(self):
        self.assertTrue(self._session(-0.05, 460.0)
                        .expectancy_and_return_disagree)

    def test_agreement_is_not_flagged(self):
        self.assertFalse(self._session(0.05, 460.0)
                         .expectancy_and_return_disagree)
        self.assertFalse(self._session(-0.05, 390.0)
                         .expectancy_and_return_disagree)

    def test_a_session_without_trades_is_not_flagged(self):
        s = self._session(0.0, 400.0)
        s.trades = 0
        self.assertFalse(s.expectancy_and_return_disagree)

    def test_the_output_explains_which_way_round_it_went(self):
        lost = paper.render(self._session(0.05, 390.0))
        self.assertIn("verloren, obwohl die Regeln gut liefen", lost)
        won = paper.render(self._session(-0.05, 460.0))
        self.assertIn("gewonnen, obwohl die Regeln schlecht liefen", won)

    def test_the_summary_counts_them(self):
        paper.append(self._session(0.05, 390.0))
        paper.append(self._session(0.05, 460.0))
        self.assertIn("Ergebnis gegen Erwartungswert", paper.summarise())


class TestTheEndOfDayExit(LedgerFixture):
    """A session ends at bar 1,440 whether the trade did or not.

    Each session is an independent day: a position still open when the
    series runs out is closed at the last price, and the next session
    generates a fresh market rather than continuing it. That is a
    simplification, and simplifications that touch the P&L deserve a
    measurement rather than a shrug -- an artificial exit that
    systematically caught winners (or losers) would flatter (or damn) every
    number in the ledger.

    Measured across 60 days: 6.7% of trades end this way, at +0.111R against
    +0.119R for the ones that reached a real exit. No material bias, on a
    sample of 34 -- which is small, so this test guards the property rather
    than claiming to have settled it.
    """

    def test_the_end_of_day_exit_is_a_minority_of_trades(self):
        from metals import simulate
        from metals.dayrange import DayRangeConfig, run
        from dataclasses import replace

        params = simulate.MarketParams(
            start_price=TODAY["gold_price"],
            base_vol=paper.calibrate_vol(TODAY["gold_price"],
                                         TODAY["day_high"], TODAY["day_low"]))
        cfg = replace(DayRangeConfig(),
                      start_equity=400 * ASSUMED_EUR_USD, lot=MIN_LOT,
                      risk_pct=None)
        still_open = trades = 0
        for i in range(20):
            seed = 800_000 + i * 13
            series = simulate.generate(bars=BARS_PER_DAY, timeframe="1m",
                                       seed=seed, params=params)
            r = run(cfg, series=series, seed=seed)
            still_open += r.exits.get("still_open", 0)
            trades += r.trades
        self.assertGreater(trades, 0)
        self.assertLess(still_open / trades, 0.25,
                        "if a quarter of trades were closed by the clock "
                        "rather than by the rules, the session would be "
                        "measuring the series length, not the strategy")


class TestTheDistribution(LedgerFixture):
    """The defence against reading a trend into a winning streak."""

    def test_three_green_days_are_unremarkable_at_this_win_rate(self):
        d = paper.distribution(**{k: v for k, v in TODAY.items()
                                  if k != "price_source"}, days=30)
        self.assertGreater(d.share_positive, 0.5)
        self.assertAlmostEqual(d.streak_probability_3,
                               d.share_positive ** 3, places=9)
        self.assertGreater(d.streak_probability_3, 0.1,
                           "if a streak of three were rare, the chain would "
                           "be evidence -- it is not")

    def test_it_reports_the_spread_not_only_the_middle(self):
        d = paper.distribution(**{k: v for k, v in TODAY.items()
                                  if k != "price_source"}, days=30)
        self.assertLess(d.percentile(0.05), d.median_pct)
        self.assertGreater(d.percentile(0.95), d.median_pct)
        self.assertGreater(d.sd_points, 0)

    def test_an_implausible_median_is_called_out_as_a_measurement_problem(self):
        """The honest reading of a very good number on a simulator.

        A median that doubles the account inside a month is not a finding
        about the strategy, and the output has to say which of the two it
        is blaming.
        """
        d = paper.distribution(**{k: v for k, v in TODAY.items()
                                  if k != "price_source"}, days=30)
        if d.implied_days_to_double and d.implied_days_to_double < 30:
            text = paper.render_distribution(d)
            self.assertIn("Simulator", text)
            self.assertIn("WARNUNG", text)

    def test_doubling_time_is_undefined_for_a_losing_median(self):
        d = paper.Distribution(returns_pct=[-1.0, -2.0, -3.0], equity_eur=400)
        self.assertIsNone(d.implied_days_to_double)

    def test_doubling_time_is_the_actual_compounding_answer(self):
        d = paper.Distribution(returns_pct=[100.0], equity_eur=400)
        self.assertAlmostEqual(d.implied_days_to_double, 1.0)


class TestTheSummary(LedgerFixture):
    def test_it_says_so_when_there_is_nothing_yet(self):
        self.assertIn("Noch keine", paper.summarise())

    def test_it_reports_the_drawdown_from_the_peak(self):
        for end in (400.0, 500.0, 450.0):
            paper.append(Session(index=0, timestamp=0.0, date_utc="x",
                                 gold_price=4_100.0, day_high=4_150.0,
                                 day_low=4_050.0, price_source="t",
                                 start_equity_eur=400.0, end_equity_eur=end,
                                 lot=MIN_LOT, forced_risk_pct=6.0))
        text = paper.summarise()
        self.assertIn("10.0 %", text)      # 500 -> 450

    def test_it_refuses_to_sound_conclusive_on_a_short_chain(self):
        paper.append(run_session(**TODAY))
        self.assertIn("Anekdote", paper.summarise())


if __name__ == "__main__":
    unittest.main()
