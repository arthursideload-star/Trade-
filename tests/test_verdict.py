"""The one command for the day a downloaded history arrives.

What is being tested here is not arithmetic -- the underlying measurements
have their own tests. It is the **decision**: that the command is willing to
say "do not install this", that it says so for the right reasons, and that it
does not quietly upgrade a result the sample cannot carry.

A verdict function that can only say yes is a marketing page with a progress
bar. Every branch that returns an encouraging answer has a matching test that
takes it away.
"""

from __future__ import annotations

import unittest

from metals import simulate
from metals.verdict import (Step, Verdict, _decide, render,
                            run_verdict)


def _series(bars=6_000, reversion=0.002, seed=4242):
    return simulate.generate(
        bars=bars, timeframe="5m", seed=seed,
        params=simulate.MarketParams(start_price=4_105.62,
                                     reversion=reversion))


class TestTheStepsRun(unittest.TestCase):
    def setUp(self):
        self.v = run_verdict(_series(), equity_eur=400.0)

    def test_every_step_is_present(self):
        for name in ("daten", "rueckkehr", "zufallspfad", "tagesspanne",
                     "scalping"):
            with self.subTest(name=name):
                self.assertIsNotNone(self.v.step(name))

    def test_every_step_carries_a_status_the_renderer_knows(self):
        for s in self.v.steps:
            with self.subTest(step=s.name):
                self.assertIn(s.status, ("ok", "warn", "fail", "info"))
                self.assertTrue(s.headline.strip())

    def test_a_recommendation_is_always_produced(self):
        self.assertTrue(self.v.recommendation)
        self.assertTrue(self.v.reasoning)

    def test_the_report_renders_without_placeholders(self):
        text = render(self.v)
        self.assertIn("URTEIL AUF ECHTEN DATEN", text)
        self.assertIn("EMPFEHLUNG", text)
        self.assertNotIn("{", text)

    def test_a_step_that_fails_does_not_take_the_run_down(self):
        """Step 5 resamples and re-runs a second engine. If that raises, the
        first four answers are still worth having."""
        from unittest import mock
        with mock.patch("metals.backtest.run", side_effect=RuntimeError("x")):
            v = run_verdict(_series(bars=3_000))
        step = v.step("scalping")
        self.assertIsNotNone(step)
        self.assertEqual(step.status, "warn")
        self.assertTrue(v.recommendation)


class TestItAnswersTheQuestionItWasBuiltFor(unittest.TestCase):
    """A27's question: is the mean reversion real or was it the generator?

    A28 decided which measure gets to answer it. The day-close statistic --
    the share of days finishing in the middle third of their own range --
    was the obvious cheap proxy and PC-SETUP.md told the reader to make an
    install decision on it. Measured against the generator it is **not
    monotone in the thing it claims to measure**:

        reversion   5m bars        1m bars
        0.0000      40.9%          36.4%
        0.0020      38.6%          47.7%
        0.0080      27.3%          61.4%

    Same generator, same days, opposite directions. So it is reported as
    context and the variance ratio decides, because that one is monotone at
    both timeframes and comes with a test statistic.
    """

    def test_the_variance_ratio_moves_the_right_way_with_reversion(self):
        """The property the whole verdict now rests on."""
        from metals.persistence import log_prices, variance_ratio
        weak = variance_ratio(log_prices(_series(reversion=0.0,
                                                 bars=12_000)), 8)
        strong = variance_ratio(log_prices(_series(reversion=0.008,
                                                   bars=12_000)), 8)
        self.assertLess(strong.ratio, weak.ratio,
                        "more reversion must lower the variance ratio")
        self.assertLess(strong.z, weak.z)

    def test_the_day_close_statistic_is_reported_but_decides_nothing(self):
        v = run_verdict(_series(bars=6_000))
        step = v.step("rueckkehr")
        self.assertEqual(step.status, "info")
        self.assertTrue(any("NICHT monoton" in d for d in step.detail))

    def test_the_step_still_shows_the_number(self):
        """Demoted, not deleted. It is a real observation about the file and
        worth seeing -- it just cannot carry a decision."""
        v = run_verdict(_series(bars=6_000))
        detail = " ".join(v.step("rueckkehr").detail)
        self.assertIn("mittleren Drittel", detail)
        self.assertIn("Handelstage", detail)


class TestTheDecisionIsAllowedToSayNo(unittest.TestCase):
    """Each branch, driven directly. Building the market conditions that
    trigger each one takes minutes; the decision logic takes microseconds and
    is the part that can be wrong in a way that costs money."""

    @staticmethod
    def _v(**statuses) -> Verdict:
        v = Verdict(steps=[Step(name, status, "x")
                           for name, status in statuses.items()])
        _decide(v)
        return v

    def test_movement_that_continues_plus_no_edge_means_do_not_install(self):
        """The premise contradicted: the strategy fades moves, and the test
        says moves continue."""
        v = Verdict(steps=[
            Step("rueckkehr", "info", "x"),
            Step("zufallspfad", "warn",
                 "Verworfen, aber in die FALSCHE Richtung: Bewegungen laufen "
                 "weiter. Diese Strategie setzt auf Rueckkehr"),
            Step("tagesspanne", "warn", "x"),
            Step("scalping", "warn", "x")])
        _decide(v)
        self.assertEqual(v.recommendation, "NICHT INSTALLIEREN")
        self.assertTrue(any("A27" in line for line in v.reasoning))

    def test_failing_to_reject_is_not_treated_as_a_refutation(self):
        """The error this branch was one edit away from encoding.

        "The variance ratio did not reject the random walk" and "gold does
        not revert" are different statements. An install tool that conflates
        them turns absence of evidence into evidence of absence -- which is
        the mistake this project has spent twenty-eight audit entries
        guarding against, and it would be the tool making it.
        """
        v = Verdict(steps=[
            Step("rueckkehr", "info", "x"),
            Step("zufallspfad", "warn",
                 "Kein Horizont verwirft den Zufallspfad. Das ist kein "
                 "Nachweis gegen die Strategie, aber auch keiner dafuer"),
            Step("tagesspanne", "warn", "x"),
            Step("scalping", "warn", "x")])
        _decide(v)
        self.assertEqual(v.recommendation, "NOCH NICHT INSTALLIEREN")

    def test_a_losing_strategy_means_do_not_install(self):
        v = self._v(rueckkehr="info", zufallspfad="ok", tagesspanne="fail",
                    scalping="fail")
        self.assertEqual(v.recommendation, "NICHT INSTALLIEREN")

    def test_a_measurable_edge_means_install_but_in_advisor_mode(self):
        v = self._v(rueckkehr="info", zufallspfad="ok", tagesspanne="ok",
                    scalping="ok")
        self.assertIn("INSTALLIEREN", v.recommendation)
        self.assertIn("Advisor", v.recommendation)

    def test_a_good_day_range_with_losing_scalps_says_so(self):
        """The confusion this project has hit repeatedly: the EA trades S1-S6
        by default, not the day-range strategy. An install recommendation
        that does not separate them is dangerous."""
        v = self._v(rueckkehr="info", zufallspfad="ok", tagesspanne="ok",
                    scalping="fail")
        self.assertIn("INSTALLIEREN", v.recommendation)
        self.assertTrue(any("S1-S6" in line for line in v.reasoning))

    def test_an_inconclusive_result_does_not_become_a_yes(self):
        v = self._v(rueckkehr="info", zufallspfad="warn", tagesspanne="warn",
                    scalping="warn")
        self.assertEqual(v.recommendation, "NOCH NICHT INSTALLIEREN")

    def test_an_inconclusive_result_suggests_the_entry_rule_not_the_exit(self):
        """Where the work belongs when nothing is established. Tuning exits
        on a sample that shows no edge is how A18's grid-edge winners
        happened."""
        v = self._v(rueckkehr="info", zufallspfad="warn", tagesspanne="warn",
                    scalping="warn")
        self.assertTrue(any("Einstiegsregel" in line for line in v.reasoning))

    def test_a_random_walk_finding_is_explained_rather_than_shrugged_off(self):
        v = Verdict(steps=[
            Step("rueckkehr", "warn", "x"),
            Step("zufallspfad", "warn",
                 "Kein Horizont verwirft den Zufallspfad. ..."),
            Step("tagesspanne", "warn", "x"),
            Step("scalping", "warn", "x")])
        _decide(v)
        self.assertTrue(any("Ausstiegsregel" in line for line in v.reasoning))


class TestTheCommandRefusesRatherThanGuessing(unittest.TestCase):
    def _run(self, argv):
        import io
        from contextlib import redirect_stderr, redirect_stdout
        from metals.cli import build_parser
        args = build_parser().parse_args(argv)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = args.func(args)
        return code, out.getvalue() + err.getvalue()

    def test_without_a_file_it_says_where_to_get_one(self):
        code, text = self._run(["verdict"])
        self.assertEqual(code, 2)
        self.assertIn("DATENQUELLEN", text)
        self.assertIn("A27", text)

    def test_without_a_timezone_it_refuses_and_lists_the_common_ones(self):
        code, text = self._run(["verdict", "--file", "x.csv"])
        self.assertEqual(code, 2)
        self.assertIn("broker_gmt3", text)

    def test_a_missing_file_is_reported_not_traced(self):
        code, text = self._run(["verdict", "--file", "/nope/missing.csv",
                                "--tz", "utc"])
        self.assertEqual(code, 1)
        self.assertIn("could not load", text)
        self.assertNotIn("Traceback", text)


if __name__ == "__main__":
    unittest.main()


class TestTheVerdictNamesWhatItDidNotJudge(unittest.TestCase):
    """A command called "the verdict" must be explicit about its scope.

    There are three strategies in this repository and this command measures
    two. A reader who sees five green checks and installs the third has been
    misled by an omission, which is the harder kind to notice than a wrong
    claim -- nothing on the page is false.
    """

    def test_every_render_says_the_half_target_tactic_is_not_covered(self):
        v = Verdict()
        v.recommendation = "NOCH NICHT INSTALLIEREN"
        text = render(v)
        self.assertIn("NICHT GEPRUEFT", text)
        self.assertIn("Halbziel", text)

    def test_it_points_at_the_command_that_would_judge_it(self):
        v = Verdict()
        v.recommendation = "INSTALLIEREN"
        text = render(v)
        self.assertIn("metals halfscalp", text)
        self.assertIn("--tz", text)
