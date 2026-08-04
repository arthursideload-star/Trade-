"""The half-target scalp: many short trades, banked at half the projection.

Described by the user on 04.08.2026 and implemented here as described:

    The bot watches the chart continuously. As soon as it sees an
    opportunity it takes it. It forms a target -- how far the move would
    plausibly go -- and closes at **half** of that target, for safety. It
    also sets a stop. A trade lasts one to ten minutes; then it watches for
    another one to ten minutes and trades again.

This is a real and named technique. Banking early raises the hit rate,
because a half-distance target is reached far more often than a full one.
That part of the intuition is correct and this module does not argue with it.

What the module does insist on is the other half of the trade, because it is
the half that decides the outcome and it is invisible from the inside:

**Halving the target halves the reward, but not the risk.** With a target of
one measured move, a take at half of it and a stop at the full projection,
the trade risks more than it stands to make. The hit rate has to carry the
whole strategy, and the level it has to carry it to is arithmetic, not
opinion -- `RunResult.breakeven_win_rate` computes it and the report prints
it next to the observed one. If the observed rate is not clearly above it,
the strategy loses money while winning most of its trades, which is exactly
what it feels like it cannot do.

**At this horizon the spread is not a detail, it is the opponent.** A move
worth 1.5 USD/oz banked at half is 0.75 USD/oz gross. A 0.20 spread with
slippage costs 0.30 of it -- 40% of the gross result, on every trade, paid
whether the trade wins or loses. Sixty trades a day is sixty times that.
`RunResult.friction_r` reports what was paid, so the cost is a number in the
output rather than an assumption in the design.

Trades whose half-target does not clear the cost by `min_edge_multiple` are
**refused and counted** (`refused_cost`). A trade that cannot pay its own
spread is not a trade with a small edge; it is a trade with a negative one.

    from metals.halfscalp import HalfScalpConfig, run, report
    print(report(run(HalfScalpConfig())))
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime

from .candles import Candle, CandleSeries
from .indicators import atr
from .risk import MAX_RISK_PER_TRADE_PCT
from .specs import get_spec

# How the opportunity is recognised. Both are offered because the project has
# only ever measured reversion, and finding A27 showed that what it measured
# was largely the simulator's own reversion guard rail. A momentum variant
# that shares every other line of this file is the cheapest way to find out
# whether the direction of the edge is a property of the market or of the
# generator -- the two answers are distinguishable here and nowhere else.
SIGNALS = ("momentum", "reversion")

# How the spread is charged.
#
# "flat" charges one number all day. That is what every engine in this repo
# did until now, and for a strategy taking four trades inside the London/NY
# overlap it is roughly fair. For one taking a hundred and fifty a day it is
# not: a bot that watches the chart continuously watches it through the
# rollover too, and XAUUSD_SPEC puts the rollover spread at 5.00 USD/oz
# against a typical 0.20 -- twenty-five times.
#
# "session" charges what the session actually costs, derived from the same
# spec constants the rest of the project quotes.
SPREAD_MODELS = ("flat", "session")

# Multipliers on the spec's typical spread, by session quality.
#
# Provenance, because it differs by row and that matters more than the
# numbers: PRIME is 1.00 by definition -- the spec's typical figure describes
# the overlap. AVOID uses the spec's own `thin_spread_usd_oz`, which carries a
# source note in specs.py. **GOOD and MARGINAL are estimates**, placed inside
# the 0.20-0.40 band that SPREAD_NOTE quotes for standard conditions. They are
# the weakest numbers in this module and the first thing to replace with a
# reading off your own broker.
_QUALITY_SPREAD: dict[str, float] = {
    "prime": 1.00,
    "good": 1.25,
    "marginal": 2.00,
}


@dataclass(frozen=True)
class HalfScalpConfig:
    """One configuration. Every number that changes behaviour lives here."""

    symbol: str = "XAUUSD"
    start_equity: float = 1_000.0

    # --- what counts as an opportunity ------------------------------------
    # "reversion", not "momentum". The literal specification followed the
    # push and lost on 85 of 85 simulated days (A34); all nine momentum
    # variants in the grid were negative. A default is a claim about what
    # should run, and shipping the losing one as the default would be the
    # A33 mistake again -- two code paths that were supposed to be one.
    signal: str = "reversion"
    # The triggering bar must be at least this many ATRs. Below roughly one
    # ATR a bar is noise and the "projection" projects noise.
    #
    # 0.60 rather than 1.00, and the reason is a requirement rather than a
    # measurement. Out of sample on 30 markets that took no part in choosing
    # it:  0.6 -> +0.0284 R [+0.0172 .. +0.0397], a trade every 8.5 minutes
    #      1.0 -> +0.0412 R [+0.0293 .. +0.0531], a trade every 11.4 minutes
    # The slower setting earns more per trade and marginally more per hour.
    # 0.6 is the default because it is the one that delivers a trade at
    # least every ten minutes, which is what was asked for. The price of
    # that requirement is roughly 0.013 R per trade and it is written here
    # rather than left for someone to rediscover.
    trigger_atr: float = 0.60
    # ... and must have closed this decisively within its own range. 0.70
    # means the close sits in the outer 30%.
    close_position_min: float = 0.70

    # --- the target, and the half of it that gets taken -------------------
    # The projection is a measured move: the triggering impulse, continued.
    # `target_multiple` scales it, 1.0 being "as far again as it just came".
    #
    # 2.0, because the spread is fixed and the risk is not: doubling the
    # projection roughly halves the cost per R. At 1.0 the same strategy
    # measured +0.0056 R with a band across zero.
    target_multiple: float = 2.0
    # THE rule the user asked for. 0.5 = bank at half the projection.
    take_fraction: float = 0.5
    # The stop, as a fraction of the same projection.
    stop_fraction: float = 1.0
    # A stop is never tighter than this many ATRs, whatever the arithmetic
    # says. M1 noise on gold will take out anything closer, and a stop inside
    # the noise converts a winning idea into a losing one.
    min_stop_atr: float = 0.8

    # --- timing -----------------------------------------------------------
    max_hold_minutes: int = 10
    cooldown_minutes: int = 1
    # Refuse to open outside PRIME and GOOD windows. "Watch the chart
    # continuously" and "trade whenever it is open" are different
    # instructions, and the second one costs money -- the spread outside
    # those windows is two to twenty-five times the overlap figure.
    #
    # On by default because it is worth a measured +0.0182 R per trade
    # [+0.0122 .. +0.0243], paired over 24 markets (A35). Watching stays
    # continuous either way; only the opening of positions is restricted.
    session_filter: bool = True

    # --- costs ------------------------------------------------------------
    spread_usd_oz: float = 0.20
    slippage_fraction: float = 0.5
    # "flat" or "session" -- see SPREAD_MODELS. "session" by default: the flat
    # model reported this strategy at +0.0429 R per trade where charging by
    # session gives +0.0104, a fourfold inflation (A35). A default that
    # flatters is the failure this repository keeps writing findings about.
    spread_model: str = "session"
    # The half-target must clear the round-trip cost by this factor or the
    # trade is refused. 1.5 is deliberately modest; at 1.0 the strategy is
    # trading for the broker.
    min_edge_multiple: float = 1.5

    # --- risk -------------------------------------------------------------
    risk_pct: float = 1.0

    def __post_init__(self) -> None:
        if self.signal not in SIGNALS:
            raise ValueError(f"signal must be one of {SIGNALS}")
        if self.spread_model not in SPREAD_MODELS:
            raise ValueError(f"spread_model must be one of {SPREAD_MODELS}")

    @property
    def cost_per_unit(self) -> float:
        """Round-trip cost in USD/oz, same model as metals/backtest.py."""
        return self.spread_usd_oz * (1 + self.slippage_fraction)

    def spread_at(self, moment: datetime) -> float:
        """What the spread costs at this moment, in USD/oz.

        Under "flat" the answer never changes, which is the assumption this
        module inherited and the one most likely to flatter it.
        """
        if self.spread_model == "flat":
            return self.spread_usd_oz
        quality = _quality_at(moment)
        spec = get_spec(self.symbol)
        if quality in _QUALITY_SPREAD:
            return self.spread_usd_oz * _QUALITY_SPREAD[quality]
        # AVOID: rollover, deep Asia, Friday late. The spec's own thin figure,
        # scaled if the caller is modelling a broker with a different base.
        base = spec.typical_spread_usd_oz or self.spread_usd_oz
        return spec.thin_spread_usd_oz * (self.spread_usd_oz / base)

    def cost_at(self, moment: datetime) -> float:
        return self.spread_at(moment) * (1 + self.slippage_fraction)


# classify() does daylight-saving arithmetic per call, and this module asks it
# once per bar over tens of thousands of bars. Five-minute granularity is
# finer than any session boundary in sessions.py and turns the call into a
# dictionary lookup.
_QUALITY_CACHE: dict[tuple, str] = {}


def _quality_at(moment: datetime) -> str:
    from .sessions import classify

    key = (moment.year, moment.month, moment.day, moment.hour,
           moment.minute // 5)
    cached = _QUALITY_CACHE.get(key)
    if cached is None:
        cached = classify(moment).quality.value
        _QUALITY_CACHE[key] = cached
    return cached


@dataclass
class HalfTrade:
    """One completed round trip."""

    direction: str
    opened_at: datetime
    closed_at: datetime
    entry: float
    stop: float
    take: float
    projection: float
    exit_price: float
    exit_reason: str
    gross_r: float
    net_r: float
    minutes_held: int

    @property
    def won(self) -> bool:
        return self.net_r > 0


@dataclass
class RunResult:
    trades: list[HalfTrade] = field(default_factory=list)
    bars_tested: int = 0
    signals_seen: int = 0
    refused_cost: int = 0
    refused_stop: int = 0
    refused_session: int = 0
    # A position still open when the data ran out. Not a trade -- it has no
    # outcome -- but it consumed a signal, so without this the counters do
    # not add up to signals_seen and the arithmetic is quietly one short.
    left_open: int = 0
    config: HalfScalpConfig = field(default_factory=HalfScalpConfig)
    minutes_covered: int = 0

    # --- headline numbers -------------------------------------------------

    @property
    def n(self) -> int:
        return len(self.trades)

    @property
    def wins(self) -> int:
        return sum(1 for t in self.trades if t.won)

    @property
    def win_rate(self) -> float | None:
        return self.wins / self.n if self.n else None

    @property
    def expectancy_r(self) -> float | None:
        return statistics.fmean(t.net_r for t in self.trades) if self.n else None

    @property
    def total_r(self) -> float:
        return sum(t.net_r for t in self.trades)

    @property
    def friction_r(self) -> float:
        """What the spread and slippage cost, in R. Paid on every trade."""
        return sum(t.gross_r - t.net_r for t in self.trades)

    @property
    def trades_per_day(self) -> float | None:
        days = self.minutes_covered / (60 * 24)
        return self.n / days if days else None

    @property
    def mean_minutes_held(self) -> float | None:
        return (statistics.fmean(t.minutes_held for t in self.trades)
                if self.n else None)

    @property
    def payoff_ratio(self) -> float | None:
        """Mean win over mean loss. The half-target pushes this below 1."""
        wins = [t.net_r for t in self.trades if t.won]
        losses = [-t.net_r for t in self.trades if not t.won]
        if not wins or not losses:
            return None
        return statistics.fmean(wins) / statistics.fmean(losses)

    @property
    def breakeven_win_rate(self) -> float | None:
        """The hit rate this payoff needs just to break even.

        This is the number the "bank at half for safety" idea has to be
        judged against. Taking half the projection genuinely raises the hit
        rate -- and it raises this threshold at the same time. Whether the
        first rises further than the second is the entire question, and it
        is not answerable by reasoning about it.
        """
        ratio = self.payoff_ratio
        return None if ratio is None else 1.0 / (1.0 + ratio)

    @property
    def margin_over_breakeven(self) -> float | None:
        """Observed hit rate minus the one required. Negative means it loses."""
        observed, needed = self.win_rate, self.breakeven_win_rate
        return None if observed is None or needed is None else observed - needed


def _projection(cfg: HalfScalpConfig, bar: Candle, direction: str,
                a: float) -> float:
    """How far the move would plausibly go, in USD/oz.

    A measured move: the impulse just printed, continued by the same distance
    again. Floored at one ATR so that a narrow trigger bar cannot produce a
    projection smaller than the noise it sits in.
    """
    return max(bar.range, a) * cfg.target_multiple


def _entry_signal(cfg: HalfScalpConfig, bar: Candle,
                  a: float) -> str | None:
    """Is this bar an opportunity, and in which direction?"""
    if a <= 0 or bar.range < a * cfg.trigger_atr:
        return None

    position = bar.close_position
    if position >= cfg.close_position_min:
        pushed = "long"
    elif position <= 1.0 - cfg.close_position_min:
        pushed = "short"
    else:
        return None

    if cfg.signal == "momentum":
        return pushed
    # Reversion: the decisive bar is treated as stretched, and the trade is
    # taken against it.
    return "short" if pushed == "long" else "long"


def run(cfg: HalfScalpConfig | None = None,
        m1: CandleSeries | None = None) -> RunResult:
    """Walk M1 bars, taking every opportunity that can pay for itself.

    The loop sees bars `0..i` when deciding at bar `i`, so lookahead is
    structurally impossible rather than merely avoided. Within a bar the stop
    is assumed to be hit before the target whenever the bar's range covers
    both -- the opposite assumption produces a backtest that cannot be traded.
    """
    from .simulate import generate

    cfg = cfg or HalfScalpConfig()
    m1 = m1 if m1 is not None else generate(bars=5_000, timeframe="1m",
                                            symbol=cfg.symbol)
    result = RunResult(config=cfg)
    if len(m1) < 30:
        return result

    atr_series = atr(m1.highs, m1.lows, m1.closes, 14)

    # The cooldown is stated in minutes but applied as a bar count, so it has
    # to be converted rather than used raw. On M1 the two happen to coincide,
    # which is exactly why this was worth writing down: the moment the module
    # is pointed at a 5m file, an uncorrected `i + cooldown_minutes` would
    # wait five times too long and quietly change the strategy.
    per_bar = _minutes_per_bar(m1)
    cooldown_bars = max(1, math.ceil(cfg.cooldown_minutes / per_bar))

    open_trade: dict | None = None
    cooldown_until = 0

    for i in range(20, len(m1)):
        bar = m1[i]
        result.bars_tested += 1
        # Charged at the moment of the trade, not averaged over the day. The
        # difference is the whole point of the "session" model: a strategy
        # this frequent meets the rollover spread whether it planned to or not.
        cost = cfg.cost_at(bar.ts)

        # --- manage an open position first --------------------------------
        if open_trade is not None:
            closed = _try_close(open_trade, bar, cfg, cost, result)
            if closed:
                open_trade = None
                cooldown_until = i + cooldown_bars
            continue

        if i < cooldown_until:
            continue

        a = atr_series[i]
        if not a:
            continue

        direction = _entry_signal(cfg, bar, a)
        if direction is None:
            continue
        result.signals_seen += 1

        # Checked after detection rather than before, so that this counts
        # refused *signals* and is comparable with refused_cost beside it in
        # the report. Checking first was cheaper and counted refused bars --
        # two different units printed as if they were one.
        if cfg.session_filter and _quality_at(bar.ts) not in ("prime", "good"):
            result.refused_session += 1
            continue

        projection = _projection(cfg, bar, direction, a)
        take_distance = projection * cfg.take_fraction
        stop_distance = max(projection * cfg.stop_fraction, a * cfg.min_stop_atr)

        # The gate that matters most at this horizon: a half-target that
        # cannot clear its own round-trip cost is not a small edge, it is a
        # negative one. Refused and counted, never silently taken.
        if take_distance < cost * cfg.min_edge_multiple:
            result.refused_cost += 1
            continue
        if stop_distance <= 0:
            result.refused_stop += 1
            continue

        entry = bar.close
        if direction == "long":
            stop = entry - stop_distance
            take = entry + take_distance
        else:
            stop = entry + stop_distance
            take = entry - take_distance

        open_trade = {
            "direction": direction, "entry": entry, "stop": stop,
            "take": take, "projection": projection,
            "risk": stop_distance, "opened_at": bar.ts, "opened_i": i,
            # Half the round trip is paid entering, half leaving. Under the
            # session model those two can be different numbers -- a trade
            # opened in the overlap and closed after the rollover starts pays
            # both, which is exactly the case a single average would hide.
            "cost_in": cost / 2.0,
        }

    if open_trade is not None:
        result.left_open = 1
    result.minutes_covered = (len(m1) - 20) * per_bar
    return result


def _minutes_per_bar(series: CandleSeries) -> int:
    return {"1m": 1, "5m": 5, "15m": 15, "1h": 60}.get(series.timeframe, 1)


def _try_close(trade: dict, bar: Candle, cfg: HalfScalpConfig,
               cost: float, result: RunResult) -> bool:
    """Close on stop, target or the time limit. Stop wins ties."""
    direction = trade["direction"]
    risk = trade["risk"]
    held = int((bar.ts - trade["opened_at"]).total_seconds() // 60)

    hit_stop = (bar.low <= trade["stop"] if direction == "long"
                else bar.high >= trade["stop"])
    hit_take = (bar.high >= trade["take"] if direction == "long"
                else bar.low <= trade["take"])

    if hit_stop:                       # pessimistic ordering, on purpose
        price, reason = trade["stop"], "stop"
    elif hit_take:
        price, reason = trade["take"], "half_target"
    elif held >= cfg.max_hold_minutes:
        price, reason = bar.close, "time"
    else:
        return False

    move = (price - trade["entry"]) if direction == "long" \
        else (trade["entry"] - price)
    gross_r = move / risk if risk else 0.0
    paid = trade["cost_in"] + cost / 2.0
    net_r = gross_r - (paid / risk if risk else 0.0)

    result.trades.append(HalfTrade(
        direction=direction, opened_at=trade["opened_at"], closed_at=bar.ts,
        entry=trade["entry"], stop=trade["stop"], take=trade["take"],
        projection=trade["projection"], exit_price=price, exit_reason=reason,
        gross_r=gross_r, net_r=net_r, minutes_held=max(held, 1),
    ))
    return True


def report(result: RunResult) -> str:
    cfg = result.config
    lines = [
        "Half-target scalp",
        f"  Signal          {cfg.signal}",
        f"  Target          measured move x {cfg.target_multiple:g}, "
        f"banked at {cfg.take_fraction:.0%}",
        f"  Stop            {cfg.stop_fraction:g} x projection, "
        f"never under {cfg.min_stop_atr:g} ATR",
        f"  Hold            up to {cfg.max_hold_minutes} min, then "
        f"{cfg.cooldown_minutes} min cooldown",
        f"  Spread          {cfg.spread_usd_oz:.2f} USD/oz "
        f"(+{cfg.slippage_fraction:.0%} slippage = "
        f"{cfg.cost_per_unit:.2f} round trip), charged {cfg.spread_model}",
        "",
        f"  Bars            {result.bars_tested}",
        f"  Signals seen    {result.signals_seen}",
        f"  Refused: cost   {result.refused_cost}   "
        f"(half-target under {cfg.min_edge_multiple:g}x the round trip)",
        f"  Refused: window {result.refused_session}   "
        f"(session filter {'on' if cfg.session_filter else 'off'})",
        f"  Trades          {result.n}",
    ]
    if result.trades_per_day is not None:
        lines.append(f"  Per day         {result.trades_per_day:.1f}")
    if result.mean_minutes_held is not None:
        lines.append(f"  Held            {result.mean_minutes_held:.1f} min "
                     f"on average")
    if not result.n:
        lines.append("")
        lines.append("  No trades. Nothing to judge.")
        return "\n".join(lines)

    lines += [
        "",
        f"  Win rate        {result.win_rate:.1%} "
        f"({result.wins} of {result.n})",
        f"  Expectancy      {result.expectancy_r:+.4f} R per trade",
        f"  Total           {result.total_r:+.1f} R",
        f"  Paid in costs   {result.friction_r:.1f} R",
    ]

    ratio = result.payoff_ratio
    needed = result.breakeven_win_rate
    margin = result.margin_over_breakeven
    if ratio is not None and needed is not None and margin is not None:
        lines += [
            "",
            f"  Payoff ratio    {ratio:.2f}  (mean win / mean loss)",
            f"  Break-even at   {needed:.1%} win rate",
            f"  Margin          {margin:+.1%}",
            "",
        ]
        if margin > 0:
            lines.append("  The hit rate clears what the payoff demands. "
                         "Whether it clears it by more than the noise is a "
                         "separate question -- see metals.journal for bands.")
        else:
            lines.append("  The hit rate does NOT clear what the payoff "
                         "demands. Banking at half raised the win rate and "
                         "raised the bar by more. This is the failure mode "
                         "that feels like success from the inside: most "
                         "trades win and the account still falls.")

    by_reason: dict[str, int] = {}
    for t in result.trades:
        by_reason[t.exit_reason] = by_reason.get(t.exit_reason, 0) + 1
    lines.append("")
    lines.append("  Exits: " + ", ".join(f"{k} {v}"
                                         for k, v in sorted(by_reason.items())))
    return "\n".join(lines)
