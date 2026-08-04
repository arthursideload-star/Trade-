"""The journal, and the statistics that keep it honest.

The arithmetic in metals/journal.py exists to stop a good evening from being
mistaken for an edge. If it is wrong in the optimistic direction it is worse
than having no journal at all, because it lends a number to a feeling. So the
intervals are checked against values that can be verified by hand, and the
sample-size rule is checked at the magnitude that actually decides the
question.
"""

from __future__ import annotations

import os
import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from metals.journal import (CLOSE, COLUMNS, MIN_TRADES_FOR_A_BREAKDOWN,
                            REFERENCE_EDGE_R, SIGNAL, Entry, JournalError,
                            append, load, mean_and_sd, mean_interval,
                            multiple_comparison_risk, render, summarise,
                            trades_needed, wilson_interval)

UTC = timezone.utc
T0 = datetime(2026, 7, 27, 13, 0, tzinfo=UTC)


def close_entry(r: float, *, setup="S2", session="prime", minutes=0,
                exit_reason="target", direction="long",
                confidence=None) -> Entry:
    return Entry(
        timestamp=T0 + timedelta(minutes=minutes),
        kind=CLOSE, symbol="XAUUSD", setup=setup, direction=direction,
        session=session, mode="auto", r_multiple=r, exit_reason=exit_reason,
        pnl=r * 100.0, minutes_held=20.0, confidence=confidence,
    )


class TestWilsonInterval(unittest.TestCase):
    """Checked against values that can be recomputed by hand."""

    def test_five_of_ten(self):
        lo, hi = wilson_interval(5, 10)
        self.assertAlmostEqual(lo, 0.2366, places=3)
        self.assertAlmostEqual(hi, 0.7634, places=3)

    def test_it_never_leaves_the_unit_interval(self):
        """The reason Wilson is used instead of the textbook interval.

        The normal approximation gives 0 +/- 0 at zero wins and a negative
        lower bound just above it -- both nonsense that would be printed as
        fact.
        """
        for n in range(1, 60):
            for wins in range(0, n + 1):
                lo, hi = wilson_interval(wins, n)
                self.assertGreaterEqual(lo, 0.0)
                self.assertLessEqual(hi, 1.0)
                self.assertLessEqual(lo, hi)

    def test_a_perfect_record_still_admits_doubt(self):
        """Eight wins from eight is the sort of evening that ends in a live
        account. The lower bound must make clear that it does not settle
        anything."""
        lo, hi = wilson_interval(8, 8)
        self.assertLess(lo, 0.75, "8/8 must not imply a win rate above 75%")
        self.assertEqual(hi, 1.0)

    def test_the_interval_narrows_as_evidence_accumulates(self):
        widths = [wilson_interval(n // 2, n)[1] - wilson_interval(n // 2, n)[0]
                  for n in (10, 50, 200, 1000)]
        self.assertEqual(widths, sorted(widths, reverse=True))

    def test_no_sample_means_no_knowledge(self):
        self.assertEqual(wilson_interval(0, 0), (0.0, 1.0))


class TestMeanStatistics(unittest.TestCase):
    def test_mean_and_sd(self):
        mean, sd = mean_and_sd([1.0, 2.0, 3.0, 4.0])
        self.assertAlmostEqual(mean, 2.5)
        # Sample SD with n-1: sqrt(5/3)
        self.assertAlmostEqual(sd, (5.0 / 3.0) ** 0.5)

    def test_a_single_observation_has_no_spread_and_no_interval(self):
        self.assertEqual(mean_and_sd([3.0]), (3.0, 0.0))
        lo, hi = mean_interval([3.0])
        self.assertEqual((lo, hi), (float("-inf"), float("inf")))

    def test_the_interval_straddles_zero_for_a_typical_small_sample(self):
        """The case this project is actually in, and the whole point of
        printing a band rather than a mean."""
        # Four wins at +2R, six losses at -1R: +0.2R mean, looks like an edge.
        sample = [2.0] * 4 + [-1.0] * 6
        lo, hi = mean_interval(sample)
        self.assertLess(lo, 0.0)
        self.assertGreater(hi, 0.0)


class TestTradesNeeded(unittest.TestCase):
    def test_the_number_that_decides_the_go_live_question(self):
        """A 0.1R edge with 1R of trade-to-trade noise -- realistic for a
        scalper -- needs several hundred trades before it is visible."""
        self.assertEqual(trades_needed(0.1, 1.0), 385)

    def test_a_bigger_edge_is_cheaper_to_prove(self):
        self.assertLess(trades_needed(0.5, 1.0), trades_needed(0.1, 1.0))

    def test_more_noise_costs_more_trades(self):
        self.assertGreater(trades_needed(0.2, 2.0), trades_needed(0.2, 1.0))

    def test_scaling_is_quadratic(self):
        """Halving the edge quadruples the trades. The reason 'a slightly
        better version' is not a small change in evidence terms.

        Compared as a ratio with tolerance, because both values are rounded
        up to whole trades and 385/97 is 3.97, not exactly 4.
        """
        ratio = trades_needed(0.1, 1.0) / trades_needed(0.2, 1.0)
        self.assertAlmostEqual(ratio, 4.0, delta=0.1)

    def test_no_positive_mean_means_nothing_to_prove(self):
        self.assertIsNone(trades_needed(0.0, 1.0))
        self.assertIsNone(trades_needed(-0.3, 1.0))


class TestMultipleComparisons(unittest.TestCase):
    def test_nine_buckets_is_a_coin_flip_not_a_five_percent_risk(self):
        self.assertAlmostEqual(multiple_comparison_risk(9), 0.3698, places=3)

    def test_one_bucket_is_the_nominal_level(self):
        self.assertAlmostEqual(multiple_comparison_risk(1), 0.05)

    def test_it_grows_with_slicing(self):
        values = [multiple_comparison_risk(k) for k in (1, 3, 9, 20)]
        self.assertEqual(values, sorted(values))

    def test_no_buckets_no_risk(self):
        self.assertEqual(multiple_comparison_risk(0), 0.0)


class TestRoundTrip(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "journal.csv")

    def tearDown(self):
        self.dir.cleanup()

    def test_write_then_read_preserves_the_outcome(self):
        append(self.path, close_entry(1.7))
        append(self.path, close_entry(-1.0, minutes=30, exit_reason="stop"))
        entries = load(self.path)
        self.assertEqual(len(entries), 2)
        self.assertAlmostEqual(entries[0].r_multiple, 1.7)
        self.assertEqual(entries[1].exit_reason, "stop")
        self.assertEqual(entries[0].symbol, "XAUUSD")

    def test_the_header_is_written_once(self):
        append(self.path, close_entry(1.0))
        append(self.path, close_entry(1.0, minutes=5))
        with open(self.path, encoding="utf-8") as fh:
            body = fh.read()
        self.assertEqual(body.count("timestamp"), 1)

    def test_a_signal_row_survives_the_round_trip(self):
        append(self.path, Entry(
            timestamp=T0, kind=SIGNAL, symbol="XAUUSD", setup="S4",
            direction="short", session="prime", mode="advisor", taken=False,
            skip_reason="S6 spread gate", entry=4500.0, stop=4506.0,
        ))
        (e,) = load(self.path)
        self.assertEqual(e.kind, SIGNAL)
        self.assertIs(e.taken, False)
        self.assertEqual(e.skip_reason, "S6 spread gate")
        self.assertAlmostEqual(e.entry, 4500.0)

    def test_entries_come_back_in_time_order(self):
        append(self.path, close_entry(1.0, minutes=90))
        append(self.path, close_entry(2.0, minutes=10))
        entries = load(self.path)
        self.assertEqual([e.timestamp for e in entries],
                         sorted(e.timestamp for e in entries))

    def test_a_torn_final_line_costs_one_row_not_the_file(self):
        """A journal copied off a running VPS ends mid-write. Losing the
        file at that moment would lose the whole record."""
        append(self.path, close_entry(1.0))
        append(self.path, close_entry(2.0, minutes=5))
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write("2026-07-27 15:00:00,NOT_A_KIND,XAUUSD\n")
        entries = load(self.path)
        self.assertEqual(len(entries), 2)

    def test_a_missing_file_says_where_to_look(self):
        with self.assertRaises(JournalError) as ctx:
            load(os.path.join(self.dir.name, "nope.csv"))
        self.assertIn("Open Data Folder", str(ctx.exception))

    def test_a_foreign_csv_is_rejected_rather_than_misread(self):
        path = os.path.join(self.dir.name, "other.csv")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("date,open,high,low,close\n2026-01-01,1,2,0,1\n")
        with self.assertRaises(JournalError):
            load(path)

    def test_naive_timestamps_are_read_as_utc(self):
        """The EA converts to UTC before writing, so a zone-less stamp is UTC
        and must not be shifted by the reader's local time."""
        path = os.path.join(self.dir.name, "naive.csv")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(",".join(COLUMNS) + "\n")
            fh.write("2026-07-27 13:00:00,close,XAUUSD,S2,long,prime,auto,"
                     ",,,,,,,,,,target,1.5,150,20\n")
        (e,) = load(path)
        self.assertEqual(e.timestamp, T0)


class TestSummary(unittest.TestCase):
    def test_it_separates_signals_from_closed_trades(self):
        entries = [
            Entry(timestamp=T0, kind=SIGNAL, taken=False,
                  skip_reason="news blackout"),
            Entry(timestamp=T0, kind=SIGNAL, taken=True),
            close_entry(1.0, minutes=10),
        ]
        s = summarise(entries)
        self.assertEqual(len(s.signals), 2)
        self.assertEqual(s.n, 1)
        self.assertEqual(s.skipped, {"news blackout": 1})

    def test_totals(self):
        s = summarise([close_entry(2.0), close_entry(-1.0, minutes=10),
                       close_entry(0.5, minutes=20)])
        self.assertEqual(s.n, 3)
        self.assertEqual(s.wins, 2)
        self.assertAlmostEqual(s.total_r, 1.5)
        self.assertAlmostEqual(s.mean_r, 0.5)

    def test_buckets_split_by_setup_and_session(self):
        s = summarise([
            close_entry(1.0, setup="S2", session="prime"),
            close_entry(-1.0, setup="S4", session="prime", minutes=10),
            close_entry(2.0, setup="S2", session="good", minutes=20),
        ])
        self.assertEqual(s.by_setup["S2"].n, 2)
        self.assertAlmostEqual(s.by_setup["S2"].total_r, 3.0)
        self.assertEqual(s.by_setup["S4"].n, 1)
        self.assertEqual(s.by_session["prime"].n, 2)

    def test_worst_streak_counts_consecutive_losses(self):
        s = summarise([close_entry(-1.0, minutes=i * 10) if i in (1, 2, 3, 6)
                       else close_entry(1.0, minutes=i * 10)
                       for i in range(8)])
        self.assertEqual(s.worst_streak, 3)

    def test_a_loss_bigger_than_one_r_is_reported_as_a_process_failure(self):
        s = summarise([close_entry(-1.0), close_entry(-1.8, minutes=10)])
        breaches = s.discipline_breaches
        self.assertEqual(len(breaches), 1)
        self.assertIn("-1.80R", breaches[0])

    def test_a_stop_that_held_exactly_is_not_a_breach(self):
        s = summarise([close_entry(-1.0), close_entry(-1.05, minutes=10)])
        self.assertEqual(s.discipline_breaches, [],
                         "normal slippage must not be reported as indiscipline")

    def test_an_edge_is_not_established_by_a_good_evening(self):
        """Eight wins in a row. The property that gates the live-money
        decision must still be False."""
        s = summarise([close_entry(1.5, minutes=i * 10) for i in range(8)])
        self.assertGreater(s.mean_r, 0)
        self.assertFalse(s.edge_is_established,
                         "8 winning trades must not count as a demonstrated "
                         "edge -- this is the guard against going live on a "
                         "good night")

    def test_an_edge_needs_both_a_sample_and_a_band_above_zero(self):
        # 40 trades, strongly positive and consistent: this should qualify.
        good = [close_entry(1.0, minutes=i * 10) for i in range(30)] + \
               [close_entry(0.8, minutes=(30 + i) * 10) for i in range(10)]
        self.assertTrue(summarise(good).edge_is_established)
        # Same count, mixed enough that the band includes zero: must not.
        mixed = [close_entry(2.0 if i % 3 else -1.5, minutes=i * 10)
                 for i in range(40)]
        s = summarise(mixed)
        lo, _ = s.mean_r_interval
        if lo <= 0:
            self.assertFalse(s.edge_is_established)

    def test_remaining_trades_needed_shrinks_as_the_record_grows(self):
        small = summarise([close_entry(1.0 if i % 2 else -0.8, minutes=i * 10)
                           for i in range(10)])
        large = summarise([close_entry(1.0 if i % 2 else -0.8, minutes=i * 10)
                           for i in range(100)])
        self.assertIsNotNone(small.trades_still_needed)
        self.assertGreater(small.trades_still_needed, large.trades_still_needed)

    def test_min_trades_matches_the_figure_the_project_commits_to(self):
        self.assertEqual(MIN_TRADES_FOR_A_BREAKDOWN, 30)


class TestRender(unittest.TestCase):
    def test_an_empty_journal_explains_itself(self):
        text = render(summarise([]))
        self.assertIn("Noch keine Eintraege", text)

    def test_signals_without_closes_are_the_advisor_normal_case(self):
        text = render(summarise([
            Entry(timestamp=T0, kind=SIGNAL, taken=True, setup="S2"),
        ]))
        self.assertIn("NO CLOSED TRADES YET", text)
        self.assertIn("Advisor", text)

    def test_a_small_sample_is_labelled_as_proving_nothing(self):
        text = render(summarise([close_entry(1.0, minutes=i * 10)
                                 for i in range(6)]))
        self.assertIn("belegt nichts", text)

    def test_the_multiple_comparison_warning_appears_with_the_tables(self):
        text = render(summarise([
            close_entry(1.0, setup="S2", session="prime"),
            close_entry(-1.0, setup="S4", session="good", minutes=10,
                        exit_reason="stop"),
        ]))
        self.assertIn("Schubladen", text)

    def test_it_reports_a_clean_stop_record_as_the_finding_it_is(self):
        text = render(summarise([close_entry(-1.0, minutes=i * 10)
                                 for i in range(5)]))
        self.assertIn("Kein Trade hat mehr als 1R verloren", text)

    def test_the_exit_table_admits_that_its_r_columns_are_circular(self):
        """A trade that closed at its target won by definition. Printing that
        as a 100% win rate next to the setup table invites the reader to
        conclude something about exits that the number cannot support."""
        text = render(summarise([
            close_entry(1.0, exit_reason="target"),
            close_entry(-1.0, exit_reason="stop", minutes=10),
        ]))
        self.assertIn("zirkulaer", text)

    def test_the_sample_size_estimate_warns_about_its_own_optimism(self):
        """Computed from the edge measured so far, which at small n is
        inflated by the same luck that makes the record look good. Without
        the warning it reads as 'nearly there' at exactly the wrong moment.
        """
        text = render(summarise([close_entry(1.0 if i % 4 else -1.0,
                                             minutes=i * 10)
                                 for i in range(12)]))
        self.assertIn("GEMESSENEN", text)
        self.assertIn("quadratisch", text)

    def test_the_reference_edge_puts_the_real_magnitude_on_screen(self):
        """The requirement for a modest edge is in the hundreds, and that
        number has to appear or the optimistic one stands alone."""
        trades = [close_entry(1.0 if i % 4 else -1.0, minutes=i * 10)
                  for i in range(12)]
        s = summarise(trades)
        modest = trades_needed(REFERENCE_EDGE_R, s.sd_r)
        self.assertGreater(modest, 200,
                           "a 0.1R edge must need hundreds of trades, "
                           "otherwise the comparison makes the wrong point")
        self.assertIn(str(modest), render(s))

    def test_rendering_never_raises_on_any_shape_of_record(self):
        shapes = [
            [],
            [close_entry(1.0)],
            [close_entry(-1.0)],
            [close_entry(0.0)],
            [Entry(timestamp=T0, kind=SIGNAL, taken=False, skip_reason="x")],
            [close_entry(float(i % 5) - 2.0, minutes=i * 7) for i in range(120)],
        ]
        for shape in shapes:
            with self.subTest(n=len(shape)):
                self.assertIsInstance(render(summarise(shape)), str)


class TestTheLearningDocStaysTrue(unittest.TestCase):
    """docs/LERNEN.md argues its case with computed numbers.

    Those numbers are the whole argument -- "385 trades" is why the answer to
    "can I go live tomorrow" is no. Prose cannot be recomputed, so if the
    functions behind it ever change, the document silently becomes a set of
    confident claims that the code no longer supports.
    """

    DOC = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docs", "LERNEN.md")

    @classmethod
    def setUpClass(cls):
        with open(cls.DOC, encoding="utf-8") as fh:
            cls.text = fh.read()

    def test_the_sample_size_table_matches_the_function(self):
        # German writes thousands as "1 537", and that space may be plain or
        # non-breaking depending on what wrote the file. Collapsing only a
        # space that sits *between two digits* normalises the separator
        # without joining unrelated numbers across a table cell.
        flat = re.sub(r"(?<=\d)\s(?=\d)", "", self.text)
        for edge in (0.5, 0.3, 0.2, 0.1, 0.05):
            need = trades_needed(edge, 1.0)
            with self.subTest(edge=edge):
                self.assertIn(str(need), flat,
                              f"an edge of {edge}R needs {need} trades, "
                              f"which the document does not state")

    def test_the_multiple_comparison_table_matches_the_function(self):
        for buckets, pct in ((3, 14), (4, 19), (9, 37), (12, 46), (20, 64)):
            with self.subTest(buckets=buckets):
                self.assertEqual(
                    round(multiple_comparison_risk(buckets) * 100), pct,
                    f"the document claims {pct}% for {buckets} buckets")
                self.assertIn(f"{pct} %", self.text)

    def test_the_perfect_evening_bound_matches_wilson(self):
        lo, _ = wilson_interval(8, 8)
        self.assertAlmostEqual(lo, 0.676, places=3)
        self.assertIn("67,6 %", self.text)

    def test_it_states_the_reference_edge_the_code_uses(self):
        self.assertIn(f"{REFERENCE_EDGE_R:.2f}".replace(".", ","), self.text)

    def test_it_does_not_promise_a_return(self):
        """A document about learning is exactly where an accidental promise
        would slip in."""
        for forbidden in ("garantiert", "sicher Gewinn", "verdoppel",
                          "risikolos", "todsicher"):
            self.assertNotIn(forbidden, self.text.lower())

    def test_it_says_plainly_that_the_bot_does_not_retune_itself(self):
        self.assertIn("stellt sich nicht selbst um", self.text)


if __name__ == "__main__":
    unittest.main()


class TestConfidenceIsRecordedAndChecked(unittest.TestCase):
    """The column added when the EA started scoring its setups (A33).

    A confidence score that nobody can compare against outcomes is
    decoration. The point of a threshold is that trades above it do better
    than trades below it, and that is a measurable claim -- so the journal
    has to be able to measure it.
    """

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "journal.csv")

    def tearDown(self):
        self.dir.cleanup()

    def test_confidence_survives_the_round_trip(self):
        append(self.path, close_entry(1.2, confidence=0.72))
        (e,) = load(self.path)
        self.assertAlmostEqual(e.confidence, 0.72)

    def test_a_journal_written_before_the_column_existed_still_loads(self):
        """The reason the column is appended last rather than inserted.

        Anyone already running the EA has a file without it. That file must
        keep working and simply report no confidence.
        """
        old_header = ",".join(COLUMNS[:-1])
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(old_header + "\n")
            fh.write("2026-07-27T13:00:00Z,close,XAUUSD,S2,long,prime,auto,"
                     ",,,,,,,,,,target,1.50,150,20\n")
        (e,) = load(self.path)
        self.assertAlmostEqual(e.r_multiple, 1.5)
        self.assertIsNone(e.confidence)

    def test_trades_are_grouped_into_confidence_bands(self):
        entries = [close_entry(1.0, confidence=0.61, minutes=1),
                   close_entry(1.0, confidence=0.66, minutes=2),
                   close_entry(1.0, confidence=0.80, minutes=3)]
        bands = summarise(entries).by_confidence
        self.assertEqual(set(bands), {"0.60-0.65", "0.65-0.70", "0.70+"})

    def test_a_trade_without_a_confidence_is_not_given_a_band(self):
        """Silence must not be rendered as a bucket named for nothing."""
        bands = summarise([close_entry(1.0)]).by_confidence
        self.assertEqual(bands, {})

    def test_the_report_asks_whether_the_score_earns_its_keep(self):
        entries = [close_entry(1.0, confidence=0.80, minutes=i)
                   for i in range(3)]
        text = render(summarise(entries))
        self.assertIn("BY CONFIDENCE", text)
        self.assertIn("Dekoration", text)

    def test_an_unscored_setup_is_not_bucketed_as_low_confidence(self):
        """DR carries no confidence and writes 0. That is not a reading.

        Bucketing it as "0.60-0.65" would fill the low band with trades that
        were never scored and make the score look worse than it is -- a wrong
        answer to the only question the table exists to ask.
        """
        entries = [close_entry(-1.0, confidence=0.0, minutes=1),
                   close_entry(1.0, confidence=0.72, minutes=2)]
        bands = summarise(entries).by_confidence
        self.assertEqual(set(bands), {"0.70+"})

    def test_a_nonsense_confidence_is_not_bucketed_either(self):
        for bogus in (-0.5, 1.4, 99.0):
            with self.subTest(confidence=bogus):
                bands = summarise([close_entry(1.0, confidence=bogus)])
                self.assertEqual(bands.by_confidence, {})
