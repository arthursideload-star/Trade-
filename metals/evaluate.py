"""Multi-run evaluation: how does the strategy behave across many markets?

A single backtest is one sample. It answers "what happened in this history",
which is the wrong question -- the right one is "what is the distribution of
outcomes this strategy produces, and how often is it negative".

So the evaluation runs the same configuration across many independently
generated markets and reports the distribution: median expectancy, the spread,
and the share of runs that lost money. A strategy whose median is positive but
which loses in 40% of runs is not a strategy, it is a coin flip with extra
steps.

This also provides the honest answer to "what is the success rate": not a
single number, but a distribution with a confidence interval and an explicit
statement of what the underlying data is.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import simulate
from .backtest import BacktestConfig, run


@dataclass
class RunSummary:
    seed: int
    trades: int
    win_rate: float | None
    expectancy_r: float | None
    total_r: float
    max_drawdown_r: float
    profit_factor: float | None


@dataclass
class Evaluation:
    label: str
    runs: list[RunSummary] = field(default_factory=list)
    config: BacktestConfig = field(default_factory=BacktestConfig)
    bars_per_run: int = 3000

    @property
    def completed(self) -> list[RunSummary]:
        return [r for r in self.runs if r.trades > 0]

    @property
    def total_trades(self) -> int:
        return sum(r.trades for r in self.runs)

    def _values(self, attr: str) -> list[float]:
        return [getattr(r, attr) for r in self.completed
                if getattr(r, attr) is not None]

    def median(self, attr: str) -> float | None:
        v = sorted(self._values(attr))
        if not v:
            return None
        mid = len(v) // 2
        return v[mid] if len(v) % 2 else (v[mid - 1] + v[mid]) / 2

    def mean(self, attr: str) -> float | None:
        v = self._values(attr)
        return sum(v) / len(v) if v else None

    def percentile(self, attr: str, pct: float) -> float | None:
        v = sorted(self._values(attr))
        if not v:
            return None
        idx = max(0, min(len(v) - 1, int(round(pct / 100 * (len(v) - 1)))))
        return v[idx]

    @property
    def losing_run_share(self) -> float | None:
        v = self._values("total_r")
        if not v:
            return None
        return sum(1 for x in v if x < 0) / len(v) * 100

    def pooled_expectancy_ci(self, z: float = 1.96) -> tuple[float, float] | None:
        """CI on expectancy pooling every trade across every run.

        Pooling is the right unit here: each trade is one observation, and
        which synthetic market it came from is not information the strategy
        had access to.
        """
        weighted: list[float] = []
        for r in self.completed:
            if r.expectancy_r is None:
                continue
            weighted.extend([r.expectancy_r] * r.trades)
        n = len(weighted)
        if n < 2:
            return None
        mean = sum(weighted) / n
        var = sum((v - mean) ** 2 for v in weighted) / (n - 1)
        se = math.sqrt(var / n)
        return mean - z * se, mean + z * se


def evaluate(config: BacktestConfig, runs: int = 100, bars: int = 3000,
             base_seed: int = 1000, label: str = "default",
             progress: bool = False) -> Evaluation:
    """Run the same config over `runs` independently generated markets."""
    ev = Evaluation(label=label, config=config, bars_per_run=bars)
    for i in range(runs):
        seed = base_seed + i * 17
        market = simulate.generate(bars=bars, timeframe="5m", seed=seed)
        result = run(market, config, data_source=f"sim seed {seed}")
        ev.runs.append(RunSummary(
            seed=seed,
            trades=result.n,
            win_rate=result.win_rate,
            expectancy_r=result.expectancy_r,
            total_r=result.total_r,
            max_drawdown_r=result.max_drawdown_r,
            profit_factor=result.profit_factor
            if result.profit_factor not in (None, float("inf")) else None,
        ))
        if progress and (i + 1) % 10 == 0:
            print(f"  ... {i + 1}/{runs} runs", flush=True)
    return ev


def report(ev: Evaluation) -> str:
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append(f"  EVALUATION: {ev.label}")
    lines.append("=" * 72)
    lines.append(f"  runs             {len(ev.runs)} independent markets, "
                 f"{ev.bars_per_run:,} M5 bars each")
    lines.append(f"  runs with trades {len(ev.completed)}")
    lines.append(f"  total trades     {ev.total_trades:,}")

    if not ev.completed:
        lines.append("\n  No run produced a trade. The filters are too tight "
                     "or the detectors never fire.")
        lines.append("=" * 72)
        return "\n".join(lines)

    lines.append("")
    lines.append(f"  win rate       median {_f(ev.median('win_rate'), '%.1f%%')}   "
                 f"[p10 {_f(ev.percentile('win_rate', 10), '%.1f')} .. "
                 f"p90 {_f(ev.percentile('win_rate', 90), '%.1f')}]")
    lines.append(f"  expectancy     median {_f(ev.median('expectancy_r'), '%+.3f')}R  "
                 f"[p10 {_f(ev.percentile('expectancy_r', 10), '%+.3f')} .. "
                 f"p90 {_f(ev.percentile('expectancy_r', 90), '%+.3f')}]")
    lines.append(f"  total per run  median {_f(ev.median('total_r'), '%+.1f')}R   "
                 f"[p10 {_f(ev.percentile('total_r', 10), '%+.1f')} .. "
                 f"p90 {_f(ev.percentile('total_r', 90), '%+.1f')}]")
    lines.append(f"  max drawdown   median {_f(ev.median('max_drawdown_r'), '%.1f')}R  "
                 f"worst {_f(ev.percentile('max_drawdown_r', 0), '%.1f')}R")
    lines.append(f"  trades per run median "
                 f"{_f(ev.median('trades'), '%.0f')}")

    losing = ev.losing_run_share
    lines.append("")
    lines.append(f"  LOSING RUNS    {losing:.0f}% of markets ended negative")

    ci = ev.pooled_expectancy_ci()
    if ci:
        lines.append(f"  95% CI on pooled expectancy: "
                     f"[{ci[0]:+.3f}R, {ci[1]:+.3f}R]")
        if ci[0] > 0:
            verdict = ("positive expectancy across the whole sample -- in this "
                       "synthetic market")
        elif ci[1] < 0:
            verdict = ("NEGATIVE expectancy across the whole sample. This "
                       "configuration loses money.")
        else:
            verdict = ("interval spans zero -- no edge demonstrated even at "
                       "this sample size")
        lines.append(f"  -> {verdict}")

    lines.append("=" * 72)
    return "\n".join(lines)


def compare(evaluations: list[Evaluation]) -> str:
    """Side-by-side table of several configurations."""
    lines: list[str] = []
    lines.append("=" * 96)
    lines.append("  CONFIGURATION COMPARISON")
    lines.append("=" * 96)
    lines.append(f"  {'configuration':<34} {'trades':>7} {'win%':>7} "
                 f"{'exp R':>9} {'losing runs':>12} {'median R':>10}")
    lines.append("  " + "-" * 92)
    for ev in evaluations:
        lines.append(
            f"  {ev.label:<34} {ev.total_trades:>7,} "
            f"{_f(ev.median('win_rate'), '%.1f'):>7} "
            f"{_f(ev.median('expectancy_r'), '%+.3f'):>9} "
            f"{_f(ev.losing_run_share, '%.0f%%'):>12} "
            f"{_f(ev.median('total_r'), '%+.1f'):>10}"
        )
    lines.append("=" * 96)
    return "\n".join(lines)


def _f(value, fmt: str) -> str:
    return "n/a" if value is None else fmt % value


# --- The experiment grid ----------------------------------------------------
#
# These are the configurations worth comparing, chosen because the first
# backtest exposed a specific structural problem: taking 60% off at 1R caps
# the average win near 0.6R while losses stay at 1.0R, which needs a ~62% win
# rate merely to break even. Each variant attacks that from a different angle.

def experiment_grid() -> dict[str, BacktestConfig]:
    base = dict(symbol="XAUUSD", spread_usd_oz=0.20, slippage_fraction=0.5,
                style="scalp", min_confidence=0.50, max_trades_per_day=4)

    def cfg(**overrides) -> BacktestConfig:
        return BacktestConfig(**{**base, **overrides})

    return {
        "A baseline 60% at 1R": cfg(),
        "B 33% at 1R (smaller partial)": cfg(first_target_fraction=0.33),
        "C first target at 1.5R": cfg(first_target_r=1.5),
        "D no partial, single 2R target": cfg(first_target_fraction=0.0,
                                              runner_target_r=2.0),
        "E wider trail (2.0x ATR)": cfg(trail_atr_multiple=2.0),
        "F longer time stop (120 min)": cfg(time_stop_minutes=120),
        "G 33% at 1.5R + wide trail": cfg(first_target_fraction=0.33,
                                          first_target_r=1.5,
                                          trail_atr_multiple=2.0,
                                          time_stop_minutes=120),
        "H higher confidence bar (0.60)": cfg(min_confidence=0.60),
        "I overlap session only": cfg(scalp_sessions=("london_ny_overlap",)),
        "J zero spread (cost check)": cfg(spread_usd_oz=0.0,
                                          slippage_fraction=0.0),
    }
