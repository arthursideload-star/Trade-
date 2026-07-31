"""One training iteration, designed to be run repeatedly and add up.

The point of running this on a schedule is only served if each run produces
information the previous ones did not. Re-running a deterministic simulation
with the same seeds produces the same number forever, which looks like
progress in a log and is not.

So each iteration:

* draws a **fresh block of market seeds** that no previous run has used, so
  the markets are genuinely new rather than the same ones re-measured;
* sweeps one parameter of the day-range strategy, rotating through them so
  every dial gets revisited with new markets over time;
* appends the outcome to `training/log.jsonl`, which accumulates across runs
  and is what later analysis reads;
* re-runs the shuffle diagnostic on the current best configuration, because
  the one failure mode that matters here is an edge that is really an
  artifact, and it has already happened once in this project.

The accumulated log is the deliverable, not any single run. `summarise` reads
it back and reports what has held up across all the markets seen so far --
with the sample size attached, since a parameter that won three sweeps out of
three has still only been seen three times.
"""

from __future__ import annotations

import json
import math
import os
import random
import statistics
import time
from dataclasses import asdict, dataclass, field

from .candles import Candle, CandleSeries
from .dayrange import DayRangeConfig, run, sweep

LOG_DIR = "training"
LOG_PATH = os.path.join(LOG_DIR, "log.jsonl")

# Markets the shuffle diagnostic runs on. Was 8, which was demonstrably too
# few: the same configuration measured on twelve blocks of eight returned a
# survival ratio anywhere between 0% and 70%.
SHUFFLE_SEEDS = 16

# Which dial to sweep, rotated by iteration so each gets fresh markets in
# turn rather than one being over-measured and the rest never revisited.
DIALS: tuple[tuple[str, tuple[float, ...]], ...] = (
    ("take_fraction", (0.30, 0.50, 0.75, 1.00)),
    ("stop_fraction", (0.25, 0.50, 0.75, 1.00)),
    ("edge_fraction", (0.15, 0.25, 0.35, 0.45)),
    ("confirm_bars", (2, 3, 4, 5)),
    # These values are far higher than they look like they should be, and
    # that is the point. A day's range on M1 gold is 20 to 100 times ATR(14),
    # so anything from 1 to 5 never binds -- the sweep that used to sit here
    # compared four settings that produced identical trades, and reported a
    # "best" among them for four training runs. See REPO-AUDIT.md, A12.
    ("min_range_atr", (2.0, 10.0, 20.0, 35.0)),
    ("time_stop_bars", (60, 120, 240, 480)),
)


def _shuffled(series: CandleSeries, seed: int) -> CandleSeries:
    bars = list(series.candles)
    shapes = [(b.high - b.open, b.low - b.open, b.close - b.open, b.volume)
              for b in bars]
    random.Random(seed).shuffle(shapes)
    out, price = [], bars[0].open
    for i, (dh, dl, dc, vol) in enumerate(shapes):
        o, c = price, price + dc
        out.append(Candle(ts=bars[i].ts, open=o, high=max(o, o + dh, c),
                          low=min(o, o + dl, c), close=c, volume=vol))
        price = c
    return CandleSeries(series.symbol, series.timeframe, out, source="shuffled")


def iterations_so_far() -> int:
    if not os.path.exists(LOG_PATH):
        return 0
    with open(LOG_PATH, encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


def next_seed_base() -> int:
    """A block of seeds no earlier iteration has used.

    Blocks of 10,000 keep runs from overlapping even if the market count is
    raised later.
    """
    return 100_000 + iterations_so_far() * 10_000


@dataclass
class Iteration:
    index: int
    dial: str
    seed_base: int
    markets: int
    bars: int
    results: list[dict] = field(default_factory=list)
    best_value: float = 0.0
    best_expectancy_r: float = 0.0
    shuffle_real_r: float = 0.0
    shuffle_random_r: float = 0.0
    timestamp: float = 0.0

    # How much better the winner was than the second-best value, measured on
    # the same markets, and the standard error of that difference. Without
    # these two numbers a "best value" is just the largest of four samples --
    # run 5 recorded min_range_atr=10 beating min_range_atr=2 when both
    # printed +0.126R, a winner decided entirely by noise.
    runner_up_value: float = 0.0
    best_margin_r: float = 0.0
    best_margin_se: float = 0.0

    # The shuffle diagnostic as a paired difference rather than a ratio.
    # The ratio divides by a noisy denominator, and measuring the same
    # configuration on twelve blocks of eight seeds returned anywhere from
    # 0% to 70%, crossing the 50% warning line 2 times in 12 -- a one in six
    # false alarm on the project's most important check. The difference
    # real minus shuffled, paired market by market, has no such denominator.
    shuffle_margin_r: float = 0.0
    shuffle_margin_se: float = 0.0
    shuffle_seeds: int = 0

    # Which rule set produced this iteration. slippage_fraction was already
    # here; R2 and M5 were added to the engine later, and an iteration run
    # before them is not comparable with one run after -- exactly the reason
    # the paper ledger records the same thing per session.
    daily_loss_limit: bool = False
    weekend_flat: bool = False

    @property
    def winner_is_on_the_grid_edge(self) -> bool:
        """Did the sweep bracket an optimum, or just run out of range?

        A winner at the lowest or highest value tested means the search
        stopped at the edge of the grid rather than at a peak. Five of the
        first six iterations did this -- take_fraction picked its maximum,
        stop_fraction, edge_fraction and confirm_bars their minimums,
        time_stop_bars its maximum. Reporting those as "best" without
        saying so invites a dial being moved to a boundary that was never
        shown to be better than what lies past it.
        """
        values = [r["value"] for r in self.results]
        return bool(values) and self.best_value in (min(values), max(values))
    # Which cost model produced this iteration. Recorded because it changed
    # mid-log: runs 1-3 charged spread alone, run 4 onward charges
    # spread x 1.5 (docs/REPO-AUDIT.md, A8). Comparing a dial's best value
    # across that boundary compares two different worlds.
    slippage_fraction: float = 0.0

    @property
    def edge_beats_shuffling(self) -> bool:
        """The gate that replaces the ratio.

        Real minus shuffled, paired by market, more than two standard errors
        above zero. This is the claim the diagnostic was always trying to
        make -- that destroying the order of the bars destroys the edge --
        stated so that a quiet block cannot fake a failure.
        """
        if self.shuffle_margin_se <= 0:
            return False
        return self.shuffle_margin_r > 2 * self.shuffle_margin_se

    @property
    def margin_clears_the_noise(self) -> bool:
        """Whether the winner beat the runner-up by more than measurement error.

        Two standard errors, so roughly the 95% level. Below it the sweep
        has not found a better value -- it has found the largest of four
        samples drawn from the same distribution, which is what happens
        every time regardless of whether the dial does anything.
        """
        if self.best_margin_se <= 0:
            return False
        return self.best_margin_r > 2 * self.best_margin_se

    @property
    def edge_survives_shuffling(self) -> float:
        """Share of the edge left once the bar order is destroyed.

        Below roughly a half means the strategy is reading the sequence,
        which is the whole claim. Above it, the number is coming from
        somewhere else.
        """
        if self.shuffle_real_r <= 0:
            return 1.0
        return max(0.0, self.shuffle_random_r / self.shuffle_real_r)


def one_iteration(markets: int = 20, bars: int = 12_000,
                  base: DayRangeConfig | None = None) -> Iteration:
    base = base or DayRangeConfig()
    index = iterations_so_far()
    dial, values = DIALS[index % len(DIALS)]
    seed_base = next_seed_base()

    it = Iteration(index=index, dial=dial, seed_base=seed_base,
                   markets=markets, bars=bars, timestamp=time.time(),
                   slippage_fraction=base.slippage_fraction,
                   daily_loss_limit=base.daily_loss_limit,
                   weekend_flat=base.weekend_flat)

    best_r, best_val = float("-inf"), values[0]
    # Per-market expectancies, kept so the winner can be compared with the
    # runner-up on the *same* markets. An unpaired comparison would drown a
    # real difference in between-market variance, which is far larger than
    # the difference any dial makes.
    by_value: dict[float, list[float]] = {}
    for value in values:
        cfg = DayRangeConfig(**{**asdict(base), dial: value})
        s = sweep(cfg, markets=markets, bars=bars, seed_base=seed_base)
        by_value[value] = [r.expectancy_r for r in s.runs]
        it.results.append({
            "value": value,
            "expectancy_r": round(s.mean_expectancy_r, 4),
            "win_rate": round(s.mean_win_rate, 4),
            "median_return_pct": round(s.median_return_pct, 2),
            "trades": round(s.mean_trades, 1),
            "losing_rate": round(s.losing_rate, 3),
        })
        if s.mean_expectancy_r > best_r:
            best_r, best_val = s.mean_expectancy_r, value
    it.best_value, it.best_expectancy_r = best_val, round(best_r, 4)

    runner_up = max((v for v in values if v != best_val),
                    key=lambda v: statistics.fmean(by_value[v]), default=None)
    if runner_up is not None:
        it.runner_up_value = runner_up
        diffs = [a - b for a, b in zip(by_value[best_val], by_value[runner_up])]
        it.best_margin_r = round(statistics.fmean(diffs), 5)
        if len(diffs) > 1:
            se = statistics.stdev(diffs) / math.sqrt(len(diffs))
            it.best_margin_se = round(se, 5)

    # The diagnostic that already caught one false positive in this project.
    best_cfg = DayRangeConfig(**{**asdict(base), dial: best_val})
    from . import simulate
    real, shuf = [], []
    for i in range(SHUFFLE_SEEDS):
        seed = seed_base + 5_000 + i
        s = simulate.generate(bars=bars, timeframe="1m", seed=seed)
        real.append(run(best_cfg, series=s, seed=seed).expectancy_r)
        shuf.append(run(best_cfg, series=_shuffled(s, seed), seed=seed)
                    .expectancy_r)
    diffs = [a - b for a, b in zip(real, shuf)]
    it.shuffle_seeds = len(diffs)
    it.shuffle_margin_r = round(statistics.fmean(diffs), 5)
    if len(diffs) > 1:
        it.shuffle_margin_se = round(
            statistics.stdev(diffs) / math.sqrt(len(diffs)), 5)
    it.shuffle_real_r = round(statistics.fmean(real), 4)
    it.shuffle_random_r = round(statistics.fmean(shuf), 4)
    return it


def append(it: Iteration) -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(it)) + "\n")


def load_log() -> list[dict]:
    if not os.path.exists(LOG_PATH):
        return []
    out = []
    with open(LOG_PATH, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def render(it: Iteration) -> str:
    lines = [f"TRAINING — DURCHGANG {it.index + 1}", "=" * 68]
    lines.append(f"  Stellschraube: {it.dial}")
    lines.append(f"  {it.markets} frische Maerkte (Seeds ab {it.seed_base}), "
                 f"{it.bars:,} Bars")
    lines.append("")
    lines.append(f"  {'Wert':>8} {'Trades':>8} {'Treffer':>9} {'Erwartung':>11} "
                 f"{'Median':>9}")
    lines.append("  " + "-" * 50)
    for r in it.results:
        mark = " *" if r["value"] == it.best_value else "  "
        lines.append(f"  {r['value']:>8g} {r['trades']:>8.0f} "
                     f"{r['win_rate'] * 100:>8.1f}% {r['expectancy_r']:>+10.3f}R "
                     f"{r['median_return_pct']:>+8.1f}%{mark}")
    lines.append("")
    lines.append(f"  Bester Wert: {it.dial} = {it.best_value:g} "
                 f"({it.best_expectancy_r:+.3f}R)")
    if it.best_margin_se > 0:
        lines.append(f"    Vorsprung auf {it.dial} = {it.runner_up_value:g}: "
                     f"{it.best_margin_r:+.4f}R "
                     f"(± {it.best_margin_se:.4f} Standardfehler)")
        if not it.margin_clears_the_noise:
            lines.append("    DER VORSPRUNG IST KLEINER ALS DAS RAUSCHEN.")
            lines.append("    Dieser 'beste Wert' ist der groesste von vier")
            lines.append("    Stichproben, kein Befund. Nicht uebernehmen.")
    if it.winner_is_on_the_grid_edge:
        lines.append("    RANDTREFFER: der Sieger liegt am Ende des")
        lines.append("    getesteten Rasters. Das Raster hat kein Optimum")
        lines.append("    eingeschlossen — es ist ausgegangen. Was jenseits")
        lines.append("    davon liegt, wurde nicht gemessen.")
    lines.append("")
    lines.append(f"  MISCH-TEST auf der besten Konfiguration "
                 f"({it.shuffle_seeds or 8} Maerkte)")
    lines.append(f"    original {it.shuffle_real_r:+.3f}R · "
                 f"gemischt {it.shuffle_random_r:+.3f}R · "
                 f"uebrig {it.edge_survives_shuffling * 100:.0f}%")
    if it.shuffle_margin_se > 0:
        # The verdict comes from the paired difference, not the ratio above.
        # The ratio stays visible because it is the intuitive form, but it
        # swings from 0% to 70% on identical configurations and must not be
        # what decides anything.
        lines.append(f"    Vorsprung gepaart: {it.shuffle_margin_r:+.4f}R "
                     f"(± {it.shuffle_margin_se:.4f})")
        if it.edge_beats_shuffling:
            lines.append("    In Ordnung: die Kante haengt an der Reihenfolge,")
            lines.append("    und der Abstand ist groesser als das Rauschen.")
        else:
            lines.append("    WARNUNG: das Mischen kostet die Kante nicht")
            lines.append("    nachweislich. Sie kaeme dann nicht aus dem")
            lines.append("    Chartmuster. Nichts uebernehmen.")
    elif it.edge_survives_shuffling > 0.5:
        lines.append("    WARNUNG: mehr als die Haelfte ueberlebt das Mischen.")
        lines.append("    Die Kante kaeme dann nicht aus dem Chartmuster.")
    else:
        lines.append("    In Ordnung: die Kante haengt an der Reihenfolge.")
    return "\n".join(lines)


def regime_of(entry: dict) -> str:
    """A short label for the rule set an iteration ran under.

    Iterations from before a field existed read as its old value, which is
    correct: they really did run without that rule.
    """
    parts = [f"Slippage {entry.get('slippage_fraction', 0.0):g}"]
    parts.append("R2 an" if entry.get("daily_loss_limit") else "R2 aus")
    parts.append("M5 an" if entry.get("weekend_flat") else "M5 aus")
    return ", ".join(parts)


def summarise() -> str:
    """What has held up across every iteration so far."""
    log = load_log()
    if not log:
        return "Noch keine Trainingsdurchgaenge."

    lines = [f"TRAINING — {len(log)} DURCHGAENGE INSGESAMT", "=" * 68]
    markets = sum(e["markets"] for e in log)
    lines.append(f"  {markets:,} Marktlaeufe gesehen, "
                 f"alle mit unterschiedlichen Seeds")
    lines.append("")

    # Which rule set each iteration ran under. Pooling across a change to
    # the rules compares numbers that were never comparable -- the same
    # reason the paper ledger records it per session. slippage_fraction was
    # already tracked; R2 and M5 arrived later and split the log in two.
    regimes = {regime_of(e) for e in log}
    if len(regimes) > 1:
        lines.append("  ACHTUNG: dieses Log mischt Regelwerke.")
        for r in sorted(regimes):
            n = sum(1 for e in log if regime_of(e) == r)
            lines.append(f"    {n:>3} Durchgaenge mit {r}")
        lines.append("  Zahlen ueber alle Durchgaenge vergleichen damit")
        lines.append("  Laeufe, die nie vergleichbar waren.")
        lines.append("")

    by_dial: dict[str, list[dict]] = {}
    for e in log:
        by_dial.setdefault(e["dial"], []).append(e)

    lines.append("  Bester Wert je Stellschraube, ueber alle Durchgaenge:")
    lines.append(f"  {'Stellschraube':>16} {'Wert':>8} {'Durchgaenge':>12} "
                 f"{'Erwartung':>11}")
    lines.append("  " + "-" * 52)
    for dial, entries in sorted(by_dial.items()):
        votes: dict[float, list[float]] = {}
        for e in entries:
            votes.setdefault(e["best_value"], []).append(e["best_expectancy_r"])
        winner = max(votes.items(), key=lambda kv: (len(kv[1]),
                                                    statistics.fmean(kv[1])))
        # A winner whose margin never cleared the noise is not a winner.
        solid = sum(1 for e in entries
                    if e.get("best_margin_se", 0) > 0
                    and e.get("best_margin_r", 0) > 2 * e["best_margin_se"])
        mark = "" if solid else "  (kein Vorsprung ueber dem Rauschen)"
        lines.append(f"  {dial:>16} {winner[0]:>8g} {len(entries):>12} "
                     f"{statistics.fmean(winner[1]):>+10.3f}R{mark}")

    # Clamped the same way Iteration.edge_survives_shuffling clamps it. A
    # shuffled run that loses money gives a negative ratio, which printed as
    # "-0% of the edge survives" -- true but absurd-looking, and two
    # different numbers for the same quantity in one module.
    survives = [max(0.0, e["shuffle_random_r"] / e["shuffle_real_r"])
                for e in log if e["shuffle_real_r"] > 0]
    if survives:
        lines.append("")
        lines.append(f"  Misch-Test im Mittel: "
                     f"{statistics.fmean(survives) * 100:.0f}% der Kante "
                     f"ueberlebt")
        worst = max(survives)
        lines.append(f"  Schlechtester Durchgang: {worst * 100:.0f}%")

    # Pooled verdict. A single run's shuffle check is too noisy to decide
    # anything: measuring one unchanged configuration on twelve blocks
    # failed the check twice, at eight seeds and again at sixteen. Raising
    # the seed count did not fix that -- the variance is between market
    # blocks, not within them -- so the verdict belongs to the accumulated
    # log rather than to any one iteration.
    margins = [(e["shuffle_margin_r"], e["shuffle_margin_se"])
               for e in log
               if e.get("shuffle_margin_se", 0) > 0]
    if margins:
        # Inverse-variance weighting: a run measured on more markets, or on
        # calmer ones, says more about the question.
        weights = [1.0 / (se ** 2) for _, se in margins]
        pooled = sum(m * w for (m, _), w in zip(margins, weights)) / sum(weights)
        pooled_se = math.sqrt(1.0 / sum(weights))
        lines.append("")
        lines.append(f"  Gepaart ueber alle Durchgaenge: {pooled:+.4f}R "
                     f"(± {pooled_se:.4f})")
        if pooled > 2 * pooled_se:
            lines.append("  Zusammengefasst haelt die Kante dem Mischen NICHT")
            lines.append("  stand — das heisst hier: sie verschwindet beim")
            lines.append("  Mischen, also liest die Strategie die Reihenfolge.")
        else:
            lines.append("  Zusammengefasst ist kein Unterschied zum gemischten")
            lines.append("  Chart nachweisbar. Das waere der ernste Fall.")
        if len(margins) < 5:
            lines.append(f"  (erst {len(margins)} Durchgaenge mit dieser "
                         f"Messung — noch duenn)")

    models = sorted({e.get("slippage_fraction", 0.0) for e in log})
    if len(models) > 1:
        lines.append("")
        lines.append(f"  ACHTUNG: {len(models)} Kostenmodelle im Log "
                     f"({', '.join(f'{m:.0%}' for m in models)}).")
        lines.append("  Ein Wert, der vor und nach der Umstellung gewonnen hat,")
        lines.append("  hat in zwei verschiedenen Welten gewonnen. Die Tabelle")
        lines.append("  oben vergleicht sie trotzdem.")

    lines.append("")
    if len(log) < 10:
        lines.append("  Bei unter zehn Durchgaengen ist das eine Tendenz, kein")
        lines.append("  Befund. Ein Wert, der dreimal gewonnen hat, wurde")
        lines.append("  dreimal gesehen.")
    return "\n".join(lines)
