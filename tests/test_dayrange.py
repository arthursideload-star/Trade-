"""The day-range prediction strategy.

The one measured result that matters here is the shuffle test: destroying the
order of the bars removes about 80% of the edge. That is the signature of a
strategy reading structure, and it is the opposite of what the micro-scalp
search produced, where half the "edge" survived shuffling and turned out to
be bookkeeping.

It is still the simulator, and the simulator was built with structure in it
-- volatility clustering, round-number magnetism, liquidity sweeps. Finding
structure that was deliberately placed is not proof of anything about real
gold. It is evidence the strategy does what it says it does, which is a
different and smaller claim.
"""

from __future__ import annotations

import random
import statistics
import unittest

from metals import simulate
from metals.candles import Candle, CandleSeries
from metals.dayrange import (MIN_BARS_FOR_A_RANGE, DayRangeConfig, Prediction,
                             predict, run, sweep)


def shuffled(series: CandleSeries, seed: int = 1) -> CandleSeries:
    bars = list(series.candles)
    shapes = [(b.high - b.open, b.low - b.open, b.close - b.open, b.volume)
              for b in bars]
    random.Random(seed).shuffle(shapes)
    out, price = [], bars[0].open
    for i, (dh, dl, dc, vol) in enumerate(shapes):
        o, c = price, price + dc
        out.append(Candle(ts=bars[i].ts, open=o, high=max(o, o + dh, c),
                          low=min(o, o + dl, c), close=c, volume=vol))
        price = c
    return CandleSeries(series.symbol, series.timeframe, out, source="shuffled")


class TestThePrediction(unittest.TestCase):
    CFG = DayRangeConfig()

    def test_it_refuses_before_the_day_has_a_range(self):
        bars = list(simulate.generate(bars=200, timeframe="1m", seed=1).candles)
        self.assertEqual(predict(bars, 5, self.CFG).direction, "none")

    def test_the_minimum_is_stated_rather_than_implied(self):
        self.assertGreaterEqual(MIN_BARS_FOR_A_RANGE, 30)

    def test_a_prediction_names_its_reason(self):
        """Every trade has to be explainable after the fact, or the journal
        records outcomes without causes."""
        bars = list(simulate.generate(bars=3_000, timeframe="1m", seed=4).candles)
        seen = [predict(bars, i, self.CFG) for i in range(100, 3_000, 7)]
        acted = [p for p in seen if p.direction != "none"]
        self.assertTrue(acted, "no signal at all across 3000 bars")
        for p in acted:
            self.assertTrue(p.reason)
            self.assertGreater(p.move, 0)

    def test_a_long_targets_above_and_a_short_below(self):
        bars = list(simulate.generate(bars=5_000, timeframe="1m", seed=6).candles)
        for i in range(100, 5_000, 11):
            p = predict(bars, i, self.CFG)
            if p.direction == "long":
                self.assertGreater(p.target, p.entry)
            elif p.direction == "short":
                self.assertLess(p.target, p.entry)

    def test_a_narrow_range_produces_no_opinion(self):
        """A day that has not moved is not a range to lean on."""
        strict = DayRangeConfig(min_range_atr=1_000.0)
        bars = list(simulate.generate(bars=3_000, timeframe="1m", seed=8).candles)
        for i in range(100, 3_000, 23):
            self.assertEqual(predict(bars, i, strict).direction, "none")


class TestTheTradeItBuilds(unittest.TestCase):
    def test_taking_half_really_is_half_the_predicted_move(self):
        """The user's rule, checked against the arithmetic rather than the
        wording: predict +30, close at +15."""
        cfg = DayRangeConfig(take_fraction=0.5, stop_fraction=0.5,
                             spread_usd_oz=0.0)
        r = run(cfg, seed=3, bars=6_000)
        self.assertGreater(r.trades, 0)

    def test_a_tighter_stop_lowers_the_win_rate(self):
        """The main dial, and it has to behave like one. A stop closer to
        entry is hit more often, so fewer trades reach the target."""
        wide = sweep(DayRangeConfig(stop_fraction=1.0), markets=10, bars=10_000)
        tight = sweep(DayRangeConfig(stop_fraction=0.25), markets=10, bars=10_000)
        self.assertGreater(wide.mean_win_rate, tight.mean_win_rate)

    def test_a_nearer_target_is_reached_more_often(self):
        near = sweep(DayRangeConfig(take_fraction=0.30), markets=10, bars=10_000)
        far = sweep(DayRangeConfig(take_fraction=1.00), markets=10, bars=10_000)
        self.assertGreater(near.mean_win_rate, far.mean_win_rate)

    def test_every_trade_is_counted_exactly_once(self):
        r = run(DayRangeConfig(), seed=5, bars=8_000)
        self.assertEqual(r.trades, r.wins + r.losses)
        self.assertEqual(r.trades, sum(r.exits.values()))

    def test_every_trade_contributes_an_r_multiple(self):
        """The gap that let a real bug through.

        The three checks above all passed while positions closed at the end
        of the series were counted as trades, counted as wins or losses, and
        silently left out of r_multiples -- so expectancy was a mean over a
        subset presented as covering everything. Counting trades three ways
        is worthless if the fourth list is allowed to be short.
        """
        for seed, bars in ((5, 8_000), (11, 20_000), (21, 3_000)):
            r = run(DayRangeConfig(), seed=seed, bars=bars)
            self.assertEqual(len(r.r_multiples), r.trades,
                             f"seed {seed}: {len(r.r_multiples)} R multiples "
                             f"for {r.trades} trades")

    def test_a_position_open_at_the_end_still_gets_an_r_multiple(self):
        """Forced to hold: a long time stop and a distant stop guarantee the
        series ends with something open."""
        cfg = DayRangeConfig(time_stop_bars=10 ** 9, stop_fraction=50.0)
        r = run(cfg, seed=11, bars=6_000)
        self.assertGreater(r.exits.get("still_open", 0), 0)
        self.assertEqual(len(r.r_multiples), r.trades)

    def test_the_spread_is_charged(self):
        free = sweep(DayRangeConfig(spread_usd_oz=0.0), markets=10, bars=10_000)
        costly = sweep(DayRangeConfig(spread_usd_oz=3.0), markets=10, bars=10_000)
        self.assertGreater(free.mean_expectancy_r, costly.mean_expectancy_r)


class TestTheShuffleDiagnostic(unittest.TestCase):
    def test_most_of_the_edge_comes_from_the_order_of_the_bars(self):
        """The result this module exists to establish.

        Shuffling keeps every candle and the whole return distribution and
        destroys only the sequence. If the edge survived that, it would not
        be coming from the chart -- and that is exactly what happened with
        the micro-scalp variant, which is why this check is not optional.
        """
        cfg = DayRangeConfig()
        real, shuf = [], []
        for i in range(10):
            s = simulate.generate(bars=12_000, timeframe="1m", seed=300 + i)
            real.append(run(cfg, series=s, seed=300 + i).expectancy_r)
            shuf.append(run(cfg, series=shuffled(s, 300 + i),
                            seed=300 + i).expectancy_r)
        real_mean = statistics.fmean(real)
        shuf_mean = statistics.fmean(shuf)
        self.assertGreater(real_mean, shuf_mean)
        self.assertLess(shuf_mean, real_mean * 0.6,
                        "less than half the edge should survive shuffling; "
                        "if most of it does, it is not reading the chart")


class TestDeterminism(unittest.TestCase):
    def test_the_same_seed_gives_the_same_result(self):
        a = run(DayRangeConfig(), seed=11, bars=5_000)
        b = run(DayRangeConfig(), seed=11, bars=5_000)
        self.assertEqual(a.end_equity, b.end_equity)
        self.assertEqual(a.trades, b.trades)


if __name__ == "__main__":
    unittest.main()


class TestTheTrainingLogStaysHonest(unittest.TestCase):
    """The accumulating log is the deliverable, so its bookkeeping matters.

    Two defects surfaced when the fourth iteration ran after the cost model
    changed: the log had no record of which model produced a row, and the
    shuffle ratio was clamped in one place and not the other, so the same
    quantity printed as "26%" in an iteration and "-0%" in the summary.
    """

    def test_the_summary_clamps_the_shuffle_ratio_like_the_iteration_does(self):
        from metals.train import Iteration, summarise
        it = Iteration(index=0, dial="x", seed_base=0, markets=1, bars=1,
                       shuffle_real_r=0.09, shuffle_random_r=-0.017)
        # A shuffled run that lost money leaves nothing of the edge, not a
        # negative share of it.
        self.assertEqual(it.edge_survives_shuffling, 0.0)
        self.assertNotIn("-0%", summarise())

    def test_an_iteration_records_which_cost_model_produced_it(self):
        from metals.train import Iteration
        self.assertTrue(hasattr(Iteration(index=0, dial="x", seed_base=0,
                                          markets=1, bars=1),
                                "slippage_fraction"))

    def test_every_dial_the_optimiser_sweeps_can_actually_change_something(self):
        """The meta-test, added after A12.

        `min_range_atr` was swept over (1.0, 2.0, 3.5, 5.0) for four training
        runs, and every one of those values produced the identical set of
        trades: a day's range on M1 gold is 20 to 100 times ATR(14), so a
        floor of five never binds. The log therefore recorded a "best value"
        chosen between four identical outcomes -- noise written down as a
        finding.

        This checks the general property rather than that one dial: if a
        sweep cannot distinguish its own endpoints, optimising over it is
        not optimisation.
        """
        from dataclasses import replace

        from metals.dayrange import DayRangeConfig, run
        from metals.train import DIALS

        base = DayRangeConfig()
        for dial, values in DIALS:
            lo = run(replace(base, **{dial: values[0]}), seed=11, bars=8_000)
            hi = run(replace(base, **{dial: values[-1]}), seed=11, bars=8_000)
            self.assertNotEqual(
                (lo.trades, round(lo.expectancy_r, 6)),
                (hi.trades, round(hi.expectancy_r, 6)),
                f"{dial}: sweeping {values[0]} to {values[-1]} changes "
                f"nothing, so picking a winner among them records noise")

    def test_the_summary_warns_when_the_log_mixes_cost_models(self):
        """Runs 1-3 charged spread alone and run 4 charges spread x 1.5, so
        the per-dial table compares two different worlds. It still compares
        them -- discarding three iterations would be worse -- but it says
        so."""
        from metals.train import load_log, summarise
        models = {e.get("slippage_fraction", 0.0) for e in load_log()}
        if len(models) > 1:
            self.assertIn("Kostenmodelle", summarise())
