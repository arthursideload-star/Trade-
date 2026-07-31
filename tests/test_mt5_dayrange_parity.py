"""The day-range detector in the EA, held to the Python it was ported from.

MQL5 cannot be compiled in this environment, so a port written here is a
liability until something checks it. The project already has the pattern:
the EA's timezone arithmetic is transliterated into Python and tested hour
by hour against the implementation that has tests. This does the same for
`DetectDayRange`.

Three things are checked, and the difference between them matters:

1. **The constants are the same numbers.** Read out of the .mq5 source, not
   copied here, so a change on either side fails rather than drifting.
2. **The logic fires on the same bars.** A transliteration of the MQL5 runs
   against `metals.dayrange.predict` over thousands of bars; every signal,
   every direction and every predicted target has to agree.
3. **The stop is never tighter than Python's.** This one is an inequality,
   not an equality, and deliberately so: SECTION 10 applies M2's buffer,
   M1's ATR floor and the broker minimum after the setup hands over its
   level. Those can only widen a stop, and a hard risk rule outranks
   matching a backtest exactly.

What none of this can check is whether the file compiles. That still needs
MetaEditor and is stated as an open risk in docs/REPO-AUDIT.md, A10.
"""

from __future__ import annotations

import pathlib
import re
import unittest

from metals import simulate
from metals.dayrange import DayRangeConfig, predict

EA = pathlib.Path("mt5/Experts/GoldScalpAssistant.mq5").read_text(encoding="utf-8")


def ea_input(name: str) -> float:
    """Read an input default straight out of the EA source."""
    m = re.search(rf"input\s+(?:double|int)\s+{name}\s*=\s*([-\d.]+)\s*;", EA)
    if not m:
        raise AssertionError(f"{name} is not an input in the EA any more")
    return float(m.group(1))


def ea_define(name: str) -> float:
    m = re.search(rf"#define\s+{name}\s+([-\d.]+)", EA)
    if not m:
        raise AssertionError(f"{name} is not defined in the EA any more")
    return float(m.group(1))


class TestTheConstantsMatch(unittest.TestCase):
    """Read from both sides. Neither number is written down twice here."""

    CFG = DayRangeConfig()

    def test_edge_fraction(self):
        self.assertAlmostEqual(ea_input("InpDrEdgeFraction"),
                               self.CFG.edge_fraction)

    def test_confirm_bars(self):
        self.assertEqual(int(ea_input("InpDrConfirmBars")),
                         self.CFG.confirm_bars)

    def test_min_range_atr(self):
        self.assertAlmostEqual(ea_input("InpDrMinRangeAtr"),
                               self.CFG.min_range_atr)

    def test_stop_fraction(self):
        self.assertAlmostEqual(ea_input("InpDrStopFraction"),
                               self.CFG.stop_fraction)

    def test_the_minimum_bar_count_is_the_same_hour(self):
        """60 M1 bars in Python, 12 M5 bars in the EA -- one hour either
        way. Expressed as the conversion so a change to one is visible."""
        self.assertEqual(ea_define("MIN_DR_BARS") * 5,
                         self.CFG.min_bars_for_range)

    def test_the_day_window_is_a_day_on_the_eas_timeframe(self):
        m = re.search(r"const int DAY_BARS = (\d+);", EA)
        self.assertIsNotNone(m, "DAY_BARS is gone from the EA")
        self.assertEqual(int(m.group(1)) * 5, self.CFG.bars_per_day)


def mql_detect(bars, i, cfg, day_bars: int, min_bars: int):
    """Transliteration of DetectDayRange, deliberately literal.

    Written to mirror the MQL5 line for line rather than to be good Python:
    a tidied version would stop testing the thing it is meant to test.
    Returns (found, is_long, target) using the same bar-0-is-newest
    convention the EA uses.
    """
    window = bars[max(0, i - day_bars + 1):i + 1]
    if len(window) < min_bars:
        return False, False, 0.0

    high = max(b.high for b in window)
    low = min(b.low for b in window)
    span = high - low
    if span <= 0:
        return False, False, 0.0

    atr = _atr(bars, i)
    if atr <= 0 or span < atr * cfg.min_range_atr:
        return False, False, 0.0

    price = bars[i].close
    position = (price - low) / span

    rising = falling = True
    for k in range(cfg.confirm_bars):
        if i - k < 0:
            break
        b = bars[i - k]
        if b.close < b.open:
            rising = False
        if b.close > b.open:
            falling = False

    at_low = position <= cfg.edge_fraction
    at_high = position >= 1.0 - cfg.edge_fraction
    if not ((at_low and rising) or (at_high and falling)):
        return False, False, 0.0

    is_long = at_low and rising
    return True, is_long, (high if is_long else low)


def _atr(bars, i, period: int = 14) -> float:
    from metals.dayrange import _atr as python_atr
    return python_atr(bars, i, period)


class TestTheLogicAgrees(unittest.TestCase):
    """The transliteration against the Python it was ported from."""

    def setUp(self):
        self.cfg = DayRangeConfig()
        self.bars = list(simulate.generate(bars=12_000, timeframe="1m",
                                           seed=77).candles)

    def test_the_same_bars_produce_the_same_signals(self):
        agreed = signals = 0
        for i in range(200, len(self.bars), 13):
            p = predict(self.bars, i, self.cfg)
            found, is_long, target = mql_detect(
                self.bars, i, self.cfg,
                day_bars=self.cfg.bars_per_day,
                min_bars=self.cfg.min_bars_for_range)

            self.assertEqual(p.direction != "none", found,
                             f"bar {i}: python says {p.direction!r}, "
                             f"the port says {found}")
            if found:
                signals += 1
                self.assertEqual(p.direction == "long", is_long, f"bar {i}")
                self.assertAlmostEqual(p.target, target, places=6,
                                       msg=f"bar {i}")
                agreed += 1
        self.assertGreater(signals, 20,
                           "too few signals to call this a comparison")
        self.assertEqual(agreed, signals)

    def test_it_refuses_before_an_hour_of_bars_exists(self):
        for i in range(0, self.cfg.min_bars_for_range):
            found, _, _ = mql_detect(self.bars, i, self.cfg,
                                     day_bars=self.cfg.bars_per_day,
                                     min_bars=self.cfg.min_bars_for_range)
            self.assertFalse(found)


class TestTheStopIsNeverTighter(unittest.TestCase):
    """The one intentional difference, pinned as an inequality.

    The EA hands SECTION 10 a level at stop_fraction of the predicted move,
    and M2, M1 and the broker minimum may then push it further away. Further
    is always allowed; closer never is.
    """

    def test_the_buffer_and_floor_only_widen(self):
        cfg = DayRangeConfig()
        bars = list(simulate.generate(bars=8_000, timeframe="1m",
                                      seed=91).candles)
        buffer_atr = ea_define("STOP_BUFFER_ATR")
        floor_atr = ea_define("MIN_STOP_ATR_MULTIPLE")

        checked = 0
        for i in range(200, len(bars), 11):
            p = predict(bars, i, cfg)
            if p.direction == "none":
                continue
            atr = _atr(bars, i)
            long = p.direction == "long"
            entry = p.entry
            level = (entry - p.move * cfg.stop_fraction if long
                     else entry + p.move * cfg.stop_fraction)

            ea_stop = level - atr * buffer_atr if long else level + atr * buffer_atr
            floor = atr * floor_atr
            if abs(entry - ea_stop) < floor:
                ea_stop = entry - floor if long else entry + floor

            python_distance = p.move * cfg.stop_fraction
            self.assertGreaterEqual(abs(entry - ea_stop) + 1e-9,
                                    python_distance,
                                    f"bar {i}: the EA's stop came out tighter "
                                    f"than Python's, which the risk rules "
                                    f"must never do")
            checked += 1
        self.assertGreater(checked, 20)


class TestItIsWiredIn(unittest.TestCase):
    def test_the_detector_is_reachable_from_the_dispatch(self):
        self.assertIn("if(InpUseDayRange && !s.found) s = DetectDayRange(", EA)

    def test_it_is_off_by_default(self):
        """Unproven on real gold. A strategy switches itself on when the
        evidence says so, not when it is written."""
        m = re.search(r"input bool\s+InpUseDayRange\s*=\s*(\w+)\s*;", EA)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "false")

    def test_the_setup_identifies_itself_in_the_journal(self):
        self.assertIn('s.id               = "DR";', EA)

    def test_it_names_its_failure_mode_like_every_other_setup(self):
        block = EA[EA.index("Setup DetectDayRange"):]
        block = block[:block.index("\n}\n")]
        self.assertIn("s.failure_mode", block)
        self.assertIn("s.evidence", block)


if __name__ == "__main__":
    unittest.main()
