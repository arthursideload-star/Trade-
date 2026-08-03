"""Write the bot's trades into the Obsidian vault, one note per trade.

The point is not tidiness. It is that a trade you can search, tag and write
on is a trade you can learn from, and a row in a CSV is not.

    python -m metals vault --journal GoldScalpAssistant.csv

What this does and does not claim
---------------------------------
It does **not** make the expert advisor read the vault. The EA is a compiled
MQL5 file; its rules are in its own source and nothing in Obsidian reaches
them. Anyone who believes otherwise will eventually edit a note expecting the
bot to behave differently, and it will not.

What it does is close the other direction: everything the EA did lands in the
vault as notes, so the human and the chat assistant can read the record in
the same place they keep everything else.

Two properties matter more than the formatting
----------------------------------------------
**Your own text survives regeneration.** Each note has a fenced block for
what you wrote. The exporter reads it back before overwriting and puts it
back afterwards. A generator that wipes the human's notes on every run makes
the folder worthless after the second run -- and worthless in the specific
way where you only find out once you have lost something.

**The generated half is honest about being generated.** It carries a marker
saying it will be overwritten, so nobody edits inside it and quietly loses
the edit next Sunday.

What lands here
---------------
Only **closed trades** -- rows the EA wrote when a position finished. Signals
that were seen and skipped are counted in the index rather than given their
own note: three hundred "no trade" notes bury the twenty that happened, and
the reasons for skipping are already aggregated by `metals journal`.
"""

from __future__ import annotations

import os
import re
import statistics
from dataclasses import dataclass, field

from .journal import CLOSE, Entry, load

TRADES_FOLDER = "05-Trades"

# Everything between these markers belongs to the person, not the exporter.
OWN_START = "<!-- DEINE NOTIZEN — bleiben beim Export erhalten -->"
OWN_END = "<!-- ENDE DEINE NOTIZEN -->"

GENERATED_START = "<!-- GENERIERT — wird beim naechsten Export ueberschrieben -->"
GENERATED_END = "<!-- ENDE GENERIERT -->"

_OWN_BLOCK = re.compile(
    re.escape(OWN_START) + r"(.*?)" + re.escape(OWN_END), re.DOTALL)

# What an untouched note contains. Kept as one constant so that "has the
# human written here" is a comparison against the thing that was written,
# not a guess about what their text looks like -- the first version counted
# the placeholder itself as a note and reported "2 notes preserved" for two
# notes nobody had touched.
PLACEHOLDER = """
*Drei Zeilen reichen. Die mittlere ist die wichtigste:*

- **Was ich gesehen habe:** 
- **Habe ich den Plan befolgt?** 
- **Wuerde ich diesen Trade nochmal so nehmen?** 

> Ein Trade, der **gewonnen hat, obwohl du die Regel gebrochen hast**,
> gehoert ausdruecklich hierher. Er ist der gefaehrlichste Eintrag im
> ganzen Journal, weil er schlechtes Verhalten belohnt.
"""


def _is_placeholder(text: str) -> bool:
    """Whitespace-insensitive, because Obsidian reflows on save."""
    squash = " ".join(text.split())
    return squash == " ".join(PLACEHOLDER.split())


@dataclass
class ExportResult:
    written: list[str] = field(default_factory=list)
    kept_notes: int = 0
    skipped_signals: int = 0
    folder: str = ""

    @property
    def trades(self) -> int:
        return len(self.written)


def _slug(entry: Entry) -> str:
    """A filename that sorts by time and says what the trade was."""
    setup = re.sub(r"[^A-Za-z0-9]+", "", entry.setup) or "Trade"
    direction = entry.direction[:1].upper() or "-"
    return f"{entry.timestamp:%Y-%m-%d %H%M} {setup} {direction}"


def _existing_own_text(path: str) -> str | None:
    """Read back what the human wrote, so it can be put back."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            match = _OWN_BLOCK.search(fh.read())
    except OSError:
        return None
    if not match:
        return None
    text = match.group(1).strip("\n")
    if not text.strip() or _is_placeholder(text):
        return None
    return text


def _verdict(entry: Entry) -> str:
    if entry.r_multiple is None:
        return "unbekannt"
    if entry.r_multiple > 0:
        return "gewonnen"
    if entry.r_multiple < 0:
        return "verloren"
    return "null"


def _num(value: float | None, digits: int = 2) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def render_trade(entry: Entry, own_text: str | None = None) -> str:
    r = entry.r_multiple
    r_text = "—" if r is None else f"{r:+.2f}"
    title = (f"{entry.timestamp:%Y-%m-%d %H:%M} · "
             f"{entry.setup or 'Trade'} {entry.direction or ''}".strip()
             + f" · {r_text} R")

    lines = [
        "---",
        "typ: trade",
        f"datum: {entry.timestamp:%Y-%m-%d}",
        f"zeit: {entry.timestamp:%H:%M}",
        f"symbol: {entry.symbol or 'XAUUSD'}",
        f"setup: {entry.setup or 'unbekannt'}",
        f"richtung: {entry.direction or 'unbekannt'}",
        f"session: {entry.session or 'unbekannt'}",
        f"modus: {entry.mode or 'unbekannt'}",
        f"r: {r_text}",
        f"ergebnis: {_verdict(entry)}",
        f"ausstieg: {entry.exit_reason or 'unbekannt'}",
        "---",
        "",
        f"# {title}",
        "",
        GENERATED_START,
        "",
        "| | |",
        "|---|---|",
        f"| Einstieg | {_num(entry.entry)} |",
        f"| Stop | {_num(entry.stop)} |",
        f"| Ziel 1 | {_num(entry.target1)} |",
        f"| Ziel 2 | {_num(entry.target2)} |",
        f"| Losgroesse | {_num(entry.lots, 2)} |",
        f"| Risiko je Unze | {_num(entry.risk_per_unit)} |",
        f"| ATR beim Einstieg | {_num(entry.atr)} |",
        f"| **Spread beim Einstieg** | **{_num(entry.spread)} $/oz** |",
        f"| Ausstieg | {entry.exit_reason or '—'} |",
        f"| Gehalten | {_num(entry.minutes_held, 0)} Minuten |",
        f"| **Ergebnis** | **{r_text} R** |",
        "",
        GENERATED_END,
        "",
        "## Was ich dazu weiss",
        "",
        OWN_START,
    ]

    lines.extend((own_text or PLACEHOLDER).split("\n"))

    lines.extend([OWN_END, "", "---", "", "Uebersicht: [[Alle Trades]]"])
    return "\n".join(lines) + "\n"


def render_index(entries: list[Entry], skipped: int) -> str:
    closed = [e for e in entries if e.kind == CLOSE and e.r_multiple is not None]
    lines = ["---", "typ: uebersicht", "---", "",
             "# Alle Trades", "",
             GENERATED_START, ""]

    if not closed:
        lines += [
            "Noch keine abgeschlossenen Trades im Journal.",
            "",
            "Die Datei entsteht, sobald der EA das erste Setup erkennt und",
            "eine Position schliesst. In ruhigen Stunden dauert das.",
            "", GENERATED_END, ""]
        return "\n".join(lines) + "\n"

    rs = [e.r_multiple for e in closed if e.r_multiple is not None]
    wins = [x for x in rs if x > 0]
    losses = [x for x in rs if x <= 0]

    lines += [
        f"**{len(closed)} abgeschlossene Trades**, "
        f"{skipped} Signale gesehen und nicht genommen.",
        "",
        "| | |",
        "|---|---|",
        f"| Summe | {sum(rs):+.2f} R |",
        f"| Gewonnen | {len(wins)} ({len(wins) / len(rs):.0%}) |",
        f"| Verloren | {len(losses)} |",
    ]
    if wins:
        lines.append(f"| Gewinner im Mittel | {statistics.fmean(wins):+.2f} R |")
    if losses:
        lines.append(f"| Verlierer im Mittel | {statistics.fmean(losses):+.2f} R |")
    lines += [
        "",
        "> Diese Tabelle sagt, **was passiert ist**. Sie sagt nicht, was das",
        "> belegt — dafuer gibt es Konfidenzbaender, und die rechnet:",
        "> `python -m metals journal --file GoldScalpAssistant.csv`",
        "> Bei kleiner Stichprobe sagt die Auswertung ehrlich, dass es nichts",
        "> belegt — und dann belegt es nichts.",
        "",
    ]

    by_setup: dict[str, list[float]] = {}
    for e in closed:
        if e.r_multiple is not None:
            by_setup.setdefault(e.setup or "unbekannt", []).append(e.r_multiple)
    if len(by_setup) > 1:
        lines += ["## Nach Setup", "",
                  "| Setup | Trades | Summe R | Ø R |", "|---|---:|---:|---:|"]
        for setup, values in sorted(by_setup.items(),
                                    key=lambda kv: -sum(kv[1])):
            lines.append(f"| {setup} | {len(values)} | {sum(values):+.2f} | "
                         f"{statistics.fmean(values):+.2f} |")
        lines += ["", "*Bei unter 30 Trades je Setup ist das eine "
                      "Beobachtung, kein Ranking.*", ""]

    lines += ["## Die Trades", "",
              "| Datum | Setup | Richtung | Ausstieg | R |",
              "|---|---|---|---|---:|"]
    for e in sorted(closed, key=lambda x: x.timestamp, reverse=True):
        name = _slug(e)
        lines.append(
            f"| [[{name}]] | {e.setup or '—'} | {e.direction or '—'} | "
            f"{e.exit_reason or '—'} | {e.r_multiple:+.2f} |")

    lines += ["", GENERATED_END, ""]
    return "\n".join(lines) + "\n"


def export(journal_path: str, vault_path: str) -> ExportResult:
    """Write one note per closed trade, keeping any notes already written."""
    entries = load(journal_path)
    folder = os.path.join(vault_path, TRADES_FOLDER)
    os.makedirs(folder, exist_ok=True)

    result = ExportResult(folder=folder)
    result.skipped_signals = sum(
        1 for e in entries if e.kind != CLOSE and e.taken is False)

    for entry in entries:
        if entry.kind != CLOSE or entry.r_multiple is None:
            continue
        path = os.path.join(folder, _slug(entry) + ".md")
        own = _existing_own_text(path)
        if own:
            result.kept_notes += 1
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(render_trade(entry, own))
        result.written.append(os.path.basename(path))

    index = os.path.join(folder, "Alle Trades.md")
    with open(index, "w", encoding="utf-8") as fh:
        fh.write(render_index(entries, result.skipped_signals))
    return result


def render_result(r: ExportResult) -> str:
    lines = [f"{r.trades} Trades nach {r.folder} geschrieben."]
    if r.kept_notes:
        lines.append(f"{r.kept_notes} davon hatten eigene Notizen — die sind "
                     f"erhalten geblieben.")
    if r.skipped_signals:
        lines.append(f"{r.skipped_signals} gesehene, aber nicht genommene "
                     f"Signale bekommen keine eigene Notiz; sie stehen in "
                     f"der Uebersicht und in `metals journal`.")
    if not r.trades:
        lines.append("Noch keine abgeschlossenen Trades. Die Datei entsteht, "
                     "sobald der EA die erste Position schliesst.")
    return "\n".join(lines)
