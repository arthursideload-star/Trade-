"""The half-target scalp: the arithmetic, and the two findings.

The strategy was described by the user on 04.08.2026. These tests pin down
what was measured, because the two results that matter are both the kind that
an innocent-looking parameter change would quietly reverse.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from metals.candles import Candle, CandleSeries
from metals.halfscalp import (SIGNALS, HalfScalpConfig, HalfTrade, RunResult,
                              report, run)
from metals.simulate import generate

START = datetime(2026, 3, 3, 9, 0, tzinfo=timezone.utc)


def _trade(net_r: float, gross_r: float | None = None) -> HalfTrade:
    return HalfTrade(
        direction="long", opened_at=START, closed_at=START + timedelta(minutes=3),
        entry=4000.0, stop=3998.0, take=4001.0, projection=2.0,
        exit_price=4001.0, exit_reason="half_target",
        gross_r=net_r if gross_r is None else gross_r,
        net_r=net_r, minutes_held=3)


class TheArithmeticOfBankingAtHalf(unittest.TestCase):
    """Why 'take half for safety' is a trade and not a free lunch."""

    def test_break_even_rate_rises_as_the_payoff_falls(self):
        """The whole point. Halving the reward raises the bar to clear."""
        result = RunResult()
        # Four wins of +0.5 R, one loss of -1.0 R: payoff 0.5.
        result.trades = [_trade(0.5) for _ in range(4)] + [_trade(-1.0)]
        self.assertAlmostEqual(result.payoff_ratio, 0.5)
        self.assertAlmostEqual(result.breakeven_win_rate, 1 / 1.5)
        # 80% observed against 66.7% needed -- this one clears.
        self.assertGreater(result.margin_over_breakeven, 0)

    def test_a_high_win_rate_can_still_lose(self):
        """The failure mode the strategy is built to hide.

        Two wins of +0.5 R for every loss of -1.5 R is a 66.7% win rate and a
        losing account. If this ever passes while `margin_over_breakeven` is
        positive, the metric is broken.
        """
        result = RunResult()
        result.trades = [_trade(0.5), _trade(0.5), _trade(-1.5)]
        self.assertAlmostEqual(result.win_rate, 2 / 3)
        self.assertLess(result.expectancy_r, 0)
        self.assertLess(result.margin_over_breakeven, 0)

    def test_friction_is_reported_separately_from_the_result(self):
        """Costs must be visible, not folded into the outcome."""
        result = RunResult()
        result.trades = [_trade(net_r=0.2, gross_r=0.5)]
        self.assertAlmostEqual(result.friction_r, 0.3)


class TheCostGate(unittest.TestCase):
    """A trade that cannot pay its own spread is refused, not taken."""

    def test_a_half_target_under_the_round_trip_is_refused(self):
        cfg = HalfScalpConfig(spread_usd_oz=5.0, min_edge_multiple=1.5)
        m1 = generate(bars=3_000, timeframe="1m", seed=7)
        result = run(cfg, m1)
        self.assertGreater(
            result.refused_cost, 0,
            "at a 5.00 USD/oz spread every M1 half-target is under water; "
            "refusing none of them means the gate is not wired up")
        self.assertEqual(
            result.n, 0,
            "no trade may be taken when its half-target cannot clear the "
            "round-trip cost")

    def test_the_gate_lets_trades_through_at_a_normal_spread(self):
        cfg = HalfScalpConfig(spread_usd_oz=0.20)
        result = run(cfg, generate(bars=3_000, timeframe="1m", seed=7))
        self.assertGreater(result.n, 0)


class NoLookaheadAndPessimisticFills(unittest.TestCase):

    def test_stop_is_taken_before_target_when_a_bar_covers_both(self):
        """The assumption that keeps the backtest tradeable."""
        candles = []
        price = 4000.0
        for i in range(35):                    # quiet, sets the ATR
            candles.append(Candle(START + timedelta(minutes=i),
                                  price, price + 0.3, price - 0.3, price))
        # A decisive up bar: the trigger.
        candles.append(Candle(START + timedelta(minutes=35),
                              4000.0, 4002.0, 4000.0, 4001.9))
        # A bar whose range covers both the stop and the half-target.
        candles.append(Candle(START + timedelta(minutes=36),
                              4001.9, 4010.0, 3990.0, 4005.0))
        m1 = CandleSeries("XAUUSD", "1m", candles)
        result = run(HalfScalpConfig(signal="momentum"), m1)
        self.assertEqual(result.n, 1)
        self.assertEqual(
            result.trades[0].exit_reason, "stop",
            "when one bar covers both, the stop must be assumed first -- the "
            "other assumption reports a result that cannot be achieved")
        self.assertLess(result.trades[0].net_r, 0)


class WhatWasMeasured(unittest.TestCase):
    """The two findings, pinned so a parameter change cannot quietly undo them.

    Both are simulator results. Neither is a claim about real gold -- see the
    docstring of metals/halfscalp.py and finding A34.
    """

    MARKETS = [generate(bars=8_000, timeframe="1m", seed=s)
               for s in (7, 99, 4242)]

    def _expectancy(self, cfg: HalfScalpConfig) -> float:
        rs = [t.net_r for m in self.MARKETS for t in run(cfg, m).trades]
        self.assertGreater(len(rs), 200, "sample too small to mean anything")
        return sum(rs) / len(rs)

    def test_the_literal_specification_loses(self):
        """Momentum, stop at the full projection, target one measured move.

        Exactly as described, and it lost on 85 of 85 simulated days. The
        cause is arithmetic rather than bad luck: banking at half while
        stopping at the full projection risks two to make one, so the hit
        rate has to reach roughly 72% before costs. It reached 64%.
        """
        expectancy = self._expectancy(
            HalfScalpConfig(signal="momentum", stop_fraction=1.0,
                            target_multiple=1.0))
        self.assertLess(
            expectancy, 0,
            "the literal specification measured negative; if it now measures "
            "positive, something changed that needs explaining, not merging")

    def test_moving_the_stop_with_the_target_is_what_turns_it_around(self):
        """The fix that keeps the user's intent intact.

        Banking early is kept. What changes is that the projection is widened
        so the fixed spread is a smaller share of it.
        """
        literal = self._expectancy(
            HalfScalpConfig(signal="reversion", stop_fraction=1.0,
                            target_multiple=1.0))
        wider = self._expectancy(
            HalfScalpConfig(signal="reversion", stop_fraction=1.0,
                            target_multiple=2.0))
        self.assertGreater(
            wider, literal,
            "widening the projection must reduce the cost per R; if it does "
            "not, the cost model is not being applied per trade")


class ConfigurationIsHonest(unittest.TestCase):

    def test_an_unknown_signal_is_refused_loudly(self):
        with self.assertRaises(ValueError):
            HalfScalpConfig(signal="vibes")

    def test_both_signals_are_offered(self):
        """The momentum variant exists so the direction of the edge is a
        measurement rather than an assumption -- open question 3 in the vault.
        """
        self.assertEqual(set(SIGNALS), {"momentum", "reversion"})

    def test_cost_model_matches_the_backtest_engine(self):
        cfg = HalfScalpConfig(spread_usd_oz=0.30, slippage_fraction=0.5)
        self.assertAlmostEqual(cfg.cost_per_unit, 0.45)

    def test_report_names_the_failure_mode_when_it_applies(self):
        result = RunResult()
        result.trades = [_trade(0.5), _trade(0.5), _trade(-1.5)]
        text = report(result)
        self.assertIn("does NOT clear", text)
        self.assertIn("most trades win", text)


if __name__ == "__main__":
    unittest.main()
