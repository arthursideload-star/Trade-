"""The Obsidian vault, guarded the way the docs are guarded.

A vault of notes rots exactly like a folder of markdown files -- and this
project has a long record of that: URTEIL.md quoting 53 sessions when there
were 57, the skill file quoting a spread from its first week, PLAN.md calling
the finished journal module "open". The vault is set up to avoid that by
holding judgements rather than figures, and these tests hold it to that.

Three properties, and each has an incident behind it:

* **Every link resolves.** A broken wikilink in Obsidian fails silently --
  the link simply renders as unlinked text and nobody notices.
* **Every configured path exists.** The vault ships a daily-notes config
  pointing at a template. If that path is wrong, the first thing a new user
  does produces an empty note.
* **Numbers carry a date.** The one rule the vault sets for itself.
"""

from __future__ import annotations

import json
import os
import re
import unittest

VAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "obsidian")

WIKILINK = re.compile(r"\[\[([^\]|#]+)")


def _notes() -> dict[str, str]:
    out: dict[str, str] = {}
    for root, _dirs, files in os.walk(VAULT):
        if ".obsidian" in root:
            continue
        for name in files:
            if name.endswith(".md"):
                path = os.path.join(root, name)
                with open(path, encoding="utf-8") as fh:
                    out[os.path.relpath(path, VAULT)] = fh.read()
    return out


def _link_targets() -> set[str]:
    """What a wikilink may point at: a note title or a folder."""
    targets = set()
    for root, dirs, files in os.walk(VAULT):
        if ".obsidian" in root:
            continue
        for d in dirs:
            if d != ".obsidian":
                targets.add(d)
        for name in files:
            if name.endswith(".md"):
                targets.add(name[:-3])
    return targets


class TestTheVaultIsIntact(unittest.TestCase):
    def setUp(self):
        self.notes = _notes()
        self.targets = _link_targets()

    def test_the_vault_exists_and_has_an_entry_point(self):
        self.assertTrue(self.notes, "the vault has no notes at all")
        self.assertIn("00-Start/START HIER.md", self.notes)

    def test_every_wikilink_resolves(self):
        for path, text in self.notes.items():
            for target in WIKILINK.findall(text):
                target = target.strip()
                if not target:          # the deliberate empty [[]] placeholders
                    continue
                with self.subTest(note=path, link=target):
                    self.assertIn(target, self.targets,
                                  f"{path} links to [[{target}]], which does "
                                  f"not exist. Obsidian fails this silently.")

    def test_the_daily_note_config_points_at_things_that_exist(self):
        with open(os.path.join(VAULT, ".obsidian", "daily-notes.json"),
                  encoding="utf-8") as fh:
            cfg = json.load(fh)
        self.assertTrue(os.path.isdir(os.path.join(VAULT, cfg["folder"])))
        self.assertTrue(os.path.isfile(
            os.path.join(VAULT, cfg["template"] + ".md")),
            "the daily-note template path is wrong, so the first note a new "
            "user creates would come out empty")

    def test_the_template_config_points_at_a_real_folder(self):
        with open(os.path.join(VAULT, ".obsidian", "templates.json"),
                  encoding="utf-8") as fh:
            cfg = json.load(fh)
        self.assertTrue(os.path.isdir(os.path.join(VAULT, cfg["folder"])))

    def test_every_folder_a_reader_lands_in_explains_itself(self):
        for folder in ("10-Handelstage", "20-Wissen", "30-Entscheidungen"):
            with self.subTest(folder=folder):
                self.assertIn(f"{folder}/README.md", self.notes)


class TestTheVaultKeepsItsOwnRule(unittest.TestCase):
    """It tells the reader not to copy figures. It has to obey that itself.

    The exception the vault grants is explicit: a number may appear when it
    carries the date it was taken. So a note containing a measured figure
    must also contain either a date or the command that reproduces it.
    """

    MEASURED = re.compile(r"[+-]\d+[,.]\d+\s*R\b")

    def setUp(self):
        self.notes = _notes()

    def test_the_rule_is_actually_written_down(self):
        text = self.notes["00-Start/Warum hier keine Zahlen stehen.md"]
        self.assertIn("Datum", text)
        self.assertIn("paper --review", text)

    def test_any_r_figure_is_dated_or_reproducible(self):
        for path, text in self.notes.items():
            for match in self.MEASURED.finditer(text):
                line_start = text.rfind("\n", 0, match.start()) + 1
                line_end = text.find("\n", match.end())
                context = text[max(0, line_start - 400):
                               line_end if line_end > 0 else len(text)]
                with self.subTest(note=path, figure=match.group()):
                    self.assertTrue(
                        re.search(r"\d{2}\.\d{2}\.\d{4}", context)
                        or "python -m metals" in context
                        or "REPO-AUDIT" in context
                        or "Stand" in context,
                        f"{path} states {match.group()} without a date or a "
                        f"way to reproduce it -- which is the exact habit "
                        f"this vault tells the reader to avoid")

    def test_it_does_not_promise_plugins_the_user_has_to_install(self):
        """Every plugin is a step between the user and the first note, and a
        vault that needs setup gets abandoned during the setup."""
        readme = self.notes["README.md"]
        self.assertIn("Keine Plugins", readme)
        with open(os.path.join(VAULT, ".obsidian", "core-plugins.json"),
                  encoding="utf-8") as fh:
            core = json.load(fh)
        self.assertTrue(core.get("daily-notes"))
        self.assertTrue(core.get("templates"))
        self.assertFalse(os.path.exists(
            os.path.join(VAULT, ".obsidian", "community-plugins.json")))


if __name__ == "__main__":
    unittest.main()
