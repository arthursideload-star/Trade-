"""Every subcommand, through the parser and the dispatch function.

This file exists because of audit finding A9. The `--news` flag on `metals
paper` was wired into the wrong function and did nothing for ten sessions
while four unit tests of the blackout passed -- all of them calling the
engine directly. A command that never reaches its engine cannot be caught by
a test of the engine.

So these are deliberately shallow. They do not check that any command
produces the right answer; other files do that. They check that the command
exists, that its arguments parse, that dispatch reaches the function, and
that the function runs to completion. Every defect A9 was made of would have
failed here.

Commands needing network are exercised only where they have an offline path.
The rest are listed in NETWORK_ONLY so that the set is explicit rather than
silently incomplete -- an untested command should be a visible decision.
"""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from metals import paper
from metals.cli import build_parser

# Commands whose only path goes through a price or macro provider. All of
# them fail with 403 in this environment, so a smoke test would assert the
# proxy's behaviour rather than ours.
NETWORK_ONLY = {"analyse", "quote", "ratio"}


def run_command(argv: list[str]) -> str:
    """Parse, dispatch, capture. The whole path a user actually takes.

    Both streams: a command that explains on stderr why it cannot proceed
    has still reached its function and run, which is what is being checked.
    """
    args = build_parser().parse_args(argv)
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        args.func(args)
    return out.getvalue() + err.getvalue()


class TestEverySubcommandIsReachable(unittest.TestCase):
    def test_the_parser_knows_every_command_we_document(self):
        sub = [a for a in build_parser()._actions if a.dest == "command"][0]
        self.assertEqual(
            set(sub.choices),
            {"analyse", "backtest", "challenge", "check", "claims", "dayrange",
             "journal", "microscalp", "minimum", "paper", "quote", "ratio",
             "rules", "setups", "size", "sources", "stop", "train"},
            "a command was added or removed without updating this test, "
            "which is the file that decides whether it gets smoke coverage")

    def test_every_command_either_runs_offline_or_is_listed_as_network(self):
        sub = [a for a in build_parser()._actions if a.dest == "command"][0]
        covered = set(SMOKE_ARGS) | NETWORK_ONLY
        self.assertEqual(set(sub.choices), covered,
                         "every command must either have a smoke case or be "
                         "declared network-only -- silence is not a decision")


# Small on purpose: these measure reachability, not results, and a smoke
# test that takes a minute stops being run.
SMOKE_ARGS: dict[str, list[str]] = {
    "rules": ["rules"],
    "setups": ["setups", "scalp"],
    "sources": ["sources"],
    "check": ["check", "--no-network"],
    "minimum": ["minimum", "XAUUSD", "--equity", "5000"],
    "stop": ["stop", "--equity", "10000"],
    "size": ["size", "XAUUSD", "--entry", "4100", "--stop", "4088",
             "--target", "4130", "--equity", "10000"],
    "claims": ["claims"],
    "challenge": ["challenge", "--fee", "500", "--runs", "50"],
    "microscalp": ["microscalp", "--markets", "2", "--bars", "500"],
    "dayrange": ["dayrange", "--markets", "2", "--bars", "1500"],
    "backtest": ["backtest", "--source", "sim", "--bars", "1500"],
    "journal": ["journal"],
    "paper": ["paper", "--summary"],
    "train": ["train", "--summary"],
}


class TestSmoke(unittest.TestCase):
    """Each command runs to completion and prints something."""

    def setUp(self):
        # train and journal read and write real project files; point them
        # somewhere disposable so a test run cannot alter the record.
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for module, attr, value in (
            (paper, "LEDGER_DIR", self.tmp.name),
            (paper, "LEDGER_PATH", os.path.join(self.tmp.name, "l.jsonl")),
        ):
            patcher = mock.patch.object(module, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)


def _make_smoke_test(name: str, argv: list[str]):
    def test(self):
        from metals import train
        with mock.patch.object(train, "LOG_DIR", self.tmp.name), \
             mock.patch.object(train, "LOG_PATH",
                               os.path.join(self.tmp.name, "t.jsonl")):
            out = run_command(argv)
        self.assertTrue(out.strip(), f"{name} printed nothing at all")
    test.__name__ = f"test_{name}_runs"
    test.__doc__ = f"`metals {' '.join(argv)}` reaches its function and runs."
    return test


for _name, _argv in SMOKE_ARGS.items():
    setattr(TestSmoke, f"test_{_name}_runs", _make_smoke_test(_name, _argv))


class TestTheFlagsThatCarryData(unittest.TestCase):
    """Arguments that change a number, checked to actually arrive.

    A9 was not a parsing failure -- the flag parsed fine and was then handed
    to the wrong function. Only a test that inspects what the command passed
    along can see that.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for attr, value in (("LEDGER_DIR", self.tmp.name),
                            ("LEDGER_PATH",
                             os.path.join(self.tmp.name, "l.jsonl"))):
            patcher = mock.patch.object(paper, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_dayrange_passes_risk_through_to_the_config(self):
        from metals import dayrange
        captured: dict = {}
        real = dayrange.sweep

        def spy(cfg=None, **kwargs):
            captured["risk_pct"] = cfg.risk_pct if cfg else None
            return real(cfg, **kwargs)

        with mock.patch.object(dayrange, "sweep", spy):
            run_command(["dayrange", "--markets", "2", "--bars", "1500",
                         "--risk", "1"])
        self.assertEqual(captured.get("risk_pct"), 1.0)

    def test_paper_passes_the_equity_override(self):
        captured: dict = {}
        real = paper.run_session

        def spy(**kwargs):
            captured.update(kwargs)
            return real(**kwargs)

        with mock.patch.object(paper, "run_session", spy):
            run_command(["paper", "--price", "4100", "--high", "4130",
                         "--low", "4070", "--equity", "1234", "--dry-run"])
        self.assertEqual(captured.get("start_equity_eur"), 1234.0)


if __name__ == "__main__":
    unittest.main()
