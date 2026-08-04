"""Scalping setups for gold, on M5 with M1 confirmation.

Why M5 and not M1: M1 on gold is mostly spread and noise. The published
consensus across scalping sources is that M5 is the usable floor -- it filters
M1's noise while still producing several signals per session. M1 is used here
only for the entry trigger once an M5 setup has armed.

**The state machine.** Each setup is a four-phase machine rather than a
single-bar test:

    SCANNING -> ARMED -> WINDOW_OPEN -> ENTRY

A setup that arms can also *invalidate* before it triggers, and most do. This
structure is borrowed from ilahuerta-IA/backtrader-pullback-window-xauusd
(MIT); the code here is written from scratch, the idea is what was taken. It
matters because a one-bar check cannot express "I was waiting for this, and
then the market did something that says I was wrong" -- and that distinction
is most of what separates a setup from a pattern.

**The economics of a gold scalp, stated up front.** With a 0.20 USD/oz spread
and a 3 USD/oz stop, every trade starts 6.7% of its risk behind. At four
trades a day that is a meaningful, permanent drag that the win rate has to
overcome before anything is left. This is why S6 exists (spread gate) and why
the module refuses setups whose stop is small relative to the spread.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .candles import Candle, CandleSeries
from .indicators import atr, ema
from .levels import LevelMap
from .patterns import detect_sweep, engulfing, pin_bar
from .sessions import SessionState, classify
from .specs import get_spec


class Phase(str, Enum):
    SCANNING = "scanning"        # nothing yet
    ARMED = "armed"              # precondition met, waiting for the pullback
    WINDOW_OPEN = "window_open"  # trigger level established, waiting for the break
    ENTRY = "entry"              # conditions met, trade is live
    INVALIDATED = "invalidated"  # the setup died before it triggered


@dataclass
class ScalpSignal:
    """A fired scalping setup."""

    setup_id: str
    name: str
    symbol: str
    direction: str
    entry: float
    structural_level: float
    confidence: float
    atr_value: float
    spread_used: float
    phase_log: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failure_mode: str = ""
    expected_hold_minutes: int = 30

    @property
    def risk_per_unit(self) -> float:
        return abs(self.entry - self.structural_level)

    @property
    def spread_as_pct_of_risk(self) -> float:
        return (self.spread_used / self.risk_per_unit * 100.0
                if self.risk_per_unit else 100.0)


@dataclass(frozen=True)
class ScalpSpec:
    setup_id: str
    name: str
    idea: str
    phases: str
    entry_rule: str
    stop_rule: str
    exit_rule: str
    failure_mode: str
    best_window: str
    base_confidence: float
    expected_hold_minutes: int


CATALOGUE: dict[str, ScalpSpec] = {
    "S1": ScalpSpec(
        setup_id="S1",
        name="Killzone Sweep Scalp",
        idea=(
            "The M5 version of G1. Price sweeps a session extreme inside a "
            "killzone, closes back inside, and the first M1 structure break "
            "is the entry. Shorter horizon than G1 and correspondingly "
            "tighter targets: this is a move of 1-3 ATR, not a session trend."
        ),
        phases=(
            "SCANNING: inside a killzone with a defined session extreme. "
            "ARMED: price trades beyond the extreme. "
            "WINDOW_OPEN: an M5 bar closes back inside; the sweep extreme "
            "becomes the invalidation. "
            "ENTRY: M1 closes beyond the M5 sweep bar in the reversal "
            "direction. "
            "INVALIDATED: two consecutive M5 closes outside -- it was a "
            "breakout."
        ),
        entry_rule="M1 close beyond the sweep bar, inside the killzone only.",
        stop_rule="0.35x ATR(14) M5 beyond the sweep extreme.",
        exit_rule="60% at 1R, remainder trailed by 1.2x ATR, time stop 45 min.",
        failure_mode=(
            "The sweep is a genuine breakout and the second bar closes outside "
            "too. Entering on the first close back inside without waiting for "
            "the M1 confirmation roughly doubles the number of these."
        ),
        best_window="London killzone and NY killzone only",
        base_confidence=0.62,
        expected_hold_minutes=35,
    ),
    "S2": ScalpSpec(
        setup_id="S2",
        name="Pullback Window Break",
        idea=(
            "An M5 EMA stack establishes direction, price pulls back one to "
            "three counter-trend candles, and the break of that small "
            "pullback's extreme is the entry. The pullback depth cap is the "
            "important part: a pullback deeper than three bars is no longer a "
            "pause, it is a reversal in progress."
        ),
        phases=(
            "SCANNING: EMA9 > EMA21 > EMA50 on M5 (or reverse) with a positive "
            "slope. "
            "ARMED: 1-3 counter-trend candles print. "
            "WINDOW_OPEN: the pullback's extreme becomes the trigger level. "
            "ENTRY: an M5 close beyond that level in the trend direction. "
            "INVALIDATED: a fourth counter-trend candle, or the EMA stack "
            "breaking."
        ),
        entry_rule="M5 close beyond the pullback extreme in the trend direction.",
        stop_rule="0.35x ATR(14) M5 beyond the pullback extreme.",
        exit_rule="60% at 1R, remainder trailed, time stop 45 min.",
        failure_mode=(
            "The EMA stack is flat and the 'trend' is a range. The slope "
            "filter exists for this; without it the setup fires all day in "
            "chop and loses on the spread alone."
        ),
        best_window="London and NY sessions",
        base_confidence=0.58,
        expected_hold_minutes=30,
    ),
    "S3": ScalpSpec(
        setup_id="S3",
        name="Prior-Day Sweep with Bias Filter",
        idea=(
            "A sweep of the prior day's high or low, filtered by the prior "
            "day's own direction: after a bullish day, only take sweeps of "
            "the prior low (long); after a bearish day, only sweeps of the "
            "prior high (short). The filter is the whole point -- it halves "
            "the signal count and removes most of the trend-day losses that "
            "an unfiltered version collects."
        ),
        phases=(
            "SCANNING: prior day's range and direction known. "
            "ARMED: price breaches the bias-appropriate extreme. "
            "WINDOW_OPEN: an M5 close back inside. "
            "ENTRY: M1 structure break. "
            "INVALIDATED: the breach holds for three M5 closes."
        ),
        entry_rule="M1 structure break after an M5 close back inside the range.",
        stop_rule="0.4x ATR(14) M5 beyond the sweep extreme.",
        exit_rule=(
            "First target the sweep point itself, then the opposite prior-day "
            "extreme."
        ),
        failure_mode=(
            "A trend day, where the prior extreme breaks and never returns. "
            "The bias filter catches most but not all: on the third "
            "consecutive day in one direction, skip this setup entirely."
        ),
        best_window="London open through NY open",
        base_confidence=0.60,
        expected_hold_minutes=45,
    ),
    "S4": ScalpSpec(
        setup_id="S4",
        name="Round-Number Fade",
        idea=(
            "Price runs into a 10 or 50 handle after an extended move and "
            "rejects it. The scalping version of G4: smaller target, tighter "
            "horizon, and strictly first or second touch only."
        ),
        phases=(
            "SCANNING: a major handle within 1.5x ATR. "
            "ARMED: an extended approach of at least 2x ATR without a "
            "pullback. "
            "WINDOW_OPEN: an M5 rejection candle at the handle. "
            "ENTRY: M1 close away from the handle. "
            "INVALIDATED: an M5 close beyond the handle, or a third touch."
        ),
        entry_rule="M1 close away from the handle after an M5 rejection.",
        stop_rule="0.35x ATR beyond the rejection wick -- never on the handle.",
        exit_rule="First target the prior consolidation; 60/40 split.",
        failure_mode=(
            "The handle breaks and becomes support. After the second test in "
            "a session it is being accumulated against, not defended."
        ),
        best_window="Any liquid session",
        base_confidence=0.55,
        expected_hold_minutes=25,
    ),
    "S5": ScalpSpec(
        setup_id="S5",
        name="Momentum Continuation after Impulse",
        idea=(
            "A single M5 bar of at least 1.5x ATR with a close in the top or "
            "bottom 20% of its range is a repricing, not noise. The shallow "
            "retracement that follows is a continuation entry with a natural "
            "invalidation at the impulse bar's origin."
        ),
        phases=(
            "SCANNING: looking for an impulse bar. "
            "ARMED: impulse bar printed. "
            "WINDOW_OPEN: price retraces into the upper/lower third of that "
            "bar without closing beyond its origin. "
            "ENTRY: M1 rejection inside the retracement zone. "
            "INVALIDATED: a close beyond the impulse bar's origin."
        ),
        entry_rule="M1 rejection candle inside the impulse bar's retracement zone.",
        stop_rule="0.3x ATR beyond the impulse bar's origin.",
        exit_rule="60% at 1R, runner to the impulse extension.",
        failure_mode=(
            "The impulse was a news spike. Those retrace fully and continue "
            "through far more often than session-flow impulses. If a "
            "high-impact release landed in the last 30 minutes, this setup "
            "does not apply."
        ),
        best_window="NY killzone, where impulses are most often real",
        base_confidence=0.57,
        expected_hold_minutes=25,
    ),
    "S6": ScalpSpec(
        setup_id="S6",
        name="Spread Gate (filter, not a setup)",
        idea=(
            "Runs before every other scalping setup. On a 3 USD/oz stop, a "
            "0.20 USD/oz spread is 6.7% of risk; at 0.60 it is 20%, and no "
            "realistic win rate survives that. This gate refuses the trade "
            "rather than letting the cost hide inside the entry price."
        ),
        phases="n/a -- a precondition",
        entry_rule="Spread must be under 10% of the intended stop distance.",
        stop_rule="n/a",
        exit_rule="n/a",
        failure_mode=(
            "The gate uses the spread at the moment of analysis. Spreads widen "
            "between analysis and execution, especially near the hour and "
            "around news -- so pass the live spread from the platform rather "
            "than relying on the typical value."
        ),
        best_window="always",
        base_confidence=0.0,
        expected_hold_minutes=0,
    ),
}

# A scalp's stop must clear the spread by a wide margin or the cost dominates.
MAX_SPREAD_PCT_OF_STOP = 10.0
# Scalping stops are tighter than swing stops but still volatility-aware.
SCALP_STOP_ATR_MULTIPLE = 0.35
MIN_SCALP_STOP_ATR = 0.8


@dataclass
class MachineState:
    """The state machine's memory between bars."""

    setup_id: str
    phase: Phase = Phase.SCANNING
    direction: str | None = None
    trigger_level: float | None = None
    invalidation: float | None = None
    armed_at: datetime | None = None
    bars_in_phase: int = 0
    log: list[str] = field(default_factory=list)

    def to(self, phase: Phase, when: datetime, note: str) -> None:
        self.log.append(f"{when:%H:%M} {self.phase.value} -> {phase.value}: {note}")
        self.phase = phase
        self.bars_in_phase = 0


def detect_scalps(
    symbol: str,
    m5: CandleSeries | None,
    m1: CandleSeries | None,
    level_map: LevelMap,
    moment: datetime | None = None,
    session: SessionState | None = None,
    spread_usd_oz: float | None = None,
    atr_value: float | None = None,
) -> list[ScalpSignal]:
    """Run every scalping detector and return whatever fires, ranked.

    `atr_value` may be supplied by a caller that already has it (the backtest
    loop does). Recomputing ATR inside each detector is correct but quadratic
    over a long series, which makes a multi-run evaluation impractical.
    """
    moment = moment or datetime.now(timezone.utc)
    session = session or classify(moment)
    spec = get_spec(symbol)
    spread = spread_usd_oz if spread_usd_oz is not None else spec.typical_spread_usd_oz

    out: list[ScalpSignal] = []
    if m5 is None or len(m5) < 60:
        return out

    a = atr_value if atr_value is not None else _atr(m5)
    if not a:
        return out

    for fn in (
        lambda: detect_s1(symbol, m5, m1, level_map, moment, session, spread, a),
        lambda: detect_s2(symbol, m5, spread, a),
        lambda: detect_s3(symbol, m5, level_map, spread, a),
        lambda: detect_s4(symbol, m5, level_map, spread, a),
        lambda: detect_s5(symbol, m5, m1, spread, a),
    ):
        try:
            hit = fn()
        except Exception:  # noqa: BLE001 - one broken detector must not stop the scan
            continue
        if hit and spread_gate(hit):
            out.append(hit)

    return sorted(out, key=lambda s: s.confidence, reverse=True)


def spread_gate(signal: ScalpSignal) -> bool:
    """S6. Refuse a scalp whose spread eats too much of its risk."""
    if signal.spread_as_pct_of_risk > MAX_SPREAD_PCT_OF_STOP:
        signal.warnings.append(
            f"S6: spread {signal.spread_used:.3f} USD/oz is "
            f"{signal.spread_as_pct_of_risk:.0f}% of the {signal.risk_per_unit:.2f} "
            f"USD/oz stop, over the {MAX_SPREAD_PCT_OF_STOP:.0f}% ceiling. "
            f"Refused -- the cost would dominate the edge."
        )
        return False
    return True


# --- Detectors --------------------------------------------------------------

def detect_s1(symbol: str, m5: CandleSeries, m1: CandleSeries | None,
              level_map: LevelMap, moment: datetime, session: SessionState,
              spread: float, a: float) -> ScalpSignal | None:
    """Killzone Sweep Scalp."""
    spec = CATALOGUE["S1"]

    in_killzone = any(w in session.active_windows
                      for w in ("london_killzone", "ny_killzone",
                                "silver_bullet", "overlap"))
    machine = MachineState("S1")

    session_levels = [l for l in level_map.levels
                      if l.kind in ("asian_high", "asian_low",
                                    "prior_day_high", "prior_day_low")]
    if not session_levels:
        return None

    for level in session_levels:
        direction = "bullish" if level.kind.endswith("low") else "bearish"
        sweep = detect_sweep(m5, level.price, direction, -1, a,
                             max_bars_outside=3, min_penetration_atr=0.15)
        if not sweep:
            continue

        machine.to(Phase.ARMED, m5.last.ts,
                   f"price breached {level.kind} at {level.price:g}")
        machine.to(Phase.WINDOW_OPEN, m5.last.ts,
                   f"M5 closed back inside after {sweep.penetration_atr:.2f}x ATR")

        # Invalidation check: two consecutive closes outside means breakout.
        recent = m5.candles[-3:]
        outside = sum(1 for c in recent
                      if (c.close < level.price if direction == "bullish"
                          else c.close > level.price))
        if outside >= 2:
            machine.to(Phase.INVALIDATED, m5.last.ts,
                       "two M5 closes outside -- this was a breakout")
            continue

        trade_dir = "long" if direction == "bullish" else "short"
        confirmed, note = _m1_confirmation(m1, m5.last, trade_dir)
        if not confirmed:
            return None

        machine.to(Phase.ENTRY, m5.last.ts, note)

        sweep_extreme = (level.price - sweep.penetration) if direction == "bullish" \
            else (level.price + sweep.penetration)
        entry = (m1.last.close if m1 and len(m1) else m5.last.close)
        stop = _scalp_stop(trade_dir, sweep_extreme, a, entry)

        confidence = spec.base_confidence + (0.10 if in_killzone else -0.22)
        confidence += (sweep.strength - 0.6) * 0.25

        warnings: list[str] = []
        if not in_killzone:
            warnings.append(
                "outside a killzone -- this setup's edge is time-dependent and "
                "the same shape at 03:00 UTC is not the same setup"
            )

        return ScalpSignal(
            "S1", spec.name, get_spec(symbol).symbol, trade_dir,
            entry, stop, max(0.0, min(0.90, confidence)), a, spread,
            machine.log, [sweep.description, note], warnings,
            spec.failure_mode, spec.expected_hold_minutes,
        )
    return None


def detect_s2(symbol: str, m5: CandleSeries, spread: float,
              a: float) -> ScalpSignal | None:
    """Pullback Window Break."""
    spec = CATALOGUE["S2"]
    if len(m5) < 60:
        return None

    e9, e21, e50 = (ema(m5.closes, 9)[-1], ema(m5.closes, 21)[-1],
                    ema(m5.closes, 50)[-1])
    if None in (e9, e21, e50):
        return None

    up = e9 > e21 > e50
    down = e9 < e21 < e50
    if not (up or down):
        return None

    # Slope filter: a flat stack is a range wearing a trend's clothes.
    e21_prev = ema(m5.closes, 21)[-6]
    if e21_prev is None:
        return None
    slope = (e21 - e21_prev) / a
    if abs(slope) < 0.25:
        return None
    if (up and slope < 0) or (down and slope > 0):
        return None

    machine = MachineState("S2")
    machine.to(Phase.ARMED, m5.last.ts,
               f"EMA stack {'up' if up else 'down'}, 21-EMA slope "
               f"{slope:+.2f}x ATR over 5 bars")

    last = m5.last

    # The last bar is the *breakout* bar, so it is not part of the pullback
    # and it has to close with the trend. Counting it into the pullback was
    # the A31 defect: the trigger is the highest high of the pullback, so a
    # last bar inside its own pullback would have had to close above its own
    # high. `broke` was unsatisfiable and S2 never fired -- not rarely, never.
    with_trend = (last.close > last.open) if up else (last.close < last.open)
    if not with_trend:
        return None

    # Count the counter-trend pullback that ends at the bar before this one.
    counter = 0
    for c in reversed(m5.candles[:-1]):
        is_counter = (c.close < c.open) if up else (c.close > c.open)
        if is_counter:
            counter += 1
        else:
            break
    if counter == 0 or counter > 3:
        if counter > 3:
            machine.to(Phase.INVALIDATED, m5.last.ts,
                       f"{counter} counter-trend bars -- a pullback this deep "
                       f"is a reversal in progress, not a pause")
        return None

    pullback = m5.candles[-1 - counter:-1]
    trigger = max(c.high for c in pullback) if up else min(c.low for c in pullback)
    machine.to(Phase.WINDOW_OPEN, m5.last.ts,
               f"{counter}-bar pullback, trigger at {trigger:g}")

    broke = last.close > trigger if up else last.close < trigger
    if not broke:
        return None
    machine.to(Phase.ENTRY, last.ts, f"M5 closed beyond {trigger:g}")

    direction = "long" if up else "short"
    extreme = min(c.low for c in pullback) if up else max(c.high for c in pullback)
    stop = _scalp_stop(direction, extreme, a, last.close)

    confidence = spec.base_confidence + min(0.12, abs(slope) * 0.10)
    confidence -= 0.05 * (counter - 1)   # deeper pullback, less conviction

    return ScalpSignal(
        "S2", spec.name, get_spec(symbol).symbol, direction,
        last.close, stop, max(0.0, min(0.90, confidence)), a, spread,
        machine.log,
        [f"EMA9/21/50 stacked {'up' if up else 'down'}",
         f"21-EMA slope {slope:+.2f}x ATR",
         f"{counter}-bar pullback broken at {trigger:g}"],
        [], spec.failure_mode, spec.expected_hold_minutes,
    )


def detect_s3(symbol: str, m5: CandleSeries, level_map: LevelMap,
              spread: float, a: float) -> ScalpSignal | None:
    """Prior-Day Sweep with the directional bias filter."""
    spec = CATALOGUE["S3"]

    pdh = next((l for l in level_map.levels if l.kind == "prior_day_high"), None)
    pdl = next((l for l in level_map.levels if l.kind == "prior_day_low"), None)
    pdc = next((l for l in level_map.levels if l.kind == "prior_day_close"), None)
    if pdh is None or pdl is None or pdc is None:
        return None

    # The bias filter: prior day's own direction decides which side to fade.
    prior_open_proxy = (pdh.price + pdl.price) / 2.0
    prior_bullish = pdc.price > prior_open_proxy

    level = pdl if prior_bullish else pdh
    direction = "bullish" if prior_bullish else "bearish"

    sweep = detect_sweep(m5, level.price, direction, -1, a,
                         max_bars_outside=3, min_penetration_atr=0.15)
    if not sweep:
        return None

    machine = MachineState("S3")
    machine.to(Phase.ARMED, m5.last.ts,
               f"prior day closed {'bullish' if prior_bullish else 'bearish'}, "
               f"so only the {'low' if prior_bullish else 'high'} sweep qualifies")
    machine.to(Phase.WINDOW_OPEN, m5.last.ts, sweep.description)
    machine.to(Phase.ENTRY, m5.last.ts, "M5 closed back inside the prior range")

    trade_dir = "long" if direction == "bullish" else "short"
    sweep_extreme = (level.price - sweep.penetration) if direction == "bullish" \
        else (level.price + sweep.penetration)
    stop = _scalp_stop(trade_dir, sweep_extreme, a, m5.last.close, multiple=0.4)

    warnings: list[str] = []
    confidence = spec.base_confidence + (sweep.strength - 0.6) * 0.25
    if _three_day_trend(m5, trade_dir):
        confidence -= 0.25
        warnings.append(
            "third consecutive session in one direction -- the bias filter "
            "does not cover trend days, and this is where the setup loses most"
        )

    return ScalpSignal(
        "S3", spec.name, get_spec(symbol).symbol, trade_dir,
        m5.last.close, stop, max(0.0, min(0.90, confidence)), a, spread,
        machine.log,
        [f"prior day {'bullish' if prior_bullish else 'bearish'} -- bias filter "
         f"allows only this side", sweep.description],
        warnings, spec.failure_mode, spec.expected_hold_minutes,
    )


def detect_s4(symbol: str, m5: CandleSeries, level_map: LevelMap,
              spread: float, a: float) -> ScalpSignal | None:
    """Round-Number Fade."""
    spec = CATALOGUE["S4"]

    rounds = [l for l in level_map.levels
              if l.kind == "round" and l.strength >= 0.35]
    if not rounds:
        return None
    price = m5.last.close
    level = min(rounds, key=lambda l: abs(l.price - price))
    if abs(level.price - price) > a * 1.5:
        return None

    recent = m5.tail(12)
    run = abs(recent.last.close - recent[0].open)
    if run < a * 2.0:
        return None

    machine = MachineState("S4")
    machine.to(Phase.ARMED, m5.last.ts,
               f"{run / a:.1f}x ATR approach into the {level.price:g} handle")

    hit = pin_bar(m5, -1, a, level.price) or engulfing(m5, -1, a, level.price)
    if hit is None:
        return None
    machine.to(Phase.WINDOW_OPEN, m5.last.ts, f"M5 rejection: {hit}")

    approaching_up = recent.last.close > recent[0].open
    direction = "short" if approaching_up else "long"
    if (hit.direction == "bullish") != (direction == "long"):
        return None
    machine.to(Phase.ENTRY, m5.last.ts, "rejection aligned with the approach")

    extreme = m5.last.high if direction == "short" else m5.last.low
    stop = _scalp_stop(direction, extreme, a, m5.last.close)

    touches = sum(1 for c in m5.tail(36) if c.low <= level.price <= c.high)
    warnings: list[str] = []
    confidence = spec.base_confidence + (hit.strength - 0.5) * 0.25
    if touches >= 3:
        machine.to(Phase.INVALIDATED, m5.last.ts,
                   f"{touches} touches -- being accumulated against")
        return None
    if touches == 2:
        confidence -= 0.12
        warnings.append("second touch -- the next attempt usually goes through")

    return ScalpSignal(
        "S4", spec.name, get_spec(symbol).symbol, direction,
        m5.last.close, stop, max(0.0, min(0.90, confidence)), a, spread,
        machine.log,
        [f"{run / a:.1f}x ATR run into {level.price:g}", f"rejection: {hit}"],
        warnings, spec.failure_mode, spec.expected_hold_minutes,
    )


def detect_s5(symbol: str, m5: CandleSeries, m1: CandleSeries | None,
              spread: float, a: float) -> ScalpSignal | None:
    """Momentum Continuation after an impulse bar."""
    spec = CATALOGUE["S5"]
    if len(m5) < 20:
        return None

    # Find the most recent impulse bar in the last six.
    impulse = None
    impulse_idx = None
    for i in range(len(m5) - 2, max(len(m5) - 8, 0), -1):
        c = m5[i]
        if c.range >= a * 1.5 and (c.close_position >= 0.8 or c.close_position <= 0.2):
            impulse, impulse_idx = c, i
            break
    if impulse is None:
        return None

    direction = "long" if impulse.close_position >= 0.8 else "short"
    machine = MachineState("S5")
    machine.to(Phase.ARMED, impulse.ts,
               f"impulse bar {impulse.range / a:.1f}x ATR closing at "
               f"{impulse.close_position:.0%} of its range")

    origin = impulse.low if direction == "long" else impulse.high
    third = impulse.low + impulse.range / 3.0 if direction == "long" \
        else impulse.high - impulse.range / 3.0

    after = m5.candles[impulse_idx + 1:]
    if not after:
        return None
    broke_origin = any(c.close < origin for c in after) if direction == "long" \
        else any(c.close > origin for c in after)
    if broke_origin:
        machine.to(Phase.INVALIDATED, m5.last.ts,
                   "close beyond the impulse origin -- the move is being undone")
        return None

    last = m5.last
    in_zone = (last.low <= third) if direction == "long" else (last.high >= third)
    if not in_zone:
        return None
    machine.to(Phase.WINDOW_OPEN, last.ts,
               f"retraced into the impulse bar's {'lower' if direction == 'long' else 'upper'} third")

    confirmed, note = _m1_confirmation(m1, last, direction)
    if not confirmed:
        return None
    machine.to(Phase.ENTRY, last.ts, note)

    entry = (m1.last.close if m1 and len(m1) else last.close)
    stop = _scalp_stop(direction, origin, a, entry, multiple=0.3)

    # A32. Returning `spec.base_confidence` verbatim made S5's confidence the
    # constant 0.57, and the backtest's default min_confidence is 0.60. A
    # constant below a threshold is not a filter, it is an off switch: every
    # backtest in this repo that claimed to cover S5 covered zero S5 trades,
    # while the EA -- which had no confidence gate at all -- traded it
    # unfiltered. Both halves of that mismatch are fixed; this is the half
    # that gives the setup a confidence which can actually move, from the two
    # pieces of evidence it has already computed.
    impulse_strength = min(1.0, max(0.0, (impulse.range / a - 1.5) / 1.5))
    span = (third - origin) if direction == "long" else (origin - third)
    if span <= 0:
        depth = 0.0
    elif direction == "long":
        depth = min(1.0, max(0.0, (third - last.low) / span))
    else:
        depth = min(1.0, max(0.0, (last.high - third) / span))
    confidence = spec.base_confidence + 0.10 * impulse_strength - 0.08 * depth

    return ScalpSignal(
        "S5", spec.name, get_spec(symbol).symbol, direction,
        entry, stop, max(0.0, min(0.90, confidence)), a, spread,
        machine.log,
        [f"impulse {impulse.range / a:.1f}x ATR", note],
        ["if a high-impact release landed in the last 30 minutes this setup "
         "does not apply -- news impulses retrace and continue through"],
        spec.failure_mode, spec.expected_hold_minutes,
    )


# --- helpers ----------------------------------------------------------------

def _atr(series: CandleSeries | None, period: int = 14) -> float | None:
    if series is None or len(series) < period + 1:
        return None
    return atr(series.highs, series.lows, series.closes, period)[-1]


def _scalp_stop(direction: str, level: float, atr_value: float, entry: float,
                multiple: float = SCALP_STOP_ATR_MULTIPLE) -> float:
    """Stop beyond a level, floored so it never sits inside the noise band.

    Scalping stops are tighter than swing stops by design, but a stop under
    MIN_SCALP_STOP_ATR on gold is not a stop, it is a donation -- a normal
    wick takes it out before the idea has a chance to resolve. When the
    structural level sits closer than that, the stop is widened away from
    entry rather than the trade being taken with a stop that cannot survive.

    Widening the stop shrinks the position (size follows the stop, rule R8),
    which is the correct trade-off: fewer ounces at a survivable distance
    beats more ounces at a distance that gets hit by noise.
    """
    buffer = atr_value * multiple
    raw = level - buffer if direction == "long" else level + buffer

    floor = atr_value * MIN_SCALP_STOP_ATR
    if abs(entry - raw) < floor:
        raw = entry - floor if direction == "long" else entry + floor
    return raw


def _m1_confirmation(m1: CandleSeries | None, m5_bar: Candle,
                     direction: str) -> tuple[bool, str]:
    """Require an M1 close beyond the M5 setup bar before entering.

    Without this the entry is on the setup bar's close, which is where the
    reversal is least confirmed and the adverse excursion is largest. When no
    M1 data is available the setup still fires, but says so -- silently
    dropping a confirmation requirement is worse than not having it.
    """
    if m1 is None or len(m1) < 3:
        return True, ("no M1 data -- entering on the M5 close without the "
                      "usual confirmation, which widens the expected adverse "
                      "excursion")
    last = m1.last
    if direction == "long" and last.close > m5_bar.high:
        return True, f"M1 closed {last.close:g} above the M5 setup bar high"
    if direction == "short" and last.close < m5_bar.low:
        return True, f"M1 closed {last.close:g} below the M5 setup bar low"
    return False, "waiting for M1 confirmation"


def _three_day_trend(m5: CandleSeries, direction: str) -> bool:
    """Three sessions in one direction -- a poor backdrop for a fade."""
    bars_per_day = 288   # 24h of M5
    if len(m5) < bars_per_day * 3:
        return False
    closes = [m5[-1 - bars_per_day * k].close for k in range(3)]
    if direction == "short":
        return closes[0] > closes[1] > closes[2]
    return closes[0] < closes[1] < closes[2]
