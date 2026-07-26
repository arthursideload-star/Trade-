"""Scalping setups, exit management, the backtest engine and the simulator.

The tests that matter most here are the ones that guard against a backtest
that lies: lookahead, target-before-stop, and costs quietly not being charged.
A backtest bug does not crash -- it produces an attractive number, which is
far worse.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from metals import simulate
from metals.backtest import BacktestConfig, report, run
from metals.candles import Candle, CandleSeries
from metals.evaluate import evaluate, experiment_grid
from metals.exits import (COOLDOWN_AFTER_LOSS_MINUTES, DAILY_WIN_TARGET_PCT,
                          DayState, ExitPlan, ExitReason, MAX_TRADES_PER_DAY,
                          PositionState, StopSignal, advance, build_exit_plan,
                          session_advice)
from metals.levels import build_level_map
from metals.risk import AccountState
from metals.scalping import (CATALOGUE, MAX_SPREAD_PCT_OF_STOP, ScalpSignal,
                             detect_scalps, spread_gate)
from tests.helpers import series_from_ohlc

UTC = timezone.utc
MOMENT = datetime(2026, 7, 21, 14, 0, tzinfo=UTC)   # Tuesday, LDN/NY overlap


def _bar(ts, o, h, l, c):
    return Candle(ts=ts, open=o, high=h, low=l, close=c, volume=1000.0)


class TestExitPlan(unittest.TestCase):
    def test_r_geometry_long(self):
        plan = ExitPlan("XAUUSD", "long", entry=4500.0, initial_stop=4490.0)
        self.assertAlmostEqual(plan.risk_per_unit, 10.0)
        self.assertAlmostEqual(plan.price_at_r(1.0), 4510.0)
        self.assertAlmostEqual(plan.price_at_r(2.5), 4525.0)

    def test_r_geometry_short(self):
        plan = ExitPlan("XAUUSD", "short", entry=4500.0, initial_stop=4510.0)
        self.assertAlmostEqual(plan.price_at_r(1.0), 4490.0)
        self.assertAlmostEqual(plan.price_at_r(2.5), 4475.0)

    def test_blended_reward_risk_is_the_honest_number(self):
        """Quoting the runner target as 'the' R:R overstates the plan.

        60% at 1R plus 40% at 2.5R is 1.6R, not 2.5R. A plan that advertises
        2.5 is promising something 56% larger than it delivers.
        """
        plan = ExitPlan("XAUUSD", "long", 4500.0, 4490.0,
                        first_target_r=1.0, first_target_fraction=0.6,
                        runner_target_r=2.5)
        self.assertAlmostEqual(plan.blended_reward_risk, 1.6)
        self.assertLess(plan.blended_reward_risk, plan.runner_target_r)

    def test_style_changes_the_horizon(self):
        scalp = build_exit_plan("XAUUSD", "long", 4500, 4490, 5.0, "scalp")
        swing = build_exit_plan("XAUUSD", "long", 4500, 4490, 5.0, "swing")
        self.assertLess(scalp.time_stop_minutes, swing.time_stop_minutes)
        self.assertLess(scalp.first_target_r, swing.first_target_r)


class TestPositionAdvance(unittest.TestCase):
    def _state(self, direction="long"):
        plan = ExitPlan("XAUUSD", direction, entry=4500.0,
                        initial_stop=4490.0 if direction == "long" else 4510.0,
                        first_target_r=1.0, first_target_fraction=0.6,
                        runner_target_r=2.5, time_stop_minutes=45)
        return PositionState(plan=plan, opened_at=MOMENT)

    def test_stop_closes_at_minus_one_r(self):
        state = self._state()
        state = advance(state, _bar(MOMENT + timedelta(minutes=5),
                                    4500, 4502, 4485, 4488), atr_value=5.0)
        self.assertTrue(state.closed)
        self.assertIs(state.exit_reason, ExitReason.STOP)
        self.assertAlmostEqual(state.realised_r, -1.0, places=6)

    def test_stop_wins_when_a_bar_covers_both(self):
        """The bar that reaches the target and the stop must count as a loss.

        Assuming the target is the single most common way a backtest reports a
        number that cannot be achieved live.
        """
        state = self._state()
        wide = _bar(MOMENT + timedelta(minutes=5), 4500, 4530, 4485, 4520)
        state = advance(state, wide, atr_value=5.0, worst_first=True)
        self.assertIs(state.exit_reason, ExitReason.STOP)
        self.assertLess(state.realised_r, 0)

    def test_partial_at_first_target_then_breakeven(self):
        state = self._state()
        state = advance(state, _bar(MOMENT + timedelta(minutes=5),
                                    4500, 4512, 4498, 4510), atr_value=5.0)
        self.assertFalse(state.closed)
        self.assertTrue(state.first_target_hit)
        self.assertAlmostEqual(state.realised_r, 0.6, places=6)
        self.assertAlmostEqual(state.remaining_fraction, 0.4, places=6)
        self.assertAlmostEqual(state.current_stop, 4500.0)   # break-even

    def test_full_run_to_the_runner_target(self):
        state = self._state()
        state = advance(state, _bar(MOMENT + timedelta(minutes=5),
                                    4500, 4512, 4498, 4510), atr_value=5.0)
        state = advance(state, _bar(MOMENT + timedelta(minutes=10),
                                    4510, 4526, 4508, 4525), atr_value=5.0)
        self.assertTrue(state.closed)
        self.assertIs(state.exit_reason, ExitReason.TARGET)
        # 0.6 * 1.0 + 0.4 * 2.5 = 1.6
        self.assertAlmostEqual(state.realised_r, 1.6, places=6)

    def test_time_stop_fires(self):
        state = self._state()
        late = _bar(MOMENT + timedelta(minutes=50), 4500, 4503, 4497, 4501)
        state = advance(state, late, atr_value=5.0)
        self.assertTrue(state.closed)
        self.assertIs(state.exit_reason, ExitReason.TIME)

    def test_short_side_mirrors(self):
        state = self._state("short")
        state = advance(state, _bar(MOMENT + timedelta(minutes=5),
                                    4500, 4502, 4488, 4490), atr_value=5.0)
        self.assertTrue(state.first_target_hit)
        self.assertAlmostEqual(state.realised_r, 0.6, places=6)

    def test_mfe_and_mae_are_measured_not_inferred(self):
        state = self._state()
        # High 4518 = +1.8R, low 4494 = -0.6R against a 10 USD/oz risk.
        state = advance(state, _bar(MOMENT + timedelta(minutes=5),
                                    4500, 4518, 4494, 4505), atr_value=5.0)
        self.assertAlmostEqual(state.mfe_r, 1.8, places=6)
        self.assertAlmostEqual(state.mae_r, -0.6, places=6)

    def test_mae_mirrors_for_shorts(self):
        state = self._state("short")
        state = advance(state, _bar(MOMENT + timedelta(minutes=5),
                                    4500, 4506, 4496, 4499), atr_value=5.0)
        self.assertAlmostEqual(state.mae_r, -0.6, places=6)
        self.assertAlmostEqual(state.mfe_r, 0.4, places=6)


class TestSessionAdvice(unittest.TestCase):
    def test_daily_loss_limit_stops(self):
        acc = AccountState(equity=9_650.0, realised_pnl_today=-350.0,
                           starting_equity_today=10_000.0)
        advice = session_advice(acc, DayState(), MOMENT)
        self.assertIs(advice.signal, StopSignal.STOP_NOW)
        self.assertTrue(advice.should_stop)
        self.assertTrue(any("R2" in r for r in advice.reasons))

    def test_win_target_also_stops(self):
        """A good day given back is how a good week is lost."""
        acc = AccountState(equity=10_250.0, realised_pnl_today=250.0,
                           starting_equity_today=10_000.0)
        advice = session_advice(acc, DayState(), MOMENT)
        self.assertIs(advice.signal, StopSignal.STOP_NOW)
        self.assertTrue(any("Tagesziel" in r for r in advice.reasons))
        self.assertGreaterEqual(acc.day_pnl_pct, DAILY_WIN_TARGET_PCT)

    def test_two_consecutive_losses_stop(self):
        advice = session_advice(AccountState(equity=10_000.0),
                                DayState(consecutive_losses=2), MOMENT)
        self.assertIs(advice.signal, StopSignal.STOP_NOW)

    def test_trade_count_limit_stops(self):
        advice = session_advice(AccountState(equity=10_000.0),
                                DayState(trades_taken=MAX_TRADES_PER_DAY),
                                MOMENT)
        self.assertIs(advice.signal, StopSignal.STOP_NOW)

    def test_rollover_stops(self):
        rollover = datetime(2026, 7, 21, 21, 30, tzinfo=UTC)
        advice = session_advice(AccountState(equity=10_000.0), DayState(),
                                rollover)
        self.assertIs(advice.signal, StopSignal.STOP_NOW)

    def test_cooldown_after_a_loss_is_caution_not_stop(self):
        day = DayState(trades_taken=1, last_trade_was_loss=True,
                       last_trade_closed_at=MOMENT - timedelta(minutes=5))
        advice = session_advice(AccountState(equity=10_000.0), day, MOMENT)
        self.assertIs(advice.signal, StopSignal.CAUTION)
        self.assertTrue(any("Abkuehlung" in r for r in advice.reasons))
        self.assertLess(5, COOLDOWN_AFTER_LOSS_MINUTES)

    def test_clean_state_continues(self):
        advice = session_advice(AccountState(equity=10_000.0), DayState(),
                                MOMENT)
        self.assertIs(advice.signal, StopSignal.CONTINUE)
        self.assertFalse(advice.should_stop)

    def test_hard_stop_does_not_list_soft_reasons(self):
        """Once a hard stop fires the soft signals are noise that invites
        negotiation."""
        acc = AccountState(equity=9_650.0, realised_pnl_today=-350.0,
                           starting_equity_today=10_000.0)
        advice = session_advice(acc, DayState(trades_taken=3), MOMENT)
        self.assertEqual(len(advice.reasons), 1)


class TestScalpingCatalogue(unittest.TestCase):
    def test_every_setup_documents_its_failure(self):
        self.assertGreaterEqual(len(CATALOGUE), 6)
        for key, s in CATALOGUE.items():
            self.assertTrue(s.name)
            self.assertGreater(len(s.idea), 60, f"{key} idea too thin")
            self.assertGreater(len(s.failure_mode), 40,
                               f"{key} does not say how it fails")
            self.assertTrue(s.phases)

    def test_spread_gate_refuses_an_expensive_scalp(self):
        sig = ScalpSignal("S1", "test", "XAUUSD", "long",
                          entry=4500.0, structural_level=4498.0,
                          confidence=0.7, atr_value=5.0, spread_used=0.60)
        # 0.60 spread on a 2.00 stop is 30% -- far over the ceiling.
        self.assertGreater(sig.spread_as_pct_of_risk, MAX_SPREAD_PCT_OF_STOP)
        self.assertFalse(spread_gate(sig))
        self.assertTrue(any("S6" in w for w in sig.warnings))

    def test_spread_gate_allows_a_cheap_one(self):
        sig = ScalpSignal("S1", "test", "XAUUSD", "long",
                          entry=4500.0, structural_level=4490.0,
                          confidence=0.7, atr_value=5.0, spread_used=0.20)
        self.assertTrue(spread_gate(sig))

    def test_detector_returns_nothing_on_a_flat_market(self):
        flat = series_from_ohlc([(4500, 4500.4, 4499.6, 4500)] * 200,
                                timeframe="5m")
        lm = build_level_map("XAUUSD", 4500.0, flat, flat)
        self.assertEqual(detect_scalps("XAUUSD", flat, None, lm, MOMENT), [])

    def test_scalp_stop_floor_is_enforced(self):
        """A stop closer than MIN_SCALP_STOP_ATR gets widened, not accepted.

        The floor was documented but never applied -- the docstring promised
        a behaviour the code did not have.
        """
        from metals.scalping import MIN_SCALP_STOP_ATR, _scalp_stop
        atr_value = 5.0
        # Structural level 0.5 USD below entry: far inside the noise band.
        stop = _scalp_stop("long", level=4499.5, atr_value=atr_value,
                           entry=4500.0)
        self.assertAlmostEqual(abs(4500.0 - stop),
                               atr_value * MIN_SCALP_STOP_ATR, places=6)
        self.assertLess(stop, 4500.0)

    def test_scalp_stop_respects_a_distant_level(self):
        from metals.scalping import _scalp_stop
        stop = _scalp_stop("long", level=4480.0, atr_value=5.0, entry=4500.0)
        self.assertAlmostEqual(stop, 4480.0 - 5.0 * 0.35, places=6)

    def test_scalp_stop_floor_mirrors_for_shorts(self):
        from metals.scalping import MIN_SCALP_STOP_ATR, _scalp_stop
        stop = _scalp_stop("short", level=4500.5, atr_value=5.0, entry=4500.0)
        self.assertGreater(stop, 4500.0)
        self.assertAlmostEqual(abs(stop - 4500.0), 5.0 * MIN_SCALP_STOP_ATR,
                               places=6)

    def test_detectors_survive_a_short_series(self):
        short = series_from_ohlc([(4500, 4505, 4495, 4502)] * 20,
                                 timeframe="5m")
        lm = build_level_map("XAUUSD", 4502.0, short, short)
        self.assertEqual(detect_scalps("XAUUSD", short, None, lm, MOMENT), [])


class TestSimulator(unittest.TestCase):
    def test_deterministic_for_a_seed(self):
        a = simulate.generate(bars=300, seed=5)
        b = simulate.generate(bars=300, seed=5)
        self.assertEqual([c.close for c in a], [c.close for c in b])

    def test_different_seeds_differ(self):
        a = simulate.generate(bars=300, seed=5)
        b = simulate.generate(bars=300, seed=6)
        self.assertNotEqual([c.close for c in a], [c.close for c in b])

    def test_candles_are_well_formed(self):
        s = simulate.generate(bars=500, seed=11)
        for c in s:
            self.assertLessEqual(c.low, c.open)
            self.assertLessEqual(c.low, c.close)
            self.assertGreaterEqual(c.high, c.open)
            self.assertGreaterEqual(c.high, c.close)

    def test_market_closed_hours_are_absent(self):
        s = simulate.generate(bars=2000, seed=3)
        for c in s:
            self.assertNotEqual(c.ts.weekday(), 5, "Saturday bar generated")
            # Hour 22 is the daily break on every day except Sunday, when it
            # is the weekly open.
            if c.ts.weekday() != 6:
                self.assertNotEqual(c.ts.hour, 22,
                                    f"rollover-hour bar at {c.ts}")

    def test_trail_does_not_fire_on_the_partial_fill_bar(self):
        """Regression: trailing from the high of the bar that filled the first
        target left the runner ~0.4R of room and turned every runner into a
        small win."""
        plan = ExitPlan("XAUUSD", "long", entry=4500.0, initial_stop=4490.0,
                        first_target_r=1.0, first_target_fraction=0.6,
                        runner_target_r=2.5, trail_atr_multiple=1.5)
        state = PositionState(plan=plan, opened_at=MOMENT)
        state = advance(state, _bar(MOMENT + timedelta(minutes=5),
                                    4500, 4512, 4498, 4510), atr_value=5.0)
        self.assertTrue(state.first_target_hit)
        self.assertAlmostEqual(state.current_stop, 4500.0,
                               msg="stop should sit at break-even, not trailed")

    def test_produces_fat_tails_and_volatility_clustering(self):
        """The two properties that make gold gold.

        A generator without them makes every mean-reversion strategy look
        good, which would make the whole evaluation worthless.
        """
        stats = simulate.describe(simulate.generate(bars=4000, seed=9))
        self.assertGreater(stats["excess_kurtosis"], 1.0,
                           "returns are too close to normal")
        self.assertGreater(stats["vol_clustering"], 0.05,
                           "no volatility clustering")

    def test_atr_lands_in_a_gold_like_range(self):
        stats = simulate.describe(simulate.generate(bars=3000, seed=4))
        # M5 ATR on gold runs roughly 0.01%-0.07% of price.
        self.assertGreater(stats["mean_atr_pct"], 0.005)
        self.assertLess(stats["mean_atr_pct"], 0.20)


class TestBacktestEngine(unittest.TestCase):
    def test_runs_and_reports(self):
        market = simulate.generate(bars=1200, seed=21)
        result = run(market, BacktestConfig(), data_source="test")
        self.assertGreater(result.bars_tested, 0)
        text = report(result)
        self.assertIn("BACKTEST RESULT", text)

    def test_costs_reduce_expectancy(self):
        """The single most important property of the engine.

        A backtest that does not charge the spread measures a strategy nobody
        can trade.
        """
        market = simulate.generate(bars=2000, seed=33)
        free = run(market, BacktestConfig(spread_usd_oz=0.0,
                                          slippage_fraction=0.0))
        costly = run(market, BacktestConfig(spread_usd_oz=0.50,
                                            slippage_fraction=0.5))
        if free.n and costly.n:
            self.assertGreater(free.expectancy_r, costly.expectancy_r)

    def test_gross_and_net_differ_by_the_cost(self):
        market = simulate.generate(bars=2000, seed=34)
        result = run(market, BacktestConfig(spread_usd_oz=0.30))
        if result.n:
            self.assertGreater(result.gross_expectancy_r, result.expectancy_r)

    def test_no_lookahead_the_detector_only_sees_closed_history(self):
        """Truncating the future must not change past decisions.

        If it does, something reached forward. Running the same config over a
        prefix of the data must produce the same trades for the overlapping
        period.
        """
        market = simulate.generate(bars=1600, seed=44)
        prefix = CandleSeries(market.symbol, market.timeframe,
                              market.candles[:1000], market.source)
        full = run(market, BacktestConfig())
        part = run(prefix, BacktestConfig())
        cutoff = prefix.last.ts
        full_early = [(t.opened_at, t.setup_id, round(t.entry, 2))
                      for t in full.trades if t.opened_at < cutoff - timedelta(hours=3)]
        part_early = [(t.opened_at, t.setup_id, round(t.entry, 2))
                      for t in part.trades if t.opened_at < cutoff - timedelta(hours=3)]
        self.assertEqual(full_early, part_early)

    def test_session_filter_excludes_configured_sessions(self):
        market = simulate.generate(bars=2500, seed=55)
        result = run(market, BacktestConfig(
            scalp_sessions=("london_ny_overlap",)))
        for t in result.trades:
            self.assertEqual(t.session, "london_ny_overlap")

    def test_daily_trade_limit_is_respected(self):
        market = simulate.generate(bars=3000, seed=66)
        result = run(market, BacktestConfig(max_trades_per_day=2))
        per_day: dict = {}
        for t in result.trades:
            key = t.opened_at.date()
            per_day[key] = per_day.get(key, 0) + 1
        for day, count in per_day.items():
            self.assertLessEqual(count, 2, f"{day} had {count} trades")

    def test_confidence_interval_reports_uncertainty(self):
        market = simulate.generate(bars=2500, seed=77)
        result = run(market, BacktestConfig())
        if result.n >= 2:
            ci = result.expectancy_ci()
            self.assertIsNotNone(ci)
            self.assertLess(ci[0], ci[1])
            self.assertLessEqual(ci[0], result.expectancy_r)
            self.assertGreaterEqual(ci[1], result.expectancy_r)

    def test_edge_claim_requires_both_sample_size_and_a_clear_interval(self):
        market = simulate.generate(bars=1000, seed=88)
        result = run(market, BacktestConfig())
        if result.n < 30:
            self.assertFalse(result.edge_is_established)

    def test_bars_skipped_and_signals_rejected_are_separate(self):
        """Conflating them inflates the rejection count by orders of magnitude
        and makes the filters look far more active than they are."""
        market = simulate.generate(bars=2000, seed=99)
        result = run(market, BacktestConfig(max_trades_per_day=1))
        self.assertIn("daily trade limit", result.bars_skipped)
        self.assertNotIn("daily trade limit", result.signals_rejected)


class TestEvaluation(unittest.TestCase):
    def test_multi_run_produces_a_distribution(self):
        ev = evaluate(BacktestConfig(), runs=3, bars=800, label="unit")
        self.assertEqual(len(ev.runs), 3)
        self.assertIsNotNone(ev.median("total_r"))

    def test_experiment_grid_builds(self):
        grid = experiment_grid()
        self.assertGreaterEqual(len(grid), 10)
        for label, cfg in grid.items():
            self.assertIsInstance(cfg, BacktestConfig)

    def test_losing_run_share_is_a_percentage(self):
        ev = evaluate(BacktestConfig(), runs=4, bars=800, label="unit")
        share = ev.losing_run_share
        if share is not None:
            self.assertGreaterEqual(share, 0.0)
            self.assertLessEqual(share, 100.0)


if __name__ == "__main__":
    unittest.main()
