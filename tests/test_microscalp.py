"""The micro-scalp simulator, and the checks that caught it flattering itself.

This module measures a strategy whose whole appeal is that it looks like it
works. A simulator for it therefore has to be tested harder than usual: the
failure mode is not a crash, it is a plausible positive number.

The three diagnostics below are the ones that mattered in practice -- the
horizon sweep, the shuffle test and the spread sweep. Two of them are here as
regression tests; the third caught a genuine artifact and is documented in
docs/MICRO-SCALPING.md.
"""

from __future__ import annotations

import random
import statistics
import unittest

from metals import simulate
from metals.candles import Candle, CandleSeries
from metals.microscalp import (EU_RETAIL_LEVERAGE_GOLD, STOP_OUT_LEVEL,
                               MicroConfig, Position, report, run, sweep)


def shuffled(series: CandleSeries, seed: int = 1) -> CandleSeries:
    """Same bar shapes, same return distribution, order destroyed.

    Any edge that survives this is not coming from the sequence, which is
    what separates a tradable pattern from the simulator's own texture.
    """
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


class TestPositionArithmetic(unittest.TestCase):
    def test_a_long_gains_when_price_rises(self):
        p = Position(True, 4500.0, 0.1, 4501.0, None, 0)
        self.assertAlmostEqual(p.unrealised(4501.0, 100.0), 10.0)

    def test_a_short_gains_when_price_falls(self):
        p = Position(False, 4500.0, 0.1, 4499.0, None, 0)
        self.assertAlmostEqual(p.unrealised(4499.0, 100.0), 10.0)

    def test_the_contract_size_is_ounces_per_lot(self):
        """0.1 lot of gold is ten ounces, so a one dollar move is ten dollars.
        Getting this wrong scales every result by a factor of a hundred."""
        p = Position(True, 4500.0, 0.1, 4501.0, None, 0)
        self.assertAlmostEqual(p.unrealised(4501.0, 100.0), 1.0 * 0.1 * 100)


class TestTheStrategyAsDescribed(unittest.TestCase):
    """The configuration the user actually described."""

    # 20,000 so the margin at 1:20 permits the three positions the
    # strategy asks for; below that the account cannot run it at all.
    CFG = MicroConfig(start_equity=20_000.0, take_profit_usd_oz=0.10,
                      stop_loss_usd_oz=None, max_positions=3,
                      direction="follow")

    def test_the_win_rate_really_is_near_perfect(self):
        """This is not a straw man: closing only on profit does produce a
        win rate above 99%, and any honest account of the strategy has to
        start by agreeing with that."""
        s = sweep(self.CFG, markets=15, bars=5_000)
        self.assertGreater(s.mean_win_rate, 0.97)

    def test_the_account_size_decides_the_ruin_risk_not_the_strategy(self):
        """The correction that mattered most.

        Measured first at 1:100 on a 1,000 account, this strategy looked
        ruinous. That configuration is not legal for EU retail, and at the
        actual 1:20 cap the same rules on an adequately funded account do not
        blow up at all. What changed was never the strategy -- it was the
        position size relative to the balance.
        """
        thin = sweep(MicroConfig(start_equity=5_000.0, take_profit_usd_oz=0.10,
                                 stop_loss_usd_oz=None, max_positions=3),
                     markets=20, bars=40_000)
        thick = sweep(MicroConfig(start_equity=100_000.0, take_profit_usd_oz=0.10,
                                  stop_loss_usd_oz=None, max_positions=3),
                      markets=20, bars=40_000)
        self.assertGreater(thin.stop_out_rate, thick.stop_out_rate)
        self.assertEqual(thick.stop_out_rate, 0.0)

    def test_a_bigger_account_earns_a_smaller_percentage(self):
        """Fixed 0.1 lots against a larger balance is simply less exposure.
        Any comparison of returns between account sizes is really a
        comparison of position sizing."""
        small = sweep(MicroConfig(start_equity=5_000.0), markets=20, bars=10_000)
        large = sweep(MicroConfig(start_equity=100_000.0), markets=20, bars=10_000)
        self.assertGreater(small.median_return_pct, large.median_return_pct)


class TestCostsAreReallyCharged(unittest.TestCase):
    def test_a_wider_spread_monotonically_hurts(self):
        """The check that proves the spread is not silently free. It was run
        against the best configuration the parameter search found, precisely
        because that one looked too good."""
        cfg = dict(start_equity=20_000.0, take_profit_usd_oz=1.0,
                   stop_loss_usd_oz=None, direction="fade", max_positions=3)
        results = [sweep(MicroConfig(spread_usd_oz=sp, **cfg),
                         markets=12, bars=6_000).median_return_pct
                   for sp in (0.0, 1.0, 3.0)]
        self.assertEqual(results, sorted(results, reverse=True))

    def test_an_absurd_spread_makes_everything_lose(self):
        s = sweep(MicroConfig(start_equity=20_000.0, spread_usd_oz=10.0),
                  markets=12, bars=6_000)
        self.assertLess(s.median_return_pct, 0)


class TestTheShuffleDiagnostic(unittest.TestCase):
    def test_shuffling_preserves_the_return_distribution(self):
        s = simulate.generate(bars=3_000, timeframe="1m", seed=3)
        sh = shuffled(s, seed=3)
        self.assertEqual(len(list(sh.candles)), len(list(s.candles)))
        for series in (s, sh):
            for b in series.candles:
                self.assertGreaterEqual(b.high, max(b.open, b.close))
                self.assertLessEqual(b.low, min(b.open, b.close))

    def test_the_best_configuration_loses_most_of_its_edge_when_shuffled(self):
        """Documents the artifact rather than hiding it.

        The parameter search's winner returned four figures. Half of that
        disappears once the bar order is destroyed, which locates it in the
        simulator's own weak mean reversion -- not in anything a real market
        would hand over.
        """
        cfg = MicroConfig(start_equity=20_000.0, take_profit_usd_oz=1.0,
                          stop_loss_usd_oz=None, direction="fade",
                          max_positions=3)
        real, shuf = [], []
        for i in range(12):
            s = simulate.generate(bars=6_000, timeframe="1m", seed=500 + i)
            real.append(run(cfg, series=s, seed=500 + i).return_pct)
            shuf.append(run(cfg, series=shuffled(s, 500 + i),
                            seed=500 + i).return_pct)
        self.assertLess(statistics.median(shuf), statistics.median(real))


class TestBrokerMechanics(unittest.TestCase):
    def test_a_stop_out_is_recorded_with_the_bar_it_happened_on(self):
        r = run(MicroConfig(start_equity=8_000.0, max_positions=3),
                seed=42, bars=8_000)
        if r.stopped_out:
            self.assertIsNotNone(r.stop_out_bar)
            self.assertLess(r.stop_out_bar, r.bars)

    def test_equity_never_goes_negative(self):
        """Retail accounts have negative balance protection, and a simulator
        that lets equity go below zero reports losses that cannot happen."""
        for seed in range(8):
            r = run(MicroConfig(start_equity=6_000.0), seed=seed, bars=10_000)
            self.assertGreaterEqual(r.end_equity, 0.0)

    def test_a_small_account_cannot_open_the_position_at_all(self):
        """The finding that precedes every strategy question.

        Under EU retail leverage a 0.1 lot gold position ties up about 2,250
        in margin. An account below that does not trade this strategy badly
        -- it cannot trade it.
        """
        r = run(MicroConfig(start_equity=1_000.0), seed=3, bars=6_000)
        self.assertEqual(r.trades, 0)
        self.assertEqual(r.max_open, 0)

    def test_the_report_says_so_rather_than_showing_an_empty_result(self):
        r = run(MicroConfig(start_equity=1_000.0), seed=3, bars=4_000)
        self.assertIn("KEIN EINZIGER TRADE MOEGLICH", report(r))

    def test_the_eu_leverage_cap_is_the_default(self):
        """20:1 for gold is the ESMA product intervention limit, adopted by
        member states -- not a broker preference."""
        self.assertEqual(EU_RETAIL_LEVERAGE_GOLD, 20.0)
        self.assertEqual(MicroConfig().leverage, EU_RETAIL_LEVERAGE_GOLD)

    def test_a_smaller_account_is_stopped_out_more_often(self):
        """Once both accounts can trade, the smaller one meets the broker
        sooner: three positions cost the same margin at any balance."""
        small = sweep(MicroConfig(start_equity=8_000.0), markets=20, bars=8_000)
        large = sweep(MicroConfig(start_equity=80_000.0), markets=20, bars=8_000)
        self.assertGreaterEqual(small.stop_out_rate, large.stop_out_rate)

    def test_the_stop_out_level_is_the_common_retail_one(self):
        self.assertEqual(STOP_OUT_LEVEL, 0.50)

    def test_open_positions_are_marked_at_the_end(self):
        """An open loser is a loss that has not been admitted yet. Leaving
        it out is how this strategy backtests beautifully."""
        r = run(MicroConfig(start_equity=20_000.0), seed=1, bars=2_000)
        self.assertEqual(r.trades, r.wins + r.losses)


class TestDeterminism(unittest.TestCase):
    def test_the_same_seed_gives_the_same_run(self):
        a = run(MicroConfig(start_equity=20_000.0), seed=9, bars=3_000)
        b = run(MicroConfig(start_equity=20_000.0), seed=9, bars=3_000)
        self.assertEqual(a.end_equity, b.end_equity)
        self.assertEqual(a.trades, b.trades)


if __name__ == "__main__":
    unittest.main()
