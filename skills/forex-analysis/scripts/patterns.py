#!/usr/bin/env python3
"""Candlestick patterns and failed-breakout signatures (Sprint B3).

The governing rule from BOT-PLAN.md 3.2 and TRADING-WISSEN.md III/XIV: a pattern
only counts when it forms **at a level**. A hammer in the middle of nowhere is
noise; a hammer on a support that has held three times is a signal. So detection
is split in two:

  detect_patterns()  - the raw geometry of the last bar(s)
  patterns_at_level() - the same, filtered to those sitting on a known level

Only the filtered set should ever feed a recommendation.

A failed breakout (sweep + reclaim) is treated separately because it is defined
relative to a level by construction (TRADING-WISSEN.md XVI.9/XVIII).

Standard library only. OHLC lists are oldest-first.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import levels as levels_mod

# Geometry thresholds. Kept in code so a tweak is a reviewable change, but these
# are shape parameters, not risk limits.
DOJI_BODY_RATIO = 0.1  # body <= 10% of range = doji
HAMMER_WICK_RATIO = 2.0  # lower wick >= 2x body for a hammer
HAMMER_OPP_WICK_RATIO = 0.3  # and only a small wick on the other side


@dataclass
class Candle:
    open: float
    high: float
    low: float
    close: float

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def bullish(self) -> bool:
        return self.close > self.open

    @property
    def bearish(self) -> bool:
        return self.close < self.open


@dataclass
class Pattern:
    name: str
    direction: str  # "bullish", "bearish" or "neutral"
    index: int  # bar index the pattern completes on
    at_level: Optional[bool] = None
    level_price: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "direction": self.direction,
            "index": self.index,
            "at_level": self.at_level,
            "level_price": None if self.level_price is None else round(self.level_price, 6),
        }


def _candle(highs, lows, opens, closes, i) -> Candle:
    return Candle(open=opens[i], high=highs[i], low=lows[i], close=closes[i])


def is_doji(c: Candle) -> bool:
    if c.range == 0:
        return False
    return c.body <= DOJI_BODY_RATIO * c.range


def is_hammer(c: Candle) -> bool:
    """Long lower wick, small body near the top, tiny upper wick."""
    if c.body == 0 or c.range == 0:
        return False
    return (
        c.lower_wick >= HAMMER_WICK_RATIO * c.body
        and c.upper_wick <= HAMMER_OPP_WICK_RATIO * c.range
    )


def is_shooting_star(c: Candle) -> bool:
    """Long upper wick, small body near the bottom, tiny lower wick."""
    if c.body == 0 or c.range == 0:
        return False
    return (
        c.upper_wick >= HAMMER_WICK_RATIO * c.body
        and c.lower_wick <= HAMMER_OPP_WICK_RATIO * c.range
    )


def is_bullish_engulfing(prev: Candle, cur: Candle) -> bool:
    """A down bar wholly engulfed by the next up bar's body."""
    return (
        prev.bearish
        and cur.bullish
        and cur.close >= prev.open
        and cur.open <= prev.close
        and cur.body > prev.body
    )


def is_bearish_engulfing(prev: Candle, cur: Candle) -> bool:
    """An up bar wholly engulfed by the next down bar's body."""
    return (
        prev.bullish
        and cur.bearish
        and cur.open >= prev.close
        and cur.close <= prev.open
        and cur.body > prev.body
    )


def is_morning_star(a: Candle, b: Candle, c: Candle) -> bool:
    """Down bar, small indecision bar, strong up bar closing into the first."""
    midpoint = (a.open + a.close) / 2
    return (
        a.bearish
        and b.body < a.body
        and c.bullish
        and c.close > midpoint
    )


def is_evening_star(a: Candle, b: Candle, c: Candle) -> bool:
    """Up bar, small indecision bar, strong down bar closing into the first."""
    midpoint = (a.open + a.close) / 2
    return (
        a.bullish
        and b.body < a.body
        and c.bearish
        and c.close < midpoint
    )


def detect_patterns(
    highs: list[float],
    lows: list[float],
    opens: list[float],
    closes: list[float],
    index: Optional[int] = None,
) -> list[Pattern]:
    """Detect patterns completing on `index` (default: the last bar)."""
    n = len(closes)
    if n == 0:
        return []
    i = n - 1 if index is None else index
    if not 0 <= i < n:
        raise IndexError(f"index {i} out of range for {n} bars")

    found: list[Pattern] = []
    cur = _candle(highs, lows, opens, closes, i)

    if is_hammer(cur):
        found.append(Pattern("hammer", "bullish", i))
    if is_shooting_star(cur):
        found.append(Pattern("shooting_star", "bearish", i))
    if is_doji(cur):
        found.append(Pattern("doji", "neutral", i))

    if i >= 1:
        prev = _candle(highs, lows, opens, closes, i - 1)
        if is_bullish_engulfing(prev, cur):
            found.append(Pattern("bullish_engulfing", "bullish", i))
        if is_bearish_engulfing(prev, cur):
            found.append(Pattern("bearish_engulfing", "bearish", i))

    if i >= 2:
        a = _candle(highs, lows, opens, closes, i - 2)
        b = _candle(highs, lows, opens, closes, i - 1)
        if is_morning_star(a, b, cur):
            found.append(Pattern("morning_star", "bullish", i))
        if is_evening_star(a, b, cur):
            found.append(Pattern("evening_star", "bearish", i))

    return found


def patterns_at_level(
    highs: list[float],
    lows: list[float],
    opens: list[float],
    closes: list[float],
    level_report: levels_mod.LevelReport,
    symbol: str,
    proximity_pips: float = 10.0,
    index: Optional[int] = None,
) -> list[Pattern]:
    """Detect patterns, then keep only those sitting on a known level.

    The level test uses the bar's extreme in the pattern's direction — a bullish
    reversal is judged at its low (where it tested support), a bearish one at its
    high — because that wick is what actually touched the level.
    """
    raw = detect_patterns(highs, lows, opens, closes, index)
    i = (len(closes) - 1) if index is None else index

    pip = levels_mod.pip_size(symbol)
    threshold = proximity_pips * pip
    all_levels = level_report.supports + level_report.resistances

    annotated: list[Pattern] = []
    for pattern in raw:
        if pattern.direction == "bullish":
            probe = lows[i]
        elif pattern.direction == "bearish":
            probe = highs[i]
        else:
            probe = closes[i]

        nearest = _nearest_level(probe, all_levels, threshold)
        pattern.at_level = nearest is not None
        pattern.level_price = nearest
        annotated.append(pattern)

    # Only patterns confirmed at a level are signal; the rest are dropped.
    return [p for p in annotated if p.at_level]


def _nearest_level(price: float, all_levels, threshold: float) -> Optional[float]:
    best = None
    best_dist = threshold
    for level in all_levels:
        dist = abs(price - level.price)
        if dist <= best_dist:
            best_dist = dist
            best = level.price
    return best


@dataclass
class FailedBreakout:
    direction: str  # "bullish" (failed break down) or "bearish" (failed break up)
    level_price: float
    index: int
    reason: str

    def to_dict(self) -> dict:
        return {
            "type": "failed_breakout",
            "direction": self.direction,
            "level_price": round(self.level_price, 6),
            "index": self.index,
            "reason": self.reason,
        }


def detect_failed_breakout(
    highs: list[float],
    lows: list[float],
    opens: list[float],
    closes: list[float],
    level_report: levels_mod.LevelReport,
    symbol: str,
    sweep_pips: float = 3.0,
    index: Optional[int] = None,
) -> Optional[FailedBreakout]:
    """A sweep of a level that reclaims: the classic trap (XVI.9/XVIII).

    Bearish: the bar's high pokes above a resistance by at least `sweep_pips`,
    but it closes back below that resistance — buyers were trapped.
    Bullish: the mirror image on a support.
    """
    n = len(closes)
    if n == 0:
        return None
    i = n - 1 if index is None else index
    pip = levels_mod.pip_size(symbol)
    sweep = sweep_pips * pip

    high, low, close = highs[i], lows[i], closes[i]

    # Failed break above a resistance -> bearish reclaim.
    for level in level_report.resistances:
        if high >= level.price + sweep and close < level.price:
            return FailedBreakout(
                direction="bearish",
                level_price=level.price,
                index=i,
                reason=(
                    f"High {high:.5f} swept resistance {level.price:.5f} "
                    f"but closed back below at {close:.5f}"
                ),
            )

    # Failed break below a support -> bullish reclaim.
    for level in level_report.supports:
        if low <= level.price - sweep and close > level.price:
            return FailedBreakout(
                direction="bullish",
                level_price=level.price,
                index=i,
                reason=(
                    f"Low {low:.5f} swept support {level.price:.5f} "
                    f"but closed back above at {close:.5f}"
                ),
            )

    return None
