"""Level detection for gold and silver.

Metals respect three kinds of level unusually well:

1. Round numbers, because order flow clusters at prices humans can say out
   loud. Gold's 100/50/10 grid and silver's 5/1/0.50 grid are not arbitrary.
2. Swing structure, because the market genuinely reaches for the stops that
   sit behind prior highs and lows.
3. The prior session's extremes and the LBMA fix levels, because institutions
   benchmark against them.

Everything here returns levels with a strength score so the confluence logic
downstream can weigh them rather than treat all levels as equal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .candles import CandleSeries
from .indicators import swing_points
from .specs import get_spec, round_levels


@dataclass(frozen=True)
class Level:
    price: float
    kind: str            # "round", "swing_high", "swing_low", "prior_high", ...
    strength: float      # 0.0 - 1.0
    touches: int = 0
    description: str = ""

    def distance_pct(self, price: float) -> float:
        return abs(self.price - price) / price * 100.0


@dataclass
class LevelMap:
    symbol: str
    price: float
    levels: list[Level] = field(default_factory=list)

    def above(self, n: int = 5) -> list[Level]:
        return sorted([l for l in self.levels if l.price > self.price],
                      key=lambda l: l.price)[:n]

    def below(self, n: int = 5) -> list[Level]:
        return sorted([l for l in self.levels if l.price < self.price],
                      key=lambda l: l.price, reverse=True)[:n]

    def nearest(self, n: int = 3) -> list[Level]:
        return sorted(self.levels, key=lambda l: abs(l.price - self.price))[:n]

    def confluence_zones(self, tolerance_pct: float = 0.15) -> list["Zone"]:
        """Cluster levels that sit close enough to act as one zone.

        A single swing high is a level. A swing high that coincides with a
        round number and the prior day's high is a wall, and the difference
        matters more on metals than anywhere else.
        """
        if not self.levels:
            return []
        ordered = sorted(self.levels, key=lambda l: l.price)
        zones: list[Zone] = []
        bucket: list[Level] = [ordered[0]]
        for lvl in ordered[1:]:
            span = abs(lvl.price - bucket[0].price) / lvl.price * 100.0
            if span <= tolerance_pct:
                bucket.append(lvl)
            else:
                zones.append(Zone.from_levels(bucket))
                bucket = [lvl]
        zones.append(Zone.from_levels(bucket))
        return sorted(zones, key=lambda z: z.strength, reverse=True)


@dataclass(frozen=True)
class Zone:
    low: float
    high: float
    strength: float
    members: tuple[Level, ...]

    @classmethod
    def from_levels(cls, levels: list[Level]) -> "Zone":
        prices = [l.price for l in levels]
        if len(levels) == 1:
            # A lone level is worth exactly its own score -- clustering is what
            # earns the bonus, and there is nothing to cluster with.
            strength = min(0.99, levels[0].strength)
        else:
            # Confluence compounds but saturates: three coinciding levels are
            # much stronger than one, ten are not much stronger than three.
            total = sum(l.strength for l in levels)
            strength = min(1.0, total / (total + 0.8))
        return cls(min(prices), max(prices), strength, tuple(levels))

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2.0

    def contains(self, price: float, tolerance_pct: float = 0.05) -> bool:
        pad = self.mid * tolerance_pct / 100.0
        return self.low - pad <= price <= self.high + pad

    def describe(self) -> str:
        kinds = ", ".join(sorted({m.kind for m in self.members}))
        return f"{self.low:g}-{self.high:g} ({kinds}, strength {self.strength:.2f})"


# --- Round numbers ----------------------------------------------------------

def round_number_levels(symbol: str, price: float,
                        reach_pct: float = 2.0) -> list[Level]:
    """Round-number grid around the current price.

    Strength scales with the size of the step: the 4500 handle on gold matters
    more than 4510, which matters more than 4505.
    """
    steps = round_levels(symbol)
    span = price * reach_pct / 100.0
    out: list[Level] = []
    seen: set[float] = set()
    for rank, step in enumerate(steps):
        strength = [0.85, 0.60, 0.35][min(rank, 2)]
        start = int((price - span) / step)
        end = int((price + span) / step) + 1
        for k in range(start, end + 1):
            level = round(k * step, 6)
            if level <= 0 or level in seen:
                continue
            if abs(level - price) > span:
                continue
            seen.add(level)
            out.append(Level(
                price=level,
                kind="round",
                strength=strength,
                description=f"round number ({step:g} grid)",
            ))
    return out


# --- Swing structure --------------------------------------------------------

def swing_levels(series: CandleSeries, left: int = 2, right: int = 2,
                 lookback: int = 200, touch_tolerance_pct: float = 0.10
                 ) -> list[Level]:
    """Swing highs and lows, scored by how often price has respected them."""
    data = series.tail(lookback)
    if len(data) < left + right + 2:
        return []
    highs, lows = data.highs, data.lows
    sh_idx, sl_idx = swing_points(highs, lows, left, right)

    out: list[Level] = []
    for idx in sh_idx:
        price = highs[idx]
        touches = _count_touches(data, price, touch_tolerance_pct)
        out.append(Level(
            price=price,
            kind="swing_high",
            strength=min(0.9, 0.35 + 0.15 * touches),
            touches=touches,
            description=f"swing high, {touches} touch(es)",
        ))
    for idx in sl_idx:
        price = lows[idx]
        touches = _count_touches(data, price, touch_tolerance_pct)
        out.append(Level(
            price=price,
            kind="swing_low",
            strength=min(0.9, 0.35 + 0.15 * touches),
            touches=touches,
            description=f"swing low, {touches} touch(es)",
        ))
    return _merge_close(out, touch_tolerance_pct)


def equal_highs_lows(series: CandleSeries, tolerance_pct: float = 0.06,
                     lookback: int = 120) -> list[Level]:
    """Clusters of near-identical highs or lows.

    These are the clearest liquidity pools on a metals chart: two or three
    highs within a few tenths of a dollar have a visible pile of stop orders
    just above them, and the market reaches for it often enough that the sweep
    is a tradable event in its own right.
    """
    data = series.tail(lookback)
    sh_idx, sl_idx = swing_points(data.highs, data.lows, 2, 2)
    out: list[Level] = []

    for idx_list, source, kind in (
        (sh_idx, data.highs, "equal_highs"),
        (sl_idx, data.lows, "equal_lows"),
    ):
        prices = sorted(source[i] for i in idx_list)
        group: list[float] = []
        for p in prices:
            if group and abs(p - group[0]) / p * 100.0 <= tolerance_pct:
                group.append(p)
            else:
                if len(group) >= 2:
                    out.append(_equal_level(group, kind))
                group = [p]
        if len(group) >= 2:
            out.append(_equal_level(group, kind))
    return out


def _equal_level(group: list[float], kind: str) -> Level:
    price = sum(group) / len(group)
    return Level(
        price=round(price, 4),
        kind=kind,
        strength=min(0.95, 0.55 + 0.15 * (len(group) - 2)),
        touches=len(group),
        description=(
            f"{len(group)} near-equal {'highs' if 'high' in kind else 'lows'} "
            f"-- a visible pool of resting stop orders"
        ),
    )


# --- Session and prior-period levels ---------------------------------------

def prior_period_levels(series: CandleSeries, moment: datetime) -> list[Level]:
    """Previous day's and previous week's high, low and close.

    Institutional desks benchmark against these; on metals they act as
    magnets and as the first target of a session's move.
    """
    out: list[Level] = []
    day_start = moment.replace(hour=0, minute=0, second=0, microsecond=0)

    prev_day = [c for c in series
                if day_start - timedelta(days=1) <= c.ts < day_start]
    if prev_day:
        out.append(Level(max(c.high for c in prev_day), "prior_day_high", 0.65,
                         description="previous day high"))
        out.append(Level(min(c.low for c in prev_day), "prior_day_low", 0.65,
                         description="previous day low"))
        out.append(Level(prev_day[-1].close, "prior_day_close", 0.45,
                         description="previous day close"))

    week_start = day_start - timedelta(days=day_start.weekday())
    prev_week = [c for c in series
                 if week_start - timedelta(days=7) <= c.ts < week_start]
    if prev_week:
        out.append(Level(max(c.high for c in prev_week), "prior_week_high", 0.75,
                         description="previous week high"))
        out.append(Level(min(c.low for c in prev_week), "prior_week_low", 0.75,
                         description="previous week low"))
    return out


def session_range_levels(series: CandleSeries, moment: datetime) -> list[Level]:
    """High and low of the Asian session -- London's first liquidity target."""
    from .sessions import asian_range

    rng = asian_range(series, moment)
    if rng is None:
        return []
    high, low = rng
    return [
        Level(high, "asian_high", 0.70,
              description="Asian session high -- the liquidity London reaches for"),
        Level(low, "asian_low", 0.70,
              description="Asian session low -- the liquidity London reaches for"),
    ]


# --- Fibonacci and pivots ---------------------------------------------------

GOLDEN_POCKET = (0.618, 0.65)


def fib_levels(swing_low: float, swing_high: float,
               direction: str = "long") -> list[Level]:
    """Retracement levels for a completed swing.

    The 0.618-0.65 golden pocket earns a higher score than the other ratios
    because it is the only one with a consistent showing in the metals data;
    the rest are included as context, not as signals.
    """
    span = swing_high - swing_low
    if span <= 0:
        return []
    ratios = {0.236: 0.25, 0.382: 0.45, 0.5: 0.50,
              0.618: 0.70, 0.65: 0.70, 0.786: 0.45}
    out: list[Level] = []
    for ratio, strength in ratios.items():
        price = (swing_high - span * ratio) if direction == "long" \
            else (swing_low + span * ratio)
        tag = "golden pocket" if ratio in GOLDEN_POCKET else "retracement"
        out.append(Level(round(price, 4), f"fib_{ratio}", strength,
                         description=f"{ratio:.3f} {tag}"))
    return out


def pivot_points(high: float, low: float, close: float) -> dict[str, float]:
    """Classic floor-trader pivots from the prior period."""
    p = (high + low + close) / 3.0
    return {
        "P": p,
        "R1": 2 * p - low,
        "S1": 2 * p - high,
        "R2": p + (high - low),
        "S2": p - (high - low),
        "R3": high + 2 * (p - low),
        "S3": low - 2 * (high - p),
    }


def pivot_levels(high: float, low: float, close: float) -> list[Level]:
    pivots = pivot_points(high, low, close)
    strengths = {"P": 0.60, "R1": 0.50, "S1": 0.50,
                 "R2": 0.40, "S2": 0.40, "R3": 0.30, "S3": 0.30}
    return [
        Level(round(price, 4), f"pivot_{name}", strengths[name],
              description=f"floor pivot {name}")
        for name, price in pivots.items()
    ]


# --- Assembly ---------------------------------------------------------------

def build_level_map(
    symbol: str,
    price: float,
    htf: CandleSeries | None = None,
    ltf: CandleSeries | None = None,
    moment: datetime | None = None,
    reach_pct: float = 2.0,
) -> LevelMap:
    """Assemble every level type into one scored map.

    `htf` should be the 4h or daily series (structure), `ltf` the 15m or 1h
    series (session detail).
    """
    levels: list[Level] = list(round_number_levels(symbol, price, reach_pct))

    if htf is not None and len(htf) > 10:
        levels += swing_levels(htf)
        levels += equal_highs_lows(htf)
        if len(htf) >= 2:
            prev = htf[-2]
            levels += pivot_levels(prev.high, prev.low, prev.close)

    if ltf is not None and len(ltf) > 10:
        levels += swing_levels(ltf, lookback=120)
        levels += equal_highs_lows(ltf)
        if moment is not None:
            levels += prior_period_levels(ltf, moment)
            levels += session_range_levels(ltf, moment)

    span = price * reach_pct / 100.0
    levels = [l for l in levels if abs(l.price - price) <= span * 1.5]
    return LevelMap(symbol=get_spec(symbol).symbol, price=price, levels=levels)


# --- helpers ----------------------------------------------------------------

def _count_touches(series: CandleSeries, price: float,
                   tolerance_pct: float) -> int:
    pad = price * tolerance_pct / 100.0
    return sum(1 for c in series if c.low - pad <= price <= c.high + pad)


def _merge_close(levels: list[Level], tolerance_pct: float) -> list[Level]:
    """Collapse levels that are effectively the same price.

    The merged description is summarised rather than concatenated. Chaining
    "swing low, 20 touches + swing low, 24 touches + ..." across a dozen merges
    produces a line nobody reads, which defeats the purpose of explaining the
    level at all.
    """
    if not levels:
        return []
    ordered = sorted(levels, key=lambda l: l.price)
    merged: list[Level] = []
    counts: list[int] = []
    for lvl in ordered:
        if merged and abs(lvl.price - merged[-1].price) / lvl.price * 100.0 <= tolerance_pct:
            prev = merged[-1]
            counts[-1] += 1
            touches = prev.touches + lvl.touches
            kinds = "swings" if prev.kind != lvl.kind else prev.kind.replace("_", " ")
            merged[-1] = Level(
                price=(prev.price * counts[-1] + lvl.price) / (counts[-1] + 1),
                kind=prev.kind,
                strength=min(0.95, max(prev.strength, lvl.strength) + 0.10),
                touches=touches,
                description=(
                    f"{counts[-1] + 1} overlapping {kinds}, {touches} touches "
                    f"in total"
                ),
            )
        else:
            merged.append(lvl)
            counts.append(1)
    return merged
