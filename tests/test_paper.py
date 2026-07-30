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
