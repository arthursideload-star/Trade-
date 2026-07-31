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
import os
import random
import statistics
import time
from dataclasses import asdict, dataclass, field

from .candles import Candle, CandleSeries
from .dayrange import DayRangeConfig, run, sweep

LOG_DIR = "training"
LOG_PATH = os.path.join(LOG_DIR, "log.jsonl")

# Which dial to sweep, rotated by iteration so each gets fresh markets in
# turn rather than one being over-measured and the rest never revisited.
DIALS: tuple[tuple[str, tuple[float, ...]], ...] = (
    ("take_fraction", (0.30, 0.50, 0.75, 1.00)),
    ("stop_fraction", (0.25, 0.50, 0.75, 1.00)),
    ("edge_fraction", (0.15, 0.25, 0.35, 0.45)),
    ("confirm_bars", (2, 3, 4, 5)),
    ("min_range_atr", (1.0, 2.0, 3.5, 5.0)),
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
    # Which cost model produced this iteration. Recorded because it changed
    # mid-log: runs 1-3 charged spread alone, run 4 onward charges
    # spread x 1.5 (docs/REPO-AUDIT.md, A8). Comparing a dial's best value
    # across that boundary compares two different worlds.
    slippage_fraction: float = 0.0

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
                   slippage_fraction=base.slippage_fraction)

    best_r, best_val = float("-inf"), values[0]
    for value in values:
        cfg = DayRangeConfig(**{**asdict(base), dial: value})
        s = sweep(cfg, markets=markets, bars=bars, seed_base=seed_base)
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

    # The diagnostic that already caught one false positive in this project.
    best_cfg = DayRangeConfig(**{**asdict(base), dial: best_val})
    from . import simulate
    real, shuf = [], []
    for i in range(8):
        seed = seed_base + 5_000 + i
        s = simulate.generate(bars=bars, timeframe="1m", seed=seed)
        real.append(run(best_cfg, series=s, seed=seed).expectancy_r)
        shuf.append(run(best_cfg, series=_shuffled(s, seed), seed=seed)
                    .expectancy_r)
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
    lines.append("")
    lines.append("  MISCH-TEST auf der besten Konfiguration")
    lines.append(f"    original {it.shuffle_real_r:+.3f}R · "
                 f"gemischt {it.shuffle_random_r:+.3f}R · "
                 f"uebrig {it.edge_survives_shuffling * 100:.0f}%")
    if it.edge_survives_shuffling > 0.5:
        lines.append("    WARNUNG: mehr als die Haelfte ueberlebt das Mischen.")
        lines.append("    Die Kante kaeme dann nicht aus dem Chartmuster.")
    else:
        lines.append("    In Ordnung: die Kante haengt an der Reihenfolge.")
    return "\n".join(lines)


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
        lines.append(f"  {dial:>16} {winner[0]:>8g} {len(entries):>12} "
                     f"{statistics.fmean(winner[1]):>+10.3f}R")

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
