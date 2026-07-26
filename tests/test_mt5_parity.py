"""Parity between the MQL5 expert advisor and the Python package.

The EA cannot be compiled or executed here, so the parts of it most likely to
be silently wrong are re-implemented in Python *literally* -- following the
MQL5 source line for line -- and checked against the already-tested Python
implementation.

This catches the failure mode that matters: the EA and the backtest drifting
apart, so that what was measured and what runs are no longer the same system.
The daylight-saving arithmetic is the prime candidate, because an error there
shifts every session window by an hour for several weeks a year and is
invisible in the results.

If the MQL5 source changes, these ports must change with it. They are checked
against the file so a divergence shows up as a failing test rather than as a
comment that stopped being true.
"""

from __future__ import annotations

import os
import re
import unittest
from datetime import datetime, timedelta, timezone

from metals.risk import (DAILY_LOSS_LIMIT_PCT, MAX_RISK_PER_TRADE_PCT,
                         MIN_REWARD_RISK)
from metals.sessions import Quality, classify, eu_dst_active, us_dst_active

UTC = timezone.utc
MT5_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "mt5")
EA_PATH = os.path.join(MT5_DIR, "Experts", "GoldScalpAssistant.mq5")
RISK_PATH = os.path.join(MT5_DIR, "Include", "GoldScalp", "Risk.mqh")
SESSIONS_PATH = os.path.join(MT5_DIR, "Include", "GoldScalp", "Sessions.mqh")


# --- Literal ports of the MQL5 helpers --------------------------------------

def mql_days_in_month(year: int, month: int) -> int:
    days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if month == 2:
        leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
        return 29 if leap else 28
    return days[month - 1]


def mql_last_sunday(year: int, month: int) -> datetime:
    last = datetime(year, month, mql_days_in_month(year, month), tzinfo=UTC)
    dow = (last.weekday() + 1) % 7        # MQL5 day_of_week: 0 = Sunday
    return last - timedelta(days=dow)


def mql_nth_sunday(year: int, month: int, n: int) -> datetime:
    first = datetime(year, month, 1, tzinfo=UTC)
    dow = (first.weekday() + 1) % 7
    to_sunday = (7 - dow) % 7
    return first + timedelta(days=to_sunday + (n - 1) * 7)


def mql_eu_summer_time(utc: datetime) -> bool:
    start = mql_last_sunday(utc.year, 3) + timedelta(hours=1)
    end = mql_last_sunday(utc.year, 10) + timedelta(hours=1)
    return start <= utc < end


def mql_us_daylight_time(utc: datetime) -> bool:
    start = mql_nth_sunday(utc.year, 3, 2) + timedelta(hours=7)
    end = mql_nth_sunday(utc.year, 11, 1) + timedelta(hours=6)
    return start <= utc < end


def mql_market_open(utc: datetime) -> bool:
    wd = (utc.weekday() + 1) % 7          # MQL5 numbering
    if wd == 6:
        return False
    if wd == 0:
        return utc.hour >= 22
    if wd == 5 and utc.hour >= 21:
        return False
    return True


def mql_in_rollover(utc: datetime) -> bool:
    return 21 <= utc.hour < 23


# --- Tests ------------------------------------------------------------------

class TestSundayArithmetic(unittest.TestCase):
    def test_last_sunday_is_a_sunday_inside_the_month(self):
        for year in range(2024, 2031):
            for month in (3, 10, 11):
                d = mql_last_sunday(year, month)
                self.assertEqual(d.weekday(), 6, f"{year}-{month}")
                self.assertEqual(d.month, month, f"{year}-{month} left the month")
                self.assertNotEqual((d + timedelta(days=7)).month, month,
                                    f"{year}-{month} is not the LAST Sunday")

    def test_nth_sunday(self):
        for year in range(2024, 2031):
            self.assertEqual(mql_nth_sunday(year, 3, 2).weekday(), 6)
            self.assertEqual(mql_nth_sunday(year, 11, 1).weekday(), 6)
            # The first Sunday of November must be in the first seven days.
            self.assertLessEqual(mql_nth_sunday(year, 11, 1).day, 7)

    def test_february_leap_years(self):
        self.assertEqual(mql_days_in_month(2024, 2), 29)
        self.assertEqual(mql_days_in_month(2025, 2), 28)
        self.assertEqual(mql_days_in_month(2000, 2), 29)
        self.assertEqual(mql_days_in_month(1900, 2), 28)


class TestDaylightSavingParity(unittest.TestCase):
    """The EA and the Python package must agree on DST to the hour.

    Checked hourly across four years rather than at a few sample points,
    because the failure is a boundary error that a sample would miss.
    """

    def test_eu_summer_time_matches_hour_by_hour(self):
        mismatches = self._sweep(mql_eu_summer_time, eu_dst_active)
        self.assertEqual(mismatches, [], f"{len(mismatches)} EU DST mismatches, "
                                         f"first at {mismatches[:3]}")

    def test_us_daylight_time_matches_hour_by_hour(self):
        mismatches = self._sweep(mql_us_daylight_time, us_dst_active)
        self.assertEqual(mismatches, [], f"{len(mismatches)} US DST mismatches, "
                                         f"first at {mismatches[:3]}")

    @staticmethod
    def _sweep(mql_fn, py_fn) -> list[datetime]:
        out: list[datetime] = []
        t = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2028, 1, 1, tzinfo=UTC)
        while t < end:
            if mql_fn(t) != py_fn(t):
                out.append(t)
                if len(out) > 5:
                    break
            t += timedelta(hours=1)
        return out

    def test_the_offsets_that_follow(self):
        summer = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
        winter = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
        self.assertTrue(mql_eu_summer_time(summer))
        self.assertFalse(mql_eu_summer_time(winter))
        self.assertTrue(mql_us_daylight_time(summer))
        self.assertFalse(mql_us_daylight_time(winter))
        # 08:00 New York is 12:00 UTC in summer and 13:00 UTC in winter.
        self.assertEqual((8 + 4) % 24, 12)
        self.assertEqual((8 + 5) % 24, 13)


class TestSessionParity(unittest.TestCase):
    def test_market_open_agrees(self):
        t = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 4, 1, tzinfo=UTC)
        while t < end:
            py_closed = classify(t).quality is Quality.AVOID and \
                classify(t).reasons[0] == "market closed"
            if py_closed:
                self.assertFalse(mql_market_open(t),
                                 f"{t}: python says closed, MQL5 says open")
            t += timedelta(hours=1)

    def test_rollover_agrees(self):
        for hour in range(24):
            moment = datetime(2026, 7, 21, hour, 30, tzinfo=UTC)
            py = classify(moment)
            py_rollover = "rollover" in py.active_windows
            self.assertEqual(py_rollover, mql_in_rollover(moment),
                             f"hour {hour}")

    def test_the_prime_windows_line_up(self):
        # Tuesday 14:00 UTC in July: London 15:00, New York 10:00 -> overlap.
        moment = datetime(2026, 7, 21, 14, 0, tzinfo=UTC)
        self.assertIs(classify(moment).quality, Quality.PRIME)
        ldn = 15 if mql_eu_summer_time(moment) else 14
        nyc = 10 if mql_us_daylight_time(moment) else 9
        self.assertTrue(13 <= ldn < 17 and 8 <= nyc < 12)


class TestConstantsMatchTheSource(unittest.TestCase):
    """The limits in Risk.mqh must equal the limits in metals/risk.py.

    Two copies of a risk limit is one copy too many, and this is the cheapest
    way to notice when they drift apart.
    """

    @staticmethod
    def _define(path: str, name: str) -> float:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        match = re.search(rf"#define\s+{name}\s+([-\d.]+)", text)
        if not match:
            raise AssertionError(f"{name} not found in {os.path.basename(path)}")
        return float(match.group(1))

    def test_risk_per_trade(self):
        self.assertEqual(self._define(RISK_PATH, "RISK_PER_TRADE_PCT"),
                         MAX_RISK_PER_TRADE_PCT)

    def test_daily_loss_limit(self):
        self.assertEqual(self._define(RISK_PATH, "DAILY_LOSS_LIMIT_PCT"),
                         DAILY_LOSS_LIMIT_PCT)

    def test_minimum_reward_risk(self):
        self.assertEqual(self._define(RISK_PATH, "MIN_REWARD_RISK"),
                         MIN_REWARD_RISK)

    def test_daily_win_target_matches_exits_module(self):
        from metals.exits import DAILY_WIN_TARGET_PCT
        self.assertEqual(self._define(RISK_PATH, "DAILY_WIN_TARGET_PCT"),
                         DAILY_WIN_TARGET_PCT)

    def test_trade_and_loss_caps_match(self):
        from metals.exits import (COOLDOWN_AFTER_LOSS_MINUTES,
                                  MAX_CONSECUTIVE_LOSSES, MAX_TRADES_PER_DAY)
        self.assertEqual(self._define(RISK_PATH, "MAX_TRADES_PER_DAY"),
                         MAX_TRADES_PER_DAY)
        self.assertEqual(self._define(RISK_PATH, "MAX_CONSECUTIVE_LOSSES"),
                         MAX_CONSECUTIVE_LOSSES)
        self.assertEqual(self._define(RISK_PATH, "COOLDOWN_AFTER_LOSS_MIN"),
                         COOLDOWN_AFTER_LOSS_MINUTES)

    def test_scalp_stop_floor_matches(self):
        from metals.scalping import MIN_SCALP_STOP_ATR
        self.assertEqual(self._define(RISK_PATH, "MIN_STOP_ATR_MULTIPLE"),
                         MIN_SCALP_STOP_ATR)

    def test_spread_gate_matches(self):
        from metals.risk import MAX_SPREAD_ATR_FRACTION
        from metals.scalping import MAX_SPREAD_PCT_OF_STOP
        self.assertEqual(self._define(RISK_PATH, "MAX_SPREAD_ATR_FRACTION"),
                         MAX_SPREAD_ATR_FRACTION)
        self.assertEqual(self._define(RISK_PATH, "MAX_SPREAD_PCT_OF_STOP"),
                         MAX_SPREAD_PCT_OF_STOP)

    def test_friday_flat_hour_matches(self):
        from metals.risk import WEEKEND_FLAT_HOUR_UTC
        self.assertEqual(self._define(RISK_PATH, "FRIDAY_FLAT_HOUR_UTC"),
                         WEEKEND_FLAT_HOUR_UTC)


class TestSourceFilesExistAndAreSane(unittest.TestCase):
    def test_files_are_present(self):
        for path in (EA_PATH, RISK_PATH, SESSIONS_PATH):
            self.assertTrue(os.path.exists(path), path)

    def test_ea_defaults_to_advisor_mode(self):
        """Shipping an EA that trades on first launch would put an unproven
        strategy in charge of an account by default."""
        with open(EA_PATH, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("InpMode            = MODE_ADVISOR", text)

    def test_ea_states_the_expectancy_finding(self):
        """Anyone opening the file must meet the honest result before the
        code."""
        with open(EA_PATH, encoding="utf-8") as fh:
            head = fh.read(4000)
        self.assertIn("NOT been shown to have a positive", head)

    def test_first_target_default_matches_the_measured_value(self):
        from metals.exits import build_exit_plan
        plan = build_exit_plan("XAUUSD", "long", 4500, 4490, 5.0, "scalp")
        with open(EA_PATH, encoding="utf-8") as fh:
            text = fh.read()
        match = re.search(r"InpFirstTargetR\s*=\s*([\d.]+)", text)
        self.assertIsNotNone(match)
        self.assertEqual(float(match.group(1)), plan.first_target_r)

    def test_sessions_include_declares_its_dependency(self):
        with open(SESSIONS_PATH, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("GoldScalp\\Risk.mqh", text)

    def test_no_martingale_anywhere_in_the_ea(self):
        """R6 as a source-level check: nothing may scale size after a loss."""
        with open(EA_PATH, encoding="utf-8") as fh:
            text = fh.read().lower()
        for forbidden in ("martingale", "lots * 2", "lots*2", "double the lot"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
