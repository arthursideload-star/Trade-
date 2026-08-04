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
        # 20 USD/oz is absurd on purpose. At the default projection -- twice
        # the trigger bar -- a merely bad spread still lets the widest bars
        # through, and a test of the gate should not depend on how wide the
        # widest bar in one seed happens to be.
        cfg = HalfScalpConfig(spread_usd_oz=20.0, min_edge_multiple=1.5)
        m1 = generate(bars=3_000, timeframe="1m", seed=7)
        result = run(cfg, m1)
        self.assertGreater(
            result.refused_cost, 0,
            "at a 20.00 USD/oz spread every M1 half-target is under water; "
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

    # A34 was measured under the flat spread and with no session filter,
    # which were the defaults at the time. Both defaults have since changed
    # (A35), so these tests state the old ones explicitly rather than
    # silently measuring something else and still calling it A34.
    A34 = dict(spread_model="flat", session_filter=False, trigger_atr=1.0)

    def test_the_literal_specification_loses(self):
        """Momentum, stop at the full projection, target one measured move.

        Exactly as described, and it lost on 85 of 85 simulated days. The
        cause is arithmetic rather than bad luck: banking at half while
        stopping at the full projection risks two to make one, so the hit
        rate has to reach roughly 72% before costs. It reached 64%.
        """
        expectancy = self._expectancy(
            HalfScalpConfig(signal="momentum", stop_fraction=1.0,
                            target_multiple=1.0, **self.A34))
        self.assertLess(
            expectancy, 0,
            "the literal specification measured negative; if it now measures "
            "positive, something changed that needs explaining, not merging")

    def test_widening_the_target_is_what_turns_it_around(self):
        """The fix that keeps the user's intent intact.

        Banking early is kept. What changes is that the projection is widened
        so the fixed spread is a smaller share of it.
        """
        literal = self._expectancy(
            HalfScalpConfig(signal="reversion", stop_fraction=1.0,
                            target_multiple=1.0, **self.A34))
        wider = self._expectancy(
            HalfScalpConfig(signal="reversion", stop_fraction=1.0,
                            target_multiple=2.0, **self.A34))
        self.assertGreater(
            wider, literal,
            "widening the projection must reduce the cost per R; if it does "
            "not, the cost model is not being applied per trade")


class TheSpreadIsChargedWhenItIsPaid(unittest.TestCase):
    """A35. A strategy this frequent meets the rollover whether it meant to.

    The flat model reported four times the edge the session model reports.
    These tests hold the mechanism in place; the magnitudes live in the audit.
    """

    MARKETS = [generate(bars=8_000, timeframe="1m", seed=s)
               for s in (7, 99, 4242)]

    def _expectancy(self, cfg: HalfScalpConfig) -> float:
        rs = [t.net_r for m in self.MARKETS for t in run(cfg, m).trades]
        self.assertGreater(len(rs), 100)
        return sum(rs) / len(rs)

    def test_rollover_costs_more_than_the_overlap(self):
        cfg = HalfScalpConfig(spread_model="session", spread_usd_oz=0.20)
        overlap = datetime(2026, 3, 3, 14, 0, tzinfo=timezone.utc)
        rollover = datetime(2026, 3, 3, 22, 0, tzinfo=timezone.utc)
        self.assertGreater(
            cfg.spread_at(rollover), cfg.spread_at(overlap) * 5,
            "XAUUSD_SPEC puts the rollover spread at 5.00 against a typical "
            "0.20; if these are close, the session model is not reading it")

    def test_the_flat_model_ignores_the_clock(self):
        cfg = HalfScalpConfig(spread_model="flat", spread_usd_oz=0.20)
        for hour in (2, 14, 22):
            moment = datetime(2026, 3, 3, hour, tzinfo=timezone.utc)
            self.assertAlmostEqual(cfg.spread_at(moment), 0.20)

    def test_charging_by_session_lowers_the_measured_edge(self):
        """The finding, as a direction rather than a magnitude."""
        base = dict(signal="reversion", stop_fraction=1.0,
                    target_multiple=2.0, session_filter=False)
        flat = self._expectancy(HalfScalpConfig(spread_model="flat", **base))
        session = self._expectancy(
            HalfScalpConfig(spread_model="session", **base))
        self.assertLess(
            session, flat,
            "charging the real session spread cannot make a strategy that "
            "trades around the clock look better")

    def test_the_session_filter_recovers_part_of_it(self):
        base = dict(signal="reversion", stop_fraction=1.0,
                    target_multiple=2.0, spread_model="session")
        unfiltered = self._expectancy(
            HalfScalpConfig(session_filter=False, **base))
        filtered = self._expectancy(
            HalfScalpConfig(session_filter=True, **base))
        self.assertGreater(filtered, unfiltered)

    def test_the_defaults_are_the_realistic_ones(self):
        """The defaults decide what a casual run reports, so they are a claim.

        A default of flat-and-around-the-clock reported four times the edge.
        If someone flips these back, it should be a decision with a diff.
        """
        cfg = HalfScalpConfig()
        self.assertEqual(cfg.spread_model, "session")
        self.assertTrue(cfg.session_filter)

    def test_a_trade_pays_the_spread_of_its_own_exit(self):
        """Half the round trip on the way in, half on the way out.

        A trade opened in the overlap and closed after the rollover begins
        pays both, which a single averaged figure would hide.
        """
        cfg = HalfScalpConfig(spread_model="session", session_filter=False)
        result = run(cfg, generate(bars=6_000, timeframe="1m", seed=7))
        costs = {round(t.gross_r - t.net_r, 6) for t in result.trades}
        self.assertGreater(
            len(costs), 1,
            "every trade paid the same cost, so the per-bar spread is not "
            "reaching the trade accounting")


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


class TimingIsInMinutesNotBars(unittest.TestCase):
    """The cooldown is stated in minutes and applied as a bar count.

    On M1 the two coincide, which is why the conversion was easy to omit and
    impossible to notice. The moment the module is pointed at a coarser file
    an uncorrected count waits several times too long, which is a different
    strategy wearing the same configuration.
    """

    def _cooldown_gap(self, timeframe: str, minutes: int) -> int:
        step = {"1m": 1, "5m": 5}[timeframe]
        m1 = generate(bars=3_000, timeframe=timeframe, seed=7)
        cfg = HalfScalpConfig(cooldown_minutes=minutes, session_filter=False,
                              spread_model="flat")
        trades = run(cfg, m1).trades
        self.assertGreater(len(trades), 5)
        gaps = [int((b.opened_at - a.closed_at).total_seconds() // 60)
                for a, b in zip(trades, trades[1:])]
        return min(gaps), step

    def test_a_one_minute_cooldown_does_not_become_five_on_five_minute_bars(self):
        gap_m1, _ = self._cooldown_gap("1m", 1)
        gap_m5, step = self._cooldown_gap("5m", 1)
        self.assertLessEqual(
            gap_m5, step,
            "a 1-minute cooldown on 5m bars must wait one bar, not five; "
            "a raw `i + cooldown_minutes` waits five bars = 25 minutes")

    def test_the_cooldown_is_never_shorter_than_one_bar(self):
        m1 = generate(bars=2_000, timeframe="5m", seed=7)
        cfg = HalfScalpConfig(cooldown_minutes=0, session_filter=False,
                              spread_model="flat")
        trades = run(cfg, m1).trades
        self.assertGreater(len(trades), 2)
        for a, b in zip(trades, trades[1:]):
            self.assertGreater(
                b.opened_at, a.closed_at,
                "two positions must never overlap, whatever the cooldown says")


class RefusalCountersAreComparable(unittest.TestCase):
    """The two refusal counters print side by side, so they must share units.

    refused_session once counted bars while refused_cost counted signals.
    Printed adjacently that reads as "the window rejected 4,445 and the cost
    rejected 790", which was never a comparison anyone could make.
    """

    def test_both_counters_count_signals(self):
        m1 = generate(bars=6_000, timeframe="1m", seed=7)
        result = run(HalfScalpConfig(session_filter=True), m1)
        accounted = (result.n + result.refused_cost + result.refused_stop
                     + result.refused_session + result.left_open)
        self.assertEqual(
            accounted, result.signals_seen,
            "every signal must end up either traded or in exactly one refusal "
            "counter; a mismatch means a counter is measuring something else")

    def test_the_window_refuses_nothing_when_the_filter_is_off(self):
        m1 = generate(bars=6_000, timeframe="1m", seed=7)
        result = run(HalfScalpConfig(session_filter=False), m1)
        self.assertEqual(result.refused_session, 0)
