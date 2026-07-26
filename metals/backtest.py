"""Backtest engine and performance metrics.

Design decisions that determine whether the numbers mean anything:

* **No lookahead.** The detector at bar `i` sees only bars `0..i`. The series
  is sliced, not indexed with a window that reaches forward.
* **Stop before target.** When one bar's range covers both, the stop is
  assumed hit first. Every backtest that assumes otherwise reports a number it
  cannot achieve.
* **Costs are always charged.** Spread on entry and exit, plus configurable
  slippage. A gold scalp with a 3 USD/oz stop starts 6.7% of its risk behind
  at a 0.20 spread; a backtest that omits this is measuring a different
  strategy.
* **Results are reported in R, not currency.** R multiples are comparable
  across account sizes and volatility regimes; currency is not.
* **Sample size is reported next to every number.** A win rate on 12 trades is
  not a win rate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

from .candles import CandleSeries
from .exits import ExitReason, PositionState, advance, build_exit_plan
from .indicators import atr
from .levels import build_level_map
from .scalping import MIN_SCALP_STOP_ATR, detect_scalps
from .sessions import Quality, classify


@dataclass
class Trade:
    """One completed round trip."""

    setup_id: str
    symbol: str
    direction: str
    opened_at: datetime
    closed_at: datetime | None
    entry: float
    stop: float
    exit_price: float | None
    exit_reason: ExitReason
    gross_r: float
    net_r: float
    mfe_r: float
    mae_r: float
    confidence: float
    bars_held: int
    session: str

    @property
    def won(self) -> bool:
        return self.net_r > 0


@dataclass
class BacktestConfig:
    symbol: str = "XAUUSD"
    spread_usd_oz: float = 0.20
    # Extra adverse fill beyond the spread, as a fraction of the spread.
    slippage_fraction: float = 0.5
    style: str = "scalp"
    min_confidence: float = 0.50
    # Bars to wait after a trade closes before taking the next signal.
    cooldown_bars: int = 3
    max_trades_per_day: int = 4
    session_filter: bool = True
    warmup_bars: int = 120
    # How often the level map is rebuilt, in bars. Swing structure does not
    # change inside half an hour, and rebuilding it every bar dominates the
    # runtime of a multi-run evaluation.
    level_refresh_bars: int = 6
    # Sessions a scalp may be taken in. Empty means all. The Tokyo session is
    # excluded by default: it is thin enough on gold that the spread alone
    # outweighs the edge, which the first backtest showed clearly.
    scalp_sessions: tuple[str, ...] = ("london", "new_york", "london_ny_overlap")
    # Exit-plan overrides, so a parameter sweep does not need to touch exits.py.
    first_target_r: float | None = None
    first_target_fraction: float | None = None
    runner_target_r: float | None = None
    trail_atr_multiple: float | None = None
    time_stop_minutes: int | None = None


@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    bars_tested: int = 0
    signals_generated: int = 0
    signals_rejected: dict[str, int] = field(default_factory=dict)
    bars_skipped: dict[str, int] = field(default_factory=dict)
    config: BacktestConfig = field(default_factory=BacktestConfig)
    data_source: str = "unknown"

    # --- headline metrics ---

    @property
    def n(self) -> int:
        return len(self.trades)

    @property
    def wins(self) -> int:
        return sum(1 for t in self.trades if t.won)

    @property
    def win_rate(self) -> float | None:
        return self.wins / self.n * 100 if self.n else None

    @property
    def expectancy_r(self) -> float | None:
        return sum(t.net_r for t in self.trades) / self.n if self.n else None

    @property
    def total_r(self) -> float:
        return sum(t.net_r for t in self.trades)

    @property
    def gross_expectancy_r(self) -> float | None:
        """Expectancy before costs -- the gap to net is what the broker takes."""
        return sum(t.gross_r for t in self.trades) / self.n if self.n else None

    @property
    def profit_factor(self) -> float | None:
        gains = sum(t.net_r for t in self.trades if t.net_r > 0)
        losses = -sum(t.net_r for t in self.trades if t.net_r < 0)
        if losses <= 0:
            return None if gains <= 0 else float("inf")
        return gains / losses

    @property
    def avg_win_r(self) -> float | None:
        w = [t.net_r for t in self.trades if t.net_r > 0]
        return sum(w) / len(w) if w else None

    @property
    def avg_loss_r(self) -> float | None:
        l = [t.net_r for t in self.trades if t.net_r < 0]
        return sum(l) / len(l) if l else None

    @property
    def max_drawdown_r(self) -> float:
        peak = running = 0.0
        worst = 0.0
        for t in self.trades:
            running += t.net_r
            peak = max(peak, running)
            worst = min(worst, running - peak)
        return worst

    @property
    def max_consecutive_losses(self) -> int:
        worst = run = 0
        for t in self.trades:
            run = run + 1 if not t.won else 0
            worst = max(worst, run)
        return worst

    def expectancy_ci(self, z: float = 1.96) -> tuple[float, float] | None:
        """Confidence interval on expectancy.

        The most important number in the whole report and the one most often
        omitted. If the interval spans zero, the strategy has not been shown
        to have an edge -- regardless of how good the point estimate looks.
        """
        if self.n < 2:
            return None
        values = [t.net_r for t in self.trades]
        mean = sum(values) / self.n
        var = sum((v - mean) ** 2 for v in values) / (self.n - 1)
        se = math.sqrt(var / self.n)
        return mean - z * se, mean + z * se

    @property
    def edge_is_established(self) -> bool:
        """True only when the confidence interval on expectancy clears zero."""
        ci = self.expectancy_ci()
        return bool(ci and ci[0] > 0 and self.n >= 30)

    def by_setup(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for t in self.trades:
            b = out.setdefault(t.setup_id, {"n": 0, "wins": 0, "total_r": 0.0})
            b["n"] += 1
            b["wins"] += 1 if t.won else 0
            b["total_r"] += t.net_r
        for b in out.values():
            b["win_rate"] = b["wins"] / b["n"] * 100
            b["expectancy_r"] = b["total_r"] / b["n"]
        return out

    def by_exit_reason(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for t in self.trades:
            out[t.exit_reason.value] = out.get(t.exit_reason.value, 0) + 1
        return out

    def by_session(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for t in self.trades:
            b = out.setdefault(t.session, {"n": 0, "wins": 0, "total_r": 0.0})
            b["n"] += 1
            b["wins"] += 1 if t.won else 0
            b["total_r"] += t.net_r
        for b in out.values():
            b["win_rate"] = b["wins"] / b["n"] * 100
            b["expectancy_r"] = b["total_r"] / b["n"]
        return out


def run(m5: CandleSeries, config: BacktestConfig | None = None,
        m1: CandleSeries | None = None,
        data_source: str = "unknown") -> BacktestResult:
    """Walk the series bar by bar, taking every qualifying signal.

    The loop is deliberately simple and slow rather than vectorised: the
    detectors see a sliced series, which makes lookahead structurally
    impossible rather than merely avoided by discipline.
    """
    cfg = config or BacktestConfig()
    result = BacktestResult(config=cfg, data_source=data_source)

    cost_per_unit = cfg.spread_usd_oz * (1 + cfg.slippage_fraction)

    open_state: PositionState | None = None
    open_trade_meta: dict | None = None
    cooldown = 0
    trades_today = 0
    current_day = None
    level_map = None
    level_map_at = -10 ** 9

    atr_series = atr(m5.highs, m5.lows, m5.closes, 14)

    for i in range(cfg.warmup_bars, len(m5)):
        bar = m5[i]
        result.bars_tested += 1

        if current_day != bar.ts.date():
            current_day = bar.ts.date()
            trades_today = 0

        a = atr_series[i]
        if not a:
            continue

        # --- manage an open position first --------------------------------
        if open_state is not None and not open_state.closed:
            open_state = advance(open_state, bar, a)
            if open_state.closed:
                result.trades.append(_finalise(open_state, open_trade_meta,
                                               bar, cost_per_unit, i))
                open_state = None
                open_trade_meta = None
                cooldown = cfg.cooldown_bars
            continue

        if cooldown > 0:
            cooldown -= 1
            continue

        # These two skip the bar before any detector runs, so they are counted
        # as bars skipped rather than signals rejected -- conflating them
        # inflates the rejection count by three orders of magnitude and makes
        # the report look like the filters are doing far more than they are.
        if trades_today >= cfg.max_trades_per_day:
            result.bars_skipped["daily trade limit"] = (
                result.bars_skipped.get("daily trade limit", 0) + 1)
            continue

        session = classify(bar.ts)
        if cfg.session_filter and session.quality is Quality.AVOID:
            result.bars_skipped["session closed or avoid"] = (
                result.bars_skipped.get("session closed or avoid", 0) + 1)
            continue
        if cfg.scalp_sessions and session.session.value not in cfg.scalp_sessions:
            result.bars_skipped["outside the allowed scalping sessions"] = (
                result.bars_skipped.get(
                    "outside the allowed scalping sessions", 0) + 1)
            continue

        # --- look for a signal on the closed history only ------------------
        history = CandleSeries(m5.symbol, m5.timeframe,
                               m5.candles[:i + 1], m5.source)
        m1_history = None
        if m1 is not None:
            m1_history = CandleSeries(
                m1.symbol, m1.timeframe,
                [c for c in m1.candles if c.ts <= bar.ts][-120:], m1.source,
            )

        # The level map is expensive (swing detection over 200 bars) and does
        # not change materially inside half an hour, so it is rebuilt every
        # `level_refresh_bars` and reused in between. Prices used for the
        # round-number grid still come from the current bar.
        if (level_map is None or i - level_map_at >= cfg.level_refresh_bars):
            level_map = build_level_map(cfg.symbol, bar.close, history,
                                        history, bar.ts)
            level_map_at = i
        else:
            level_map.price = bar.close

        signals = detect_scalps(cfg.symbol, history, m1_history, level_map,
                                bar.ts, session, cfg.spread_usd_oz,
                                atr_value=a)
        if not signals:
            continue
        result.signals_generated += 1

        sig = signals[0]
        if sig.confidence < cfg.min_confidence:
            _reject(result, "below confidence threshold")
            continue

        stop_distance = abs(sig.entry - sig.structural_level)
        if stop_distance < a * MIN_SCALP_STOP_ATR:
            _reject(result, "stop inside the noise band")
            continue

        plan = build_exit_plan(cfg.symbol, sig.direction, sig.entry,
                               sig.structural_level, a, cfg.style)
        if cfg.first_target_r is not None:
            plan.first_target_r = cfg.first_target_r
        if cfg.first_target_fraction is not None:
            plan.first_target_fraction = cfg.first_target_fraction
        if cfg.runner_target_r is not None:
            plan.runner_target_r = cfg.runner_target_r
        if cfg.trail_atr_multiple is not None:
            plan.trail_atr_multiple = cfg.trail_atr_multiple
        if cfg.time_stop_minutes is not None:
            plan.time_stop_minutes = cfg.time_stop_minutes
        open_state = PositionState(plan=plan, opened_at=bar.ts)
        open_trade_meta = {
            "setup_id": sig.setup_id,
            "confidence": sig.confidence,
            "session": session.session.value,
            "entry_index": i,
            "atr": a,
        }
        trades_today += 1

    # An unclosed position at the end of the data is discarded rather than
    # marked to market: counting it either way biases the result, and dropping
    # it is the only choice that does not.
    return result


def _reject(result: BacktestResult, reason: str) -> None:
    result.signals_rejected[reason] = result.signals_rejected.get(reason, 0) + 1


def _finalise(state: PositionState, meta: dict, bar, cost_per_unit: float,
              index: int) -> Trade:
    plan = state.plan
    gross_r = state.realised_r
    # Cost is charged twice -- once entering, once leaving -- expressed in R.
    cost_r = (2 * cost_per_unit / plan.risk_per_unit) if plan.risk_per_unit else 0.0
    net_r = gross_r - cost_r

    return Trade(
        setup_id=meta["setup_id"],
        symbol=plan.symbol,
        direction=plan.direction,
        opened_at=state.opened_at,
        closed_at=bar.ts,
        entry=plan.entry,
        stop=plan.initial_stop,
        exit_price=state.exit_price,
        exit_reason=state.exit_reason,
        gross_r=gross_r,
        net_r=net_r,
        mfe_r=state.mfe_r,
        mae_r=state.mae_r,
        confidence=meta["confidence"],
        bars_held=index - meta["entry_index"],
        session=meta["session"],
    )


# --- Reporting --------------------------------------------------------------

def report(result: BacktestResult) -> str:
    """Human-readable report that refuses to overstate what it measured."""
    lines: list[str] = []
    r = result
    lines.append("=" * 72)
    lines.append("  BACKTEST RESULT")
    lines.append("=" * 72)
    lines.append(f"  data source     {r.data_source}")
    lines.append(f"  bars tested     {r.bars_tested:,}")
    lines.append(f"  signals seen    {r.signals_generated:,}")
    lines.append(f"  trades taken    {r.n:,}")

    if r.n == 0:
        lines.append("\n  No trades. Rejection reasons:")
        for k, v in sorted(r.signals_rejected.items(), key=lambda x: -x[1]):
            lines.append(f"    {v:6,}  {k}")
        lines.append("=" * 72)
        return "\n".join(lines)

    lines.append("")
    lines.append(f"  win rate        {r.win_rate:.1f}%  ({r.wins}W / "
                 f"{r.n - r.wins}L)")
    lines.append(f"  expectancy      {r.expectancy_r:+.3f}R per trade")
    lines.append(f"  gross (no cost) {r.gross_expectancy_r:+.3f}R  "
                 f"-> costs take {r.gross_expectancy_r - r.expectancy_r:.3f}R")
    pf = r.profit_factor
    lines.append("  profit factor   "
                 + (f"{pf:.2f}" if pf and pf != float('inf') else "n/a"))
    if r.avg_win_r is not None:
        lines.append(f"  avg win         {r.avg_win_r:+.2f}R")
    if r.avg_loss_r is not None:
        lines.append(f"  avg loss        {r.avg_loss_r:+.2f}R")
    lines.append(f"  total           {r.total_r:+.1f}R")
    lines.append(f"  max drawdown    {r.max_drawdown_r:.1f}R")
    lines.append(f"  worst streak    {r.max_consecutive_losses} losses in a row")

    ci = r.expectancy_ci()
    if ci:
        lines.append("")
        lines.append(f"  95% CI on expectancy: [{ci[0]:+.3f}R, {ci[1]:+.3f}R]")
        if ci[0] > 0:
            lines.append("  -> the interval clears zero: an edge is present in "
                         "this data")
        elif ci[1] < 0:
            lines.append("  -> the interval is entirely below zero: this loses "
                         "money in this data")
        else:
            lines.append("  -> the interval SPANS ZERO: no edge has been "
                         "demonstrated. The point estimate is not evidence; "
                         "with this many trades it is consistent with random.")

    if r.n < 30:
        lines.append(f"\n  WARNING: {r.n} trades is below the 30 needed for any "
                     f"of the above to mean anything.")

    lines.append("\n  BY SETUP")
    lines.append("  " + "-" * 68)
    for setup_id, b in sorted(r.by_setup().items()):
        flag = "" if b["n"] >= 30 else "   (sample too small)"
        lines.append(f"    {setup_id}  n={b['n']:4d}  win {b['win_rate']:5.1f}%  "
                     f"exp {b['expectancy_r']:+.3f}R{flag}")

    lines.append("\n  BY SESSION")
    lines.append("  " + "-" * 68)
    for sess, b in sorted(r.by_session().items()):
        flag = "" if b["n"] >= 30 else "   (sample too small)"
        lines.append(f"    {sess:20s}  n={b['n']:4d}  win {b['win_rate']:5.1f}%  "
                     f"exp {b['expectancy_r']:+.3f}R{flag}")

    lines.append("\n  EXCURSIONS (what the trades actually did while open)")
    lines.append("  " + "-" * 68)
    winners = [t for t in r.trades if t.won]
    losers = [t for t in r.trades if not t.won]
    if winners:
        mae_w = sum(t.mae_r for t in winners) / len(winners)
        mfe_w = sum(t.mfe_r for t in winners) / len(winners)
        lines.append(f"    winners  avg MAE {mae_w:+.2f}R   avg MFE {mfe_w:+.2f}R")
        if mae_w > -0.35:
            lines.append(f"      -> winners rarely went more than "
                         f"{abs(mae_w):.2f}R against you. The stop is wider "
                         f"than it needs to be; a tighter one would raise the "
                         f"R multiple on every win.")
    if losers:
        mfe_l = sum(t.mfe_r for t in losers) / len(losers)
        lines.append(f"    losers   avg MFE {mfe_l:+.2f}R")
        if mfe_l > 0.6:
            lines.append(f"      -> losers reached {mfe_l:.2f}R in profit "
                         f"before failing. Banking a partial earlier would "
                         f"convert a share of these into scratches.")

    lines.append("\n  HOW TRADES ENDED")
    lines.append("  " + "-" * 68)
    for reason, count in sorted(r.by_exit_reason().items(), key=lambda x: -x[1]):
        lines.append(f"    {reason:16s} {count:4d}  ({count / r.n * 100:.0f}%)")

    if r.signals_rejected:
        lines.append("\n  SIGNALS REJECTED (a detector fired, a filter refused it)")
        lines.append("  " + "-" * 68)
        for k, v in sorted(r.signals_rejected.items(), key=lambda x: -x[1])[:6]:
            lines.append(f"    {v:6,}  {k}")

    if r.bars_skipped:
        lines.append("\n  BARS SKIPPED BEFORE ANY DETECTOR RAN")
        lines.append("  " + "-" * 68)
        for k, v in sorted(r.bars_skipped.items(), key=lambda x: -x[1])[:6]:
            lines.append(f"    {v:6,}  {k}")

    lines.append("\n  COSTS")
    lines.append("  " + "-" * 68)
    lines.append(f"    spread {r.config.spread_usd_oz:.3f} USD/oz + "
                 f"{r.config.slippage_fraction:.0%} slippage, charged on "
                 f"entry and exit")

    lines.append("=" * 72)
    return "\n".join(lines)
