"""The challenge simulator, and the two modelling errors it started with.

Both errors flattered the product, which is the direction an error here is
most dangerous in: the module exists to price a sales pitch, and a generous
model would launder the pitch instead of testing it. Both are pinned by
tests below so they cannot come back.
"""

from __future__ import annotations

import unittest

from metals.challenge import (BREACHED_TOTAL, PASSED, RAN_OUT_OF_TIME,
                              ChallengeRules, Edge, Outcome, evaluate_program,
                              render, render_program, simulate,
                              simulate_funded)


class TestEdgeArithmetic(unittest.TestCase):
    def test_break_even_is_actually_break_even(self):
        e = Edge.break_even(win_r=1.3, loss_r=1.0, cost_r=0.0)
        self.assertAlmostEqual(e.gross_expectancy_r, 0.0, places=12)

    def test_break_even_for_other_payoffs(self):
        for win_r, loss_r in ((2.0, 1.0), (1.0, 1.0), (0.5, 1.0), (3.7, 2.1)):
            e = Edge.break_even(win_r=win_r, loss_r=loss_r, cost_r=0.0)
            with self.subTest(win_r=win_r, loss_r=loss_r):
                self.assertAlmostEqual(e.gross_expectancy_r, 0.0, places=12)

    def test_the_default_is_break_even_not_fifty_percent(self):
        """A 50% win rate against 1.3R/1.0R is +0.15R -- a strong edge wearing
        the costume of a neutral assumption. Defaulting to it made every
        challenge look passable."""
        self.assertAlmostEqual(Edge().gross_expectancy_r, 0.0, places=12)
        self.assertNotAlmostEqual(Edge().win_rate, 0.50, places=2)

    def test_costs_are_subtracted_from_expectancy(self):
        e = Edge(win_rate=0.5, win_r=1.0, loss_r=1.0, cost_r=0.05)
        self.assertAlmostEqual(e.gross_expectancy_r, 0.0, places=12)
        self.assertAlmostEqual(e.expectancy_r, -0.05, places=12)

    def test_costs_are_charged_by_default(self):
        """Leaving them out is what made a coin flipper look profitable."""
        self.assertGreater(Edge().cost_r, 0)
        self.assertLess(Edge().expectancy_r, 0)

    def test_standard_deviation_of_a_two_point_outcome(self):
        e = Edge(win_rate=0.5, win_r=1.0, loss_r=1.0, cost_r=0.0)
        self.assertAlmostEqual(e.sd_r, 1.0, places=12)


class TestSimulation(unittest.TestCase):
    RULES = ChallengeRules.two_step_phase_one(100_000, fee=500)

    def test_it_is_deterministic_for_a_given_seed(self):
        a = simulate(self.RULES, Edge(), runs=500, seed=3)
        b = simulate(self.RULES, Edge(), runs=500, seed=3)
        self.assertEqual(a.counts, b.counts)

    def test_every_run_ends_in_exactly_one_verdict(self):
        o = simulate(self.RULES, Edge(), runs=800, seed=5)
        self.assertEqual(sum(o.counts.values()), o.runs)
        self.assertTrue(set(o.counts) <= {PASSED, BREACHED_TOTAL,
                                          RAN_OUT_OF_TIME,
                                          "breached_daily_loss"})

    def test_a_real_edge_passes_more_often(self):
        weak = simulate(self.RULES, Edge(), runs=3000, seed=5)
        strong = simulate(self.RULES,
                          Edge(win_rate=0.60, win_r=1.3, loss_r=1.0,
                               cost_r=0.05), runs=3000, seed=5)
        self.assertGreater(strong.pass_rate, weak.pass_rate)

    def test_a_negative_edge_almost_never_passes(self):
        awful = simulate(self.RULES,
                         Edge(win_rate=0.30, win_r=1.0, loss_r=1.0,
                              cost_r=0.05), runs=3000, seed=5)
        self.assertLess(awful.pass_rate, 0.05)

    def test_a_trailing_drawdown_is_harder(self):
        """It follows equity up, so a good run tightens the floor under it."""
        static = simulate(self.RULES, Edge(), runs=3000, seed=5)
        trailing = simulate(
            ChallengeRules.two_step_phase_one(100_000, fee=500,
                                              trailing_drawdown=True),
            Edge(), runs=3000, seed=5)
        self.assertLess(trailing.pass_rate, static.pass_rate)

    def test_bigger_risk_breaches_more(self):
        small = simulate(self.RULES, Edge(risk_pct=0.5), runs=3000, seed=5)
        large = simulate(self.RULES, Edge(risk_pct=3.0), runs=3000, seed=5)
        self.assertGreater(large.breach_rate, small.breach_rate)

    def test_the_minimum_trading_day_rule_is_respected(self):
        o = simulate(ChallengeRules.two_step_phase_one(100_000),
                     Edge(win_rate=0.95, win_r=2.0, loss_r=1.0, cost_r=0.0),
                     runs=300, seed=5)
        self.assertTrue(all(d >= 4 for d in o.days_to_pass))

    def test_expected_attempts_is_the_reciprocal_of_the_pass_rate(self):
        o = simulate(self.RULES, Edge(), runs=2000, seed=5)
        self.assertAlmostEqual(o.expected_attempts, 1 / o.pass_rate, places=6)

    def test_no_property_treats_evaluation_profit_as_income(self):
        """The first modelling error: passing an evaluation pays nothing, it
        buys access. Crediting the demo profit turned a losing purchase into
        an apparently excellent one."""
        for gone in ("profit_at_target", "net_expected"):
            self.assertFalse(hasattr(Outcome(self.RULES, Edge(), 1), gone),
                             f"{gone} is back -- evaluation profit is not a "
                             f"payout")


class TestFundedStageAndTheFreeOption(unittest.TestCase):
    RULES = ChallengeRules.two_step_phase_one(100_000, fee=500)

    def test_without_costs_a_coin_flipper_still_gets_paid(self):
        """The counter-intuitive result the simulation actually shows.

        Losses are capped by the drawdown floor while withdrawals bank the
        upside, so at zero gross expectancy and zero cost the funded stage has
        positive expected payout. Documented as a test because the module's
        prose originally claimed the opposite, and the claim was wrong.
        """
        free = simulate_funded(self.RULES,
                               Edge.break_even(cost_r=0.0), runs=2000, seed=11)
        self.assertGreater(free.mean_payout, 0)

    def test_costs_are_what_close_it(self):
        free = simulate_funded(self.RULES, Edge.break_even(cost_r=0.0),
                               runs=2000, seed=11)
        costed = simulate_funded(self.RULES, Edge.break_even(cost_r=0.05),
                                 runs=2000, seed=11)
        self.assertLess(costed.mean_payout, free.mean_payout)

    def test_a_funded_account_on_no_edge_nearly_always_breaches(self):
        o = simulate_funded(self.RULES, Edge(), runs=2000, seed=11)
        self.assertGreater(o.ruin_rate, 0.90)


class TestProgram(unittest.TestCase):
    def test_reaching_funded_needs_both_phases(self):
        p = evaluate_program(100_000, fee=500, edge=Edge(), runs=1500)
        self.assertAlmostEqual(
            p.reach_funded, p.phase1.pass_rate * p.phase2.pass_rate, places=9)
        self.assertLess(p.reach_funded, p.phase1.pass_rate)

    def test_the_default_assumption_gives_a_negative_expected_value(self):
        """No demonstrated edge plus a spread equals a losing purchase. This
        is the headline the whole module exists to produce."""
        p = evaluate_program(100_000, fee=500, edge=Edge(), runs=4000)
        self.assertLess(p.expected_value, 0)

    def test_a_trailing_drawdown_makes_it_worse(self):
        flat = evaluate_program(100_000, fee=500, edge=Edge(), runs=2500,
                                trailing_drawdown=False)
        trail = evaluate_program(100_000, fee=500, edge=Edge(), runs=2500,
                                 trailing_drawdown=True)
        self.assertLess(trail.expected_value, flat.expected_value)

    def test_a_bigger_fee_lowers_the_value_one_for_one(self):
        a = evaluate_program(100_000, fee=300, edge=Edge(), runs=1500)
        b = evaluate_program(100_000, fee=800, edge=Edge(), runs=1500)
        self.assertAlmostEqual(a.expected_value - b.expected_value, 500,
                               delta=1e-6)


class TestRendering(unittest.TestCase):
    def test_the_single_phase_report_names_the_fee_as_your_money(self):
        text = render(simulate(ChallengeRules.two_step_phase_one(100_000),
                               Edge(), runs=400, seed=5))
        self.assertIn("Gebuehr", text)

    def test_it_says_passing_is_not_a_payout(self):
        text = render(simulate(
            ChallengeRules.two_step_phase_one(100_000, fee=500),
            Edge(), runs=400, seed=5))
        self.assertIn("Bestehen ist keine Auszahlung", text)

    def test_the_programme_report_shows_the_cost_line(self):
        text = render_program(evaluate_program(100_000, fee=500, edge=Edge(),
                                               runs=800))
        self.assertIn("Kosten", text)
        self.assertIn("ERWARTUNGSWERT", text)

    def test_it_admits_the_simulation_is_optimistic(self):
        """It models neither consistency rules nor human rule-breaking, and
        lands well above the published payout rate. Saying so is the
        difference between a model and a claim."""
        text = render_program(evaluate_program(100_000, fee=500, edge=Edge(),
                                               runs=800))
        self.assertIn("optimistisch", text)

    def test_rendering_never_raises(self):
        for edge in (Edge(), Edge(win_rate=0.9, win_r=3.0, cost_r=0.0),
                     Edge(win_rate=0.05, win_r=1.0, cost_r=0.2)):
            with self.subTest(edge=edge):
                self.assertIsInstance(
                    render_program(evaluate_program(50_000, fee=250, edge=edge,
                                                    runs=300)), str)


if __name__ == "__main__":
    unittest.main()
