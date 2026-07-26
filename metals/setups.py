"""The metals setup catalogue: G1-G12.

Each setup is a named, checkable pattern with explicit entry, invalidation and
target logic. They are deliberately few and deliberately specific -- a system
with forty setups has no setups, because every bar matches something.

Design rules shared by all of them:

* **The stop comes from structure.** Every setup defines where it is wrong
  before it defines where it enters. Size follows (rule R8).
* **A setup fires only at a level.** Every detector requires either a level
  from metals.levels or a session boundary. A pattern in open space is not
  a setup.
* **Every setup states how it fails.** `failure_mode` is not documentation
  garnish -- it is what the journal checks against when reviewing losers, and
  the difference between a setup that stopped working and one that was
  executed wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .candles import CandleSeries
from .indicators import adx, atr, ema, squeeze_on
from .levels import LevelMap
from .patterns import (detect_sweep, divergence, engulfing,
                       fair_value_gaps, market_structure_shift, pin_bar, scan)
from .sessions import SessionState, classify
from .specs import get_spec


@dataclass
class SetupSignal:
    """A fired setup, with everything needed to size and journal it."""

    setup_id: str
    name: str
    symbol: str
    direction: str              # "long" | "short"
    entry: float
    structural_level: float     # where the idea is wrong
    target: float
    confidence: float           # 0.0 - 1.0, before global vetoes
    timeframe: str
    evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failure_mode: str = ""
    atr_value: float = 0.0

    def __str__(self) -> str:
        return (f"{self.setup_id} {self.name}: {self.direction} {self.symbol} "
                f"@ {self.entry:g} (conf {self.confidence:.2f})")


@dataclass(frozen=True)
class SetupSpec:
    """Static description of a setup, independent of any market data."""

    setup_id: str
    name: str
    regime: str                 # "trend" | "range" | "reversal" | "breakout" | "relative"
    timeframes: str
    idea: str
    entry_rule: str
    stop_rule: str
    target_rule: str
    failure_mode: str
    best_window: str
    base_confidence: float


CATALOGUE: dict[str, SetupSpec] = {
    "G1": SetupSpec(
        setup_id="G1",
        name="London Sweep Reversal",
        regime="reversal",
        timeframes="context H4/H1, trigger M15/M5",
        idea=(
            "The Asian session builds a narrow range. Stops accumulate above "
            "its high and below its low. At the London open the market reaches "
            "through one side to collect them, then reverses and trends the "
            "other way for the session. This is the highest-frequency "
            "repeatable pattern on gold and it is a direct consequence of how "
            "the market sources the liquidity it needs to move."
        ),
        entry_rule=(
            "Wait for price to trade beyond the Asian high or low and then "
            "close back inside within three M15 bars. Wait for a market "
            "structure shift in the reversal direction. Enter on the retest of "
            "the fair value gap or the order block created by the shift -- not "
            "on the sweep candle itself."
        ),
        stop_rule="Beyond the sweep extreme by 0.25x ATR(14) M15.",
        target_rule=(
            "First target the opposite side of the Asian range, then the prior "
            "day's high or low. Take partial profit at 1R and move the stop to "
            "break-even only after 1R is banked."
        ),
        failure_mode=(
            "The sweep does not close back inside -- it was a genuine breakout, "
            "not a sweep, and the trend continues through the level. The tell "
            "is the close: entering before the close back inside is what turns "
            "this from a good setup into a bad one."
        ),
        best_window="London killzone, 07:00-10:00 London time",
        base_confidence=0.70,
    ),
    "G2": SetupSpec(
        setup_id="G2",
        name="New York Killzone Continuation",
        regime="trend",
        timeframes="context H1, trigger M15/M5",
        idea=(
            "London sets a direction. New York opens, adds volume, and extends "
            "it. The retracement into the New York open is the entry into a "
            "move that is already established rather than a bet on a new one."
        ),
        entry_rule=(
            "London session has a clear direction (higher highs and higher "
            "lows, or the reverse). Between 08:00 and 11:00 New York time, wait "
            "for a pullback into the 20 EMA on M15 that coincides with a level, "
            "and a rejection candle there."
        ),
        stop_rule="Beyond the pullback swing by 0.25x ATR(14) M15.",
        target_rule="Extension of the London range, or the next H1 level.",
        failure_mode=(
            "New York reverses London instead of extending it, which happens "
            "on data days and around the 15:00 London fix. Checking the "
            "calendar before taking this one removes most of its losses."
        ),
        best_window="New York killzone, 08:00-11:00 New York time",
        base_confidence=0.65,
    ),
    "G3": SetupSpec(
        setup_id="G3",
        name="Trend Pullback at Level",
        regime="trend",
        timeframes="context H4, setup H1, trigger M15",
        idea=(
            "The most durable setup in the book and the least exciting. An "
            "established H4 trend pulls back into a level that lines up with a "
            "moving average, and continues. It works because it asks the market "
            "to do what it is already doing."
        ),
        entry_rule=(
            "H4 trend confirmed by EMA20 > EMA50 > EMA200 (or the reverse) and "
            "ADX above 20. Price pulls back into a confluence zone containing "
            "the H1 EMA20 or EMA50. Enter on a rejection candle on M15 with the "
            "close back in the trend direction."
        ),
        stop_rule="Beyond the confluence zone by 0.25x ATR(14) H1.",
        target_rule="Prior swing extreme, then a measured move of the prior leg.",
        failure_mode=(
            "The pullback is the start of a reversal rather than a pause. The "
            "warning sign is the pullback taking longer than the impulse that "
            "preceded it, or breaking the prior swing low in an uptrend."
        ),
        best_window="London and New York sessions",
        base_confidence=0.68,
    ),
    "G4": SetupSpec(
        setup_id="G4",
        name="Round Number Rejection",
        regime="reversal",
        timeframes="setup H1, trigger M15",
        idea=(
            "Gold respects its 100 and 50 handles, and silver its whole and "
            "half dollars, more reliably than almost any technical level, "
            "because that is where resting orders actually sit. The first "
            "approach to a major handle after an extended run is rejected more "
            "often than it is broken."
        ),
        entry_rule=(
            "Price approaches a major round level after an extended directional "
            "move of at least 2x ATR(14) H1 without a meaningful pullback. Wait "
            "for a pin bar or engulfing candle on M15 that closes back away "
            "from the level."
        ),
        stop_rule=(
            "Beyond the rejection wick by 0.25x ATR -- never on the round "
            "number itself, which is where the sweep goes."
        ),
        target_rule="The prior consolidation, or the next intermediate handle.",
        failure_mode=(
            "The level breaks and becomes support. A round number that has been "
            "tested three or more times in a session is being accumulated "
            "against, not defended -- stop taking the rejection after the "
            "second test."
        ),
        best_window="Any liquid session",
        base_confidence=0.60,
    ),
    "G5": SetupSpec(
        setup_id="G5",
        name="Asian Range Breakout",
        regime="breakout",
        timeframes="setup M15, trigger M5",
        idea=(
            "The counterpart to G1 and its direct competitor. When the Asian "
            "range is unusually tight and the macro backdrop is one-directional, "
            "London breaks it and runs rather than sweeping and reversing."
        ),
        entry_rule=(
            "Asian range is narrower than 0.6x the 20-day average Asian range. "
            "Price closes beyond the range on M15 with volume above 1.5x its "
            "20-bar average, and does not close back inside on the next bar."
        ),
        stop_rule="The opposite side of the Asian range, or 1.0x ATR, whichever is nearer.",
        target_rule="Range height projected from the break point.",
        failure_mode=(
            "This is G1 wearing a disguise, and telling them apart in advance "
            "is genuinely hard. The distinguishing evidence is the macro "
            "backdrop: breakouts hold when real yields and the dollar are "
            "moving in gold's favour and fail when they are not. Without a "
            "macro read, treat every apparent breakout as a possible sweep and "
            "wait for the retest."
        ),
        best_window="London open",
        base_confidence=0.55,
    ),
    "G6": SetupSpec(
        setup_id="G6",
        name="Prior Day Extreme Sweep",
        regime="reversal",
        timeframes="setup H1, trigger M15",
        idea=(
            "The previous day's high and low are the levels every desk marks. "
            "Price reaching through one and failing is the same mechanic as G1 "
            "at a level with more weight behind it."
        ),
        entry_rule=(
            "Price exceeds the prior day's high or low and closes back inside "
            "within two H1 bars, with a market structure shift on M15."
        ),
        stop_rule="Beyond the sweep extreme by 0.25x ATR(14) H1.",
        target_rule="The opposite prior-day extreme, or the day's VWAP.",
        failure_mode=(
            "On a trend day the prior extreme breaks and never comes back. "
            "Checking whether the last three days made higher highs filters "
            "most of these out."
        ),
        best_window="London and New York",
        base_confidence=0.65,
    ),
    "G7": SetupSpec(
        setup_id="G7",
        name="Failed Breakout Reversal",
        regime="reversal",
        timeframes="setup H1, trigger M15",
        idea=(
            "A level is broken convincingly, then price closes back inside "
            "within a few bars. Everyone who entered on the break is trapped, "
            "and their stops become the fuel for the reverse move. On metals "
            "this is more common than a clean breakout."
        ),
        entry_rule=(
            "Price closes beyond a level that has held at least twice, then "
            "closes back inside within three bars. Enter on the close back "
            "inside, or on the first retest of the level from the inside."
        ),
        stop_rule="Beyond the failed-breakout extreme by 0.25x ATR.",
        target_rule="The opposite side of the range the level bounds.",
        failure_mode=(
            "A second break in the same direction, which usually holds. One "
            "failed breakout is a trap; two is a trend."
        ),
        best_window="Any liquid session, best when the daily range is already spent",
        base_confidence=0.62,
    ),
    "G8": SetupSpec(
        setup_id="G8",
        name="Squeeze Expansion",
        regime="breakout",
        timeframes="setup H1/H4, trigger M15",
        idea=(
            "Bollinger Bands contract inside the Keltner Channel: volatility "
            "has compressed and, on metals, compression resolves violently "
            "because the resolution usually coincides with a macro catalyst."
        ),
        entry_rule=(
            "Squeeze condition true for at least six consecutive H1 bars, then "
            "the first close outside the Bollinger Band. Enter in the direction "
            "of that close."
        ),
        stop_rule="The opposite Bollinger Band, or 1.5x ATR, whichever is nearer.",
        target_rule="2x the width of the compressed range.",
        failure_mode=(
            "The first expansion is the wrong way -- a squeeze can release, "
            "reverse, and release again. Waiting for the close outside the band "
            "rather than the touch removes most, but not all, of these."
        ),
        best_window="Ahead of a scheduled catalyst, entered after it, never before",
        base_confidence=0.58,
    ),
    "G9": SetupSpec(
        setup_id="G9",
        name="Divergence Reversal at HTF Level",
        regime="reversal",
        timeframes="setup H4, trigger H1",
        idea=(
            "Price makes a new extreme into a higher-timeframe level while RSI "
            "does not. Momentum is leaving the move. On its own this is worth "
            "little; arriving at an H4 level, it is worth acting on."
        ),
        entry_rule=(
            "RSI divergence against price at an H4 level, confirmed by a "
            "structure break on H1. The level requirement is not optional -- "
            "divergence in open space is the single most expensive signal in "
            "metals trading."
        ),
        stop_rule="Beyond the divergent extreme by 0.25x ATR(14) H4.",
        target_rule="The prior H4 swing in the opposite direction.",
        failure_mode=(
            "Divergence persists and price keeps going. In a strong trend gold "
            "can hold a divergence for weeks. This is why the structure break "
            "is required before entry rather than the divergence alone."
        ),
        best_window="Any, but confirmation must come from a closed H1 bar",
        base_confidence=0.55,
    ),
    "G10": SetupSpec(
        setup_id="G10",
        name="Fair Value Gap Retest",
        regime="trend",
        timeframes="setup H1, trigger M15",
        idea=(
            "An impulsive move leaves a band of prices that traded through in "
            "one direction only. Price returns to it, fills it, and continues. "
            "A continuation entry with a naturally tight invalidation."
        ),
        entry_rule=(
            "Identify an unfilled gap of at least 0.2x ATR in the direction of "
            "the H1 trend. Enter when price returns into it and prints a "
            "rejection candle on M15."
        ),
        stop_rule="Beyond the far edge of the gap by 0.25x ATR.",
        target_rule="The extreme of the impulse that created the gap.",
        failure_mode=(
            "Price fills the gap and keeps going through it, which means the "
            "impulse was a liquidation rather than an initiation. Gaps created "
            "by news spikes fill and continue far more often than gaps created "
            "by session flow."
        ),
        best_window="London and New York",
        base_confidence=0.60,
    ),
    "G11": SetupSpec(
        setup_id="G11",
        name="Metal Selection by Ratio",
        regime="relative",
        timeframes="context D1",
        idea=(
            "Not an entry setup: a filter that runs before every other setup. "
            "The gold/silver ratio's trend says which metal is leading and "
            "therefore which one expresses a directional view with a better "
            "payoff for the same risk."
        ),
        entry_rule=(
            "Apply to whichever setup fired. A rising ratio favours gold longs "
            "and silver shorts; a falling ratio favours silver longs and gold "
            "shorts. When the ratio is flat, default to gold for its tighter "
            "spread."
        ),
        stop_rule="n/a -- modifies the chosen instrument, not the risk.",
        target_rule="n/a",
        failure_mode=(
            "The ratio turns while a position is open, which usually means the "
            "regime changed -- defensive to cyclical or back. That is a reason "
            "to take profit earlier, not to reverse."
        ),
        best_window="Evaluated once per day, not intraday",
        base_confidence=0.0,
    ),
    "G12": SetupSpec(
        setup_id="G12",
        name="Post-News Structure",
        regime="reversal",
        timeframes="setup M15, trigger M5",
        idea=(
            "Not a news trade -- the opposite. After a high-impact release the "
            "first move is frequently retraced, spreads normalise within 15-30 "
            "minutes, and the level the spike reached becomes tradable "
            "structure. This setup trades the structure the news created, once "
            "the news is over."
        ),
        entry_rule=(
            "Wait a minimum of 30 minutes after the release. Spread must be "
            "back under 15% of ATR. Then treat the spike high and low as levels "
            "and take G6 or G7 against them."
        ),
        stop_rule="Beyond the spike extreme by 0.5x ATR -- wider than usual, "
                  "because post-news volatility is still elevated.",
        target_rule="The pre-release price, which acts as a magnet.",
        failure_mode=(
            "The release genuinely repriced the metal -- a CPI surprise that "
            "moves the real-yield path is not noise to be faded. The tell is "
            "whether the move retraces half of itself in the first hour: if it "
            "does not, the repricing was real and this setup does not apply."
        ),
        best_window="30-120 minutes after a high-impact release",
        base_confidence=0.50,
    ),
}


# --- Detectors ---------------------------------------------------------------

def detect_all(
    symbol: str,
    h4: CandleSeries | None,
    h1: CandleSeries | None,
    m15: CandleSeries | None,
    level_map: LevelMap,
    moment: datetime | None = None,
    session: SessionState | None = None,
) -> list[SetupSignal]:
    """Run every applicable detector and return whatever fires, ranked."""
    moment = moment or datetime.now(timezone.utc)
    session = session or classify(moment)
    out: list[SetupSignal] = []

    for fn in (
        lambda: detect_g1(symbol, m15, level_map, moment, session),
        lambda: detect_g3(symbol, h4, h1, m15, level_map),
        lambda: detect_g4(symbol, h1, m15, level_map),
        lambda: detect_g6(symbol, h1, level_map, moment),
        lambda: detect_g7(symbol, h1, level_map),
        lambda: detect_g8(symbol, h1, m15),
        lambda: detect_g9(symbol, h4, h1, level_map),
        lambda: detect_g10(symbol, h1, m15),
    ):
        try:
            hit = fn()
        except Exception:  # noqa: BLE001 - one broken detector must not kill the scan
            continue
        if hit:
            out.append(hit)

    return sorted(out, key=lambda s: s.confidence, reverse=True)


def detect_g1(symbol: str, m15: CandleSeries | None, level_map: LevelMap,
              moment: datetime, session: SessionState) -> SetupSignal | None:
    """London Sweep Reversal."""
    if m15 is None or len(m15) < 40:
        return None
    spec = CATALOGUE["G1"]
    a = _atr(m15)
    if not a:
        return None

    asian_levels = [l for l in level_map.levels
                    if l.kind in ("asian_high", "asian_low")]
    if not asian_levels:
        return None

    evidence: list[str] = []
    warnings: list[str] = []

    in_window = "london_killzone" in session.active_windows
    if not in_window:
        warnings.append(
            "outside the London killzone -- this setup's edge is "
            "time-dependent, and the same shape at 03:00 UTC is not the same "
            "setup"
        )

    for level in asian_levels:
        direction = "bullish" if level.kind == "asian_low" else "bearish"
        sweep = detect_sweep(m15, level.price, direction, -1, a)
        if not sweep:
            continue

        mss = market_structure_shift(m15)
        if mss is None or mss.direction != direction:
            warnings.append(
                "sweep detected but no market structure shift yet -- this is "
                "the hypothesis, not the trade. Wait for the shift."
            )
            continue

        evidence.append(sweep.description)
        evidence.append(mss.description)

        trade_dir = "long" if direction == "bullish" else "short"
        entry = m15.last.close
        structural = (level.price - sweep.penetration) if direction == "bullish" \
            else (level.price + sweep.penetration)

        opposite = next(
            (l for l in asian_levels if l.kind != level.kind), None
        )
        target = opposite.price if opposite else (
            entry + 3 * a if trade_dir == "long" else entry - 3 * a
        )
        if trade_dir == "long" and target <= entry:
            target = entry + 3 * a
        if trade_dir == "short" and target >= entry:
            target = entry - 3 * a

        confidence = spec.base_confidence
        confidence += 0.10 if in_window else -0.20
        confidence += (sweep.strength - 0.6) * 0.3
        confidence = max(0.0, min(0.95, confidence))

        return SetupSignal(
            "G1", spec.name, get_spec(symbol).symbol, trade_dir,
            entry, structural, target, confidence, "M15",
            evidence, warnings, spec.failure_mode, a,
        )
    return None


def detect_g3(symbol: str, h4: CandleSeries | None, h1: CandleSeries | None,
              m15: CandleSeries | None, level_map: LevelMap) -> SetupSignal | None:
    """Trend Pullback at Level."""
    if h4 is None or h1 is None or len(h4) < 60 or len(h1) < 60:
        return None
    spec = CATALOGUE["G3"]
    a = _atr(h1)
    if not a:
        return None

    trend = _trend_state(h4)
    if trend["direction"] == "none":
        return None
    if (trend["adx"] or 0) < 20:
        return None

    e20 = ema(h1.closes, 20)[-1]
    e50 = ema(h1.closes, 50)[-1]
    if e20 is None or e50 is None:
        return None

    price = h1.last.close
    zones = level_map.confluence_zones()
    near = [z for z in zones
            if z.contains(e20, 0.20) or z.contains(e50, 0.20)]
    if not near:
        return None
    zone = max(near, key=lambda z: z.strength)

    direction = "long" if trend["direction"] == "up" else "short"
    if direction == "long" and price > zone.high * 1.006:
        return None
    if direction == "short" and price < zone.low * 0.994:
        return None

    trigger_series = m15 or h1
    hits = scan(trigger_series, zone.mid)
    aligned = [h for h in hits
               if (h.direction == "bullish") == (direction == "long")]
    if not aligned:
        return None
    best = max(aligned, key=lambda h: h.strength)

    entry = trigger_series.last.close
    structural = zone.low if direction == "long" else zone.high
    swing = _last_swing_extreme(h1, direction)
    target = swing if swing else (
        entry + 3 * a if direction == "long" else entry - 3 * a
    )
    if direction == "long" and target <= entry:
        target = entry + 3 * a
    if direction == "short" and target >= entry:
        target = entry - 3 * a

    confidence = spec.base_confidence + (zone.strength - 0.5) * 0.2 \
        + (best.strength - 0.5) * 0.2
    confidence += 0.05 if (trend["adx"] or 0) > 30 else 0.0

    return SetupSignal(
        "G3", spec.name, get_spec(symbol).symbol, direction,
        entry, structural, target, max(0.0, min(0.95, confidence)), "H1",
        [
            f"H4 trend {trend['direction']} with ADX {trend['adx']:.0f}",
            f"pullback into {zone.describe()}",
            f"trigger: {best}",
        ],
        [], spec.failure_mode, a,
    )


def detect_g4(symbol: str, h1: CandleSeries | None, m15: CandleSeries | None,
              level_map: LevelMap) -> SetupSignal | None:
    """Round Number Rejection."""
    if h1 is None or len(h1) < 30:
        return None
    spec = CATALOGUE["G4"]
    a = _atr(h1)
    if not a:
        return None

    rounds = [l for l in level_map.levels
              if l.kind == "round" and l.strength >= 0.60]
    if not rounds:
        return None
    price = h1.last.close
    level = min(rounds, key=lambda l: abs(l.price - price))
    if abs(level.price - price) > a * 1.5:
        return None

    # Require an extended approach: this is a first-touch setup.
    recent = h1.tail(8)
    run = abs(recent.last.close - recent[0].open)
    if run < a * 2.0:
        return None

    trigger = m15 or h1
    hit = pin_bar(trigger, -1, _atr(trigger), level.price) or \
        engulfing(trigger, -1, _atr(trigger), level.price)
    if hit is None:
        return None

    approaching_up = recent.last.close > recent[0].open
    direction = "short" if approaching_up else "long"
    if (hit.direction == "bullish") != (direction == "long"):
        return None

    entry = trigger.last.close
    structural = trigger.last.high if direction == "short" else trigger.last.low
    target = entry - 3 * a if direction == "short" else entry + 3 * a

    touches = sum(1 for c in h1.tail(24) if c.low <= level.price <= c.high)
    warnings: list[str] = []
    confidence = spec.base_confidence + (hit.strength - 0.5) * 0.25
    if touches >= 3:
        confidence -= 0.20
        warnings.append(
            f"the {level.price:g} handle has been tested {touches} times in the "
            f"last 24 hours. Repeated tests mean it is being accumulated "
            f"against rather than defended, and the next attempt usually goes "
            f"through."
        )

    return SetupSignal(
        "G4", spec.name, get_spec(symbol).symbol, direction,
        entry, structural, target, max(0.0, min(0.95, confidence)), "M15",
        [f"extended {run / a:.1f}x ATR approach into the {level.price:g} handle",
         f"rejection: {hit}"],
        warnings, spec.failure_mode, a,
    )


def detect_g6(symbol: str, h1: CandleSeries | None, level_map: LevelMap,
              moment: datetime) -> SetupSignal | None:
    """Prior Day Extreme Sweep."""
    if h1 is None or len(h1) < 30:
        return None
    spec = CATALOGUE["G6"]
    a = _atr(h1)
    if not a:
        return None

    for kind, direction in (("prior_day_high", "bearish"),
                            ("prior_day_low", "bullish")):
        level = next((l for l in level_map.levels if l.kind == kind), None)
        if level is None:
            continue
        sweep = detect_sweep(h1, level.price, direction, -1, a, max_bars_outside=2)
        if not sweep:
            continue

        trade_dir = "long" if direction == "bullish" else "short"
        entry = h1.last.close
        structural = (level.price - sweep.penetration) if direction == "bullish" \
            else (level.price + sweep.penetration)
        opposite_kind = "prior_day_low" if kind == "prior_day_high" else "prior_day_high"
        opposite = next((l for l in level_map.levels if l.kind == opposite_kind), None)
        target = opposite.price if opposite else (
            entry + 3 * a if trade_dir == "long" else entry - 3 * a
        )
        if trade_dir == "long" and target <= entry:
            target = entry + 3 * a
        if trade_dir == "short" and target >= entry:
            target = entry - 3 * a

        warnings: list[str] = []
        confidence = spec.base_confidence + (sweep.strength - 0.6) * 0.3
        if _is_trend_day(h1, trade_dir):
            confidence -= 0.25
            warnings.append(
                "the last three sessions made consecutive higher highs or lower "
                "lows. On a trend day the prior extreme breaks and does not come "
                "back -- this setup is at its weakest here."
            )

        return SetupSignal(
            "G6", spec.name, get_spec(symbol).symbol, trade_dir,
            entry, structural, target, max(0.0, min(0.95, confidence)), "H1",
            [sweep.description], warnings, spec.failure_mode, a,
        )
    return None


def detect_g7(symbol: str, h1: CandleSeries | None,
              level_map: LevelMap) -> SetupSignal | None:
    """Failed Breakout Reversal."""
    if h1 is None or len(h1) < 30:
        return None
    spec = CATALOGUE["G7"]
    a = _atr(h1)
    if not a:
        return None

    candidates = [l for l in level_map.levels
                  if l.touches >= 2 and l.kind in
                  ("swing_high", "swing_low", "equal_highs", "equal_lows")]
    if not candidates:
        return None

    price = h1.last.close
    for level in sorted(candidates, key=lambda l: abs(l.price - price)):
        for direction in ("bullish", "bearish"):
            sweep = detect_sweep(h1, level.price, direction, -1, a,
                                 max_bars_outside=3, min_penetration_atr=0.25)
            if not sweep:
                continue
            trade_dir = "long" if direction == "bullish" else "short"
            entry = h1.last.close
            structural = (level.price - sweep.penetration) if direction == "bullish" \
                else (level.price + sweep.penetration)
            target = entry + 3 * a if trade_dir == "long" else entry - 3 * a

            confidence = spec.base_confidence + (level.strength - 0.5) * 0.2 \
                + (sweep.strength - 0.6) * 0.2
            return SetupSignal(
                "G7", spec.name, get_spec(symbol).symbol, trade_dir,
                entry, structural, target, max(0.0, min(0.95, confidence)), "H1",
                [f"{level.description}", sweep.description],
                [], spec.failure_mode, a,
            )
    return None


def detect_g8(symbol: str, h1: CandleSeries | None,
              m15: CandleSeries | None) -> SetupSignal | None:
    """Squeeze Expansion."""
    if h1 is None or len(h1) < 40:
        return None
    spec = CATALOGUE["G8"]
    a = _atr(h1)
    if not a:
        return None

    sq = squeeze_on(h1.highs, h1.lows, h1.closes, 20)
    recent = [v for v in sq[-8:-1] if v is not None]
    if len(recent) < 6 or not all(recent):
        return None
    if sq[-1]:  # still compressed; nothing has resolved yet
        return None

    from .indicators import bollinger
    up, mid, lo = bollinger(h1.closes, 20, 2.0)
    if up[-1] is None or lo[-1] is None:
        return None

    close = h1.last.close
    if close > up[-1]:
        direction, structural = "long", lo[-1]
    elif close < lo[-1]:
        direction, structural = "short", up[-1]
    else:
        return None

    width = abs(up[-1] - lo[-1])
    entry = close
    target = entry + 2 * width if direction == "long" else entry - 2 * width
    if abs(entry - structural) > a * 3.0:
        structural = entry - a * 1.5 if direction == "long" else entry + a * 1.5

    return SetupSignal(
        "G8", spec.name, get_spec(symbol).symbol, direction,
        entry, structural, target, spec.base_confidence, "H1",
        [f"squeeze held for {len(recent)} bars and released with a close "
         f"outside the band"],
        ["a squeeze can release, reverse and release again -- the first "
         "expansion is not always the real one"],
        spec.failure_mode, a,
    )


def detect_g9(symbol: str, h4: CandleSeries | None, h1: CandleSeries | None,
              level_map: LevelMap) -> SetupSignal | None:
    """Divergence Reversal at HTF Level."""
    if h4 is None or h1 is None or len(h4) < 40:
        return None
    spec = CATALOGUE["G9"]
    a = _atr(h4)
    if not a:
        return None

    div = divergence(h4)
    if div is None:
        return None

    zones = level_map.confluence_zones()
    at_level = next((z for z in zones
                     if div.at_level is not None and z.contains(div.at_level, 0.25)),
                    None)
    if at_level is None:
        return None

    mss = market_structure_shift(h1)
    if mss is None or mss.direction != div.direction:
        return None

    direction = "long" if div.direction == "bullish" else "short"
    entry = h1.last.close
    structural = div.at_level if div.at_level is not None else (
        entry - a if direction == "long" else entry + a
    )
    swing = _last_swing_extreme(h4, direction)
    target = swing if swing else (
        entry + 3 * a if direction == "long" else entry - 3 * a
    )
    if direction == "long" and target <= entry:
        target = entry + 3 * a
    if direction == "short" and target >= entry:
        target = entry - 3 * a

    return SetupSignal(
        "G9", spec.name, get_spec(symbol).symbol, direction,
        entry, structural, target,
        min(0.95, spec.base_confidence + (at_level.strength - 0.5) * 0.25), "H4",
        [div.description, f"at {at_level.describe()}", mss.description],
        ["divergence can persist for weeks in a strong trend -- the H1 "
         "structure break is what makes this actionable, not the divergence"],
        spec.failure_mode, a,
    )


def detect_g10(symbol: str, h1: CandleSeries | None,
               m15: CandleSeries | None) -> SetupSignal | None:
    """Fair Value Gap Retest."""
    if h1 is None or len(h1) < 40:
        return None
    spec = CATALOGUE["G10"]
    a = _atr(h1)
    if not a:
        return None

    trend = _trend_state(h1)
    if trend["direction"] == "none":
        return None
    want = "bullish" if trend["direction"] == "up" else "bearish"

    gaps = [g for g in fair_value_gaps(h1) if not g.filled and g.direction == want]
    if not gaps:
        return None

    price = h1.last.close
    gap = min(gaps, key=lambda g: abs(g.mid - price))
    if not (gap.low - a * 0.3 <= price <= gap.high + a * 0.3):
        return None

    trigger = m15 or h1
    hit = pin_bar(trigger, -1, _atr(trigger), gap.mid) or \
        engulfing(trigger, -1, _atr(trigger), gap.mid)
    if hit is None or hit.direction != want:
        return None

    direction = "long" if want == "bullish" else "short"
    entry = trigger.last.close
    structural = gap.low if direction == "long" else gap.high
    target = entry + 3 * a if direction == "long" else entry - 3 * a

    return SetupSignal(
        "G10", spec.name, get_spec(symbol).symbol, direction,
        entry, structural, target,
        min(0.95, spec.base_confidence + (hit.strength - 0.5) * 0.2), "H1",
        [f"unfilled {gap.direction} gap {gap.low:g}-{gap.high:g} "
         f"({gap.size_atr:.2f}x ATR) in the direction of the H1 trend",
         f"trigger: {hit}"],
        [], spec.failure_mode, a,
    )


# --- shared helpers ---------------------------------------------------------

def _atr(series: CandleSeries | None, period: int = 14) -> float | None:
    if series is None or len(series) < period + 1:
        return None
    values = atr(series.highs, series.lows, series.closes, period)
    return values[-1]


def _trend_state(series: CandleSeries) -> dict:
    """EMA stack plus ADX, reduced to a direction and a strength."""
    closes = series.closes
    e20, e50, e200 = ema(closes, 20)[-1], ema(closes, 50)[-1], ema(closes, 200)[-1]
    a_series, _, _ = adx(series.highs, series.lows, series.closes, 14)
    a_val = a_series[-1] if a_series else None

    direction = "none"
    if e20 is not None and e50 is not None:
        if e200 is not None:
            if e20 > e50 > e200:
                direction = "up"
            elif e20 < e50 < e200:
                direction = "down"
        else:
            direction = "up" if e20 > e50 else "down"
    return {"direction": direction, "adx": a_val, "ema20": e20,
            "ema50": e50, "ema200": e200}


def _last_swing_extreme(series: CandleSeries, direction: str) -> float | None:
    from .indicators import swing_points

    sh, sl = swing_points(series.highs, series.lows, 2, 2)
    if direction == "long" and sh:
        return series.highs[sh[-1]]
    if direction == "short" and sl:
        return series.lows[sl[-1]]
    return None


def _is_trend_day(series: CandleSeries, direction: str) -> bool:
    """Three consecutive sessions in one direction -- a poor reversal backdrop."""
    if len(series) < 72:
        return False
    daily_closes = [series[-1 - 24 * k].close for k in range(3)]
    if direction == "short":
        return daily_closes[0] > daily_closes[1] > daily_closes[2]
    return daily_closes[0] < daily_closes[1] < daily_closes[2]
