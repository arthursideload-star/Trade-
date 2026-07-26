"""Candle and structure pattern detection, tuned for metals.

Two design decisions that differ from generic pattern libraries:

1. **Patterns are only reported at a level.** A pin bar in the middle of a
   range is noise. The same pin bar rejecting the previous day's high is
   information. Every detector here takes an optional level and scores the
   pattern lower when it fires in open space.

2. **Wick thresholds are volatility-normalised.** Gold's wicks are long by
   nature -- the market reaches through levels to collect stops before moving.
   A fixed "wick must be 2x the body" rule fires constantly on gold and rarely
   on a quiet forex pair. Thresholds here are expressed relative to ATR.
"""

from __future__ import annotations

from dataclasses import dataclass
from .candles import Candle, CandleSeries
from .indicators import atr, rsi, swing_points


@dataclass(frozen=True)
class PatternHit:
    name: str
    index: int
    direction: str          # "bullish" | "bearish"
    strength: float         # 0.0 - 1.0
    at_level: float | None
    description: str

    def __str__(self) -> str:
        loc = f" at {self.at_level:g}" if self.at_level is not None else ""
        return f"{self.name} ({self.direction}, {self.strength:.2f}){loc}"


# --- Single-candle patterns -------------------------------------------------

def pin_bar(series: CandleSeries, index: int = -1, atr_value: float | None = None,
            level: float | None = None) -> PatternHit | None:
    """Long wick rejecting a level, small body at the opposite end.

    On metals the wick length is measured against ATR rather than against the
    body, because a gold bar can have a large body *and* a large wick and
    still be a clean rejection.
    """
    c = series[index]
    if c.range <= 0:
        return None
    a = atr_value or _atr_at(series, index)
    if not a:
        return None

    upper, lower = c.upper_wick, c.lower_wick
    body_frac = c.body_ratio

    if lower >= a * 0.6 and lower > upper * 2 and body_frac < 0.45:
        direction, wick = "bullish", lower
    elif upper >= a * 0.6 and upper > lower * 2 and body_frac < 0.45:
        direction, wick = "bearish", upper
    else:
        return None

    strength = min(0.9, 0.35 + (wick / a) * 0.20 + (0.45 - body_frac) * 0.4)
    strength = _level_adjust(strength, c, level)
    return PatternHit(
        "pin_bar", _abs_index(series, index), direction, strength, level,
        f"wick {wick:.3f} USD/oz = {wick / a:.2f}x ATR, body {body_frac:.0%} of range",
    )


def marubozu(series: CandleSeries, index: int = -1,
             atr_value: float | None = None) -> PatternHit | None:
    """Full-body candle with almost no wick -- one-sided pressure.

    On gold this is the signature of a news-driven repricing rather than of
    accumulation, so it is reported as momentum, not as a reversal.
    """
    c = series[index]
    a = atr_value or _atr_at(series, index)
    if not a or c.range <= 0:
        return None
    if c.body_ratio < 0.85 or c.range < a * 0.9:
        return None
    direction = "bullish" if c.bullish else "bearish"
    strength = min(0.85, 0.45 + (c.range / a - 0.9) * 0.25)
    return PatternHit(
        "marubozu", _abs_index(series, index), direction, strength, None,
        f"body is {c.body_ratio:.0%} of a {c.range / a:.2f}x ATR range -- "
        f"one-sided repricing, treat as momentum not reversal",
    )


def doji(series: CandleSeries, index: int = -1,
         atr_value: float | None = None, level: float | None = None
         ) -> PatternHit | None:
    """Indecision. Only meaningful after a directional run into a level."""
    c = series[index]
    a = atr_value or _atr_at(series, index)
    if not a or c.range <= 0:
        return None
    if c.body_ratio > 0.10 or c.range < a * 0.5:
        return None
    prior = series[index - 3: index] if _abs_index(series, index) >= 3 else []
    if len(prior) < 3:
        return None
    run_up = all(x.close > x.open for x in prior)
    run_down = all(x.close < x.open for x in prior)
    if not (run_up or run_down):
        return None
    direction = "bearish" if run_up else "bullish"
    strength = _level_adjust(0.40, c, level)
    return PatternHit(
        "doji", _abs_index(series, index), direction, strength, level,
        "indecision after a three-bar directional run",
    )


# --- Two- and three-candle patterns ----------------------------------------

def engulfing(series: CandleSeries, index: int = -1,
              atr_value: float | None = None, level: float | None = None
              ) -> PatternHit | None:
    """Body of the current bar swallows the previous body.

    Requires the engulfing bar to close beyond the prior bar's extreme, not
    merely beyond its body -- the weaker definition fires far too often on
    metals to be usable.
    """
    i = _abs_index(series, index)
    if i < 1:
        return None
    prev, cur = series[i - 1], series[i]
    a = atr_value or _atr_at(series, index)
    if not a:
        return None

    if cur.bullish and prev.bearish and cur.close > prev.high and cur.open <= prev.close:
        direction = "bullish"
    elif cur.bearish and prev.bullish and cur.close < prev.low and cur.open >= prev.close:
        direction = "bearish"
    else:
        return None

    size = cur.body / a
    if size < 0.5:
        return None
    strength = _level_adjust(min(0.85, 0.40 + size * 0.20), cur, level)
    return PatternHit(
        "engulfing", i, direction, strength, level,
        f"body {size:.2f}x ATR, closes beyond the prior bar's extreme",
    )


def inside_bar(series: CandleSeries, index: int = -1) -> PatternHit | None:
    """Contraction. Direction is unknown until the break -- reported neutral-ish.

    Useful on metals as a volatility signal ahead of a session open rather
    than as a directional pattern.
    """
    i = _abs_index(series, index)
    if i < 1:
        return None
    prev, cur = series[i - 1], series[i]
    if not (cur.high <= prev.high and cur.low >= prev.low):
        return None
    compression = 1.0 - (cur.range / prev.range if prev.range else 1.0)
    direction = "bullish" if cur.close > cur.open else "bearish"
    return PatternHit(
        "inside_bar", i, direction, min(0.45, 0.20 + compression * 0.4), None,
        f"range compressed {compression:.0%} inside the prior bar -- "
        f"expansion pending, direction not yet decided",
    )


def three_bar_reversal(series: CandleSeries, index: int = -1,
                       level: float | None = None) -> PatternHit | None:
    """Morning/evening star: impulse, pause, reversal."""
    i = _abs_index(series, index)
    if i < 2:
        return None
    a, b, c = series[i - 2], series[i - 1], series[i]
    if b.range <= 0 or a.range <= 0:
        return None
    if b.body_ratio > 0.35:
        return None
    mid_a = (a.open + a.close) / 2.0

    if a.bearish and c.bullish and c.close > mid_a and b.low <= min(a.low, c.low):
        direction = "bullish"
    elif a.bullish and c.bearish and c.close < mid_a and b.high >= max(a.high, c.high):
        direction = "bearish"
    else:
        return None
    return PatternHit(
        "three_bar_reversal", i, direction, _level_adjust(0.60, c, level), level,
        "impulse, indecision, reversal closing past the midpoint of bar one",
    )


# --- Structure patterns: the ones that matter most on metals ----------------

@dataclass(frozen=True)
class SweepHit:
    """A liquidity sweep: price takes out a level, then closes back inside.

    This is the single most characteristic metals pattern. Gold needs
    liquidity to move, so it reaches through obvious levels to collect the
    stops resting there, then moves in the opposite direction. Distinguishing
    a sweep from a genuine breakout is most of the edge.
    """

    index: int
    direction: str          # "bullish" = swept lows, expect up
    level: float
    penetration: float      # how far past the level, USD/oz
    penetration_atr: float
    close_back_inside: bool
    bars_outside: int
    strength: float
    description: str


def detect_sweep(
    series: CandleSeries,
    level: float,
    direction: str,
    index: int = -1,
    atr_value: float | None = None,
    max_bars_outside: int = 3,
    min_penetration_atr: float = 0.10,
) -> SweepHit | None:
    """Detect a sweep of `level` finishing at `index`.

    `direction` is the expected move after the sweep: "bullish" means the
    lows were swept. A sweep is confirmed only when price closes back on the
    original side within `max_bars_outside` bars -- otherwise it is a
    breakout, which is the opposite trade.
    """
    i = _abs_index(series, index)
    a = atr_value or _atr_at(series, index)
    if not a or i < max_bars_outside:
        return None

    window = series[max(0, i - max_bars_outside): i + 1]
    cur = series[i]

    if direction == "bullish":
        breached = [c for c in window if c.low < level]
        if not breached:
            return None
        extreme = min(c.low for c in breached)
        penetration = level - extreme
        back_inside = cur.close > level
        bars_outside = sum(1 for c in window if c.close < level)
    elif direction == "bearish":
        breached = [c for c in window if c.high > level]
        if not breached:
            return None
        extreme = max(c.high for c in breached)
        penetration = extreme - level
        back_inside = cur.close < level
        bars_outside = sum(1 for c in window if c.close > level)
    else:
        raise ValueError("direction must be 'bullish' or 'bearish'")

    pen_atr = penetration / a
    if pen_atr < min_penetration_atr:
        return None
    if not back_inside:
        return None

    # A shallow, fast sweep that closes straight back is the cleanest signal.
    # A deep one that took several bars to recover is closer to a failed
    # breakout, which resolves less reliably.
    depth_score = 0.75 if 0.15 <= pen_atr <= 1.2 else 0.45
    speed_score = {0: 0.0, 1: 0.20, 2: 0.10}.get(bars_outside, 0.0)
    strength = min(0.95, depth_score + speed_score)

    return SweepHit(
        index=i,
        direction=direction,
        level=level,
        penetration=penetration,
        penetration_atr=pen_atr,
        close_back_inside=True,
        bars_outside=bars_outside,
        strength=strength,
        description=(
            f"swept {'lows' if direction == 'bullish' else 'highs'} at "
            f"{level:g} by {penetration:.3f} USD/oz ({pen_atr:.2f}x ATR) and "
            f"closed back inside within {bars_outside + 1} bar(s)"
        ),
    )


def market_structure_shift(series: CandleSeries, lookback: int = 40,
                           left: int = 2, right: int = 2) -> PatternHit | None:
    """Break of the most recent opposing swing -- confirmation after a sweep.

    A sweep alone is a hypothesis. A sweep followed by a close beyond the last
    swing in the new direction is the confirmation the entry waits for.
    """
    data = series.tail(lookback)
    if len(data) < left + right + 5:
        return None
    sh_idx, sl_idx = swing_points(data.highs, data.lows, left, right)
    if not sh_idx or not sl_idx:
        return None

    last_close = data.last.close
    recent_high = data.highs[sh_idx[-1]]
    recent_low = data.lows[sl_idx[-1]]

    if last_close > recent_high and sh_idx[-1] < len(data) - 1:
        return PatternHit(
            "market_structure_shift", len(series) - 1, "bullish", 0.65,
            recent_high,
            f"close {last_close:g} above the last swing high {recent_high:g} -- "
            f"structure has shifted up",
        )
    if last_close < recent_low and sl_idx[-1] < len(data) - 1:
        return PatternHit(
            "market_structure_shift", len(series) - 1, "bearish", 0.65,
            recent_low,
            f"close {last_close:g} below the last swing low {recent_low:g} -- "
            f"structure has shifted down",
        )
    return None


@dataclass(frozen=True)
class FairValueGap:
    """Three-bar imbalance: bar 1's extreme and bar 3's opposite extreme
    do not overlap, leaving a price band that traded through in one direction
    only. Metals fill these often enough to be worth watching as entry zones.
    """

    start_index: int
    low: float
    high: float
    direction: str          # "bullish" gap sits below price
    size_atr: float
    filled: bool

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2.0


def fair_value_gaps(series: CandleSeries, lookback: int = 60,
                    min_size_atr: float = 0.20) -> list[FairValueGap]:
    data = series.tail(lookback)
    a_series = atr(data.highs, data.lows, data.closes, 14)
    out: list[FairValueGap] = []
    for i in range(2, len(data)):
        a = a_series[i]
        if not a:
            continue
        first, third = data[i - 2], data[i]
        if third.low > first.high:
            lo, hi, direction = first.high, third.low, "bullish"
        elif third.high < first.low:
            lo, hi, direction = third.high, first.low, "bearish"
        else:
            continue
        size = (hi - lo) / a
        if size < min_size_atr:
            continue
        later = data[i + 1:]
        filled = any(c.low <= lo and c.high >= hi for c in later) or \
            any(lo <= c.close <= hi for c in later)
        out.append(FairValueGap(i, lo, hi, direction, size, filled))
    return out


def divergence(series: CandleSeries, period: int = 14,
               lookback: int = 60) -> PatternHit | None:
    """RSI divergence against price at the two most recent swings.

    Reported at moderate strength only: divergence is a warning that momentum
    is fading, not an entry. On metals it can persist for a long time in a
    strong trend, which is exactly when acting on it is most expensive.
    """
    data = series.tail(lookback)
    r = rsi(data.closes, period)
    sh_idx, sl_idx = swing_points(data.highs, data.lows, 2, 2)

    def valid(idxs: list[int]) -> list[int]:
        return [i for i in idxs if r[i] is not None][-2:]

    highs = valid(sh_idx)
    if len(highs) == 2:
        i1, i2 = highs
        if data.highs[i2] > data.highs[i1] and r[i2] < r[i1]:  # type: ignore[operator]
            return PatternHit(
                "bearish_divergence", i2, "bearish", 0.45, data.highs[i2],
                f"price made a higher high ({data.highs[i1]:g} -> "
                f"{data.highs[i2]:g}) while RSI made a lower high "
                f"({r[i1]:.1f} -> {r[i2]:.1f}); momentum is fading, but this "
                f"is a warning, not a trigger",
            )

    lows = valid(sl_idx)
    if len(lows) == 2:
        i1, i2 = lows
        if data.lows[i2] < data.lows[i1] and r[i2] > r[i1]:  # type: ignore[operator]
            return PatternHit(
                "bullish_divergence", i2, "bullish", 0.45, data.lows[i2],
                f"price made a lower low ({data.lows[i1]:g} -> "
                f"{data.lows[i2]:g}) while RSI made a higher low "
                f"({r[i1]:.1f} -> {r[i2]:.1f}); momentum is fading, but this "
                f"is a warning, not a trigger",
            )
    return None


# --- Aggregation -------------------------------------------------------------

def scan(series: CandleSeries, level: float | None = None,
         index: int = -1) -> list[PatternHit]:
    """Run every candle detector at one bar and return whatever fires."""
    a = _atr_at(series, index)
    hits: list[PatternHit] = []
    for fn in (
        lambda: pin_bar(series, index, a, level),
        lambda: engulfing(series, index, a, level),
        lambda: three_bar_reversal(series, index, level),
        lambda: doji(series, index, a, level),
        lambda: marubozu(series, index, a),
        lambda: inside_bar(series, index),
    ):
        hit = fn()
        if hit:
            hits.append(hit)
    return sorted(hits, key=lambda h: h.strength, reverse=True)


# --- helpers ----------------------------------------------------------------

def _abs_index(series: CandleSeries, index: int) -> int:
    return index if index >= 0 else len(series) + index


def _atr_at(series: CandleSeries, index: int, period: int = 14) -> float | None:
    i = _abs_index(series, index)
    if i < period:
        return None
    values = atr(series.highs, series.lows, series.closes, period)
    return values[i]


def _level_adjust(strength: float, candle: Candle, level: float | None,
                  tolerance_pct: float = 0.12) -> float:
    """Raise the score when the pattern actually touches its level, cut it hard
    when it fires in open space. This is the rule that keeps the pattern
    output usable on a market that prints reversal shapes all day long.
    """
    if level is None:
        return strength * 0.55
    pad = level * tolerance_pct / 100.0
    touched = candle.low - pad <= level <= candle.high + pad
    return min(0.95, strength * 1.15) if touched else strength * 0.55
