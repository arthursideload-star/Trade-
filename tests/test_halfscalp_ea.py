"""The half-target EA, checked against the Python it is a port of.

This file cannot be compiled here -- there is no MetaEditor in the
container -- so everything a compiler would catch has to be caught by
reading. That is the same bargain tests/test_mt5_parity.py makes for the
other EA, and the same checks apply: balanced braces, format strings whose
placeholders match their arguments, and a journal schema identical to the
one metals/journal.py reads.

Beyond the mechanics, two things are worth more than the rest:

**The numbers must match the Python.** Every figure published about this
strategy -- the expectancy, the trade rate, the out-of-sample band -- was
measured by metals/halfscalp.py. If the EA charges a different cost or
projects a different target, those figures describe something that is not
running, which is the failure A33 was about.

**The two copies of the session arithmetic must not drift.** The daylight
saving code is duplicated rather than shared, because the project ships one
self-contained .mq5 per EA. Duplication is a decision with a maintenance
cost, and this file is where that cost is paid.
"""

from __future__ import annotations

import os
import re
import unittest

from metals.halfscalp import HalfScalpConfig
from metals.journal import COLUMNS

HERE = os.path.dirname(os.path.abspath(__file__))
MT5_DIR = os.path.join(os.path.dirname(HERE), "mt5")
EA_PATH = os.path.join(MT5_DIR, "Experts", "GoldHalfScalp.mq5")
OTHER_EA_PATH = os.path.join(MT5_DIR, "Experts", "GoldScalpAssistant.mq5")


def _strip_comments_and_strings(source: str) -> str:
    """Strings first, then comments -- the order is the whole trick.

    `#property link "https://github.com/..."` contains `//` inside a string
    literal. Stripping comments first eats the rest of that line including
    its closing quote, which leaves every following string literal paired
    with the wrong neighbour and makes the brace and parenthesis counts
    meaningless. This is the same order metals' other parity test uses, and
    for the same reason.
    """
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    out = []
    for line in source.splitlines():
        line = re.sub(r'"(\\.|[^"\\])*"', '""', line)
        line = re.sub(r"//.*$", "", line)
        out.append(line)
    return "\n".join(out)


def _balanced_call_body(text: str, start: int) -> str:
    depth, i = 1, start
    while i < len(text) and depth:
        if text[i] == '"':
            i += 1
            while i < len(text) and text[i] != '"':
                i += 2 if text[i] == "\\" else 1
        elif text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if not depth:
                return text[start:i]
        i += 1
    return ""


def _split_top_level_args(body: str) -> list[str]:
    args, depth, current, i = [], 0, [], 0
    while i < len(body):
        ch = body[i]
        if ch == '"':
            current.append(ch)
            i += 1
            while i < len(body) and body[i] != '"':
                current.append(body[i])
                i += 2 if body[i] == "\\" else 1
                if i - 1 < len(body) and body[i - 1] == "\\":
                    current.append(body[i - 1])
            current.append('"')
        elif ch in "([":
            depth += 1
            current.append(ch)
        elif ch in ")]":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    args.append("".join(current))
    return [a.strip() for a in args if a.strip()]


class TheFileIsPlausiblyCompilable(unittest.TestCase):
    """What a compiler would catch, caught by reading instead."""

    @classmethod
    def setUpClass(cls):
        with open(EA_PATH, encoding="utf-8") as fh:
            cls.raw = fh.read()
        cls.code = _strip_comments_and_strings(cls.raw)

    def test_braces_balance(self):
        self.assertEqual(self.code.count("{"), self.code.count("}"),
                         "unbalanced braces -- the file will not compile")

    def test_parentheses_balance(self):
        self.assertEqual(self.code.count("("), self.code.count(")"))

    def test_every_string_format_has_the_arguments_it_asks_for(self):
        checked = 0
        for m in re.finditer(r"StringFormat\s*\(", self.raw):
            body = _balanced_call_body(self.raw, m.end())
            args = _split_top_level_args(body)
            fmt = "".join(re.findall(r'"((?:\\.|[^"\\])*)"', args[0]))
            specs = len(re.findall(r"%[-+ #0-9.*]*[diouxXeEfgGscp]",
                                   fmt.replace("%%", "")))
            self.assertEqual(
                specs, len(args) - 1,
                f"StringFormat with {specs} placeholders and {len(args) - 1} "
                f"arguments: {fmt[:70]!r}")
            checked += 1
        # The file has six. The floor guards against the scan silently
        # matching nothing, not against the file having few.
        self.assertGreaterEqual(checked, 6,
                                "the scan found almost no StringFormat calls, "
                                "so it is not doing its job")

    def test_the_lifecycle_functions_exist(self):
        for fn in ("int OnInit()", "void OnTick()", "void OnDeinit("):
            self.assertIn(fn, self.raw, f"{fn} is missing")


class TheJournalSchemaMatchesPython(unittest.TestCase):
    """Same schema as the other EA, so metals journal/vault need no changes."""

    @classmethod
    def setUpClass(cls):
        with open(EA_PATH, encoding="utf-8") as fh:
            cls.raw = fh.read()

    def test_the_header_is_exactly_the_python_column_list(self):
        body = self.raw.split("string JournalHeader()", 1)[1].split("}", 1)[0]
        header = "".join(re.findall(r'"([^"]*)"', body))
        self.assertEqual(tuple(header.split(",")), COLUMNS)

    def test_every_journal_row_has_one_field_per_column(self):
        """A row with the wrong field count corrupts every later column.

        Counted as commas rather than placeholders, because most fields in
        these rows are deliberately empty.
        """
        checked = 0
        for m in re.finditer(r"JournalAppend\s*\(\s*StringFormat\s*\(", self.raw):
            body = _balanced_call_body(self.raw, m.end())
            args = _split_top_level_args(body)
            fmt = "".join(re.findall(r'"((?:\\.|[^"\\])*)"', args[0]))
            self.assertEqual(
                fmt.count(",") + 1, len(COLUMNS),
                f"journal row has {fmt.count(',') + 1} fields, the schema has "
                f"{len(COLUMNS)}: {fmt[:70]!r}")
            checked += 1
        self.assertEqual(checked, 2, "expected exactly a signal row and a "
                                     "close row")

    def test_it_writes_to_its_own_file(self):
        """Sharing GoldScalpAssistant.csv would mix two strategies in one
        record, which is the confusion this project keeps writing findings
        about."""
        self.assertIn('#define JOURNAL_FILE "GoldHalfScalp.csv"', self.raw)


class TheNumbersMatchTheMeasuredPython(unittest.TestCase):
    """The EA has to trade what metals/halfscalp.py measured.

    Not "something similar". Every figure in A34, A35 and the vault note
    describes the Python; a divergence here makes those figures describe
    nothing that runs.
    """

    @classmethod
    def setUpClass(cls):
        with open(EA_PATH, encoding="utf-8") as fh:
            cls.raw = fh.read()

    def _input_default(self, name: str) -> str:
        m = re.search(rf"input\s+\w+\s+{name}\s*=\s*([^;]+);", self.raw)
        self.assertIsNotNone(m, f"input {name} not found")
        return m.group(1).strip()

    def _const_value(self, name: str) -> str:
        m = re.search(rf"const\s+\w+\s+{name}\s*=\s*([^;]+);", self.raw)
        self.assertIsNotNone(m, f"const {name} not found")
        return m.group(1).strip()

    def test_the_take_fraction_is_the_half_the_strategy_is_named_for(self):
        self.assertEqual(float(self._input_default("InpTakeFraction")),
                         HalfScalpConfig().take_fraction)

    def test_the_stop_fraction_matches_python(self):
        self.assertEqual(float(self._input_default("InpStopFraction")),
                         HalfScalpConfig().stop_fraction)

    def test_the_minimum_stop_in_atrs_matches_python(self):
        self.assertEqual(float(self._const_value("MIN_STOP_ATR")),
                         HalfScalpConfig().min_stop_atr)

    def test_the_cost_gate_matches_python(self):
        cfg = HalfScalpConfig()
        self.assertEqual(float(self._const_value("MIN_EDGE_MULTIPLE")),
                         cfg.min_edge_multiple)
        self.assertEqual(float(self._const_value("SLIPPAGE_FRACTION")),
                         cfg.slippage_fraction)

    def test_the_round_trip_is_one_spread_plus_slippage_not_two(self):
        """A long buys at the ask and sells at the bid, so the bid-ask
        difference is paid once across the pair. Charging it twice would
        refuse trades the measured version took."""
        self.assertIn("spread * (1.0 + SLIPPAGE_FRACTION)", self.raw)

    def test_the_hold_and_cooldown_match_python(self):
        cfg = HalfScalpConfig()
        self.assertEqual(int(self._input_default("InpMaxHoldMinutes")),
                         cfg.max_hold_minutes)
        self.assertEqual(int(self._input_default("InpCooldownMinutes")),
                         cfg.cooldown_minutes)

    def test_it_defaults_to_the_variant_that_measured_positive(self):
        """The literal specification -- momentum, target 1.0 -- lost on 85 of
        85 simulated days. Defaulting to it would ship the losing version."""
        self.assertEqual(self._input_default("InpSignal"), "SIGNAL_REVERSION")
        self.assertEqual(float(self._input_default("InpTargetMultiple")), 2.0)

    def test_the_trigger_matches_python(self):
        self.assertEqual(float(self._input_default("InpTriggerAtr")),
                         HalfScalpConfig().trigger_atr)
        self.assertEqual(float(self._input_default("InpClosePositionMin")),
                         HalfScalpConfig().close_position_min)

    def test_every_python_default_has_the_same_value_in_the_ea(self):
        """The guard that keeps `metals halfscalp` describing what runs.

        A33 was two code paths that were supposed to be one: the backtest
        filtered at 0.60 and the EA filtered at nothing, so the published
        numbers described a strategy nobody was trading. This table is the
        version of that mistake this EA could make, so it is checked as a
        whole rather than one field at a time.
        """
        cfg = HalfScalpConfig()
        pairs = {
            "InpTriggerAtr": cfg.trigger_atr,
            "InpClosePositionMin": cfg.close_position_min,
            "InpTargetMultiple": cfg.target_multiple,
            "InpTakeFraction": cfg.take_fraction,
            "InpStopFraction": cfg.stop_fraction,
            "InpMaxHoldMinutes": float(cfg.max_hold_minutes),
            "InpCooldownMinutes": float(cfg.cooldown_minutes),
        }
        for name, expected in pairs.items():
            with self.subTest(setting=name):
                self.assertEqual(
                    float(self._input_default(name)), expected,
                    f"{name} differs from HalfScalpConfig. Every figure "
                    f"published about this strategy came from the Python; a "
                    f"divergence makes them describe something that is not "
                    f"running.")
        self.assertEqual(self._input_default("InpSignal"),
                         "SIGNAL_" + cfg.signal.upper())
        self.assertEqual(self._input_default("InpSessionFilter"),
                         "true" if cfg.session_filter else "false")

    def test_the_session_filter_is_on_by_default(self):
        self.assertEqual(self._input_default("InpSessionFilter"), "true")
        self.assertTrue(HalfScalpConfig().session_filter)


class TheRiskLimitsAreInCodeNotInputs(unittest.TestCase):
    """CLAUDE.md: risk limits live in code so changing one needs a commit."""

    @classmethod
    def setUpClass(cls):
        with open(EA_PATH, encoding="utf-8") as fh:
            cls.raw = fh.read()

    def test_the_limits_are_constants(self):
        for name in ("RISK_PER_TRADE_PCT", "DAILY_LOSS_LIMIT_PCT",
                     "MAX_TRADES_PER_DAY", "MIN_STOP_ATR",
                     "MIN_EDGE_MULTIPLE"):
            with self.subTest(limit=name):
                self.assertRegex(self.raw, rf"const\s+\w+\s+{name}\s*=")
                self.assertNotRegex(self.raw, rf"input\s+\w+\s+{name}\s*=")

    def test_risk_per_trade_is_far_below_the_four_trade_ea(self):
        """One percent per trade is sized for four trades a day. This EA
        takes around a hundred, and the same figure would put a fifth of the
        account through the market on an ordinary day."""
        m = re.search(r"const\s+double\s+RISK_PER_TRADE_PCT\s*=\s*([\d.]+)",
                      self.raw)
        self.assertLessEqual(float(m.group(1)), 0.5)

    def test_there_is_a_daily_loss_limit_and_a_trade_ceiling(self):
        self.assertIn("DayIsOver", self.raw)
        self.assertIn("day.halted", self.raw)


class TheGuardsThatStopItDoingHarm(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(EA_PATH, encoding="utf-8") as fh:
            cls.raw = fh.read()

    def test_it_refuses_a_non_gold_symbol(self):
        """A30 all over again: on EURUSD every figure here is nonsense
        computed without error, and this EA places orders."""
        self.assertIn('StringFind(_Symbol, "XAU")', self.raw)
        self.assertIn("INIT_PARAMETERS_INCORRECT", self.raw)

    def test_it_refuses_a_live_account_by_default(self):
        """What is known about this strategy is that its measured edge came
        from a feature of the market simulator. A default that permitted
        real money on that basis would be this project's worst line."""
        self.assertIn("ACCOUNT_TRADE_MODE_DEMO", self.raw)
        m = re.search(r"input\s+bool\s+InpAllowLiveAccount\s*=\s*([^;]+);",
                      self.raw)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1).strip(), "false")

    def test_the_stop_goes_on_with_the_order(self):
        """At a hundred trades a day, managing exits from OnTick means one
        disconnected minute leaves a position unprotected."""
        self.assertRegex(self.raw, r"trade\.Buy\([^)]*s\.stop,\s*s\.take")
        self.assertRegex(self.raw, r"trade\.Sell\([^)]*s\.stop,\s*s\.take")

    def test_an_adopted_position_without_a_stop_is_closed(self):
        self.assertIn("adopted a position with NO stop loss", self.raw)


class TheDuplicatedSessionCodeDoesNotDrift(unittest.TestCase):
    """The daylight-saving arithmetic exists twice, on purpose.

    The project ships one self-contained .mq5 per EA because the setup guide
    tells the user to copy a single file; an #include would silently break
    that. Duplication is a decision with a maintenance cost and this is
    where it gets paid -- the two copies are compared function by function.
    """

    SHARED = ("DaysInMonth", "LastSundayOfMonth", "NthSundayOfMonth",
              "EuSummerTime", "UsDaylightTime", "LondonOffsetHours",
              "NewYorkOffsetHours", "LocalHour", "MarketOpen", "InRollover",
              "ClassifySession", "QualityLabel", "SessionWord",
              "MinStopDistance", "ServerOffsetSeconds", "ServerToUtc")

    @classmethod
    def setUpClass(cls):
        with open(EA_PATH, encoding="utf-8") as fh:
            cls.new = fh.read()
        with open(OTHER_EA_PATH, encoding="utf-8") as fh:
            cls.old = fh.read()

    @staticmethod
    def _body(source: str, name: str) -> str | None:
        m = re.search(rf"^\w[\w ]*\s{re.escape(name)}\s*\([^)]*\)\s*\{{",
                      source, re.MULTILINE)
        if not m:
            return None
        depth, i = 1, m.end()
        while i < len(source) and depth:
            if source[i] == "{":
                depth += 1
            elif source[i] == "}":
                depth -= 1
            i += 1
        body = source[m.end():i - 1]
        body = re.sub(r"//[^\n]*", "", body)
        return " ".join(body.split())

    def test_the_shared_helpers_are_character_for_character_the_same(self):
        for name in self.SHARED:
            with self.subTest(function=name):
                new = self._body(self.new, name)
                old = self._body(self.old, name)
                self.assertIsNotNone(new, f"{name} missing from GoldHalfScalp")
                self.assertIsNotNone(old, f"{name} missing from the other EA")
                self.assertEqual(
                    new, old,
                    f"{name} has drifted between the two EAs. One of them is "
                    f"now computing sessions differently from every published "
                    f"number.")

    def test_the_friday_cutoff_is_the_same_hour(self):
        for label, source in (("GoldHalfScalp", self.new),
                              ("GoldScalpAssistant", self.old)):
            with self.subTest(ea=label):
                m = re.search(r"#define\s+FRIDAY_FLAT_HOUR_UTC\s+(\d+)", source)
                self.assertIsNotNone(m, "the cutoff is not a #define")
                self.assertEqual(m.group(1), "19")


if __name__ == "__main__":
    unittest.main()


class TheSetupGuideStaysTrue(unittest.TestCase):
    """The guide teaches a `wc -l` check, so the number has to be right.

    A stale line count teaches the user to read a correct download as a
    failed one. The same guard exists for the other EA and caught a stale
    number twice in one session.
    """

    GUIDE = os.path.join(MT5_DIR, "HALFSCALP-SETUP.md")

    @classmethod
    def setUpClass(cls):
        with open(cls.GUIDE, encoding="utf-8") as fh:
            cls.guide = fh.read()
        with open(EA_PATH, encoding="utf-8") as fh:
            cls.lines = len(fh.readlines())

    def test_the_stated_line_count_matches_the_file(self):
        self.assertIn(
            str(self.lines), self.guide,
            f"the guide does not mention {self.lines}. The EA now has "
            f"{self.lines} lines, so the `wc -l` check the guide teaches "
            f"would look like a failed download.")

    def test_it_warns_about_f5_versus_f7(self):
        """The mistake that cost an evening on the first EA."""
        self.assertIn("F7", self.guide)
        self.assertIn("F5", self.guide)

    def test_it_says_the_edge_is_a_simulator_result(self):
        """A guide that omits this sells the strategy."""
        self.assertIn("Simulator", self.guide)
        self.assertIn("A34", self.guide)

    def test_it_names_the_journal_file_the_ea_actually_writes(self):
        self.assertIn("GoldHalfScalp.csv", self.guide)

    def test_the_risk_limits_in_the_guide_match_the_code(self):
        """A table of limits that drifts from the code is worse than none."""
        with open(EA_PATH, encoding="utf-8") as fh:
            raw = fh.read()
        for const, shown in (("RISK_PER_TRADE_PCT", "0,25"),
                             ("DAILY_LOSS_LIMIT_PCT", "5"),
                             ("MAX_TRADES_PER_DAY", "200"),
                             ("MIN_EDGE_MULTIPLE", "1,5")):
            with self.subTest(limit=const):
                m = re.search(rf"const\s+\w+\s+{const}\s*=\s*([\d.]+)", raw)
                self.assertIsNotNone(m)
                self.assertIn(shown, self.guide,
                              f"{const} is {m.group(1)} in the code but the "
                              f"guide does not show {shown}")


class EveryNameResolvesToSomething(unittest.TestCase):
    """Stronger than "the helpers I remembered to list are defined".

    Every name called in the file must be either defined in the file or on
    the explicit list of MQL5 API calls below. A typo in a helper name would
    otherwise sail past every other check here and fail in MetaEditor, on
    the user's machine, at the point where the feedback loop is a screenshot
    over chat.

    The list doubles as documentation: it is the entire MQL5 surface this EA
    depends on. Adding to it should be a deliberate act, which is the point.
    """

    MQL5_API = {
        # Account, symbol and market data
        "AccountInfoDouble", "AccountInfoInteger", "SymbolInfoDouble",
        "SymbolInfoInteger", "CopyBuffer", "CopyRates", "iATR", "iTime",
        # Time
        "TimeGMT", "TimeTradeServer", "TimeToString", "TimeToStruct",
        "StructToTime",
        # Positions and history
        "PositionsTotal", "PositionGetTicket", "PositionGetDouble",
        "PositionGetInteger", "PositionGetString", "PositionSelectByTicket",
        "HistorySelect", "HistorySelectByPosition", "HistoryDealsTotal",
        "HistoryDealGetTicket", "HistoryDealGetDouble",
        "HistoryDealGetInteger", "HistoryDealGetString",
        # CTrade methods, called as trade.X(...)
        "Buy", "Sell", "PositionClose", "ResultRetcode",
        "ResultRetcodeDescription", "SetDeviationInPoints",
        "SetExpertMagicNumber", "SetMarginMode", "SetTypeFillingBySymbol",
        # Files
        "FileOpen", "FileClose", "FileSeek", "FileTell", "FileWriteString",
        # Strings and numbers
        "StringFormat", "StringFind", "StringReplace", "StringToLower",
        "DoubleToString", "NormalizeDouble", "MathAbs", "MathMax", "MathFloor",
        # Chart objects
        "ObjectCreate", "ObjectDelete", "ObjectFind", "ObjectSetInteger",
        "ObjectSetString",
        # Misc
        "Print", "PrintFormat", "Alert", "GetLastError", "ZeroMemory",
        "ArraySetAsSeries", "IndicatorRelease",
    }

    KEYWORDS = {"if", "for", "while", "switch", "return", "sizeof", "catch"}

    @classmethod
    def setUpClass(cls):
        with open(EA_PATH, encoding="utf-8") as fh:
            cls.code = _strip_comments_and_strings(fh.read())
        cls.defined = set(re.findall(
            r"^\s*(?:void|int|bool|double|string|datetime|ulong|Setup|"
            r"SessionQuality)\s+(\w+)\s*\(", cls.code, re.M))
        cls.called = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", cls.code))

    def test_the_lifecycle_functions_were_found_by_the_scan(self):
        """If the scan cannot see these, it is not seeing the file."""
        for fn in ("OnInit", "OnTick", "OnDeinit"):
            self.assertIn(fn, self.defined)

    def test_no_call_goes_to_a_name_that_does_not_exist(self):
        unknown = self.called - self.defined - self.MQL5_API - self.KEYWORDS
        self.assertEqual(
            unknown, set(),
            f"called but neither defined in the file nor a known MQL5 call: "
            f"{sorted(unknown)}. Either it is a typo, or it is a genuine API "
            f"call that belongs on the list above.")

    def test_no_helper_is_defined_and_then_never_used(self):
        """Dead code in a file nobody can compile is worse than dead code."""
        entry_points = {"OnInit", "OnTick", "OnDeinit"}
        unused = self.defined - self.called - entry_points
        self.assertEqual(unused, set(), f"defined but never called: "
                                        f"{sorted(unused)}")

    def test_the_api_list_has_no_stale_entries(self):
        """A list that outlives its calls stops describing the dependency."""
        stale = self.MQL5_API - self.called
        self.assertEqual(stale, set(), f"on the API list but never called: "
                                       f"{sorted(stale)}")
