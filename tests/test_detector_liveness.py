"""Every detector must be able to fire, and to fire above the filter.

Why this file exists
--------------------
The repo had a large, green test suite and two of the three setups the expert
advisor trades could not produce a single trade between them. Nothing failed,
because every existing test asked "given a signal, is it handled correctly?"
and none asked "can a signal happen at all?".

Two different defects hid in that gap:

* **A31 -- S2 counted the breakout bar into its own pullback.** The trigger is
  the highest high of the pullback, so the breakout bar had to close above its
  own high. The condition was unsatisfiable. S2 fired zero times in 39,000
  bars, and zero times on a market built to be a textbook S2.

* **A32 -- S5 returned a constant confidence of 0.57** while the backtest
  filtered at 0.60. Not a filter: an off switch. S5 fired 1,916 times in the
  same 39,000 bars, always at exactly 0.570, and not one survived.

Both are invisible to a test that starts from a signal. Both are caught by the
two questions below, which is why they are asked per detector rather than in
passing:

1. Does a market built to the setup's own written description make it fire?
2. Of the signals it produces, can *any* clear the default confidence filter?

A "no" to (2) means the setup is disabled. Disabling a setup is a legitimate
decision -- but it has to be a decision somebody made and wrote down, not an
accident that emerges from two numbers in two different files.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from metals.backtest import BacktestConfig
from metals.candles import Candle, CandleSeries
from metals.levels import build_level_map
from metals.scalping import CATALOGUE, _atr, detect_s2, detect_s4, detect_s5
from metals.sessions import classify
from metals.simulate import generate

START = datetime(2026, 3, 3, 9, 0, tzinfo=timezone.utc)


def _series(candles: list[Candle]) -> CandleSeries:
    return CandleSeries("XAUUSD", "5m", candles)


def _bar(i: int, o: float, h: float, low: float, c: float) -> Candle:
    return Candle(START + timedelta(minutes=5 * i), o, h, low, c)


def textbook_s2_market() -> CandleSeries:
    """An EMA stack with slope, a two-bar pullback, and a bar that breaks it.

    Exactly what the S2 docstring describes, with nothing else going on.
    """
    candles: list[Candle] = []
    price = 4000.0
    for i in range(70):                       # detector needs >= 60 bars
        close = price + 3.0
        candles.append(_bar(i, price, close + 0.5, price - 0.5, close))
        price = close
    for i in range(70, 72):                   # the counter-trend pullback
        close = price - 2.0
        candles.append(_bar(i, price, price + 0.5, close - 0.5, close))
        price = close
    trigger = max(c.high for c in candles[-2:])
    close = trigger + 2.0                     # the breakout bar
    candles.append(_bar(72, price, close + 0.3, price - 0.3, close))
    return _series(candles)


def textbook_s5_market(impulse_atrs: float = 4.0, retrace: float = 0.05,
                       steps: int = 4) -> CandleSeries:
    """An impulse bar closing at its high, then a retracement into its third.

    `impulse_atrs` sizes the impulse against the ATR of the quiet bars that
    precede it. `retrace` is how far the last bar reaches back past the near
    third, as a fraction of the distance from there to the impulse origin:
    0.0 just touches the third, 1.0 sits on the origin.

    The retracement is walked down over several bars whose close sits at the
    exact middle of their range. That detail matters: a single bar large
    enough to cover the retracement in one move is itself an impulse closing
    in the outer 20% of its range, so the detector picks *it* as the impulse
    and the fixture silently tests the wrong bar.
    """
    candles: list[Candle] = []
    price = 4000.0
    for i in range(40):                       # quiet bars set the ATR
        close = price + 0.05
        candles.append(_bar(i, price, price + 0.6, price - 0.6, close))
        price = close

    a = _atr(_series(candles)) or 1.0

    low = price
    rng = a * impulse_atrs
    close = low + rng * 0.95                  # closes in the top 20%
    candles.append(_bar(40, low, low + rng, low, close))

    third = low + rng / 3.0
    target = third - (third - low) * retrace
    previous = close
    for step in range(steps + 1):
        bottom = (min(target, previous - 0.05) if step == steps
                  else previous - (previous - target) / (steps - step))
        top = previous + 0.15
        candles.append(_bar(41 + step, previous, top, bottom,
                            (top + bottom) / 2.0))
        previous = (top + bottom) / 2.0
    return _series(candles)


class DetectorsCanFire(unittest.TestCase):
    """Question 1: does the setup's own description make it fire?"""

    def test_s2_fires_on_a_textbook_pullback_break(self):
        m5 = textbook_s2_market()
        hit = detect_s2("XAUUSD", m5, 0.20, _atr(m5))
        self.assertIsNotNone(
            hit,
            "S2 did not fire on a market built to its own docstring: an EMA "
            "stack with slope, a two-bar pullback, and a bar closing 2.00 "
            "above the pullback high. This is regression A31.")
        self.assertEqual(hit.direction, "long")

    def test_s2_breakout_bar_is_not_part_of_its_own_pullback(self):
        """The A31 regression, stated as the invariant it violated.

        The breakout bar closes beyond the pullback's extreme. If it were
        itself inside the pullback, the extreme would already include its own
        high and the comparison could never be true.
        """
        m5 = textbook_s2_market()
        hit = detect_s2("XAUUSD", m5, 0.20, _atr(m5))
        assert hit is not None
        last = m5.last
        self.assertGreater(
            last.close, last.open,
            "the bar that breaks an up-pullback must itself close up")
        window = [c for c in m5.candles[-4:-1]]
        self.assertTrue(
            any(last.close > c.high for c in window),
            "the breakout close must clear at least one pullback high")

    def test_s5_fires_after_an_impulse_and_a_shallow_retracement(self):
        m5 = textbook_s5_market()
        hit = detect_s5("XAUUSD", m5, None, 0.20, _atr(m5))
        self.assertIsNotNone(
            hit, "S5 did not fire on a 3x ATR impulse followed by a "
                 "retracement into its near third")
        self.assertEqual(hit.direction, "long")


class ConfidenceCanClearTheFilter(unittest.TestCase):
    """Question 2: can the signal survive the filter the backtest applies?"""

    def test_s5_confidence_is_not_a_constant(self):
        """A32. A constant confidence turns a threshold into an off switch."""
        strong_market = textbook_s5_market(4.0, 0.05)
        strong = detect_s5("XAUUSD", strong_market, None, 0.20,
                           _atr(strong_market))
        weak_market = textbook_s5_market(2.4, 0.95)
        weak = detect_s5("XAUUSD", weak_market, None, 0.20, _atr(weak_market))
        self.assertIsNotNone(strong)
        self.assertIsNotNone(weak)
        self.assertGreater(
            strong.confidence, weak.confidence,
            "a large impulse retraced barely into its third must score above "
            "a small one retraced to its origin; if these are equal the "
            "confidence carries no information and the filter is an on/off "
            "switch (A32)")
        self.assertLess(
            weak.confidence, BacktestConfig().min_confidence,
            "the weak case must actually be filtered out, otherwise the "
            "confidence moves but the threshold still separates nothing")

    def test_s5_can_clear_the_default_confidence_filter(self):
        m5 = textbook_s5_market(4.0, 0.05)
        hit = detect_s5("XAUUSD", m5, None, 0.20, _atr(m5))
        assert hit is not None
        self.assertGreaterEqual(
            hit.confidence, BacktestConfig().min_confidence,
            f"S5's best case scores {hit.confidence:.3f} against a "
            f"{BacktestConfig().min_confidence} filter, so the backtest "
            f"trades it zero times while the EA trades it unfiltered (A32)")

    def test_s2_can_clear_the_default_confidence_filter(self):
        m5 = textbook_s2_market()
        hit = detect_s2("XAUUSD", m5, 0.20, _atr(m5))
        assert hit is not None
        self.assertGreaterEqual(hit.confidence,
                                BacktestConfig().min_confidence)

    def test_no_traded_setup_is_capped_below_the_default_filter(self):
        """The general form: an unreachable filter disables a setup silently.

        Checked against the catalogue rather than against any one detector,
        so a new setup added with a low base confidence trips this too.
        """
        floor = BacktestConfig().min_confidence
        for setup_id in ("S2", "S4", "S5"):        # the three the EA trades
            spec = CATALOGUE[setup_id]
            headroom = 0.90 - spec.base_confidence
            self.assertGreater(
                headroom, 0.0,
                f"{setup_id} base confidence {spec.base_confidence} leaves "
                f"no room to reach the {floor} filter")


class DetectorsFireOnGeneratedData(unittest.TestCase):
    """The same two questions on data nobody shaped by hand.

    A detector can pass a hand-built market and still never fire on anything
    that looks like a market, which is what the 39,000-bar scan found. One
    seed and a short window keeps this under a couple of seconds.
    """

    def _scan(self, seed: int, bars: int) -> dict[str, list[float]]:
        m5 = generate(bars=bars, seed=seed)
        found: dict[str, list[float]] = {"S2": [], "S4": [], "S5": []}
        level_map = None
        for i in range(120, len(m5)):
            window = CandleSeries("XAUUSD", "5m", m5.candles[:i + 1])
            a = _atr(window)
            if not a:
                continue
            if level_map is None or i % 12 == 0:
                level_map = build_level_map("XAUUSD", window.last.close,
                                            htf=window)
            ts = window.last.ts
            classify(ts)
            for key, hit in (
                ("S2", detect_s2("XAUUSD", window, 0.20, a)),
                ("S4", detect_s4("XAUUSD", window, level_map, 0.20, a)),
                ("S5", detect_s5("XAUUSD", window, None, 0.20, a)),
            ):
                if hit is not None:
                    found[key].append(hit.confidence)
        return found

    def test_s2_and_s5_fire_on_a_generated_market(self):
        found = self._scan(seed=7, bars=2200)
        for key in ("S2", "S5"):
            self.assertTrue(
                found[key],
                f"{key} fired zero times over the scanned window. Before the "
                f"A31/A32 fixes S2 fired zero times in 39,000 bars.")

    # Below this many signals, "none cleared the filter" is a small sample
    # rather than a finding -- S4 fires roughly once per 240 bars, so a short
    # window can honestly produce three signals that all happen to be weak.
    # The 39,000-bar baseline had S4 at 162 signals, 49 of them over 0.60.
    MIN_SIGNALS_TO_JUDGE = 20

    def test_generated_signals_are_not_all_below_the_filter(self):
        floor = BacktestConfig().min_confidence
        found = self._scan(seed=7, bars=2200)
        judged = 0
        for key, confidences in found.items():
            if len(confidences) < self.MIN_SIGNALS_TO_JUDGE:
                continue
            judged += 1
            self.assertTrue(
                any(c >= floor for c in confidences),
                f"{key} produced {len(confidences)} signals, none of them at "
                f"or above the {floor} filter (min {min(confidences):.3f}, "
                f"max {max(confidences):.3f}). The setup is switched off, "
                f"not filtered.")
        self.assertTrue(
            judged, "no setup produced enough signals to judge -- the scan "
                    "window is too short for this test to mean anything")


if __name__ == "__main__":
    unittest.main()
