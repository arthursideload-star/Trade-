#!/usr/bin/env python3
"""Support and resistance levels from swing points.

A "level" is where price has repeatedly turned. The pattern rules in patterns.py
only count a candlestick signal when it sits at such a level, so the quality of
these levels decides the quality of every setup built on them.

Method: find swing highs/lows (a bar that is the extreme of a small window),
then cluster nearby swings into zones — a level touched three times matters more
than three separate near-identical lines. Distances are reported in price and in
pips so the sizing math and the human reader both get what they need.

Standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# JPY pairs quote to two decimals, so a pip is 0.01; everything else 0.0001.
PIP_SIZE_DEFAULT = 0.0001
PIP_SIZE_JPY = 0.01


def pip_size(symbol: str) -> float:
    return PIP_SIZE_JPY if symbol.upper().endswith("JPY") else PIP_SIZE_DEFAULT


@dataclass
class Level:
    price: float
    kind: str  # "support" or "resistance"
    touches: int

    def to_dict(self) -> dict:
        return {"price": round(self.price, 6), "kind": self.kind, "touches": self.touches}


@dataclass
class LevelReport:
    supports: list[Level]
    resistances: list[Level]
    nearest_support: Optional[Level]
    nearest_resistance: Optional[Level]
    distance_to_support_pips: Optional[float]
    distance_to_resistance_pips: Optional[float]
    pivot: Optional[dict]

    def to_dict(self) -> dict:
        return {
            "supports": [lv.to_dict() for lv in self.supports],
            "resistances": [lv.to_dict() for lv in self.resistances],
            "nearest_support": self.nearest_support.to_dict() if self.nearest_support else None,
            "nearest_resistance": (
                self.nearest_resistance.to_dict() if self.nearest_resistance else None
            ),
            "distance_to_support_pips": _round(self.distance_to_support_pips),
            "distance_to_resistance_pips": _round(self.distance_to_resistance_pips),
            "pivot": self.pivot,
        }


def _round(value: Optional[float], digits: int = 1) -> Optional[float]:
    return None if value is None else round(value, digits)


def find_swing_highs(highs: list[float], window: int = 2) -> list[int]:
    """Indices where a bar's high is the strict maximum of +/- window bars."""
    swings = []
    for i in range(window, len(highs) - window):
        pivot = highs[i]
        if all(pivot >= highs[j] for j in range(i - window, i + window + 1)) and any(
            pivot > highs[j] for j in range(i - window, i + window + 1) if j != i
        ):
            swings.append(i)
    return swings


def find_swing_lows(lows: list[float], window: int = 2) -> list[int]:
    """Indices where a bar's low is the strict minimum of +/- window bars."""
    swings = []
    for i in range(window, len(lows) - window):
        pivot = lows[i]
        if all(pivot <= lows[j] for j in range(i - window, i + window + 1)) and any(
            pivot < lows[j] for j in range(i - window, i + window + 1) if j != i
        ):
            swings.append(i)
    return swings


def cluster_levels(prices: list[float], kind: str, tolerance: float) -> list[Level]:
    """Merge prices within `tolerance` of each other into one level.

    The merged price is the mean of the cluster, and `touches` records how many
    swings fed it — the confirmation count that separates a real level from a
    one-off wick.
    """
    if not prices:
        return []

    ordered = sorted(prices)
    clusters: list[list[float]] = [[ordered[0]]]
    for price in ordered[1:]:
        if abs(price - clusters[-1][-1]) <= tolerance:
            clusters[-1].append(price)
        else:
            clusters.append([price])

    levels = [Level(price=sum(c) / len(c), kind=kind, touches=len(c)) for c in clusters]
    # Strongest (most-touched) first.
    levels.sort(key=lambda lv: (-lv.touches, lv.price))
    return levels


def pivot_points(prev_high: float, prev_low: float, prev_close: float) -> dict:
    """Classic floor-trader pivot and the first support/resistance around it."""
    pivot = (prev_high + prev_low + prev_close) / 3
    return {
        "pivot": round(pivot, 6),
        "r1": round(2 * pivot - prev_low, 6),
        "s1": round(2 * pivot - prev_high, 6),
        "r2": round(pivot + (prev_high - prev_low), 6),
        "s2": round(pivot - (prev_high - prev_low), 6),
    }


def analyze_levels(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    symbol: str = "EUR/USD",
    window: int = 2,
    tolerance_pips: float = 15.0,
) -> LevelReport:
    """Full level analysis for the most recent price."""
    if not closes:
        raise ValueError("closes must not be empty")

    pip = pip_size(symbol)
    tolerance = tolerance_pips * pip
    current = closes[-1]

    high_swings = [highs[i] for i in find_swing_highs(highs, window)]
    low_swings = [lows[i] for i in find_swing_lows(lows, window)]

    resistances = cluster_levels(high_swings, "resistance", tolerance)
    supports = cluster_levels(low_swings, "support", tolerance)

    # Nearest support is the highest level below price; nearest resistance the
    # lowest above. A level the price has already crossed is no longer that side.
    below = [lv for lv in supports + resistances if lv.price < current]
    above = [lv for lv in supports + resistances if lv.price > current]
    nearest_support = max(below, key=lambda lv: lv.price) if below else None
    nearest_resistance = min(above, key=lambda lv: lv.price) if above else None

    dist_support = (current - nearest_support.price) / pip if nearest_support else None
    dist_resistance = (nearest_resistance.price - current) / pip if nearest_resistance else None

    pivot = None
    if len(closes) >= 2:
        pivot = pivot_points(highs[-2], lows[-2], closes[-2])

    return LevelReport(
        supports=supports,
        resistances=resistances,
        nearest_support=nearest_support,
        nearest_resistance=nearest_resistance,
        distance_to_support_pips=dist_support,
        distance_to_resistance_pips=dist_resistance,
        pivot=pivot,
    )


def is_at_level(price: float, report: LevelReport, symbol: str, proximity_pips: float = 10.0) -> bool:
    """True when price sits within `proximity_pips` of any known level.

    This is the gate patterns.py uses: a candlestick pattern only counts when
    is_at_level is true.
    """
    pip = pip_size(symbol)
    threshold = proximity_pips * pip
    for level in report.supports + report.resistances:
        if abs(price - level.price) <= threshold:
            return True
    return False
