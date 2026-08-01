"""Does this market continue, or does it come back?

The strategy in `metals/dayrange.py` predicts a move from the day's range and
banks half of it. `paper --review` shows what that produces: winners average
+0.83 R, losers -0.82 R, a payoff ratio of 1.01. The entire edge is the hit
rate, and it breaks even at 49.8% -- ten points of headroom and nothing
underneath.

The obvious response is "hold the winners longer". Whether that can work is
not a matter of preference. It depends on one property of the market:

* **Persistent** (H > 0.5, VR > 1) -- moves continue. Widening the target
  pays, and cutting winners at half the predicted move is leaving money on
  the table.
* **Random walk** (H = 0.5, VR = 1) -- no target scheme beats another before
  costs. Every exit rule has the same expectancy and the only thing that
  separates them is what they pay in spread. The payoff ratio of ~1.0 is
  then not a flaw to fix; it is the market's answer.
* **Mean reverting** (H < 0.5, VR < 1) -- moves come back. Near targets are
  right, wide ones give the position back, and this strategy's shape is the
  correct one.

`docs/TRADING-WISSEN.md` mentions the Hurst exponent once, in a table, with
the note "computationally expensive, unstable on short windows". That was
enough reason never to compute it. It is not expensive -- the whole thing is
below -- and the instability is real and is exactly why the variance ratio
is reported alongside it, because that one comes with a test statistic.

Two measures, on purpose
------------------------
**Rescaled range (Hurst).** The classic. Intuitive, and it has no null
distribution -- an H of 0.54 on 2,000 bars is not evidence of anything and
nothing in the method says so.

**Variance ratio (Lo/MacKinlay 1988).** VR(q) = Var(q-period return) /
(q x Var(1-period return)). Under a random walk it is 1, and the paper gives
a heteroskedasticity-robust z statistic, so "VR = 0.93" becomes "VR = 0.93,
z = -1.2, which is what a random walk looks like". That is the difference
between a number and a finding, and this project has spent twenty-six audit
entries on that difference.

What this can and cannot settle here
------------------------------------
Run against `metals.simulate` it measures the simulator, which has mean
reversion built into it by construction (`simulate.py` reverts toward a slow
anchor "to prevent random walk blowups"). Finding mean reversion there is
finding what was placed, exactly as claim C3 is circular about sessions.

It becomes a real measurement the moment it is pointed at a downloaded
history:

    python -m metals persistence --file XAU_5m_data.csv --tz broker_gmt3
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from .candles import CandleSeries

# Below this many returns, neither measure means anything. R/S in particular
# will happily return 0.7 on noise at n=100.
MIN_OBSERVATIONS = 256

# |z| beyond this rejects the random walk at the 5% level, two-sided.
Z95 = 1.96


@dataclass(frozen=True)
class VarianceRatio:
    q: int
    ratio: float
    z: float
    observations: int

    @property
    def rejects_random_walk(self) -> bool:
        return abs(self.z) > Z95

    @property
    def verdict(self) -> str:
        if not self.rejects_random_walk:
            return "random walk"
        return "persistent" if self.ratio > 1.0 else "mean reverting"


@dataclass(frozen=True)
class Persistence:
    hurst: float
    ratios: tuple[VarianceRatio, ...]
    observations: int
    source: str = ""

    @property
    def any_rejection(self) -> bool:
        return any(r.rejects_random_walk for r in self.ratios)

    @property
    def verdict(self) -> str:
        """One word, and "random walk" when nothing was established.

        Deliberately does not fall back to the Hurst number when the
        variance ratios fail to reject. An H of 0.46 with every z inside
        the band is a random walk with a decorative decimal on it.
        """
        rejecting = [r for r in self.ratios if r.rejects_random_walk]
        if not rejecting:
            return "random walk"
        if all(r.ratio < 1.0 for r in rejecting):
            return "mean reverting"
        if all(r.ratio > 1.0 for r in rejecting):
            return "persistent"
        return "mixed"

    @property
    def target_advice(self) -> str:
        """What the finding means for the one dial that matters here."""
        if self.verdict == "persistent":
            return ("Moves continue: a wider target should pay, and banking "
                    "half the predicted move is leaving some of it behind. "
                    "Worth sweeping take_fraction upward -- and worth "
                    "measuring rather than assuming.")
        if self.verdict == "mean reverting":
            return ("Moves come back: near targets are right and a wider one "
                    "gives the position back. The strategy's shape matches "
                    "the market, and the payoff ratio near 1.0 is the "
                    "consequence, not a defect.")
        return ("No target scheme beats another before costs -- every exit "
                "rule has the same expectancy on a random walk, and what "
                "separates them is the spread they pay. So the lever is not "
                "the target. It is the number of trades and the cost of "
                "each.")


def log_prices(series: CandleSeries) -> list[float]:
    return [math.log(c.close) for c in series.candles if c.close > 0]


def hurst_rescaled_range(prices: list[float],
                         min_chunk: int = 16) -> float:
    """Hurst exponent by rescaled range, on log returns.

    Returns 0.5 when there is not enough data to say anything, rather than a
    number produced from three chunks. A silent 0.68 out of noise is exactly
    how this measure earned its reputation.
    """
    rets = [b - a for a, b in zip(prices, prices[1:])]
    n = len(rets)
    if n < MIN_OBSERVATIONS:
        return 0.5

    sizes: list[int] = []
    size = min_chunk
    while size <= n // 2:
        sizes.append(size)
        size *= 2
    if len(sizes) < 3:
        return 0.5

    xs: list[float] = []
    ys: list[float] = []
    for size in sizes:
        rs_values: list[float] = []
        for start in range(0, n - size + 1, size):
            chunk = rets[start:start + size]
            mean = statistics.fmean(chunk)
            deviations = [x - mean for x in chunk]
            cumulative: list[float] = []
            running = 0.0
            for d in deviations:
                running += d
                cumulative.append(running)
            spread = max(cumulative) - min(cumulative)
            sd = statistics.pstdev(chunk)
            if sd > 0 and spread > 0:
                rs_values.append(spread / sd)
        if rs_values:
            xs.append(math.log(size))
            ys.append(math.log(statistics.fmean(rs_values)))

    if len(xs) < 3:
        return 0.5
    return _slope(xs, ys)


def _slope(xs: list[float], ys: list[float]) -> float:
    mx = statistics.fmean(xs)
    my = statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den if den else 0.5


def variance_ratio(prices: list[float], q: int) -> VarianceRatio:
    """Lo/MacKinlay variance ratio with the heteroskedasticity-robust z.

    The robust version matters here rather than being a nicety: gold's
    volatility clusters hard, and the homoskedastic statistic reads
    volatility clustering as a rejection of the random walk. It would find
    structure in the one property gold definitely has and the strategy
    definitely cannot trade.
    """
    rets = [b - a for a, b in zip(prices, prices[1:])]
    T = len(rets)
    if q < 2 or T < max(MIN_OBSERVATIONS, q * 4):
        return VarianceRatio(q=q, ratio=1.0, z=0.0, observations=T)

    mu = (prices[-1] - prices[0]) / T
    dev = [r - mu for r in rets]

    var1 = sum(d * d for d in dev) / (T - 1)
    if var1 <= 0:
        return VarianceRatio(q=q, ratio=1.0, z=0.0, observations=T)

    m = q * (T - q + 1) * (1 - q / T)
    if m <= 0:
        return VarianceRatio(q=q, ratio=1.0, z=0.0, observations=T)
    total = 0.0
    for t in range(q, T + 1):
        total += (prices[t] - prices[t - q] - q * mu) ** 2
    varq = total / m

    ratio = varq / var1

    # delta_j = sum_t (r_t-mu)^2 (r_{t-j}-mu)^2 / [sum_t (r_t-mu)^2]^2
    #
    # The sample-size scaling is already inside this ratio -- numerator over
    # T terms, denominator over T^2 -- so delta is of order 1/T and the
    # square root below supplies the sqrt(T) the statistic needs. An extra
    # factor of T here (which is what the first version had) leaves theta of
    # order 1 and produces z = 0.28 for a variance ratio of 1.56, i.e. it
    # fails to reject a market with an AR(1) coefficient of 0.3 in it.
    denom = sum(d * d for d in dev) ** 2
    theta = 0.0
    for j in range(1, q):
        num = sum(dev[t] ** 2 * dev[t - j] ** 2 for t in range(j, T))
        delta = num / denom if denom else 0.0
        theta += ((2.0 * (q - j) / q) ** 2) * delta

    z = (ratio - 1.0) / math.sqrt(theta) if theta > 0 else 0.0
    return VarianceRatio(q=q, ratio=ratio, z=z, observations=T)


def measure(series: CandleSeries,
            qs: tuple[int, ...] = (2, 4, 8, 16, 32)) -> Persistence:
    prices = log_prices(series)
    return Persistence(
        hurst=hurst_rescaled_range(prices),
        ratios=tuple(variance_ratio(prices, q) for q in qs),
        observations=max(0, len(prices) - 1),
        source=f"{series.symbol} {series.timeframe} ({series.source})",
    )


def render(p: Persistence) -> str:
    lines = [f"BLEIBT DIE BEWEGUNG ODER KOMMT SIE ZURUECK? — {p.source}",
             "=" * 74,
             f"  {p.observations:,} Renditen"]
    if p.observations < MIN_OBSERVATIONS:
        lines.append(f"  ZU WENIG DATEN: unter {MIN_OBSERVATIONS} Renditen "
                     f"sagen beide Masse nichts.")
        return "\n".join(lines)

    lines.append("")
    lines.append(f"  Hurst (R/S)   {p.hurst:.3f}   "
                 f"{'> 0,5 trendend' if p.hurst > 0.5 else '< 0,5 rueckkehrend'}")
    lines.append("    Ohne Nullverteilung. Allein sagt diese Zahl nichts —")
    lines.append("    deshalb steht darunter der Test, der eine hat.")
    lines.append("")
    lines.append(f"  {'q':>4s} {'VR(q)':>8s} {'z':>8s}   Befund")
    lines.append("  " + "-" * 46)
    for r in p.ratios:
        mark = "*" if r.rejects_random_walk else " "
        lines.append(f"  {r.q:>4d} {r.ratio:>8.3f} {r.z:>+8.2f} {mark}  "
                     f"{r.verdict}")
    lines.append("")
    lines.append(f"  Gesamturteil: {p.verdict.upper()}")
    if not p.any_rejection:
        lines.append("    Kein einziges q verwirft den Zufallspfad. Das ist")
        lines.append("    ein Ergebnis, kein fehlendes Ergebnis.")
    lines.append("")
    for line in _wrap(p.target_advice, 68):
        lines.append(f"    {line}")
    return "\n".join(lines)


def _wrap(text: str, width: int) -> list[str]:
    out: list[str] = []
    line = ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out


# --- Which of the generator's features is the edge actually made of? -------

@dataclass(frozen=True)
class Ablation:
    """One generator feature switched off, and what the strategy then earns."""

    name: str
    expectancy_r: float
    low: float
    high: float
    trades: int

    @property
    def band_straddles_zero(self) -> bool:
        return self.low < 0.0 < self.high


@dataclass(frozen=True)
class AblationFinding:
    baseline: Ablation
    variants: tuple[Ablation, ...]

    def by_name(self, name: str) -> Ablation | None:
        for v in self.variants:
            if v.name == name:
                return v
        return None

    @property
    def load_bearing(self) -> list[str]:
        """Features whose removal takes the edge to something that could be
        zero. These are what the measured expectancy is actually made of."""
        return [v.name for v in self.variants
                if v.band_straddles_zero or v.high < 0.0]


def ablate(markets: int = 150, bars: int = 1_440, seed_base: int = 500_000,
           spread_usd_oz: float = 0.34) -> AblationFinding:
    """Switch off one generated feature at a time and re-measure the edge.

    The strongest diagnostic in this project, and it exists because the two
    weaker ones could not answer the question.

    `paper --evidence` says the expectancy is +0.17 R with a band above zero.
    The shuffle test in `metals/train.py` says that edge disappears when the
    bars are reordered, which was read as "the strategy is reading the
    chart". Both are true and neither asks the question that matters: **whose
    chart**. A shuffle cannot tell structure that gold has from structure the
    generator was given.

    This can, because the generator's features are parameters and parameters
    can be set to zero.

    The answer, measured over 150 one-day markets:

        everything on            +0.0988 R   [+0.042 .. +0.156]
        no liquidity sweep       +0.1151 R   [+0.059 .. +0.171]
        no round-number magnet   +0.0813 R   [+0.025 .. +0.137]
        no jumps                 +0.0738 R   [+0.016 .. +0.132]
        no mean reversion        +0.0071 R   [-0.050 .. +0.065]
        none of them             -0.1326 R   [-0.192 .. -0.073]

    Turn off `MarketParams.reversion` and the edge is gone. Turn off
    everything and the strategy loses money at roughly the cost of its own
    spread, which is what a strategy should do on a driftless random walk.

    The dose-response is near linear -- 0.0000, 0.0005, 0.0010, 0.0020,
    0.0040, 0.0080 give +0.007, +0.034, +0.057, +0.099, +0.162, +0.246 R --
    so the measured expectancy is close to a readout of that one number.

    And `reversion` is not a claim about gold. Its own comment in
    `simulate.py` says what it is for:

        # Mean reversion toward a slow anchor, which prevents random walk
        # blowups.

    A numerical guard rail, added so generated prices would not wander to
    absurdity. Every expectancy this project has published is, on this
    evidence, largely a measurement of it.

    What this does **not** show is that the strategy fails on real gold. It
    shows that the simulator cannot answer the question either way, which
    turns the real-history backtest from a nice-to-have into the only run
    that can produce a result.
    """
    from dataclasses import replace as _replace

    from . import simulate
    from .dayrange import DayRangeConfig, run as _run

    cfg = DayRangeConfig(risk_pct=None, lot=0.01, start_equity=432.0,
                         spread_usd_oz=spread_usd_oz)
    default = simulate.MarketParams(start_price=4_100.0)

    def measure_one(name: str, params) -> Ablation:
        rs: list[float] = []
        for i in range(markets):
            seed = seed_base + i * 97
            series = simulate.generate(bars=bars, timeframe="1m", seed=seed,
                                       params=params)
            rs.extend(_run(cfg, series=series, seed=seed).r_multiples)
        if len(rs) < 2:
            return Ablation(name, 0.0, 0.0, 0.0, len(rs))
        mean = statistics.fmean(rs)
        se = statistics.stdev(rs) / math.sqrt(len(rs))
        return Ablation(name, mean, mean - 1.96 * se, mean + 1.96 * se,
                        len(rs))

    variants = (
        ("ohne Liquidity-Sweep", _replace(default, sweep_probability=0.0)),
        ("ohne Runde-Zahlen-Magnet", _replace(default, round_magnet=0.0)),
        ("ohne Spruenge", _replace(default, jump_probability=0.0)),
        ("ohne Mean-Reversion", _replace(default, reversion=0.0)),
        ("nichts davon", _replace(default, sweep_probability=0.0,
                                  round_magnet=0.0, jump_probability=0.0,
                                  reversion=0.0)),
    )
    return AblationFinding(
        baseline=measure_one("alles an (Standard)", default),
        variants=tuple(measure_one(name, params) for name, params in variants),
    )


def render_ablation(f: AblationFinding) -> str:
    lines = ["WORAUS BESTEHT DIE GEMESSENE KANTE?",
             "=" * 74,
             "  Ein Merkmal des Generators abgeschaltet, Kante neu gemessen.",
             "  Der Shuffle-Test zeigt, DASS die Kante an der Balkenreihenfolge",
             "  haengt. Er kann nicht sagen, WESSEN Struktur das ist. Das hier",
             "  kann es, weil die Merkmale des Generators Parameter sind.",
             "",
             f"  {'Variante':28s} {'Trades':>7s} {'Erwartung':>10s}  95%-Band"]
    for a in (f.baseline, *f.variants):
        mark = ""
        if a.high < 0:
            mark = "  <- verliert Geld"
        elif a.band_straddles_zero:
            mark = "  <- Kante weg"
        lines.append(f"  {a.name:28s} {a.trades:>7d} {a.expectancy_r:>+10.4f}  "
                     f"{a.low:+.4f} … {a.high:+.4f}{mark}")
    lines.append("")
    bearing = f.load_bearing
    if bearing:
        lines.append(f"  Tragend: {', '.join(bearing)}")
        lines.append("")
        lines.append("  `reversion` ist keine Aussage ueber Gold. Der Kommentar")
        lines.append("  im Generator sagt, wozu es da ist: „prevents random walk")
        lines.append("  blowups\" — eine Rechenschutzplanke, damit die erzeugten")
        lines.append("  Kurse nicht ins Absurde laufen.")
        lines.append("")
        lines.append("  Das heisst NICHT, dass die Strategie an echtem Gold")
        lines.append("  scheitert. Es heisst, dass der Simulator die Frage nicht")
        lines.append("  beantworten kann — und damit ist der Backtest auf echter")
        lines.append("  Historie nicht mehr wuenschenswert, sondern der einzige")
        lines.append("  Lauf, der ueberhaupt ein Ergebnis liefert.")
    else:
        lines.append("  Kein einzelnes Merkmal traegt die Kante allein.")
    return "\n".join(lines)
