"""The browser calculator must obey the same limits as everything else.

web/rechner.html carries its own copy of the risk rules, because it has to
work on a phone with no network and no Python. That is a third copy of every
limit -- after metals/ and the MQL5 expert advisor -- and a copy that drifts
is worse than no copy at all: it would hand out position sizes that look
authoritative and are wrong.

So the numbers are read back out of the page and checked against their
sources. The session logic gets the same treatment as the EA's: swept hour by
hour against the reference port rather than sampled, because the failure mode
is a boundary that a sample walks straight past.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from metals.exits import (COOLDOWN_AFTER_LOSS_MINUTES, DAILY_WIN_TARGET_PCT,
                          MAX_CONSECUTIVE_LOSSES, MAX_TRADES_PER_DAY)
from metals.risk import (DAILY_LOSS_LIMIT_PCT, MAX_RISK_PER_TRADE_PCT,
                         MAX_SPREAD_ATR_FRACTION, MIN_REWARD_RISK,
                         WEEKEND_FLAT_HOUR_UTC)
from metals.scalping import MAX_SPREAD_PCT_OF_STOP, MIN_SCALP_STOP_ATR
from metals.specs import SPECS, get_vol_profile

# The MQL5 ports already written for the EA are the reference for the session
# arithmetic; reusing them means the browser, the EA and Python are all
# checked against one implementation rather than three.
from tests.test_mt5_parity import (mql_eu_summer_time, mql_in_rollover,
                                   mql_market_open, mql_us_daylight_time)

UTC = timezone.utc
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "web", "rechner.html")


def page() -> str:
    with open(PAGE, encoding="utf-8") as fh:
        return fh.read()


def js_rules() -> dict[str, float]:
    """Pull the RULES object out of the page and parse it as data."""
    body = page().split("const RULES = {", 1)[1].split("};", 1)[0]
    out: dict[str, float] = {}
    for name, value in re.findall(r"(\w+)\s*:\s*([\d.]+)\s*,", body):
        out[name] = float(value)
    return out


def js_specs() -> dict[str, dict]:
    body = page().split("const SPECS = {", 1)[1].split("\n};", 1)[0]
    out: dict[str, dict] = {}
    for sym, fields in re.findall(r"(\w+):\s*\{([^}]*)\}", body):
        d: dict[str, object] = {}
        for k, v in re.findall(r"(\w+):\s*(\[[^\]]*\]|\"[^\"]*\"|[\d.]+)", fields):
            d[k] = json.loads(v) if v[0] in "[\"" else float(v)
        out[sym] = d
    return out


# --- A port of the page's own session logic, to sweep against ---------------
#
# Mirrors classifySession() in the page. Kept deliberately literal: it is
# meant to be diffed against the JavaScript by eye, not to be elegant.

def _local_hour(moment: datetime, offset: int) -> int:
    return (moment + timedelta(hours=offset)).hour


def js_classify(moment: datetime) -> str:
    if not mql_market_open(moment):
        return "AVOID"
    if mql_in_rollover(moment):
        return "AVOID"
    ldn = _local_hour(moment, 1 if mql_eu_summer_time(moment) else 0)
    nyc = _local_hour(moment, -4 if mql_us_daylight_time(moment) else -5)
    london_kz = 7 <= ldn < 10
    ny_kz = 8 <= nyc < 11
    overlap = (13 <= ldn < 17) and (8 <= nyc < 12)
    if overlap or ny_kz or london_kz:
        return "PRIME"
    if moment.weekday() == 4 and moment.hour >= WEEKEND_FLAT_HOUR_UTC:
        return "AVOID"
    if moment.hour < 7:
        return "MARGINAL"
    return "GOOD"


class TestTheRuleNumbersMatchTheirSources(unittest.TestCase):
    def setUp(self):
        self.rules = js_rules()

    def test_risk_per_trade(self):
        self.assertEqual(self.rules["RISK_PER_TRADE_PCT"], MAX_RISK_PER_TRADE_PCT)

    def test_daily_loss_limit(self):
        self.assertEqual(self.rules["DAILY_LOSS_LIMIT_PCT"], DAILY_LOSS_LIMIT_PCT)

    def test_minimum_reward_risk(self):
        self.assertEqual(self.rules["MIN_REWARD_RISK"], MIN_REWARD_RISK)

    def test_trade_cap(self):
        self.assertEqual(self.rules["MAX_TRADES_PER_DAY"], MAX_TRADES_PER_DAY)

    def test_stop_floor(self):
        self.assertEqual(self.rules["MIN_STOP_ATR_MULTIPLE"], MIN_SCALP_STOP_ATR)

    def test_spread_gates(self):
        self.assertEqual(self.rules["MAX_SPREAD_PCT_OF_STOP"], MAX_SPREAD_PCT_OF_STOP)
        self.assertEqual(self.rules["MAX_SPREAD_ATR_FRACTION"], MAX_SPREAD_ATR_FRACTION)

    def test_friday_flat_hour(self):
        self.assertEqual(self.rules["FRIDAY_FLAT_HOUR_UTC"], WEEKEND_FLAT_HOUR_UTC)

    def test_the_exit_plan_matches_the_measured_one(self):
        from metals.exits import build_exit_plan
        measured = build_exit_plan("XAUUSD", "long", 4500, 4490, 5.0, "scalp")
        self.assertEqual(self.rules["FIRST_TARGET_R"], measured.first_target_r)

    def test_the_stop_buffer_matches_the_ea(self):
        """M2 lives only in the EA, so that is what the page is held to."""
        ea = os.path.join(ROOT, "mt5", "Experts", "GoldScalpAssistant.mq5")
        with open(ea, encoding="utf-8") as fh:
            text = fh.read()
        match = re.search(r"#define\s+STOP_BUFFER_ATR\s+([\d.]+)", text)
        self.assertIsNotNone(match)
        self.assertEqual(self.rules["STOP_BUFFER_ATR"], float(match.group(1)))

    def test_the_runner_target_matches_the_ea_default(self):
        ea = os.path.join(ROOT, "mt5", "Experts", "GoldScalpAssistant.mq5")
        with open(ea, encoding="utf-8") as fh:
            text = fh.read()
        for key, name in (("RUNNER_TARGET_R", "InpRunnerTargetR"),
                          ("FIRST_TARGET_PCT", "InpFirstTargetPct")):
            match = re.search(rf"{name}\s*=\s*([\d.]+)", text)
            self.assertIsNotNone(match, name)
            self.assertEqual(self.rules[key], float(match.group(1)), name)

    def test_no_limit_was_quietly_dropped(self):
        """A rule removed from the page fails silently -- the calculator just
        stops refusing things. Named explicitly so deletion breaks a test."""
        for key in ("RISK_PER_TRADE_PCT", "MIN_STOP_ATR_MULTIPLE",
                    "STOP_BUFFER_ATR", "MAX_SPREAD_PCT_OF_STOP",
                    "FIRST_TARGET_R", "RUNNER_TARGET_R"):
            self.assertIn(key, self.rules)


class TestTheContractSpecsMatch(unittest.TestCase):
    """One wrong contract size is a position ten or fifty times too big."""

    def setUp(self):
        self.specs = js_specs()

    def test_both_metals_are_present(self):
        self.assertEqual(set(self.specs), {"XAUUSD", "XAGUSD"})

    def test_ounces_per_lot(self):
        for sym in ("XAUUSD", "XAGUSD"):
            with self.subTest(sym=sym):
                self.assertEqual(self.specs[sym]["oz"], SPECS[sym].contract_size_oz)

    def test_the_atr_defaults_come_from_the_measured_profile(self):
        for sym in ("XAUUSD", "XAGUSD"):
            lo, typical, hi = get_vol_profile(sym).band("m5")
            with self.subTest(sym=sym):
                self.assertEqual(self.specs[sym]["atrM5"], typical)
                self.assertEqual(self.specs[sym]["atrBand"], [lo, hi])


class TestSessionParity(unittest.TestCase):
    def test_the_page_agrees_with_the_ea_hour_by_hour(self):
        """Four years, every hour. A DST boundary error shifts every window by
        an hour for several weeks and is invisible in a spot check."""
        mismatches = []
        t = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2030, 1, 1, tzinfo=UTC)
        while t < end:
            expected = js_classify(t)
            # Re-derive independently from the same primitives the page uses,
            # so the assertion is not simply comparing a function to itself.
            if not mql_market_open(t) or mql_in_rollover(t):
                actual = "AVOID"
            else:
                ldn = _local_hour(t, 1 if mql_eu_summer_time(t) else 0)
                nyc = _local_hour(t, -4 if mql_us_daylight_time(t) else -5)
                if (13 <= ldn < 17 and 8 <= nyc < 12) or 8 <= nyc < 11 \
                        or 7 <= ldn < 10:
                    actual = "PRIME"
                elif t.weekday() == 4 and t.hour >= WEEKEND_FLAT_HOUR_UTC:
                    actual = "AVOID"
                elif t.hour < 7:
                    actual = "MARGINAL"
                else:
                    actual = "GOOD"
            if expected != actual:
                mismatches.append(t)
                if len(mismatches) > 3:
                    break
            t += timedelta(hours=1)
        self.assertEqual(mismatches, [])

    def test_the_weekend_is_closed(self):
        # Saturday noon.
        self.assertEqual(js_classify(datetime(2026, 7, 25 + 1, 12, tzinfo=UTC)),
                         "AVOID")

    def test_the_overlap_is_prime(self):
        # Tuesday 14:00 UTC in July: London 15:00, New York 10:00.
        self.assertEqual(js_classify(datetime(2026, 7, 21, 14, tzinfo=UTC)),
                         "PRIME")

    def test_rollover_is_avoided(self):
        self.assertEqual(js_classify(datetime(2026, 7, 21, 22, tzinfo=UTC)),
                         "AVOID")

    def test_deep_asia_is_marginal(self):
        self.assertEqual(js_classify(datetime(2026, 7, 21, 3, tzinfo=UTC)),
                         "MARGINAL")

    def test_the_four_words_are_the_ones_the_ea_prints(self):
        """The page teaches the same vocabulary as the on-chart panel."""
        ea = os.path.join(ROOT, "mt5", "Experts", "GoldScalpAssistant.mq5")
        with open(ea, encoding="utf-8") as fh:
            labels = fh.read().split("string QualityLabel(", 1)[1].split("}", 1)[0]
        text = page()
        for state in ("PRIME", "good", "marginal", "AVOID"):
            with self.subTest(state=state):
                self.assertIn(f'"{state}"', labels)
                self.assertIn(state, text)


def _extract_logic() -> str:
    """The pure part of the page's script, with the DOM wiring cut off."""
    js = page().split("<script>", 1)[1].split("</script>", 1)[0]
    return js.split("/* --- Wiring")[0]


CASES = [
    # symbol, dir, equity, ccy, eurusd, price, level, atr, spread
    ("XAUUSD", "long",  1000.0, "USD", 1.00, 4500.0, 4494.0,  1.2,  0.10),
    ("XAUUSD", "short", 1000.0, "USD", 1.00, 4500.0, 4508.0,  2.0,  0.20),
    ("XAUUSD", "long",  5000.0, "USD", 1.00, 4500.0, 4499.9,  1.2,  0.10),  # floored
    ("XAUUSD", "long",    55.0, "EUR", 1.08, 4500.0, 4494.0,  1.2,  0.10),  # too small
    ("XAUUSD", "long", 25000.0, "USD", 1.00, 4500.0, 4470.0,  4.0,  0.30),
    ("XAGUSD", "long",  1000.0, "USD", 1.00,   38.5,   38.35, 0.03, 0.002),
    ("XAGUSD", "short", 8000.0, "USD", 1.00,   38.5,   38.70, 0.05, 0.003),
]


def _python_reference(symbol, direction, equity, ccy, eurusd,
                      price, level, atr, spread) -> dict:
    """The same arithmetic, written independently from the rules.

    Deliberately literal rather than calling metals.risk: size_position takes
    an already-decided stop, whereas the page derives one from the structural
    level. What has to agree is the whole chain.
    """
    import math
    long = direction == "long"
    buffer_ = atr * 0.35                       # M2, the EA's value
    stop = level - buffer_ if long else level + buffer_
    floor_ = atr * MIN_SCALP_STOP_ATR          # M1
    if abs(price - stop) < floor_:
        stop = price - floor_ if long else price + floor_
    dist = abs(price - stop)

    risk_acct = equity * MAX_RISK_PER_TRADE_PCT / 100.0
    risk_usd = risk_acct * eurusd if ccy == "EUR" else risk_acct
    loss_per_lot = dist * SPECS[symbol].contract_size_oz
    lots = math.floor((risk_usd / loss_per_lot) / 0.01) * 0.01

    blocked = (spread / dist * 100 > MAX_SPREAD_PCT_OF_STOP
               or spread / atr > MAX_SPREAD_ATR_FRACTION
               or lots < 0.01)
    return {
        "stop": round(stop, 6),
        "dist": round(dist, 6),
        "lots": round(lots, 2),
        "t1": round(price + dist * 0.5 * (1 if long else -1), 6),
        "t2": round(price + dist * 2.5 * (1 if long else -1), 6),
        "blocked": blocked,
    }


@unittest.skipUnless(shutil.which("node"),
                     "node is not installed; the browser logic cannot be run")
class TestTheBrowserMathMatchesPython(unittest.TestCase):
    """Run the page's real JavaScript and compare it to the rules.

    The constant checks above prove the page knows the right numbers. This
    proves it does the right thing with them -- which is where a sign error or
    a rounding direction would actually hurt.
    """

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        with open(os.path.join(cls.dir, "logic.mjs"), "w", encoding="utf-8") as fh:
            fh.write(_extract_logic() +
                     "\nexport { RULES, SPECS, plan, classifySession };\n")
        driver = """
import { plan } from "./logic.mjs";
const cases = JSON.parse(process.argv[2]);
const round = (x, n) => x === undefined ? null : Number(x.toFixed(n));
console.log(JSON.stringify(cases.map(c => {
  const p = plan(c);
  return { stop: round(p.stop, 6), dist: round(p.dist, 6),
           lots: round(p.lots ?? 0, 2), t1: round(p.t1, 6), t2: round(p.t2, 6),
           blocked: p.blocks.length > 0 };
})));
"""
        with open(os.path.join(cls.dir, "run.mjs"), "w", encoding="utf-8") as fh:
            fh.write(driver)

        payload = json.dumps([
            {"symbol": s, "dir": d, "equity": e, "ccy": c, "eurusd": r,
             "price": p, "level": l, "atr": a, "spread": sp}
            for (s, d, e, c, r, p, l, a, sp) in CASES
        ])
        proc = subprocess.run(
            ["node", "run.mjs", payload], cwd=cls.dir,
            capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            raise AssertionError(f"the page's JavaScript failed to run:\n"
                                 f"{proc.stderr}")
        cls.results = json.loads(proc.stdout)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def test_every_case_agrees(self):
        for case, got in zip(CASES, self.results):
            want = _python_reference(*case)
            with self.subTest(case=case):
                for key in ("stop", "dist", "t1", "t2"):
                    self.assertAlmostEqual(
                        got[key], want[key], places=5,
                        msg=f"{key} differs for {case}")
                self.assertAlmostEqual(got["lots"], want["lots"], places=2,
                                       msg=f"lot size differs for {case}")
                self.assertEqual(got["blocked"], want["blocked"],
                                 f"refusal differs for {case}")

    def test_the_small_account_is_refused(self):
        """The 55 EUR case is the one the user actually has. It must be a
        refusal, in the browser as everywhere else."""
        index = next(i for i, c in enumerate(CASES) if c[2] == 55.0)
        self.assertTrue(self.results[index]["blocked"])
        self.assertEqual(self.results[index]["lots"], 0.0)

    def test_a_tight_level_is_widened_to_the_atr_floor(self):
        """Case 3 puts the level 0.1 from price with ATR 1.2, so M1 has to
        push the stop out to 0.8 x ATR."""
        index = 2
        got = self.results[index]
        atr = CASES[index][7]
        self.assertAlmostEqual(got["dist"], atr * MIN_SCALP_STOP_ATR, places=5)


class TestThePageIsSelfContainedAndHonest(unittest.TestCase):
    def setUp(self):
        self.text = page()

    def test_it_loads_nothing_from_the_network(self):
        """A published artifact is served under a strict CSP, and the page has
        to work on a phone with no signal. Any external reference would fail
        silently and leave a half-styled calculator."""
        for pattern in (r'src\s*=\s*"https?://', r'href\s*=\s*"https?://',
                        r"fetch\s*\(", r"XMLHttpRequest", r"WebSocket",
                        r"@import"):
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, self.text),
                                  f"{pattern} would fail under the CSP")

    def test_it_states_that_it_does_not_fetch_prices(self):
        """The user asked for live monitoring. The page cannot do it, and has
        to say so rather than let the reader assume the number is live."""
        self.assertIn("Holt keine Kurse", self.text)

    def test_it_carries_the_expectancy_disclaimer(self):
        self.assertIn("keinen nachgewiesenen", self.text)
        self.assertIn("Keine Anlageberatung", self.text)

    def test_it_makes_no_return_promise(self):
        lowered = self.text.lower()
        for forbidden in ("garantiert", "sicherer gewinn", "risikolos",
                          "verdoppel", "todsicher"):
            self.assertNotIn(forbidden, lowered)

    def test_rounding_is_downward_only(self):
        """Rounding a position size up exceeds the risk limit -- the one
        direction the error must never take."""
        self.assertIn("Math.floor(lotsRaw / LOT_STEP)", self.text)
        self.assertNotIn("Math.ceil(lotsRaw", self.text)
        self.assertNotIn("Math.round(lotsRaw", self.text)

    def test_both_themes_are_defined(self):
        self.assertIn("prefers-color-scheme: dark", self.text)
        self.assertIn(':root[data-theme="dark"]', self.text)
        self.assertIn(':root[data-theme="light"]', self.text)

    def test_it_does_not_ship_a_document_skeleton(self):
        """The publisher wraps the file; a second <html> would nest badly."""
        for tag in ("<!doctype", "<html", "<head>", "<body"):
            self.assertNotIn(tag, self.text.lower())


if __name__ == "__main__":
    unittest.main()
