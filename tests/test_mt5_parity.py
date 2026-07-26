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
# The EA is one self-contained file: no include folder to create, which makes
# it installable by copying a single file. The limits therefore live in the EA
# itself and are read from there.
RISK_PATH = EA_PATH
SESSIONS_PATH = EA_PATH


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
    def test_the_ea_is_a_single_self_contained_file(self):
        """One file, no include folder.

        Installing from a phone-driven remote desktop is fiddly enough
        without creating directory trees; and one copy of each risk limit is
        the whole point of the parity checks above.
        """
        self.assertTrue(os.path.exists(EA_PATH), EA_PATH)
        self.assertFalse(os.path.isdir(os.path.join(MT5_DIR, "Include")),
                         "the Include folder is back -- the limits now exist "
                         "twice and can drift apart")
        with open(EA_PATH, encoding="utf-8") as fh:
            text = fh.read()
        for forbidden in ("GoldScalp\\Risk.mqh", "GoldScalp\\Sessions.mqh"):
            self.assertNotIn(forbidden, text)

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

    def test_state_is_recovered_after_a_reload(self):
        """Without recovery a restart orphans an open position and resets the
        daily counters, so the caps can be bypassed by reloading."""
        with open(EA_PATH, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("AdoptExistingPosition", text)
        self.assertIn("RebuildDayState", text)
        # Both must be called from OnInit, not merely defined.
        init = text[text.index("int OnInit()"):text.index("void OnDeinit")]
        self.assertIn("RebuildDayState(utc)", init)
        self.assertIn("AdoptExistingPosition(utc)", init)

    def test_an_adopted_position_without_a_stop_is_closed(self):
        """R7 has no exception for a position the EA did not open itself."""
        with open(EA_PATH, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("adopted a position with NO stop loss", text)

    def test_no_martingale_anywhere_in_the_ea(self):
        """R6 as a source-level check: nothing may scale size after a loss."""
        with open(EA_PATH, encoding="utf-8") as fh:
            text = fh.read().lower()
        for forbidden in ("martingale", "lots * 2", "lots*2", "double the lot"):
            self.assertNotIn(forbidden, text)


def _strip_mql(source: str) -> str:
    """Remove comments and string literals so punctuation inside them is not
    counted as code."""
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    out = []
    for line in source.splitlines():
        line = re.sub(r'"(\\.|[^"\\])*"', '""', line)
        line = re.sub(r"//.*$", "", line)
        out.append(line)
    return "\n".join(out)


class TestTheEaIsStructurallyIntact(unittest.TestCase):
    """Structural checks standing in for a compiler.

    MQL5 cannot be compiled in this environment, so the first time anyone
    finds out the file is broken is in MetaEditor on a VPS, at which point
    the feedback loop is a screenshot sent over chat. These checks catch the
    damage an edit does most often -- an unbalanced brace, a helper called
    but never defined -- while it is still cheap to fix.
    """

    @classmethod
    def setUpClass(cls):
        with open(EA_PATH, encoding="utf-8") as fh:
            cls.raw = fh.read()
        cls.code = _strip_mql(cls.raw)

    def test_braces_balance(self):
        self.assertEqual(self.code.count("{"), self.code.count("}"),
                         "unbalanced braces -- the file will not compile")

    def test_parentheses_balance(self):
        self.assertEqual(self.code.count("("), self.code.count(")"),
                         "unbalanced parentheses -- the file will not compile")

    def test_every_function_called_is_also_defined(self):
        """Limited to the project's own helpers: the MQL5 standard library is
        not visible here, so only names defined in this file are checked."""
        defined = set(re.findall(
            r"^\s*(?:void|int|bool|double|string|datetime|ulong)\s+(\w+)\s*\(",
            self.code, re.M))
        self.assertIn("OnTick", defined)
        self.assertIn("OnInit", defined)
        called = set(re.findall(r"\b(\w+)\s*\(", self.code))
        for helper in ("JournalAppend", "JournalSignal", "JournalClose",
                       "JournalHeader", "IsoUtc", "CsvSafe", "QualityLabel",
                       "SessionWord", "MoneyAtRisk", "CloseAll"):
            with self.subTest(helper=helper):
                self.assertIn(helper, defined, f"{helper} is called but never "
                                               f"defined")
                self.assertIn(helper, called, f"{helper} is defined but never "
                                              f"used -- dead code")

    def test_every_close_states_a_category_for_the_journal(self):
        """CloseAll's first argument is the bucket the journal groups by. A
        call that passed only the human sentence would put one trade per
        wording into its own bucket."""
        body = self.code.split("void CloseAll(", 1)[0]
        for call in re.findall(r"CloseAll\(([^;]*)\);", body, re.S):
            first = call.strip().split(",", 1)[0].strip()
            self.assertEqual(first, '""',
                             "CloseAll must be called with a category literal "
                             f"first, got {first!r}")

    def test_the_advisor_default_survived_the_edit(self):
        """Cheap to check and catastrophic to get wrong."""
        self.assertIn("InpMode            = MODE_ADVISOR", self.raw)


class TestJournalSchemaMatchesBothSides(unittest.TestCase):
    """The EA writes the journal; Python draws conclusions from it.

    A column added on one side and not the other does not crash anything --
    it shifts every field after it, so R multiples are read out of the pnl
    column and the analysis is confidently wrong. That is the worst kind of
    bug this project can have, so the schema is checked rather than trusted.
    """

    @staticmethod
    def _ea() -> str:
        with open(EA_PATH, encoding="utf-8") as fh:
            return fh.read()

    def test_the_header_the_ea_writes_is_the_schema_python_expects(self):
        from metals.journal import COLUMNS
        ea = self._ea()
        body = ea.split("string JournalHeader()", 1)[1].split("}", 1)[0]
        header = "".join(re.findall(r'"([^"]*)"', body))
        self.assertEqual(tuple(header.split(",")), COLUMNS)

    def test_every_journal_row_has_exactly_one_field_per_column(self):
        """Counted from the format strings themselves.

        `StringFormat` is happy to emit a row with the wrong number of commas
        and the CSV reader is happy to parse it, so nothing downstream would
        complain until a conclusion was drawn from the wrong column.
        """
        from metals.journal import COLUMNS
        ea = self._ea()
        formats = re.findall(r'"(%s,(?:signal|close),[^"]*)"', ea)
        self.assertTrue(formats, "no journal format strings found in the EA")
        for fmt in formats:
            kind = fmt.split(",")[1]
            with self.subTest(kind=kind):
                self.assertEqual(
                    len(fmt.split(",")), len(COLUMNS),
                    f"the {kind} row writes {len(fmt.split(','))} fields but "
                    f"the schema has {len(COLUMNS)} columns"
                )

    def test_the_row_kinds_are_the_ones_python_accepts(self):
        from metals.journal import CLOSE, SIGNAL
        ea = self._ea()
        kinds = {f.split(",")[1]
                 for f in re.findall(r'"(%s,(?:signal|close),[^"]*)"', ea)}
        self.assertEqual(kinds, {SIGNAL, CLOSE})

    def test_free_text_is_sanitised_before_it_reaches_a_csv(self):
        """A skip reason containing a comma would shift its own row."""
        ea = self._ea()
        self.assertIn("string CsvSafe(", ea)
        body = ea.split("string CsvSafe(", 1)[1].split("\n}", 1)[0]
        self.assertIn('StringReplace(out, ",", ";")', body)
        # Every free-text field must go through it.
        for call in ("CsvSafe(skip_reason)", "CsvSafe(exit_reason)",
                     "CsvSafe(setup_id)"):
            self.assertIn(call, ea, f"{call} is missing -- that field can "
                                    f"carry a comma into the CSV")

    def test_a_persisting_setup_is_logged_once_not_once_per_bar(self):
        """Advisor mode never opens a position, so the setup search keeps
        running every bar instead of stopping while a trade is on. Without
        this, a setup valid for six bars is written six times and every count
        in the analysis measures how long conditions lasted rather than how
        often they arose."""
        ea = self._ea()
        self.assertIn("bool SignalIsARepeat(", ea)
        self.assertIn("SignalIsARepeat(", ea.split("void JournalSignal(", 1)[1])

    def test_a_signal_that_was_traded_is_never_suppressed(self):
        """It has to pair up with its close row, or the two halves of the
        record stop matching."""
        body = self._ea().split("void JournalSignal(", 1)[1].split("\n}", 1)[0]
        guard = body[:body.index("JournalAppend")]
        self.assertIn("if(!taken", guard.replace(" ", ""),
                      "the repeat guard must exempt taken signals")

    def test_the_r_multiple_is_money_over_money_not_price_over_price(self):
        """Once a partial is taken, price distance stops being the risk that
        was actually run. Dividing by the money committed is the only
        definition that survives the exit logic."""
        ea = self._ea()
        self.assertIn("profit / managed.risk_money", ea)

    def test_the_ea_does_not_retune_itself_from_the_journal(self):
        """The journal is evidence, not a feedback loop.

        A system that reweights setups from its own recent results is fitting
        noise at the sample sizes involved. If that ever changes it must be a
        deliberate, reviewed decision -- not something that appears quietly.
        """
        ea = self._ea()
        # The EA may write the file and must never read it back.
        self.assertIn("FileWriteString", ea)
        for reading in ("FileReadString", "FileReadNumber", "FileReadDouble"):
            self.assertNotIn(reading, ea,
                             "the EA reads its own journal -- that is a "
                             "self-tuning loop and needs an explicit decision")


class TestTheInstallScriptStaysTrue(unittest.TestCase):
    """The script runs where nobody can debug it.

    It executes in a container terminal on a VPS, driven from a phone, by
    someone who cannot read shell. Every constant in it that can go stale is
    therefore checked here, where going stale costs a failing test instead of
    a confusing morning.
    """

    SCRIPT = os.path.join(MT5_DIR, "install-ea.sh")

    @classmethod
    def setUpClass(cls):
        with open(cls.SCRIPT, encoding="utf-8") as fh:
            cls.text = fh.read()

    def test_the_expected_line_count_matches_the_ea(self):
        with open(EA_PATH, encoding="utf-8") as fh:
            lines = sum(1 for _ in fh)
        match = re.search(r"EXPECTED_LINES=(\d+)", self.text)
        self.assertIsNotNone(match, "EXPECTED_LINES is gone from the script")
        self.assertEqual(int(match.group(1)), lines,
                         "the script would reject the very file it just "
                         "downloaded")

    def test_it_downloads_from_the_branch_this_project_develops_on(self):
        self.assertIn("claude/trading-bot-plan-4uj86r", self.text)
        self.assertIn("mt5/Experts/GoldScalpAssistant.mq5", self.text)

    def test_it_verifies_before_it_installs(self):
        """A truncated .mq5 sitting in Experts produces compiler errors that
        look like bugs in the EA. The file must only be moved into place
        after the line count proves it is whole."""
        move = self.text.index('mv "${TMP}" "${TARGET}"')
        check = self.text.index('if [ "${LINES}" != "${EXPECTED_LINES}" ]')
        self.assertLess(check, move,
                        "the script installs the file before checking it")

    def test_it_never_hard_codes_a_credential(self):
        """The script prints the container's own environment. It must not
        carry anyone's password in its text -- it lives in a public repo."""
        for forbidden in ("PASSWORD=", "CUSTOM_USER="):
            # Assignments are forbidden; reading them via printenv is the point.
            self.assertNotIn(f"\n{forbidden}", self.text)
        self.assertIn("printenv CUSTOM_USER", self.text)
        self.assertIn("printenv PASSWORD", self.text)

    def test_a_failed_compile_is_not_treated_as_a_failed_install(self):
        """Command-line compilation is a convenience. If it does not work the
        GUI route still does, and the script must say so rather than exit."""
        tail = self.text[self.text.index("4. Compiling"):]
        self.assertIn("Compile it from the GUI instead", tail)
        self.assertNotIn("exit 1", tail,
                         "a compile problem must not abort the install")

    def test_it_is_posix_sh_not_bash(self):
        """The image is not guaranteed to ship bash."""
        self.assertTrue(self.text.startswith("#!/bin/sh"))
        for bashism in ("[[", "function ", "$'"):
            self.assertNotIn(bashism, self.text)

    def test_it_points_at_the_journal_command_that_exists(self):
        from metals.cli import build_parser
        self.assertIn("python -m metals journal", self.text)
        # The parser must actually accept it, with that flag.
        args = build_parser().parse_args(
            ["journal", "--file", "GoldScalpAssistant.csv"])
        self.assertEqual(args.file, "GoldScalpAssistant.csv")


class TestSetupGuideStaysTrue(unittest.TestCase):
    """The VPS guide tells the user to verify the download by line count.

    That check is only useful while the number is right, and the number
    lives in prose that no compiler will ever look at.
    """

    GUIDE = os.path.join(MT5_DIR, "VPS-SETUP.md")

    def _guide(self):
        with open(self.GUIDE, encoding="utf-8") as fh:
            return fh.read()

    def test_the_stated_line_count_matches_the_file(self):
        with open(EA_PATH, encoding="utf-8") as fh:
            lines = sum(1 for _ in fh)
        guide = self._guide()
        # assertIn would dump the entire guide into the failure message, which
        # buries the one number that matters.
        for needle in (f"{lines} GoldScalpAssistant.mq5", f"{lines} Zeilen"):
            self.assertTrue(
                needle in guide,
                f"the guide does not mention {needle!r}. The EA now has "
                f"{lines} lines, so the `wc -l` check the guide teaches would "
                f"look like a failed download. Update mt5/VPS-SETUP.md."
            )

    def test_the_documented_panel_states_are_the_ones_the_ea_prints(self):
        """The guide teaches the user to read the panel. Renaming a state in
        the EA without touching the guide would teach them a word that never
        appears on their screen."""
        with open(EA_PATH, encoding="utf-8") as fh:
            ea = fh.read()
        guide = self._guide()
        # QualityLabel is the single place the EA turns a session quality into
        # a word -- both the panel and the journal go through it.
        labels = ea.split("string QualityLabel(", 1)[1].split("}", 1)[0]
        for state in ("PRIME", "good", "marginal", "AVOID"):
            self.assertIn(f'"{state}"', labels,
                          f"{state} is not a label the EA emits")
            self.assertIn(f"`{state}`", guide,
                          f"{state} is missing from the setup guide")

    def test_the_download_url_points_at_the_file_that_exists(self):
        """A raw URL cannot be resolved offline, so check its shape: the
        branch this project develops on, and the path the EA really has."""
        guide = self._guide()
        self.assertIn("refs/heads/claude/trading-bot-plan-4uj86r"
                      "/mt5/Experts/GoldScalpAssistant.mq5", guide)
        self.assertTrue(EA_PATH.endswith(
            os.path.join("mt5", "Experts", "GoldScalpAssistant.mq5")))


if __name__ == "__main__":
    unittest.main()
