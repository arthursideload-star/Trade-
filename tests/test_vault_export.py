"""Writing the EA's trades into the vault.

One property matters more than every other test in this file: **the human's
own notes survive regeneration**. A generator that wipes them makes the
folder worthless from the second run onward, and worthless in the specific
way where you only find out after you have lost something you wrote.

The rest guards the honesty of the output -- that the generated half says it
is generated, that "seen and skipped" does not masquerade as a trade, and
that the index counts without claiming the count proves anything.
"""

from __future__ import annotations

import csv
import os
import tempfile
import unittest

from metals import vault
from metals.journal import load

FIELDS = ["timestamp", "kind", "symbol", "setup", "direction", "session",
          "mode", "entry", "stop", "target1", "target2", "atr", "spread",
          "risk_per_unit", "lots", "taken", "skip_reason", "exit_reason",
          "r_multiple", "pnl", "minutes_held"]

WIN = dict(timestamp="2026-08-01 13:47:00", kind="close", symbol="XAUUSD",
           setup="S2", direction="long", session="overlap", mode="advisor",
           entry="4102.30", stop="4098.10", target1="4110.70", atr="4.2",
           spread="0.28", risk_per_unit="4.20", lots="0.01",
           exit_reason="target1", r_multiple="1.20", pnl="5.04",
           minutes_held="42")
LOSS = dict(timestamp="2026-08-01 16:02:00", kind="close", symbol="XAUUSD",
            setup="S5", direction="short", session="newyork", mode="advisor",
            entry="4115.80", stop="4120.40", atr="4.6", spread="0.31",
            risk_per_unit="4.60", lots="0.01", exit_reason="stop",
            r_multiple="-1.00", pnl="-4.60", minutes_held="18")
SKIPPED = dict(timestamp="2026-08-01 15:20:00", kind="signal", symbol="XAUUSD",
               setup="S4", direction="short", session="newyork",
               mode="advisor", taken="0", skip_reason="news blackout")


class VaultFixture(unittest.TestCase):
    ROWS = [WIN, SKIPPED, LOSS]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = os.path.join(self.tmp.name, "vault")
        os.makedirs(self.vault)
        self.journal = os.path.join(self.tmp.name, "j.csv")
        with open(self.journal, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            w.writeheader()
            for row in self.ROWS:
                w.writerow({k: row.get(k, "") for k in FIELDS})

    def _note(self, name: str) -> str:
        with open(os.path.join(self.vault, vault.TRADES_FOLDER, name),
                  encoding="utf-8") as fh:
            return fh.read()

    def _notes(self) -> list[str]:
        folder = os.path.join(self.vault, vault.TRADES_FOLDER)
        return sorted(f for f in os.listdir(folder) if f.endswith(".md"))


class TestTheExportWrites(VaultFixture):
    def test_one_note_per_closed_trade_plus_an_index(self):
        result = vault.export(self.journal, self.vault)
        self.assertEqual(result.trades, 2)
        self.assertIn("Alle Trades.md", self._notes())

    def test_a_seen_but_skipped_signal_gets_no_note(self):
        """Three hundred "no trade" notes bury the twenty that happened."""
        vault.export(self.journal, self.vault)
        self.assertEqual(len(self._notes()), 3)   # two trades + the index
        self.assertNotIn("S4", " ".join(self._notes()))

    def test_skipped_signals_are_counted_rather_than_dropped(self):
        result = vault.export(self.journal, self.vault)
        self.assertEqual(result.skipped_signals, 1)
        self.assertIn("1 Signale gesehen", self._note("Alle Trades.md"))

    def test_the_filename_sorts_by_time_and_says_what_it_was(self):
        vault.export(self.journal, self.vault)
        names = [n for n in self._notes() if n != "Alle Trades.md"]
        self.assertEqual(names, sorted(names), "notes must sort by time")
        self.assertTrue(any("S2" in n for n in names))

    def test_the_note_carries_the_numbers_a_decision_needs(self):
        vault.export(self.journal, self.vault)
        text = self._note("2026-08-01 1347 S2 L.md")
        for needed in ("4102.30", "4098.10", "+1.20 R", "target1", "0.28"):
            with self.subTest(needed=needed):
                self.assertIn(needed, text)

    def test_the_spread_is_in_the_note(self):
        """A19: the spread decides the sign of the expectancy. A trade record
        without it cannot be argued with afterwards."""
        vault.export(self.journal, self.vault)
        self.assertIn("Spread beim Einstieg",
                      self._note("2026-08-01 1347 S2 L.md"))

    def test_frontmatter_is_searchable(self):
        vault.export(self.journal, self.vault)
        text = self._note("2026-08-01 1602 S5 S.md")
        self.assertIn("ergebnis: verloren", text)
        self.assertIn("ausstieg: stop", text)
        self.assertIn("setup: S5", text)


class TestYourOwnNotesSurvive(VaultFixture):
    """The property the folder lives or dies by."""

    MINE = "- **Was ich gesehen habe:** Doppelboden am Vortagestief."

    def _write_own(self, name: str) -> None:
        path = os.path.join(self.vault, vault.TRADES_FOLDER, name)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        start = text.index(vault.OWN_START) + len(vault.OWN_START)
        end = text.index(vault.OWN_END)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text[:start] + "\n" + self.MINE + "\n" + text[end:])

    def test_text_written_into_the_block_is_kept(self):
        vault.export(self.journal, self.vault)
        self._write_own("2026-08-01 1347 S2 L.md")
        vault.export(self.journal, self.vault)
        self.assertIn(self.MINE, self._note("2026-08-01 1347 S2 L.md"))

    def test_the_export_reports_how_many_it_kept(self):
        vault.export(self.journal, self.vault)
        self._write_own("2026-08-01 1347 S2 L.md")
        result = vault.export(self.journal, self.vault)
        self.assertEqual(result.kept_notes, 1)

    def test_an_untouched_placeholder_does_not_count_as_a_note(self):
        """The first version counted its own placeholder and reported
        "2 notes preserved" for two notes nobody had touched. A status line
        that overstates is a status line nobody can use."""
        vault.export(self.journal, self.vault)
        result = vault.export(self.journal, self.vault)
        self.assertEqual(result.kept_notes, 0)

    def test_reflowed_whitespace_still_reads_as_untouched(self):
        """Obsidian rewrites whitespace on save. If that made the placeholder
        look like human text, every note would freeze at its first version
        and never pick up a corrected figure."""
        squashed = " ".join(vault.PLACEHOLDER.split())
        self.assertTrue(vault._is_placeholder(squashed))
        self.assertTrue(vault._is_placeholder("\n\n" + vault.PLACEHOLDER))

    def test_the_generated_half_says_it_will_be_overwritten(self):
        vault.export(self.journal, self.vault)
        text = self._note("2026-08-01 1347 S2 L.md")
        self.assertIn("ueberschrieben", text)
        self.assertLess(text.index(vault.GENERATED_START),
                        text.index(vault.OWN_START),
                        "the warning has to come before the block it warns "
                        "about")

    def test_a_note_the_user_deleted_comes_back_without_their_text(self):
        vault.export(self.journal, self.vault)
        self._write_own("2026-08-01 1347 S2 L.md")
        os.remove(os.path.join(self.vault, vault.TRADES_FOLDER,
                               "2026-08-01 1347 S2 L.md"))
        result = vault.export(self.journal, self.vault)
        self.assertEqual(result.kept_notes, 0)
        self.assertNotIn(self.MINE, self._note("2026-08-01 1347 S2 L.md"))


class TestTheIndexDoesNotOverclaim(VaultFixture):
    def test_it_counts_without_claiming_the_count_proves_anything(self):
        vault.export(self.journal, self.vault)
        text = self._note("Alle Trades.md")
        self.assertIn("+0.20 R", text)
        self.assertIn("sagt nicht, was das", text)
        self.assertIn("metals journal", text)

    def test_a_setup_breakdown_is_labelled_as_an_observation(self):
        vault.export(self.journal, self.vault)
        text = self._note("Alle Trades.md")
        self.assertIn("Nach Setup", text)
        self.assertIn("kein Ranking", text)

    def test_an_empty_journal_produces_an_index_that_says_so(self):
        empty = os.path.join(self.tmp.name, "empty.csv")
        with open(empty, "w", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=FIELDS).writeheader()
        result = vault.export(empty, self.vault)
        self.assertEqual(result.trades, 0)
        self.assertIn("Noch keine abgeschlossenen Trades",
                      self._note("Alle Trades.md"))

    def test_every_trade_is_linked_from_the_index(self):
        vault.export(self.journal, self.vault)
        text = self._note("Alle Trades.md")
        for name in self._notes():
            if name == "Alle Trades.md":
                continue
            with self.subTest(note=name):
                self.assertIn(f"[[{name[:-3]}]]", text)


class TestTheCommand(VaultFixture):
    def _run(self, argv):
        import io
        from contextlib import redirect_stderr, redirect_stdout
        from metals.cli import build_parser
        args = build_parser().parse_args(argv)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = args.func(args)
        return code, out.getvalue() + err.getvalue()

    def test_it_writes_when_pointed_at_a_journal_and_a_vault(self):
        code, text = self._run(["vault", "--journal", self.journal,
                                "--vault", self.vault])
        self.assertEqual(code, 0)
        self.assertIn("2 Trades", text)

    def test_a_missing_vault_is_reported_not_traced(self):
        code, text = self._run(["vault", "--journal", self.journal,
                                "--vault", "/nope/vault"])
        self.assertEqual(code, 2)
        self.assertNotIn("Traceback", text)
        self.assertIn("obsidian", text)

    def test_a_missing_journal_says_where_the_ea_puts_it(self):
        code, text = self._run(["vault", "--journal", "/nope/j.csv",
                                "--vault", self.vault])
        self.assertEqual(code, 1)
        self.assertNotIn("Traceback", text)
        self.assertIn("MQL5", text)


if __name__ == "__main__":
    unittest.main()
