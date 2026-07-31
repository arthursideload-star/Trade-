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
            self.assertIn("ungleiche Einsaetze", paper.render(s),
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


class TestTheCommandLineActuallyPassesItsArguments(LedgerFixture):
    """The gap that let a broken --news ship for ten sessions.

    Every test for the blackout called run_session directly, so they all
    passed while `python -m metals paper --news ...` did nothing: the
    argument had been wired into the wrong function. A unit test of the
    engine cannot catch a command that never reaches the engine, so these
    go through the parser and the command function.
    """

    def _run(self, argv: list[str]):
        from metals.cli import build_parser
        args = build_parser().parse_args(argv)
        return args

    def _base_argv(self) -> list[str]:
        return ["paper", "--price", "4105.62", "--high", "4137.85",
                "--low", "4073.39", "--dry-run"]

    def test_news_reaches_the_session(self):
        from metals.cli import cmd_paper
        args = self._run(self._base_argv() + ["--news", "12:30,18:00"])
        captured: dict = {}
        real = paper.run_session

        def spy(**kwargs):
            captured.update(kwargs)
            return real(**kwargs)

        with mock.patch.object(paper, "run_session", spy):
            cmd_paper(args)
        self.assertEqual(captured.get("news_times_utc"), ((12, 30), (18, 0)))

    def test_spread_reaches_the_session(self):
        from metals.cli import cmd_paper
        args = self._run(self._base_argv() + ["--spread", "0.34"])
        captured: dict = {}
        real = paper.run_session

        def spy(**kwargs):
            captured.update(kwargs)
            return real(**kwargs)

        with mock.patch.object(paper, "run_session", spy):
            cmd_paper(args)
        self.assertEqual(captured.get("spread_usd_oz"), 0.34)

    def test_a_dry_run_does_not_touch_the_ledger(self):
        from metals.cli import cmd_paper
        cmd_paper(self._run(self._base_argv()))
        self.assertEqual(paper.sessions_so_far(), 0)


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
        text = paper.summarise()
        self.assertIn("Konto lief gegen die Regelguete", text)
        self.assertIn("1 von 2", text)


class TestTheVolatilityWarning(LedgerFixture):
    """The chain's most easily missed bias: which day it kept repeating.

    Every session so far calibrated to 30 July -- an FOMC day whose 2.23%
    range is 1.42 times a typical one. Measured, that lifts the median
    session from about +7.4% to +9.4%. Repeating one wide day and reading
    the total as a forecast is a mistake that looks exactly like data, so
    the session has to say when its day was unusual.
    """

    def test_an_unusually_wide_day_is_flagged(self):
        s = run_session(**TODAY)          # 30 July, 2.23%
        text = paper.render(s)
        self.assertIn("untypischer Tag", text)
        self.assertIn("volatiler", text)

    def test_an_unusually_quiet_day_is_flagged_too(self):
        price = 4_102.83
        span = price * paper.TYPICAL_DAY_RANGE_PCT / 100 * 0.4
        s = run_session(gold_price=price, day_high=price + span / 2,
                        day_low=price - span / 2, price_source="t",
                        start_equity_eur=400.0)
        text = paper.render(s)
        self.assertIn("untypischer Tag", text)
        self.assertIn("ruhiger", text)

    def test_a_typical_day_is_not_flagged(self):
        price = 4_102.83
        span = price * paper.TYPICAL_DAY_RANGE_PCT / 100
        s = run_session(gold_price=price, day_high=price + span / 2,
                        day_low=price - span / 2, price_source="t",
                        start_equity_eur=400.0)
        self.assertNotIn("untypischer Tag", paper.render(s))

    def test_the_range_is_shown_as_a_percentage_not_only_in_dollars(self):
        """90 dollars means nothing without the price it is 90 dollars of."""
        self.assertIn("2.23 %", paper.render(run_session(**TODAY)))

    def test_the_typical_range_is_derived_from_an_observation(self):
        """Not a round number someone liked: 143.97 USD over five sessions
        at ~4,103, divided by sqrt(5)."""
        import math
        derived = (143.97 / math.sqrt(5)) / 4_102.83 * 100
        self.assertAlmostEqual(paper.TYPICAL_DAY_RANGE_PCT, derived, places=1)


class TestAFixedLotBehavesLikeAFixedLot(LedgerFixture):
    """Structural check on the chain, and on the headline it produces.

    With the lot pinned at 0.01 and the price level unchanged, a session's
    P&L in euro cannot depend on how much money is in the account. So the
    absolute movement should stay flat as the chain compounds, and the
    percentage should fall in inverse proportion.

    Measured over the real chain, first nine sessions against last nine:
    account x2.07, absolute movement x0.90 against an expected x1.00, and
    percentage movement x0.42 against an expected x0.48.

    That is worth a test in both directions. It would catch a lot size that
    had started scaling with equity -- and it is also the arithmetic behind
    the headline: most of a compounded percentage comes from the sessions
    when the account was smallest, not from the strategy getting better.
    """

    def _chain(self, equities: list[float], moves: list[float]) -> None:
        for equity, move in zip(equities, moves):
            paper.append(Session(
                index=0, timestamp=0.0, date_utc="x", gold_price=4_100.0,
                day_high=4_150.0, day_low=4_050.0, price_source="t",
                start_equity_eur=equity, end_equity_eur=equity + move,
                lot=MIN_LOT, forced_risk_pct=3.0, trades=8,
                r_multiples=[0.1] * 8))

    def test_absolute_movement_is_flat_while_percentage_falls(self):
        """The signature of a fixed lot, stated as the relationship."""
        equities = [400.0, 800.0, 1_600.0]
        self._chain(equities, [40.0, 40.0, 40.0])
        rows = paper.load_ledger()
        absolutes = [r["end_equity_eur"] - r["start_equity_eur"] for r in rows]
        percents = [(r["end_equity_eur"] - r["start_equity_eur"])
                    / r["start_equity_eur"] * 100 for r in rows]
        self.assertAlmostEqual(absolutes[0], absolutes[-1])
        self.assertAlmostEqual(percents[-1], percents[0] / 4, places=6)

    def test_the_real_chain_matches_that_shape(self):
        """Loose bounds on purpose: the point is the order of magnitude,
        not a number that would need updating every session."""
        import statistics
        for _ in range(6):
            paper.append(run_session(**TODAY))
        rows = [r for r in paper.load_ledger() if r["trades"]]
        if len(rows) < 4:
            self.skipTest("not enough sessions with trades")
        half = len(rows) // 2
        early, late = rows[:half], rows[half:]

        def mean_abs(g):
            return statistics.fmean(
                abs(r["end_equity_eur"] - r["start_equity_eur"]) for r in g)

        def mean_equity(g):
            return statistics.fmean(r["start_equity_eur"] for r in g)

        grew = mean_equity(late) / mean_equity(early)
        absolute_ratio = mean_abs(late) / max(1e-9, mean_abs(early))
        self.assertGreater(grew, 1.0, "the chain did not grow, nothing to test")
        self.assertLess(absolute_ratio, grew,
                        "absolute movement grew as fast as the account, which "
                        "a fixed lot cannot do -- is the lot still fixed?")


class TestTheJournalCanBeRecomputed(LedgerFixture):
    """A ledger nobody can re-derive is a claim, not a record.

    This one has been backfilled twice -- once for the spread of risk per
    trade, once after the r_multiples bug -- and a backfill is precisely the
    operation that can rewrite history into something that no longer follows
    from its inputs.
    """

    def test_a_freshly_written_chain_verifies(self):
        for _ in range(3):
            paper.append(run_session(**TODAY))
        v = paper.verify()
        self.assertTrue(v.ok, f"{v.chain_breaks} {v.equity_mismatches} "
                              f"{v.trade_mismatches}")
        self.assertEqual(v.sessions, 3)

    def test_a_broken_chain_is_caught(self):
        """Session two opening somewhere other than session one's close."""
        paper.append(run_session(**TODAY))
        s = run_session(**TODAY)
        s.start_equity_eur = 999.0
        paper.append(s)
        v = paper.verify()
        self.assertFalse(v.ok)
        self.assertTrue(v.chain_breaks)

    def test_a_doctored_result_is_caught(self):
        """The failure mode that matters: a number edited after the fact."""
        s = run_session(**TODAY)
        s.end_equity_eur += 50.0
        paper.append(s)
        v = paper.verify()
        self.assertFalse(v.ok)
        self.assertTrue(v.equity_mismatches)

    def test_a_doctored_trade_count_is_caught(self):
        s = run_session(**TODAY)
        s.trades += 3
        paper.append(s)
        v = paper.verify()
        self.assertFalse(v.ok)
        self.assertTrue(v.trade_mismatches)

    def test_an_empty_journal_verifies_trivially(self):
        v = paper.verify()
        self.assertTrue(v.ok)
        self.assertEqual(v.sessions, 0)
        self.assertIn("Kein Journal", paper.render_verify(v))

    def test_the_report_refuses_to_sound_calm_about_a_mismatch(self):
        s = run_session(**TODAY)
        s.end_equity_eur += 50.0
        paper.append(s)
        text = paper.render_verify(paper.verify())
        self.assertIn("Kontostand weicht ab", text)
        self.assertNotIn("Keine Abweichung", text)


class TestTheEvidenceReport(LedgerFixture):
    """The report that answers the account balance rather than echoing it.

    After eleven sessions the chain was up 87% and its 100 trades produced a
    95% band from -0.043R to +0.305R -- straddling zero. Both statements are
    true at once, and only one of them is about whether the strategy works.
    """

    def _session_with(self, rs: list[float]) -> Session:
        return Session(index=0, timestamp=0.0, date_utc="x",
                       gold_price=4_100.0, day_high=4_150.0, day_low=4_050.0,
                       price_source="t", start_equity_eur=400.0,
                       end_equity_eur=420.0, lot=MIN_LOT, forced_risk_pct=6.0,
                       trades=len(rs), r_multiples=rs)

    def test_it_says_so_when_the_band_straddles_zero(self):
        paper.append(self._session_with([1.0, -1.0, 1.0, -1.0, 0.5, -0.5]))
        text = paper.evidence()
        self.assertIn("schliesst die Null ein", text)
        self.assertIn("belegt keinen Vorteil", text)

    def test_it_does_not_claim_an_edge_from_a_rising_account(self):
        """A winning chain with a band over zero must still not be described
        as proof about real gold."""
        paper.append(self._session_with([1.0] * 40))
        text = paper.evidence()
        self.assertIn("Simulator", text)

    def test_a_band_above_zero_is_immediately_qualified_by_the_peeking_risk(self):
        """The moment to be most careful, not least.

        The chain's band crossed zero at 155 trades after the report had
        already been read at 100, 116 and 134. Checking repeatedly and
        believing it once it finally reads well is precisely how a 95%
        interval stops being 95%, and the report has to say so at the exact
        moment the news is good.
        """
        from metals.journal import multiple_comparison_risk
        for _ in range(6):
            paper.append(self._session_with([1.0] * 8))
        text = paper.evidence()
        self.assertIn("ueber der Null", text)
        self.assertIn("mehrfach", text)
        self.assertIn(f"{multiple_comparison_risk(6) * 100:.0f} %", text)
        self.assertIn("VORHER", text)

    def test_a_band_straddling_zero_gets_no_peeking_note(self):
        """No need to warn about a false positive that has not occurred."""
        paper.append(self._session_with([1.0, -1.0, 0.5, -0.5]))
        self.assertNotIn("mehrfach", paper.evidence())

    def test_clustering_is_measured_rather_than_assumed_away(self):
        """Every band here treats trades as independent draws.

        Trades inside one session share a market, so that assumption is not
        free. Measured on the chain it costs nothing -- ICC 0.00 -- but a
        report that never checked would be relying on luck.
        """
        paper.append(self._session_with([1.0, -1.0, 0.5, -0.5, 0.2]))
        paper.append(self._session_with([0.8, -0.9, 0.4, -0.6, 0.1]))
        self.assertIn("Sitzungs-Clustering geprueft", paper.evidence())

    def test_strong_clustering_would_shrink_the_effective_sample(self):
        """Sessions that disagree with each other far more than their own
        trades do. Then n is not n, and the report has to say so."""
        for value in (2.0, -2.0, 2.0, -2.0):
            paper.append(self._session_with([value] * 8))
        icc, deff = paper.design_effect([e["r_multiples"]
                                         for e in paper.load_ledger()])
        self.assertGreater(deff, 1.2)
        self.assertIn("effektive Stichprobe", paper.evidence())

    def test_the_design_effect_is_one_when_there_is_nothing_to_cluster(self):
        self.assertEqual(paper.design_effect([]), (0.0, 1.0))
        self.assertEqual(paper.design_effect([[1.0, -1.0]]), (0.0, 1.0))

    def test_it_reports_how_many_more_trades_are_needed(self):
        paper.append(self._session_with([1.0, -1.0, 1.0, -1.0, 1.0, 0.2]))
        self.assertIn("Trades. Vorhanden", paper.evidence())

    def test_an_empty_ledger_says_so(self):
        self.assertIn("Noch keine Trades", paper.evidence())

    def test_it_warns_that_the_observed_edge_flatters_the_sample_size(self):
        """The trap in every "almost there" sample-size figure.

        trades_needed(observed_mean) is computed from a number the good run
        itself produced, so a lucky stretch makes the proof look nearly
        finished. On the real chain it said 155 trades against 116 held --
        four more sessions -- while the same arithmetic at a sober +0.10R
        edge said 309, or twenty-two. The journal module already reports
        against that reference; the paper chain has to use the same
        yardstick or it grades itself more kindly.
        """
        from metals.journal import REFERENCE_EDGE_R, trades_needed
        rs = [1.0, -1.0, 1.0, -1.0, 1.0, 1.0, -1.0, 1.0, 0.5, 0.5] * 6
        paper.append(self._session_with(rs))
        text = paper.evidence()

        from metals.journal import mean_and_sd
        _, sd = mean_and_sd(rs)
        modest = trades_needed(REFERENCE_EDGE_R, sd)
        self.assertIn("nach oben verzerrt", text)
        self.assertIn(f"{modest:,}", text)

    def test_a_sample_spanning_two_cost_models_says_so(self):
        """A sample is one sample only if its trades were priced alike.

        The chain's were not: spread alone before session 10, spread x 1.5
        after. Averaging across that silently is exactly the kind of thing
        that makes a number look cleaner than the data behind it.
        """
        cheap = self._session_with([1.0, -1.0, 0.5])
        cheap.slippage_fraction = 0.0
        dear = self._session_with([1.0, -1.0, 0.5])
        dear.slippage_fraction = 0.5
        paper.append(cheap)
        paper.append(dear)
        text = paper.evidence()
        self.assertIn("2 Kostenmodelle", text)
        self.assertIn("nicht homogen", text)

    def test_a_uniform_sample_gets_no_such_note(self):
        for _ in range(2):
            s = self._session_with([1.0, -1.0, 0.5])
            s.slippage_fraction = 0.5
            paper.append(s)
        self.assertNotIn("Kostenmodelle", paper.evidence())

    def test_no_such_warning_when_the_observed_edge_is_already_modest(self):
        rs = [0.1, -0.05, 0.08, -0.02] * 10
        paper.append(self._session_with(rs))
        self.assertNotIn("nach oben verzerrt", paper.evidence())

    def test_it_uses_the_projects_own_statistics(self):
        """One standard of evidence for the paper chain and the EA journal.

        If this module grew its own interval, the paper run would end up
        judged more leniently than the thing it is a rehearsal for.
        """
        from metals import journal
        rs = [1.0, -1.0, 0.5, -0.5, 1.0, -1.0, 0.3, 0.8]
        paper.append(self._session_with(rs))
        lo, hi = journal.mean_interval(rs)
        text = paper.evidence()
        self.assertIn(f"{lo:+.3f}", text)
        self.assertIn(f"{hi:+.3f}", text)

    def test_every_session_records_one_r_multiple_per_trade(self):
        s = run_session(**TODAY)
        self.assertEqual(len(s.r_multiples), s.trades)


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


class TestTheOutputReadsAsSentences(LedgerFixture):
    """Prose defects in the most-read output.

    These are not cosmetic in the way a stray space is cosmetic: this text
    is the only thing anyone reads before deciding what a session meant, and
    a warning that arrives as a broken sentence gets skipped.
    """

    def test_the_unequal_stakes_warning_is_one_sentence(self):
        s = run_session(**TODAY)
        if s.risk_spread_ratio < 3.0:
            self.skipTest("this session did not trigger the warning")
        text = paper.render(s)
        start = text.index("ACHTUNG, ungleiche Einsaetze")
        warning = " ".join(text[start:].split("\n")[0:5]).split()
        warning = " ".join(warning)
        self.assertNotIn("auseinander. Bei fester", warning)
        self.assertIn("bei fester Losgroesse riskiert jeder Trade", warning)

    def test_the_disagreement_count_explains_itself(self):
        """A bare '8 von 37' told the reader nothing about what it counted."""
        for i, (start, end, exp) in enumerate([(400.0, 380.0, 0.5),
                                               (380.0, 400.0, -0.5),
                                               (400.0, 420.0, 0.5)]):
            paper.append(Session(index=i, timestamp=0.0, date_utc="x",
                                 gold_price=4_100.0, day_high=4_150.0,
                                 day_low=4_050.0, price_source="t",
                                 start_equity_eur=start, end_equity_eur=end,
                                 lot=MIN_LOT, forced_risk_pct=5.0,
                                 trades=4, wins=2, losses=2,
                                 expectancy_r=exp))
        text = paper.summarise()
        self.assertIn("Regelguete", text)
        self.assertIn("2 von 3", text)
        self.assertIn("Vorzeichen", text)


class TestObservedRangesAndProjection(LedgerFixture):
    """The projection uses only ranges actually looked up, never a modelled
    distribution -- there is no trustworthy public figure for gold's daily
    range distribution, and inventing one would put a made-up number
    underneath every projected euro."""

    def _session(self, price, high, low, end=400.0):
        return Session(index=0, timestamp=0.0, date_utc="2026-07-30 12:00",
                       gold_price=price, day_high=high, day_low=low,
                       price_source="t", start_equity_eur=400.0,
                       end_equity_eur=end, lot=MIN_LOT, forced_risk_pct=5.0,
                       trades=4, wins=2, losses=2, expectancy_r=0.1)

    def test_the_same_day_looked_up_twice_is_one_day(self):
        """The chain re-fetches the price during a session, so the same day
        arrives at slightly different quotes. Three rows for one day would
        read as three days of evidence."""
        self.paper_append_many([
            self._session(4_100.0, 4_141.0, 4_100.0),
            self._session(4_110.0, 4_151.1, 4_110.1),
        ])
        ranges = paper.observed_ranges()
        self.assertEqual(len(ranges), 1)
        self.assertEqual(ranges[0][2], 2, "both sessions should be counted")

    def test_genuinely_different_ranges_stay_separate(self):
        self.paper_append_many([
            self._session(4_100.0, 4_141.0, 4_100.0),      # 1.00%
            self._session(4_100.0, 4_200.0, 4_100.0),      # 2.44%
        ])
        self.assertEqual(len(paper.observed_ranges()), 2)

    def test_ranges_come_back_sorted_quietest_first(self):
        self.paper_append_many([
            self._session(4_100.0, 4_200.0, 4_100.0),
            self._session(4_100.0, 4_141.0, 4_100.0),
        ])
        pcts = [pct for _, pct, _ in paper.observed_ranges()]
        self.assertEqual(pcts, sorted(pcts))

    def test_an_empty_ledger_says_so_rather_than_projecting_nothing(self):
        self.assertIn("Noch keine", paper.project())

    def test_the_projection_refuses_to_call_itself_a_forecast(self):
        self.paper_append_many([self._session(4_100.0, 4_141.0, 4_100.0)])
        text = paper.project(days=5, trials=5)
        self.assertIn("KEINE Prognose", text)
        self.assertIn("Simulator", text)

    def paper_append_many(self, sessions):
        for i, s in enumerate(sessions):
            s.index = i
            paper.append(s)


class TestPriceInputsMustAgree(LedgerFixture):
    """Three numbers from a lookup, easy to take from three places.

    Over one closed weekend the feeds quoted gold at 3,990, 4,052, 4,057 and
    4,110 at the same moment. Pairing one source's spot with another's range
    produced a session that ran, reported and compounded exactly like a
    sound one -- nothing downstream can tell the difference, so the check
    has to sit at the door.
    """

    def test_a_price_below_the_days_low_is_refused(self):
        with self.assertRaises(paper.PriceInputError):
            paper.check_price_inputs(3_989.95, 4_111.19, 4_069.83)

    def test_a_price_above_the_days_high_is_refused(self):
        with self.assertRaises(paper.PriceInputError):
            paper.check_price_inputs(4_200.0, 4_111.19, 4_069.83)

    def test_an_inverted_range_is_refused(self):
        with self.assertRaises(paper.PriceInputError):
            paper.check_price_inputs(4_090.0, 4_069.83, 4_111.19)

    def test_the_boundaries_themselves_are_allowed(self):
        paper.check_price_inputs(4_069.83, 4_111.19, 4_069.83)
        paper.check_price_inputs(4_111.19, 4_111.19, 4_069.83)

    def test_run_session_refuses_rather_than_producing_a_tidy_nothing(self):
        with self.assertRaises(paper.PriceInputError):
            run_session(gold_price=3_989.95, day_high=4_111.19,
                        day_low=4_069.83, price_source="mismatched")

    def test_the_message_says_what_to_do(self):
        try:
            paper.check_price_inputs(3_989.95, 4_111.19, 4_069.83)
        except paper.PriceInputError as exc:
            self.assertIn("Quellen", str(exc))
            self.assertIn("neu holen", str(exc))

    def test_every_session_already_recorded_would_pass(self):
        """The guard is preventive. If it were retroactively catching
        entries, the chain would need repairing before anything else."""
        import json
        import os

        real = os.path.join("training", "paper-ledger.jsonl")
        if not os.path.exists(real):
            self.skipTest("no recorded chain in this checkout")
        with open(real, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                e = json.loads(line)
                paper.check_price_inputs(e["gold_price"], e["day_high"],
                                         e["day_low"])


class TestReplayingTheChain(LedgerFixture):
    """How much of the recorded result is the rules and how much the draw.

    The chain is one path. Re-running it on markets it never saw, with every
    session keeping its own calibration and order, isolates that question --
    and the answer turned out to matter: the recorded run sits at the 92nd
    percentile, so the headline owes most of its size to the sequence.
    """

    def _session(self, i, start, end):
        return Session(index=i, timestamp=0.0, date_utc="2026-07-30 12:00",
                       gold_price=4_100.0, day_high=4_141.0, day_low=4_100.0,
                       price_source="t", start_equity_eur=start,
                       end_equity_eur=end, lot=MIN_LOT, forced_risk_pct=5.0,
                       trades=4, wins=2, losses=2, expectancy_r=0.1)

    def test_an_empty_ledger_replays_to_nothing_rather_than_crashing(self):
        r = paper.replay_chain(runs=2)
        self.assertEqual(r.finals_eur, [])
        self.assertIn("Noch keine", paper.render_replay(r))

    def test_every_replay_starts_where_the_real_chain_started(self):
        paper.append(self._session(0, 400.0, 450.0))
        paper.append(self._session(1, 450.0, 500.0))
        r = paper.replay_chain(runs=3)
        self.assertEqual(r.start_eur, 400.0)
        self.assertEqual(r.actual_eur, 500.0)
        self.assertEqual(len(r.finals_eur), 3)

    def test_replays_differ_from_each_other(self):
        """If they did not, the seeds would not be doing their job and the
        whole comparison would be one run counted many times."""
        paper.append(self._session(0, 400.0, 450.0))
        r = paper.replay_chain(runs=4)
        self.assertGreater(len(set(r.finals_eur)), 1)

    def test_the_percentile_places_the_actual_run_among_them(self):
        r = paper.Replay(finals_eur=[100.0, 200.0, 300.0, 400.0],
                         actual_eur=350.0, start_eur=100.0)
        self.assertAlmostEqual(r.percentile_of_actual, 75.0)

    def test_a_lucky_run_is_called_lucky(self):
        r = paper.Replay(finals_eur=[float(x) for x in range(100)],
                         actual_eur=95.0, start_eur=10.0)
        text = paper.render_replay(r)
        self.assertIn("oberen Fuenftel", text)
        self.assertIn("Marktfolge", text)

    def test_an_unlucky_run_is_called_that_too(self):
        r = paper.Replay(finals_eur=[float(x) for x in range(100)],
                         actual_eur=5.0, start_eur=1.0)
        self.assertIn("unteren Fuenftel", paper.render_replay(r))

    def test_it_counts_replays_that_lost_money(self):
        r = paper.Replay(finals_eur=[50.0, 150.0, 200.0, 300.0],
                         actual_eur=200.0, start_eur=100.0)
        self.assertAlmostEqual(r.share_losing, 0.25)


class TestVolatilityDependence(LedgerFixture):
    """The chain's single biggest lever, measured instead of caveated.

    Eleven sessions ran on 30 July, an FOMC day with a 2.23% range against
    a typical 1.57%. "That flatters the result" was already in the docs as
    a warning; this turns it into a number.
    """

    def test_a_wider_day_pays_more(self):
        v = paper.volatility_dependence(4_086.21, range_pcts=(0.6, 3.2),
                                        equity_eur=1_600.0, days=20)
        self.assertGreater(v.wildest[1], v.quietest[1])

    def test_the_return_grows_faster_than_the_range(self):
        """The mechanistic finding: this is range harvesting, and a
        generator that mean-reverts inside the day is generous with range
        in a way real gold is not."""
        v = paper.volatility_dependence(4_086.21,
                                        range_pcts=(0.6, 1.2, 2.0, 3.2),
                                        equity_eur=1_600.0, days=25)
        self.assertGreater(v.return_multiple, v.range_multiple)
        self.assertTrue(v.grows_faster_than_the_range)

    def test_the_report_says_which_day_was_repeated_matters(self):
        v = paper.volatility_dependence(4_086.21, range_pcts=(0.6, 3.2),
                                        equity_eur=1_600.0, days=15)
        text = paper.render_volatility_dependence(v)
        self.assertIn("Kette", text)
        self.assertIn("Hebel", text)

    def test_rows_are_ordered_by_range(self):
        v = paper.volatility_dependence(4_086.21,
                                        range_pcts=(0.6, 1.2, 2.0),
                                        equity_eur=1_600.0, days=10)
        self.assertEqual([r[0] for r in v.rows], [0.6, 1.2, 2.0])

    def test_each_range_uses_its_own_markets(self):
        """Otherwise the comparison would be one market seen seven times,
        and the trend would be an artefact of that market."""
        v1 = paper.volatility_dependence(4_086.21, range_pcts=(1.2,),
                                         equity_eur=1_600.0, days=10,
                                         seed_base=800_000)
        v2 = paper.volatility_dependence(4_086.21, range_pcts=(1.2,),
                                         equity_eur=1_600.0, days=10,
                                         seed_base=900_000)
        self.assertNotEqual(v1.rows[0][1], v2.rows[0][1])


class TestTheBlockTable(LedgerFixture):
    """The five-session overview, which is read far more often than the
    ledger and therefore has more room to mislead."""

    def _fill(self, ends):
        start = 400.0
        for i, end in enumerate(ends):
            paper.append(Session(index=i, timestamp=0.0, date_utc="x",
                                 gold_price=4_100.0, day_high=4_150.0,
                                 day_low=4_050.0, price_source="t",
                                 start_equity_eur=start, end_equity_eur=end,
                                 lot=MIN_LOT, forced_risk_pct=5.0,
                                 trades=4, wins=2, losses=2,
                                 expectancy_r=0.1))
            start = end

    def test_blocks_are_contiguous_and_cover_everything(self):
        self._fill([410, 420, 430, 440, 450, 460, 470])
        bs = paper.blocks(size=5)
        self.assertEqual([(b.first, b.last) for b in bs], [(1, 5), (6, 7)])
        self.assertEqual(sum(b.trades for b in bs), 7 * 4)

    def test_a_block_carries_the_equity_across_its_own_span(self):
        self._fill([410, 420, 430, 440, 450])
        b = paper.blocks(size=5)[0]
        self.assertEqual(b.start_equity_eur, 400.0)
        self.assertEqual(b.end_equity_eur, 450.0)
        self.assertAlmostEqual(b.pnl_eur, 50.0)

    def test_a_losing_session_inside_a_winning_block_is_still_counted(self):
        """Grouping hides single-session noise on purpose. It must not also
        hide a bad session -- otherwise the table reads smoother than the
        chain actually was."""
        self._fill([500, 300, 600, 700, 800])
        b = paper.blocks(size=5)[0]
        self.assertGreater(b.return_pct, 0)
        self.assertEqual(b.sessions_up, 4)

    def test_the_total_row_matches_the_chain_ends(self):
        self._fill([410, 420, 430, 440, 450, 460])
        bs = paper.blocks(size=5)
        self.assertEqual(bs[0].start_equity_eur, 400.0)
        self.assertEqual(bs[-1].end_equity_eur, 460.0)

    def test_the_table_says_a_session_is_a_day_not_an_hour(self):
        """The misreading that actually happened, pinned so it cannot
        return: the chain was read as hours of trading."""
        self._fill([410, 420])
        text = paper.render_blocks(size=5)
        self.assertIn("HANDELSTAG", text)
        self.assertIn("URTEIL", text)

    def test_it_says_so_when_there_is_nothing_yet(self):
        self.assertIn("Noch keine", paper.render_blocks())


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

    def test_a_growing_account_on_a_fixed_lot_gets_safer_and_says_so(self):
        """The one thing compounding does for free, and the trap next to it.

        The lot stays 0.01 while the account grows, so the share of the
        account at risk falls on its own -- 5.9% at session 1 against 2.1%
        at session 10 in the real chain. Scaling the lot with the account
        gives exactly that away, which is what most small accounts do.
        """
        for equity, risk in ((400.0, 6.0), (500.0, 4.0), (700.0, 2.0)):
            paper.append(Session(
                index=0, timestamp=0.0, date_utc="x", gold_price=4_100.0,
                day_high=4_150.0, day_low=4_050.0, price_source="t",
                start_equity_eur=equity, end_equity_eur=equity + 10,
                lot=MIN_LOT, forced_risk_pct=risk, trades=5,
                expectancy_r=0.1))
        text = paper.summarise()
        self.assertIn("Risiko am Anfang / zuletzt", text)
        self.assertIn("Lot mitwachsen", text)

    def test_a_rising_risk_share_is_not_given_the_reassuring_note(self):
        for equity, risk in ((700.0, 2.0), (500.0, 4.0), (400.0, 6.0)):
            paper.append(Session(
                index=0, timestamp=0.0, date_utc="x", gold_price=4_100.0,
                day_high=4_150.0, day_low=4_050.0, price_source="t",
                start_equity_eur=equity, end_equity_eur=equity - 10,
                lot=MIN_LOT, forced_risk_pct=risk, trades=5,
                expectancy_r=-0.1))
        self.assertNotIn("Lot mitwachsen", paper.summarise())

    def test_it_refuses_to_sound_conclusive_on_a_short_chain(self):
        paper.append(run_session(**TODAY))
        self.assertIn("Anekdote", paper.summarise())


if __name__ == "__main__":
    unittest.main()


class TestTheDrawdownIsNotUnderstated(LedgerFixture):
    """Close-to-close hides most of what an account lives through.

    The chain reported an 8.0% worst drawdown for twenty-nine sessions.
    Marked to market inside the sessions it is 23.1% -- nearly three times
    as deep. The floating value was already being computed every bar for the
    stop-out check and thrown away, so the understatement was free to
    persist.

    It matters beyond presentation: a margin call responds to the marked
    value, not to the closing one.
    """

    def test_a_session_records_its_intraday_drawdown(self):
        s = run_session(**TODAY)
        self.assertGreaterEqual(s.intraday_drawdown_pct, 0.0)

    def test_the_run_tracks_a_peak_and_a_trough(self):
        from metals.dayrange import DayRangeConfig, run as run_days
        r = run_days(DayRangeConfig(start_equity=432.0, lot=0.01,
                                    risk_pct=None), seed=11, bars=1_440)
        self.assertGreaterEqual(r.peak_equity, r.start_equity)
        self.assertLessEqual(r.trough_equity, r.peak_equity)
        self.assertGreater(r.max_drawdown_pct, 0.0)

    def test_a_winning_session_can_still_have_dipped(self):
        """The case that makes the close-to-close figure misleading."""
        from metals.dayrange import DayRangeConfig, run as run_days
        r = run_days(DayRangeConfig(start_equity=432.0, lot=0.01,
                                    risk_pct=None), seed=11, bars=1_440)
        self.assertGreater(r.return_pct, 0.0)
        self.assertGreater(r.max_drawdown_pct, r.return_pct * 0.5,
                           "this run ended up while dipping more than half "
                           "its gain -- if that stops being true, pick "
                           "another seed rather than dropping the check")

    def test_the_summary_reports_both_and_labels_which_is_which(self):
        for _ in range(3):
            paper.append(run_session(**TODAY))
        text = paper.summarise()
        self.assertIn("Schluss zu Schluss", text)
        self.assertIn("innerhalb einer Sitzung", text)

    def test_the_session_output_shows_the_dip(self):
        s = run_session(**TODAY)
        if s.intraday_drawdown_pct > 0:
            self.assertIn("Unterwegs", paper.render(s))


class TestTheVerdictDocumentStaysTrue(unittest.TestCase):
    """docs/URTEIL.md is the one page someone might read on its own.

    It reports a positive result, which is exactly when the caveats are
    most likely to get trimmed later. These tests hold the five of them in
    place and check the headline figures against the code rather than
    against the last time someone typed them.
    """

    @classmethod
    def setUpClass(cls):
        import pathlib
        cls.text = pathlib.Path("docs/URTEIL.md").read_text(encoding="utf-8")

    def test_it_names_all_five_reasons_the_result_is_not_transferable(self):
        for phrase in ("Simulator enthält", "36-mal hingesehen",
                       "volatilen Tag", "Kostenmodelle", "EA steigt anders"):
            self.assertIn(phrase, self.text,
                          f"the caveat about {phrase!r} has gone missing")

    def test_it_admits_the_preregistration_was_not_clean(self):
        """The most tempting thing to quietly drop: the sample size was
        fixed after 155 trades were already visible."""
        self.assertIn("keine saubere Vorregistrierung", self.text)
        self.assertIn("155", self.text)

    def test_it_does_not_claim_the_strategy_earns_on_real_gold(self):
        lowered = self.text.lower()
        for phrase in ("verdient auf echtem gold", "beweist, dass",
                       "garantiert", "risikofrei"):
            self.assertNotIn(phrase, lowered)

    def test_the_shuffle_range_it_quotes_matches_the_training_log(self):
        from metals.train import load_log
        log = load_log()
        if not log:
            self.skipTest("no training log")
        survives = [max(0.0, e["shuffle_random_r"] / e["shuffle_real_r"])
                    for e in log if e["shuffle_real_r"] > 0]
        if survives:
            self.assertLessEqual(max(survives), 0.30,
                                 "the document claims 0-26% survives "
                                 "shuffling; the log now says otherwise")

    def test_it_points_at_real_data_as_the_next_step_not_more_sessions(self):
        self.assertIn("--file XAU_5m_data.csv", self.text)
        self.assertIn("Nicht mehr Sitzungen auf dem Simulator", self.text)

    def test_it_states_the_intraday_drawdown_rather_than_the_flattering_one(self):
        self.assertIn("23,1", self.text)


class TestTheSourceDateIsChecked(LedgerFixture):
    """The audit trail has to point at the right day.

    Added after a session was recorded with "01.08.2026" in its source line
    while the clock recorded 31.07. Nothing downstream reads that text, so
    the mistake was invisible -- and an invisible error in the field whose
    only job is provenance would have outlived every number derived from it.
    """

    def test_a_contradicting_date_is_reported(self):
        self.assertIsNotNone(
            paper.source_date_conflict("investing.com 01.08.2026",
                                       "2026-07-31 15:43"))

    def test_the_matching_date_passes_in_both_notations(self):
        for text in ("investing.com 31.07.2026", "tradingeconomics 2026-07-31"):
            self.assertIsNone(
                paper.source_date_conflict(text, "2026-07-31 15:43"), text)

    def test_a_provider_date_one_day_ahead_near_midnight_is_legitimate(self):
        """The false positive the check's own first run produced.

        Sessions 16-19 ran at 23:30-23:54 UTC carrying provider dates of the
        following day, and were flagged. They were correct: at that hour it
        is already tomorrow across Europe and Asia, and a provider dates its
        quote in its own timezone. A check that cries wolf on the ordinary
        case gets switched off, so the grace window is part of the rule.
        """
        self.assertIsNone(
            paper.source_date_conflict("tradersunion 31.07.2026 Spot 4105.62",
                                       "2026-07-30 23:30"))
        self.assertIsNone(
            paper.source_date_conflict("IFCM 30.07.2026",
                                       "2026-07-31 00:45"))

    def test_the_grace_does_not_extend_to_the_middle_of_the_day(self):
        self.assertIsNotNone(
            paper.source_date_conflict("investing.com 01.08.2026",
                                       "2026-07-31 12:00"))

    def test_two_days_off_is_a_conflict_whatever_the_hour(self):
        self.assertIsNotNone(
            paper.source_date_conflict("investing.com 29.07.2026",
                                       "2026-07-31 23:45"))

    def test_an_unparseable_timestamp_does_not_raise(self):
        self.assertIsNone(paper.source_date_conflict("x 01.08.2026", "x"))
        self.assertIsNone(paper.source_date_conflict("x 01.08.2026", ""))

    def test_an_impossible_date_in_the_text_is_skipped(self):
        self.assertIsNone(
            paper.source_date_conflict("Charge 32.13.2026", "2026-07-31 12:00"))

    def test_a_source_without_a_date_is_not_an_error(self):
        """Not every provider quote carries one, and demanding it would
        turn a provenance note into a form to be filled in."""
        self.assertIsNone(
            paper.source_date_conflict("myfxbook, Mitte aus Bid/Ask",
                                       "2026-07-31 15:43"))

    def test_prices_in_the_source_are_not_mistaken_for_dates(self):
        self.assertIsNone(
            paper.source_date_conflict("Preis 4110.14, Spanne 4069.83–4111.19",
                                       "2026-07-31 15:43"))

    def test_verify_fails_the_whole_pass_on_a_wrong_date(self):
        paper.append(Session(index=0, timestamp=0.0,
                             date_utc="2026-07-31 15:43",
                             gold_price=4_100.0, day_high=4_150.0,
                             day_low=4_050.0,
                             price_source="investing.com 05.08.2026",
                             start_equity_eur=400.0, end_equity_eur=400.0,
                             lot=MIN_LOT, forced_risk_pct=5.0))
        v = paper.verify()
        self.assertTrue(v.date_mismatches)
        self.assertFalse(v.ok)
        self.assertIn("Quellendatum widerspricht", paper.render_verify(v))
