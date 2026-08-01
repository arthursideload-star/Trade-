"""Contract specs and risk rules.

These are the tests that matter most: a bug here sizes a real position wrong.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from metals.risk import (AccountState, MAX_CORRELATED_RISK_PCT,
                         MIN_REWARD_RISK, RULES, check_daily_state,
                         size_position, structural_stop)
from metals.sessions import Quality, SessionState, Session
from metals.specs import (PIP_CONVENTIONS_USD_OZ, XAGUSD, XAUUSD, get_spec,
                          get_vol_profile, round_levels)

UTC = timezone.utc
# A Tuesday inside the London/NY overlap: the only clean window for sizing tests.
GOOD_MOMENT = datetime(2026, 7, 21, 14, 0, tzinfo=UTC)


def _good_session() -> SessionState:
    return SessionState(GOOD_MOMENT, Session.OVERLAP, Quality.PRIME,
                        ["overlap"], ["test window"])


class TestSpecs(unittest.TestCase):
    def test_gold_lot_arithmetic(self):
        # 1 lot of gold is 100 oz, so a 1 USD/oz move is 100 USD.
        self.assertEqual(XAUUSD.contract_size_oz, 100.0)
        self.assertEqual(XAUUSD.value_per_dollar_move, 100.0)
        self.assertAlmostEqual(XAUUSD.value_of_move(12.0, 0.5), 600.0)

    def test_silver_lot_arithmetic(self):
        self.assertEqual(XAGUSD.contract_size_oz, 5000.0)
        # A 0.50 USD/oz move on half a lot of silver is 1250 USD.
        self.assertAlmostEqual(XAGUSD.value_of_move(0.50, 0.5), 1250.0)

    def test_alias_resolution(self):
        for alias in ("XAU/USD", "gold", "XAUUSD", "xau"):
            self.assertEqual(get_spec(alias).symbol, "XAUUSD")
        for alias in ("XAG/USD", "silver", "SI=F"):
            self.assertIn(get_spec(alias).symbol, ("XAGUSD", "SI"))

    def test_unknown_symbol_raises(self):
        with self.assertRaises(KeyError):
            get_spec("XPTUSD")

    def test_round_grids_differ_by_metal(self):
        self.assertEqual(round_levels("XAUUSD")[0], 100.0)
        self.assertEqual(round_levels("XAGUSD")[0], 5.0)

    def test_volatility_plausibility_band(self):
        vol = get_vol_profile("XAUUSD")
        self.assertTrue(vol.is_plausible("h1", 4.5))
        self.assertFalse(vol.is_plausible("h1", 0.01))
        self.assertFalse(vol.is_plausible("h1", 500.0))

    def test_price_rounding_matches_quote_precision(self):
        self.assertEqual(XAUUSD.round_price(4500.123456), 4500.12)
        self.assertEqual(XAGUSD.round_price(52.987654), 52.988)


class TestPositionSizing(unittest.TestCase):
    def setUp(self):
        self.account = AccountState(equity=10_000.0)

    def test_gold_size_matches_hand_calculation(self):
        # 1% of 10000 = 100 USD risk. Stop is 10 USD/oz.
        # Risk per lot = 10 * 100 oz = 1000 USD. So 0.10 lots.
        plan = size_position(
            "XAUUSD", "long", entry=4500.0, stop=4490.0, target=4530.0,
            account=self.account, atr_value=5.0,
            moment=GOOD_MOMENT, session_state=_good_session(),
        )
        self.assertAlmostEqual(plan.lots, 0.10, places=4)
        self.assertAlmostEqual(plan.risk_usd, 100.0, places=2)
        self.assertAlmostEqual(plan.risk_pct, 1.0, places=4)
        self.assertAlmostEqual(plan.reward_risk, 3.0, places=4)
        self.assertTrue(plan.approved, plan.blocks)

    def test_silver_size_matches_hand_calculation(self):
        # Stop 0.40 USD/oz on silver: risk per lot = 0.40 * 5000 = 2000 USD.
        # 100 USD risk -> 0.05 lots.
        plan = size_position(
            "XAGUSD", "long", entry=52.00, stop=51.60, target=53.00,
            account=self.account, atr_value=0.20,
            moment=GOOD_MOMENT, session_state=_good_session(),
        )
        self.assertAlmostEqual(plan.lots, 0.05, places=4)
        self.assertAlmostEqual(plan.risk_usd, 100.0, places=2)

    def test_r1_caps_requested_risk(self):
        plan = size_position(
            "XAUUSD", "long", 4500.0, 4490.0, 4530.0, self.account, 5.0,
            risk_pct=5.0, moment=GOOD_MOMENT, session_state=_good_session(),
        )
        self.assertLessEqual(plan.risk_pct, 1.0001)
        self.assertTrue(any("R1" in w for w in plan.warnings))

    def test_r2_blocks_after_daily_loss(self):
        account = AccountState(equity=9_700.0, realised_pnl_today=-300.0,
                               starting_equity_today=10_000.0)
        self.assertTrue(account.daily_stop_hit)
        plan = size_position(
            "XAUUSD", "long", 4500.0, 4490.0, 4530.0, account, 5.0,
            moment=GOOD_MOMENT, session_state=_good_session(),
        )
        self.assertFalse(plan.approved)
        self.assertTrue(any("R2" in b for b in plan.blocks))

    def test_r3_blocks_poor_reward_risk(self):
        plan = size_position(
            "XAUUSD", "long", 4500.0, 4490.0, 4505.0, self.account, 5.0,
            moment=GOOD_MOMENT, session_state=_good_session(),
        )
        self.assertFalse(plan.approved)
        self.assertTrue(any("R3" in b for b in plan.blocks))
        self.assertLess(plan.reward_risk, MIN_REWARD_RISK)

    def test_m1_blocks_stop_inside_one_atr(self):
        # 2 USD/oz stop against a 6 USD/oz ATR is 0.33x -- noise, not risk.
        plan = size_position(
            "XAUUSD", "long", 4500.0, 4498.0, 4520.0, self.account, 6.0,
            moment=GOOD_MOMENT, session_state=_good_session(),
        )
        self.assertFalse(plan.approved)
        self.assertTrue(any("M1" in b for b in plan.blocks))

    def test_m3_blocks_wide_spread(self):
        plan = size_position(
            "XAUUSD", "long", 4500.0, 4490.0, 4530.0, self.account, 5.0,
            spread_usd_oz=2.0,  # 40% of ATR
            moment=GOOD_MOMENT, session_state=_good_session(),
        )
        self.assertFalse(plan.approved)
        self.assertTrue(any("M3" in b for b in plan.blocks))

    def test_m4_blocks_when_correlated_budget_is_spent(self):
        account = AccountState(equity=10_000.0, open_risk_pct=1.2,
                               open_positions=1)
        plan = size_position(
            "XAGUSD", "long", 52.0, 51.6, 53.0, account, 0.20,
            moment=GOOD_MOMENT, session_state=_good_session(),
        )
        self.assertFalse(plan.approved)
        self.assertTrue(any("M4" in b for b in plan.blocks))
        self.assertGreater(account.open_risk_pct + 1.0, MAX_CORRELATED_RISK_PCT)

    def test_m5_blocks_friday_evening(self):
        friday_late = datetime(2026, 7, 24, 19, 30, tzinfo=UTC)
        plan = size_position(
            "XAUUSD", "long", 4500.0, 4490.0, 4530.0, self.account, 5.0,
            moment=friday_late, session_state=_good_session(),
        )
        self.assertFalse(plan.approved)
        self.assertTrue(any("M5" in b for b in plan.blocks))

    def test_r4_blocks_inside_news_window(self):
        plan = size_position(
            "XAUUSD", "long", 4500.0, 4490.0, 4530.0, self.account, 5.0,
            news_minutes_away=12.0,
            moment=GOOD_MOMENT, session_state=_good_session(),
        )
        self.assertFalse(plan.approved)
        self.assertTrue(any("R4" in b for b in plan.blocks))

    def test_r5_blocks_rollover(self):
        rollover = SessionState(GOOD_MOMENT, Session.ROLLOVER, Quality.AVOID,
                                ["rollover"], ["daily rollover"])
        plan = size_position(
            "XAUUSD", "long", 4500.0, 4490.0, 4530.0, self.account, 5.0,
            moment=GOOD_MOMENT, session_state=rollover,
        )
        self.assertFalse(plan.approved)
        self.assertTrue(any("R5" in b for b in plan.blocks))

    def test_short_geometry_is_validated(self):
        # Stop below entry on a short is nonsense and must be caught.
        plan = size_position(
            "XAUUSD", "short", 4500.0, 4490.0, 4470.0, self.account, 5.0,
            moment=GOOD_MOMENT, session_state=_good_session(),
        )
        self.assertFalse(plan.approved)
        self.assertTrue(any("geometry" in b for b in plan.blocks))

    def test_valid_short_is_approved(self):
        plan = size_position(
            "XAUUSD", "short", 4500.0, 4510.0, 4470.0, self.account, 5.0,
            moment=GOOD_MOMENT, session_state=_good_session(),
        )
        self.assertTrue(plan.approved, plan.blocks)
        self.assertAlmostEqual(plan.lots, 0.10, places=4)

    def test_tiny_account_is_blocked_not_silently_rounded(self):
        """The failure a small account actually hits.

        A 40 USD/oz stop on gold needs 4000 USD of risk per lot. On a 200 USD
        account at 1%, that is 0.0005 lots. The correct answer is to refuse,
        not to round up to the 0.01 minimum -- which would be 20x the intended
        risk.
        """
        small = AccountState(equity=200.0)
        plan = size_position(
            "XAUUSD", "long", 4500.0, 4460.0, 4620.0, small, 20.0,
            moment=GOOD_MOMENT, session_state=_good_session(),
        )
        self.assertFalse(plan.approved)
        self.assertEqual(plan.lots, 0.0)
        self.assertTrue(any("minimum" in b for b in plan.blocks))

    def test_zero_stop_distance_is_refused(self):
        plan = size_position(
            "XAUUSD", "long", 4500.0, 4500.0, 4530.0, self.account, 5.0,
            moment=GOOD_MOMENT, session_state=_good_session(),
        )
        self.assertFalse(plan.approved)
        self.assertTrue(any("R7" in b or "zero" in b for b in plan.blocks))

    def test_implausible_atr_is_flagged_before_sizing(self):
        """A corrupt feed produces a plausible-looking lot number.

        Every lot figure is derived from ATR, so an ATR that fits no timeframe
        for the instrument has to surface as a warning rather than silently
        setting the size.
        """
        plan = size_position(
            "XAUUSD", "long", 4500.0, 4100.0, 5400.0, self.account,
            atr_value=380.0,   # far outside any gold band
            moment=GOOD_MOMENT, session_state=_good_session(),
        )
        self.assertTrue(any("outside the" in w and "% band" in w
                            for w in plan.warnings), plan.warnings)

    def test_plausible_atr_produces_no_such_warning(self):
        plan = size_position(
            "XAUUSD", "long", 4500.0, 4490.0, 4530.0, self.account,
            atr_value=5.0,
            moment=GOOD_MOMENT, session_state=_good_session(),
        )
        self.assertFalse(any("outside the" in w and "% band" in w
                             for w in plan.warnings))

    def test_silver_atr_is_judged_against_silver_bands(self):
        """5.0 USD/oz is a normal gold H1 ATR and absurd for silver."""
        plan = size_position(
            "XAGUSD", "long", 52.0, 46.0, 70.0, self.account,
            atr_value=5.0,
            moment=GOOD_MOMENT, session_state=_good_session(),
        )
        self.assertTrue(any("outside the" in w and "% band" in w
                            for w in plan.warnings), plan.warnings)

    def test_lots_always_round_down(self):
        """Rounding up would exceed the risk limit, which is the one direction
        that must never happen."""
        plan = size_position(
            "XAUUSD", "long", 4500.0, 4487.3, 4540.0, self.account, 6.0,
            moment=GOOD_MOMENT, session_state=_good_session(),
        )
        self.assertLessEqual(plan.risk_usd, 100.0 + 1e-9)


class TestStructuralStop(unittest.TestCase):
    def test_long_stop_sits_below_the_level(self):
        stop = structural_stop("XAUUSD", "long", 4490.0, atr_value=6.0)
        self.assertLess(stop, 4490.0)
        self.assertAlmostEqual(stop, 4488.5, places=2)

    def test_short_stop_sits_above_the_level(self):
        stop = structural_stop("XAUUSD", "short", 4510.0, atr_value=6.0)
        self.assertGreater(stop, 4510.0)

    def test_silver_stop_uses_silver_precision(self):
        stop = structural_stop("XAGUSD", "long", 52.000, atr_value=0.200)
        self.assertAlmostEqual(stop, 51.950, places=3)


class TestDailyState(unittest.TestCase):
    def test_warns_before_the_limit(self):
        account = AccountState(equity=9_780.0, realised_pnl_today=-220.0,
                               starting_equity_today=10_000.0)
        notes = check_daily_state(account)
        self.assertTrue(any("approaching" in n for n in notes))

    def test_reports_the_limit_in_force(self):
        account = AccountState(equity=9_650.0, realised_pnl_today=-350.0,
                               starting_equity_today=10_000.0)
        notes = check_daily_state(account)
        self.assertTrue(any("R2 in force" in n for n in notes))


class TestRuleDocumentation(unittest.TestCase):
    def test_every_rule_has_text(self):
        for key in ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8",
                    "M1", "M2", "M3", "M4", "M5", "M6"):
            self.assertIn(key, RULES)
            self.assertGreater(len(RULES[key]), 20)


if __name__ == "__main__":
    unittest.main()


class TestWhatTheSpreadDoesAtTheWrongMoment(unittest.TestCase):
    """The arithmetic behind R4 and R5, which the project stated as maxims.

    A gold scalp risks about 3 USD/oz on its stop. The spread it pays on
    entry is roughly 0.20 in the London/NY overlap -- and roughly 5 at the
    daily rollover, and roughly 8-15 in the seconds around a high-impact
    release, as liquidity providers pull their quotes.

    So at rollover the spread alone exceeds the entire stop, and around NFP
    it is three to five times it. There is no entry price that rescues that
    trade. "Do not trade the news" stops being caution and becomes
    subtraction.

    None of the backtests in this repository can produce this finding: the
    simulator charges one spread for the whole day. A rule the measurements
    are structurally unable to argue for still needs an argument, and this
    is it -- which is why the numbers live in the spec rather than in prose.

    Source kind: broker comparison and broker-education pages. Not academic,
    not a measurement of any account. Order-of-magnitude, and labelled so.
    """

    TYPICAL_SCALP_STOP_USD_OZ = 3.0

    def test_the_overlap_spread_is_a_small_share_of_the_stop(self):
        share = XAUUSD.typical_spread_usd_oz / self.TYPICAL_SCALP_STOP_USD_OZ
        self.assertLess(share, 0.15)

    def test_the_rollover_spread_exceeds_the_whole_stop(self):
        self.assertGreater(XAUUSD.thin_spread_usd_oz,
                           self.TYPICAL_SCALP_STOP_USD_OZ)

    def test_the_news_spread_is_a_multiple_of_the_whole_stop(self):
        self.assertGreater(XAUUSD.news_spread_usd_oz,
                           self.TYPICAL_SCALP_STOP_USD_OZ * 3)

    def test_the_widening_is_recorded_as_a_multiple_too(self):
        self.assertGreater(XAUUSD.news_spread_multiple, 20)

    def test_an_instrument_without_the_figure_reports_zero_not_one(self):
        """Silver has no news figure recorded. It must not read as 'no
        widening' -- that is the A20 confusion in miniature."""
        self.assertEqual(XAGUSD.news_spread_multiple, 0.0)

    def test_the_notes_no_longer_carry_one_broker_s_marketing(self):
        """CLAUDE.md: 'Marketingzahlen nicht als Fakten führen.' The note
        used to quote a named broker's own advertised averages as if they
        were part of the contract specification."""
        self.assertNotIn("PU Prime", XAUUSD.notes)
        self.assertIn("your own platform", XAUUSD.notes)

    def test_both_pip_conventions_are_recorded_by_quoting_precision(self):
        """The documented 10x sizing error. A broker quoting two decimals
        calls 0.10 a pip; one quoting three calls 0.01 a pip."""
        self.assertEqual(PIP_CONVENTIONS_USD_OZ[XAUUSD.price_decimals], 0.10)
        self.assertEqual(PIP_CONVENTIONS_USD_OZ[XAGUSD.price_decimals], 0.01)
        self.assertEqual(PIP_CONVENTIONS_USD_OZ[2] / PIP_CONVENTIONS_USD_OZ[3],
                         10.0)

    def test_the_notes_say_where_the_numbers_are_not_from(self):
        from metals.specs import NEWS_SPREAD_NOTE, ROLLOVER_SPREAD_NOTE, SPREAD_NOTE
        self.assertIn("not from your account", SPREAD_NOTE)
        self.assertIn("R4", NEWS_SPREAD_NOTE)
        self.assertIn("R5", ROLLOVER_SPREAD_NOTE)
