"""The record the assistant keeps of itself, and what may be concluded from it.

This module answers one question: **can the bot learn from a trade that went
badly, or one that went well?**

The honest answer has two halves.

*It records.* Every signal the EA finds, every signal it refuses and why,
every position it closes and at what R multiple, with the context that was
true at the time -- setup, session, ATR, spread, intended risk. That record is
the raw material without which "did S4 actually work?" can only be answered
from memory, and memory is the worst instrument in trading: it keeps the
trades that confirm what you already believed.

*It does not retune itself.* Deliberately. A system that reweights its setups
after every losing trade is not learning, it is fitting noise. With three
setups and three session buckets there are nine slices; at twenty trades one
of them looks excellent by chance alone, and a machine that promotes that
slice will chase its own randomness while feeling like it is improving. The
arithmetic for how badly this goes wrong is in `multiple_comparison_risk`
below, and it is worse than most people guess.

So the division of labour is: the machine gathers and quantifies, and any
change to a rule stays a human decision that costs a commit -- the same
standard every risk limit in this project is held to.

The other thing this module does is refuse to let a small sample masquerade
as a finding. `trades_needed` computes how many trades it would take before
an edge of the observed size could be distinguished from zero at all. For a
scalping strategy that number is routinely in the hundreds, which is the real
reason "I'll go live tomorrow" does not follow from a good first evening.

    from metals.journal import load, summarise, render
    print(render(summarise(load("GoldScalpAssistant.csv"))))
"""

from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

# --- The schema shared with the EA ------------------------------------------
#
# The MQL5 side writes exactly these columns in exactly this order. A test
# checks the header string in the EA source against this list, because a
# silent column shift would corrupt every conclusion drawn below while still
# parsing cleanly.

COLUMNS = (
    "timestamp",       # ISO-8601 UTC, always
    "kind",            # signal | close
    "symbol",
    "setup",           # S2 / S4 / S5, or "" on a close row the EA cannot attribute
    "direction",       # long | short
    "session",         # prime | good | marginal | avoid
    "mode",            # advisor | auto
    "entry",
    "stop",
    "target1",
    "target2",
    "atr",
    "spread",
    "risk_per_unit",   # 1R in price terms
    "lots",
    "taken",           # 1 | 0   (signal rows only)
    "skip_reason",     # why a signal was not acted on
    "exit_reason",     # target | stop | trailing_stop | time_stop | session_end
    "r_multiple",      # close rows only, the outcome that matters
    "pnl",             # account currency
    "minutes_held",
    # Appended last, deliberately: parse_row reads every field with .get, so
    # a journal written before this column existed still loads and simply
    # reports no confidence. Added because the EA started computing a
    # confidence in A33 and a score nobody can check against outcomes is
    # decoration -- the whole point of a threshold is that the trades above
    # it do better than the trades below it, and that is a measurable claim.
    "confidence",
)

SIGNAL = "signal"
CLOSE = "close"

# Below this many closed trades, a per-setup or per-session breakdown is
# decoration rather than evidence. Chosen to match the "at least 30 trades"
# figure the rest of the project already commits to, so the two cannot drift.
MIN_TRADES_FOR_A_BREAKDOWN = 30

# Standard normal quantile for a two-sided 95% interval.
Z95 = 1.959963984540054

# A plausible edge for an intraday scalping strategy after costs, used as the
# reference when reporting how much evidence would be needed. Deliberately
# modest: the point of the comparison is that the sample-size requirement
# computed from a lucky early record is far too small, and this shows by how
# much. Not a target, and not a claim that this system has an edge at all.
REFERENCE_EDGE_R = 0.1


class JournalError(Exception):
    """The file could not be read as a journal."""


@dataclass(frozen=True)
class Entry:
    """One line of the record."""

    timestamp: datetime
    kind: str
    symbol: str = ""
    setup: str = ""
    direction: str = ""
    session: str = ""
    mode: str = ""
    entry: float | None = None
    stop: float | None = None
    target1: float | None = None
    target2: float | None = None
    atr: float | None = None
    spread: float | None = None
    risk_per_unit: float | None = None
    lots: float | None = None
    taken: bool | None = None
    skip_reason: str = ""
    exit_reason: str = ""
    r_multiple: float | None = None
    pnl: float | None = None
    minutes_held: float | None = None
    confidence: float | None = None

    @property
    def is_win(self) -> bool:
        return self.r_multiple is not None and self.r_multiple > 0


# --- Reading ----------------------------------------------------------------

def _as_float(raw: str) -> float | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _as_time(raw: str) -> datetime:
    raw = (raw or "").strip().replace("Z", "+00:00")
    # The EA writes "2026-07-27 14:05:00"; ISO with a space is accepted by
    # fromisoformat, but a broker-time file pasted in by hand may not carry a
    # zone. Missing zone is treated as UTC because the EA converts before it
    # writes -- see ServerToUtc in the MQL5 source.
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise JournalError(f"unparseable timestamp {raw!r}") from exc
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def parse_row(row: dict[str, str]) -> Entry:
    kind = (row.get("kind") or "").strip().lower()
    if kind not in (SIGNAL, CLOSE):
        raise JournalError(f"unknown row kind {kind!r} -- expected "
                           f"{SIGNAL!r} or {CLOSE!r}")
    taken_raw = (row.get("taken") or "").strip()
    return Entry(
        timestamp=_as_time(row.get("timestamp", "")),
        kind=kind,
        symbol=(row.get("symbol") or "").strip(),
        setup=(row.get("setup") or "").strip(),
        direction=(row.get("direction") or "").strip().lower(),
        session=(row.get("session") or "").strip().lower(),
        mode=(row.get("mode") or "").strip().lower(),
        entry=_as_float(row.get("entry", "")),
        stop=_as_float(row.get("stop", "")),
        target1=_as_float(row.get("target1", "")),
        target2=_as_float(row.get("target2", "")),
        atr=_as_float(row.get("atr", "")),
        spread=_as_float(row.get("spread", "")),
        risk_per_unit=_as_float(row.get("risk_per_unit", "")),
        lots=_as_float(row.get("lots", "")),
        taken=(taken_raw in ("1", "true", "yes")) if taken_raw else None,
        skip_reason=(row.get("skip_reason") or "").strip(),
        exit_reason=(row.get("exit_reason") or "").strip().lower(),
        r_multiple=_as_float(row.get("r_multiple", "")),
        pnl=_as_float(row.get("pnl", "")),
        minutes_held=_as_float(row.get("minutes_held", "")),
        confidence=_as_float(row.get("confidence", "")),
    )


def load(path: str) -> list[Entry]:
    """Read a journal file written by the EA.

    Rows that cannot be parsed are skipped rather than fatal: a journal that
    was being appended to at the moment it was copied off the VPS ends in a
    torn line, and losing the last row is much better than losing the file.
    """
    if not os.path.exists(path):
        raise JournalError(
            f"{path} does not exist. The EA writes it into the terminal's "
            f"MQL5/Files folder -- in MetaTrader use File -> Open Data Folder "
            f"to find it."
        )
    entries: list[Entry] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise JournalError(f"{path} is empty")
        missing = {"timestamp", "kind"} - set(reader.fieldnames)
        if missing:
            raise JournalError(
                f"{path} is missing the {', '.join(sorted(missing))} column -- "
                f"this does not look like a journal written by the EA"
            )
        for row in reader:
            try:
                entries.append(parse_row(row))
            except JournalError:
                continue
    entries.sort(key=lambda e: e.timestamp)
    return entries


# --- Statistics that do not overstate themselves ----------------------------

def wilson_interval(wins: int, n: int, z: float = Z95) -> tuple[float, float]:
    """95% interval for a win rate, correct at the sample sizes we have.

    The textbook `p +/- z*sqrt(p(1-p)/n)` interval is wrong in exactly the
    situation this project is in -- small n, p near 0 or 1 -- where it can
    produce bounds below zero or above one and is far too narrow besides.
    Wilson's interval is barely more code and does not embarrass itself at
    n = 8.
    """
    if n <= 0:
        return (0.0, 1.0)
    p = wins / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, centre - half), min(1.0, centre + half))


def mean_and_sd(values: list[float]) -> tuple[float, float]:
    """Sample mean and standard deviation (n-1 denominator)."""
    n = len(values)
    if n == 0:
        return (0.0, 0.0)
    mean = sum(values) / n
    if n == 1:
        return (mean, 0.0)
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return (mean, math.sqrt(var))


def mean_interval(values: list[float], z: float = Z95) -> tuple[float, float]:
    """Interval for the mean R multiple.

    Reported with the caveat it deserves: R multiples are not normal, they
    are bimodal with a fat left tail, and at n below a few dozen this band is
    optimistic about its own width. It is included because a band that
    obviously straddles zero is far more informative than a point estimate
    that does not.
    """
    n = len(values)
    if n < 2:
        return (float("-inf"), float("inf"))
    mean, sd = mean_and_sd(values)
    half = z * sd / math.sqrt(n)
    return (mean - half, mean + half)


def trades_needed(mean_r: float, sd_r: float, z: float = Z95) -> int | None:
    """How many trades before an edge this size could be told apart from zero.

    Solves |mean| > z * sd / sqrt(n) for n. This is the number that decides
    whether "it worked tonight" means anything, and it is usually in the
    hundreds -- which is the arithmetic behind the project's refusal to move
    to live money on a good first session.

    Returns None when the observed mean is zero or negative, because there is
    then no positive edge whose detection could be planned for.
    """
    if mean_r <= 0 or sd_r <= 0:
        return None
    return max(1, math.ceil((z * sd_r / mean_r) ** 2))


def multiple_comparison_risk(buckets: int, alpha: float = 0.05) -> float:
    """Probability that at least one of `buckets` slices looks good by chance.

    The number that makes per-setup and per-session breakdowns dangerous
    rather than merely weak. Slicing 3 setups by 3 session qualities gives 9
    buckets, and the chance one of them is spuriously impressive is not 5%.
    """
    if buckets <= 0:
        return 0.0
    return 1.0 - (1.0 - alpha) ** buckets


# --- Aggregation ------------------------------------------------------------

@dataclass
class Bucket:
    """Outcomes for one slice of the record -- a setup, a session, an exit."""

    label: str
    r_multiples: list[float] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.r_multiples)

    @property
    def wins(self) -> int:
        return sum(1 for r in self.r_multiples if r > 0)

    @property
    def win_rate(self) -> float:
        return self.wins / self.n if self.n else 0.0

    @property
    def total_r(self) -> float:
        return sum(self.r_multiples)

    @property
    def mean_r(self) -> float:
        return self.total_r / self.n if self.n else 0.0

    @property
    def sd_r(self) -> float:
        return mean_and_sd(self.r_multiples)[1]

    @property
    def interval(self) -> tuple[float, float]:
        return mean_interval(self.r_multiples)

    @property
    def beats_zero(self) -> bool:
        """Does the 95% band for the mean sit entirely above zero?"""
        lo, _ = self.interval
        return lo > 0 and self.n >= 2


def _group(entries: list[Entry], key,
           drop_unlabelled: bool = False) -> dict[str, Bucket]:
    """Bucket the closed trades by whatever `key` returns.

    `drop_unlabelled` exists for the confidence breakdown. A trade with no
    setup recorded still belongs in the setup table under "(unattributed)" --
    the trade happened and its result counts. A trade with no *confidence*
    is different: the column post-dates the EA that wrote the row, so
    "(unattributed)" would be a bucket named for a question that was never
    asked, sitting next to buckets that answer it.
    """
    out: dict[str, Bucket] = {}
    for e in entries:
        if e.kind != CLOSE or e.r_multiple is None:
            continue
        raw = key(e)
        if drop_unlabelled and not raw:
            continue
        label = raw or "(unattributed)"
        out.setdefault(label, Bucket(label)).r_multiples.append(e.r_multiple)
    return out


@dataclass
class Summary:
    """Everything the record supports, and nothing it does not."""

    entries: list[Entry]
    trades: list[Entry]
    signals: list[Entry]
    by_setup: dict[str, Bucket]
    by_session: dict[str, Bucket]
    by_exit: dict[str, Bucket]
    by_direction: dict[str, Bucket]
    by_confidence: dict[str, Bucket]
    skipped: dict[str, int]
    first: datetime | None
    last: datetime | None

    # --- headline numbers ---
    @property
    def n(self) -> int:
        return len(self.trades)

    @property
    def r_multiples(self) -> list[float]:
        return [t.r_multiple for t in self.trades if t.r_multiple is not None]

    @property
    def wins(self) -> int:
        return sum(1 for r in self.r_multiples if r > 0)

    @property
    def total_r(self) -> float:
        return sum(self.r_multiples)

    @property
    def mean_r(self) -> float:
        return self.total_r / self.n if self.n else 0.0

    @property
    def sd_r(self) -> float:
        return mean_and_sd(self.r_multiples)[1]

    @property
    def win_rate(self) -> float:
        return self.wins / self.n if self.n else 0.0

    @property
    def win_rate_interval(self) -> tuple[float, float]:
        return wilson_interval(self.wins, self.n)

    @property
    def mean_r_interval(self) -> tuple[float, float]:
        return mean_interval(self.r_multiples)

    @property
    def edge_is_established(self) -> bool:
        """The only question that matters, answered conservatively.

        True requires both a sample worth slicing and a 95% band for the mean
        R that sits entirely above zero. Anything less is "not yet known",
        which is a different statement from "no edge" and must not be rounded
        to either "it works" or "it doesn't".
        """
        lo, _ = self.mean_r_interval
        return self.n >= MIN_TRADES_FOR_A_BREAKDOWN and lo > 0

    @property
    def trades_still_needed(self) -> int | None:
        need = trades_needed(self.mean_r, self.sd_r)
        return None if need is None else max(0, need - self.n)

    @property
    def largest_loss(self) -> float:
        losses = [r for r in self.r_multiples if r < 0]
        return min(losses) if losses else 0.0

    @property
    def worst_streak(self) -> int:
        worst = current = 0
        for r in self.r_multiples:
            current = current + 1 if r < 0 else 0
            worst = max(worst, current)
        return worst

    @property
    def discipline_breaches(self) -> list[str]:
        """Losses materially worse than 1R.

        A scalping strategy is allowed to be wrong; it is not allowed to lose
        more than it said it would risk. A cluster here means slippage,
        gapping, or a stop that was moved -- all of which are process
        failures, and all of which are invisible in a P/L curve.
        """
        out: list[str] = []
        for t in self.trades:
            if t.r_multiple is not None and t.r_multiple < -1.25:
                out.append(
                    f"{t.timestamp:%Y-%m-%d %H:%M} {t.setup or '?'} closed at "
                    f"{t.r_multiple:.2f}R -- worse than the 1R that was risked "
                    f"({t.exit_reason or 'reason not recorded'})"
                )
        return out


def _confidence_band(entry: Entry) -> str:
    """Coarse bands, because fine ones invent precision the sample lacks.

    Five-point buckets over a score that runs from roughly 0.55 to 0.90 give
    seven cells; at the trade counts this project will realistically have,
    that is one or two trades each and a league table of noise. Three bands
    is the most the data can carry, and even that needs
    MIN_TRADES_FOR_A_BREAKDOWN before it means anything.
    """
    # Outside (0, 1] the value is not a reading. Zero in particular is what a
    # setup without a score writes, and bucketing it as "0.60-0.65" would put
    # unscored trades in the low-confidence band and make the score look
    # worse than it is -- a wrong answer to the one question this table asks.
    if entry.confidence is None or not 0.0 < entry.confidence <= 1.0:
        return ""
    if entry.confidence < 0.65:
        return "0.60-0.65"
    if entry.confidence < 0.70:
        return "0.65-0.70"
    return "0.70+"


CONFIDENCE_NOTE = (
    "Die Frage dieser Tabelle: VERDIENEN DIE TRADES MIT HOHER KONFIDENZ\n"
    "MEHR ALS DIE MIT NIEDRIGER? Wenn nicht, ist die Zahl Dekoration und\n"
    "die Schwelle sortiert nichts -- dann gehoert sie abgeschafft, nicht\n"
    "nachjustiert. Ein Regler, der nichts trennt, wird nicht besser,\n"
    "wenn man ihn verschiebt.\n"
    "Zu erwarten ist eine steigende Spalte `mean R` von oben nach unten.\n"
    "Ueberlappen sich die Baender, ist die Frage noch offen."
)


def summarise(entries: list[Entry]) -> Summary:
    trades = [e for e in entries if e.kind == CLOSE and e.r_multiple is not None]
    signals = [e for e in entries if e.kind == SIGNAL]
    skipped: dict[str, int] = {}
    for s in signals:
        if s.taken is False:
            reason = s.skip_reason or "(no reason recorded)"
            skipped[reason] = skipped.get(reason, 0) + 1
    stamps = [e.timestamp for e in entries]
    return Summary(
        entries=entries,
        trades=trades,
        signals=signals,
        by_setup=_group(entries, lambda e: e.setup),
        by_session=_group(entries, lambda e: e.session),
        by_exit=_group(entries, lambda e: e.exit_reason),
        by_direction=_group(entries, lambda e: e.direction),
        by_confidence=_group(entries, _confidence_band, drop_unlabelled=True),
        skipped=skipped,
        first=min(stamps) if stamps else None,
        last=max(stamps) if stamps else None,
    )


# --- Rendering --------------------------------------------------------------

def _bucket_table(title: str, buckets: dict[str, Bucket],
                  enough: bool, note: str = "") -> list[str]:
    if not buckets:
        return []
    lines = ["", title, "-" * 72,
             f"  {'':16s} {'n':>4s} {'win%':>6s} {'mean R':>8s} "
             f"{'total R':>9s}  {'95% band for mean R':>24s}"]
    for label, b in sorted(buckets.items(), key=lambda kv: -kv[1].total_r):
        lo, hi = b.interval
        band = ("        n too small" if b.n < 2
                else f"{lo:>+9.2f} .. {hi:<+9.2f}")
        lines.append(
            f"  {label[:16]:16s} {b.n:>4d} {b.win_rate * 100:>5.0f}% "
            f"{b.mean_r:>+8.2f} {b.total_r:>+9.2f}  {band:>24s}"
        )
    if note:
        lines.append("")
        for line in note.splitlines():
            lines.append(f"  {line}")
    if not enough:
        lines.append("")
        lines.append(f"  Diese Aufteilung ist noch keine Evidenz. Unter "
                     f"{MIN_TRADES_FOR_A_BREAKDOWN} Trades sagt sie mehr")
        lines.append("  ueber den Zufall als ueber die Setups.")
    return lines


# The exit table is the one place where the R columns are circular: a trade
# that closed at its target won by definition. Saying so under the table is
# the difference between a useful distribution and a misleading league table.
EXIT_NOTE = (
    "Hier sind die R-Spalten zirkulaer: ein Trade am Ziel hat per\n"
    "Definition gewonnen, einer am Stop verloren. Zu lesen ist die\n"
    "SPALTE n -- woran die Trades sterben. Viele `time_stop` heissen,\n"
    "dass der Zeithorizont nicht zum Setup passt; viele `stop` gleich\n"
    "nach Einstieg heissen, dass zu frueh eingestiegen wird."
)


def render(summary: Summary) -> str:
    """The record, and an honest reading of it."""
    s = summary
    out: list[str] = []
    out.append("TRADING JOURNAL")
    out.append("=" * 72)

    if not s.entries:
        out.append("")
        out.append("  Noch keine Eintraege. Der EA schreibt die Datei, sobald")
        out.append("  er das erste Setup sieht -- auch im Advisor-Modus, auch")
        out.append("  wenn er es ablehnt. Ein leeres Journal nach einem Abend")
        out.append("  heisst: der EA lief nicht, oder es gab kein Setup.")
        return "\n".join(out)

    span = ""
    if s.first and s.last:
        days = max(1, (s.last - s.first).days + 1)
        span = (f"{s.first:%Y-%m-%d %H:%M} .. {s.last:%Y-%m-%d %H:%M} UTC "
                f"({days} day(s))")
    out.append(f"  {span}")
    out.append(f"  {len(s.entries)} rows: {len(s.signals)} signal(s), "
               f"{s.n} closed trade(s)")

    # --- What was refused, and why -----------------------------------------
    if s.skipped:
        out.append("")
        out.append("REFUSED SIGNALS")
        out.append("-" * 72)
        for reason, count in sorted(s.skipped.items(), key=lambda kv: -kv[1]):
            out.append(f"  {count:>4d}x  {reason}")
        out.append("")
        out.append("  Abgelehnte Signale sind kein Fehler -- die Filter sind der")
        out.append("  Teil des Systems, der nachweislich funktioniert. Auffaellig")
        out.append("  wird es erst, wenn ein einziger Grund fast alles blockiert:")
        out.append("  dann passt eine Einstellung nicht zum Broker, nicht zum Markt.")

    if s.n == 0:
        out.append("")
        out.append("NO CLOSED TRADES YET")
        out.append("-" * 72)
        out.append("  Der EA hat Setups gesehen, aber noch keine Position")
        out.append("  geschlossen. Im Advisor-Modus ist das der Normalfall:")
        out.append("  er meldet, er handelt nicht. Zum Lernen reicht das schon --")
        out.append("  vergleiche seine Meldungen mit dem, was du selbst getan")
        out.append("  haettest.")
        return "\n".join(out)

    # --- Headline -----------------------------------------------------------
    lo_w, hi_w = s.win_rate_interval
    lo_r, hi_r = s.mean_r_interval
    out.append("")
    out.append("RESULT")
    out.append("-" * 72)
    out.append(f"  trades            {s.n}")
    out.append(f"  win rate          {s.win_rate * 100:.0f}%   "
               f"(95%: {lo_w * 100:.0f}% .. {hi_w * 100:.0f}%)")
    out.append(f"  mean R            {s.mean_r:+.3f}"
               + (f"   (95%: {lo_r:+.2f} .. {hi_r:+.2f})" if s.n >= 2 else ""))
    out.append(f"  total R           {s.total_r:+.2f}")
    out.append(f"  worst single loss {s.largest_loss:+.2f}R")
    out.append(f"  longest losing streak {s.worst_streak}")

    # --- The verdict --------------------------------------------------------
    out.append("")
    out.append("WAS DAS BELEGT")
    out.append("-" * 72)

    if s.n < MIN_TRADES_FOR_A_BREAKDOWN:
        out.append(f"  {s.n} Trades. Das belegt nichts ueber den Erwartungswert --")
        out.append(f"  weder positiv noch negativ. Unter "
                   f"{MIN_TRADES_FOR_A_BREAKDOWN} Trades ist jede Bilanz")
        out.append("  im Wesentlichen eine Zufallsstichprobe.")
    elif s.edge_is_established:
        out.append("  Das 95%-Band fuer den mittleren R-Wert liegt vollstaendig")
        out.append("  ueber null. Das ist das erste Mal, dass die Zahlen mehr")
        out.append("  sagen als 'nicht widerlegt'. Es bleibt eine Stichprobe aus")
        out.append("  einem Marktregime -- aber es ist ein Befund.")
    else:
        out.append("  Das 95%-Band fuer den mittleren R-Wert schliesst null ein.")
        out.append("  Es gibt also keinen belegten Vorteil. Das heisst nicht,")
        out.append("  dass keiner da ist -- es heisst, dass diese Daten ihn nicht")
        out.append("  zeigen koennen.")

    need = s.trades_still_needed
    if need is None:
        out.append("")
        out.append("  Der beobachtete Mittelwert ist nicht positiv. Eine Rechnung,")
        out.append("  wie viele Trades zum Nachweis fehlen, waere hier sinnlos:")
        out.append("  es gibt noch nichts nachzuweisen.")
    else:
        modest = trades_needed(REFERENCE_EDGE_R, s.sd_r) or 0
        out.append("")
        if need > 0:
            out.append(f"  Bei dieser Streuung (SD {s.sd_r:.2f}R) braeuchte ein "
                       f"Vorteil von")
            out.append(f"  {s.mean_r:+.2f}R rund {need + s.n} Trades, um sich "
                       f"von null zu unterscheiden.")
            out.append(f"  Es fehlen also noch etwa {need} -- bei 4 Trades/Tag "
                       f"rund {math.ceil(need / 4)}")
            out.append("  Handelstage.")
        else:
            out.append(f"  Die Stichprobe ist gross genug, um einen Vorteil "
                       f"dieser Groesse")
            out.append("  sichtbar zu machen.")

        # The trap this whole command exists to defuse. The requirement is
        # computed from the edge measured so far, and at small n that
        # estimate is biased upward by exactly the luck that makes a record
        # look good -- so the number it produces is too small precisely when
        # it is most tempting to believe.
        out.append("")
        out.append("  Vorsicht mit dieser Zahl: sie rechnet mit dem bisher")
        out.append("  GEMESSENEN Vorteil, und der ist bei kleiner Stichprobe")
        out.append("  nach oben verzerrt. Wer Glueck hatte, bekommt hier eine")
        out.append("  zu kleine Zahl.")
        if modest:
            out.append(f"  Waere der echte Vorteil die realistischeren "
                       f"{REFERENCE_EDGE_R:.1f}R, braeuchte")
            out.append(f"  es rund {modest} Trades -- der Bedarf waechst "
                       f"quadratisch:")
            out.append("  halber Vorteil, vierfacher Aufwand.")

    # --- Process, not P/L ---------------------------------------------------
    breaches = s.discipline_breaches
    out.append("")
    out.append("DISZIPLIN")
    out.append("-" * 72)
    if breaches:
        out.append(f"  {len(breaches)} Trade(s) haben mehr als 1R verloren. Das ist")
        out.append("  der eine Befund, der auch bei kleiner Stichprobe zaehlt:")
        out.append("  ein Verlust groesser als der geplante ist ein Prozessfehler,")
        out.append("  kein Pech.")
        for b in breaches[:8]:
            out.append(f"    - {b}")
        if len(breaches) > 8:
            out.append(f"    ... und {len(breaches) - 8} weitere")
    else:
        out.append("  Kein Trade hat mehr als 1R verloren. Die Stops haben")
        out.append("  gehalten, was sie versprochen haben. Das ist die eine")
        out.append("  Eigenschaft, die auch bei 8 Trades schon etwas bedeutet.")

    # --- Breakdowns ---------------------------------------------------------
    enough = s.n >= MIN_TRADES_FOR_A_BREAKDOWN
    out += _bucket_table("BY SETUP", s.by_setup, enough)
    out += _bucket_table("BY SESSION", s.by_session, enough)
    out += _bucket_table("BY EXIT", s.by_exit, enough, EXIT_NOTE)
    out += _bucket_table("BY DIRECTION", s.by_direction, enough)
    out += _bucket_table("BY CONFIDENCE", s.by_confidence, enough,
                         CONFIDENCE_NOTE)

    buckets = (len(s.by_setup) + len(s.by_session) + len(s.by_exit)
               + len(s.by_direction) + len(s.by_confidence))
    if buckets > 1:
        risk = multiple_comparison_risk(buckets)
        out.append("")
        out.append("WARUM MAN DIESE TABELLEN NICHT UEBERLESEN DARF")
        out.append("-" * 72)
        out.append(f"  Oben stehen {buckets} Auswertungs-Schubladen. Haette "
                   f"keine")
        out.append("  einzige davon einen echten Vorteil, laege die "
                   "Wahrscheinlichkeit,")
        out.append(f"  dass trotzdem mindestens eine gut aussieht, bei "
                   f"{risk * 100:.0f}%.")
        out.append("")
        out.append("  Deshalb justiert sich hier nichts automatisch nach. Ein "
                   "Setup")
        out.append("  abschalten, weil es in 6 Trades schlecht lief, ist genau")
        out.append("  der Fehler, den diese Zahl beschreibt.")

    return "\n".join(out)


# --- Writing (for tests, and for logging trades taken by hand) --------------

def append(path: str, entry: Entry) -> None:
    """Append one entry, creating the file with its header if needed.

    Used by the tests and available for logging a trade taken by hand, so the
    manual and the automated record end up in the same file and the same
    analysis.
    """
    exists = os.path.exists(path) and os.path.getsize(path) > 0
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if not exists:
            writer.writerow(COLUMNS)
        writer.writerow([
            entry.timestamp.astimezone(timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S"),
            entry.kind, entry.symbol, entry.setup, entry.direction,
            entry.session, entry.mode,
            _fmt(entry.entry), _fmt(entry.stop), _fmt(entry.target1),
            _fmt(entry.target2), _fmt(entry.atr), _fmt(entry.spread),
            _fmt(entry.risk_per_unit), _fmt(entry.lots),
            "" if entry.taken is None else ("1" if entry.taken else "0"),
            entry.skip_reason, entry.exit_reason,
            _fmt(entry.r_multiple), _fmt(entry.pnl), _fmt(entry.minutes_held),
            _fmt(entry.confidence),
        ])


def _fmt(value: float | None) -> str:
    return "" if value is None else f"{value:g}"
