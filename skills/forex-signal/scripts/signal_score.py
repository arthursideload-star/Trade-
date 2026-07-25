#!/usr/bin/env python3
"""Weighted signal score from the deterministic analysis (Sprint B4).

Implements the ensemble in PLAN.md A5. Each factor votes in [-1, +1] (positive
= bullish, negative = bearish); the votes are combined with the plan's weights
into a net lean, from which direction and a confidence follow.

One honest deviation from the plan: it lists a 15% weight on *volume
confirmation*. Forex has no exchange volume, so that factor is unavailable and
its weight is redistributed proportionally across the factors that do have data,
rather than fed a fake zero that would drag every score toward neutral. Any
factor lacking data is handled the same way, so the weights always sum to 1 over
whatever is actually known.

Standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Weights from PLAN.md A5. Volume is present for completeness but is unavailable
# for forex and gets redistributed at runtime.
WEIGHTS = {
    "trend_alignment": 0.30,
    "momentum": 0.20,
    "pattern_at_level": 0.15,
    "volume": 0.15,
    "sr_proximity": 0.20,
}

# Confidence below this is treated as "wait" rather than a tradable signal.
MIN_CONFIDENCE_TO_TRADE = 55.0


@dataclass
class Factor:
    name: str
    contribution: Optional[float]  # [-1, +1], or None if no data
    detail: str


@dataclass
class ScoreResult:
    direction: str  # "long", "short" or "wait"
    confidence: float  # 0-100
    net: float  # [-1, +1] signed lean
    factors: list[Factor] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "direction": self.direction,
            "confidence": round(self.confidence, 1),
            "net_lean": round(self.net, 4),
            "factors": [
                {
                    "name": f.name,
                    "contribution": None if f.contribution is None else round(f.contribution, 3),
                    "weight": WEIGHTS[f.name],
                    "detail": f.detail,
                }
                for f in self.factors
            ],
        }


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def factor_trend_alignment(regimes_by_tf: dict[str, str]) -> Factor:
    """Average directional vote across the higher timeframes.

    A market trending up on 4h, 1h and 15m at once is the strongest tailwind;
    disagreement pulls the vote toward zero.
    """
    votes = []
    for tf in ("4h", "1h", "15min"):
        regime = regimes_by_tf.get(tf)
        if regime == "trend_up":
            votes.append(1.0)
        elif regime == "trend_down":
            votes.append(-1.0)
        elif regime in ("range", "volatile"):
            votes.append(0.0)
    if not votes:
        return Factor("trend_alignment", None, "No higher-timeframe regime available")
    avg = sum(votes) / len(votes)
    return Factor("trend_alignment", _clamp(avg), f"{len(votes)} timeframes, mean vote {avg:.2f}")


def factor_momentum(rsi: Optional[float], macd_hist: Optional[float]) -> Factor:
    """RSI distance from 50 plus the sign of the MACD histogram."""
    parts = []
    detail = []
    if rsi is not None:
        # RSI 50 = neutral, 80/20 ~ full vote.
        parts.append(_clamp((rsi - 50.0) / 30.0))
        detail.append(f"RSI {rsi:.0f}")
    if macd_hist is not None:
        parts.append(1.0 if macd_hist > 0 else -1.0 if macd_hist < 0 else 0.0)
        detail.append(f"MACD hist {macd_hist:+.5f}")
    if not parts:
        return Factor("momentum", None, "No momentum data")
    return Factor("momentum", _clamp(sum(parts) / len(parts)), ", ".join(detail))


def factor_pattern_at_level(patterns: list[dict], failed_breakout: Optional[dict]) -> Factor:
    """Level-confirmed patterns and a failed breakout vote directionally.

    Only patterns that already passed the "at a level" filter reach here, so
    their presence is meaningful on its own.
    """
    votes = []
    detail = []
    for p in patterns:
        if p["direction"] == "bullish":
            votes.append(1.0)
            detail.append(f"{p['name']} (bull)")
        elif p["direction"] == "bearish":
            votes.append(-1.0)
            detail.append(f"{p['name']} (bear)")
    if failed_breakout:
        votes.append(1.0 if failed_breakout["direction"] == "bullish" else -1.0)
        detail.append(f"failed breakout ({failed_breakout['direction']})")

    if not votes:
        return Factor("pattern_at_level", 0.0, "No level-confirmed pattern")
    return Factor("pattern_at_level", _clamp(sum(votes) / len(votes)), ", ".join(detail))


def factor_sr_proximity(
    dist_support_pips: Optional[float],
    dist_resistance_pips: Optional[float],
) -> Factor:
    """Near support leans long (room above); near resistance leans short.

    The vote scales with how much closer price is to one side than the other.
    """
    if dist_support_pips is None and dist_resistance_pips is None:
        return Factor("sr_proximity", None, "No levels around price")
    # Treat a missing side as far away.
    ds = dist_support_pips if dist_support_pips is not None else 1e9
    dr = dist_resistance_pips if dist_resistance_pips is not None else 1e9
    total = ds + dr
    if total <= 0:
        return Factor("sr_proximity", 0.0, "Price sitting on a level")
    # +1 when hugging support (ds=0), -1 when hugging resistance (dr=0).
    vote = (dr - ds) / total
    return Factor(
        "sr_proximity",
        _clamp(vote),
        f"{ds:.0f} pips to support, {dr:.0f} pips to resistance",
    )


def factor_volume() -> Factor:
    """Volume confirmation is unavailable for forex; contributes nothing."""
    return Factor("volume", None, "No exchange volume for forex; weight redistributed")


def combine(factors: list[Factor]) -> ScoreResult:
    """Combine factor votes, redistributing the weight of any missing factor."""
    available = [f for f in factors if f.contribution is not None]
    total_weight = sum(WEIGHTS[f.name] for f in available)

    if total_weight <= 0:
        return ScoreResult(direction="wait", confidence=0.0, net=0.0, factors=factors)

    net = sum(f.contribution * WEIGHTS[f.name] for f in available) / total_weight
    net = _clamp(net)
    confidence = abs(net) * 100.0

    if confidence < MIN_CONFIDENCE_TO_TRADE:
        direction = "wait"
    elif net > 0:
        direction = "long"
    else:
        direction = "short"

    return ScoreResult(direction=direction, confidence=confidence, net=net, factors=factors)


def score_from_analysis(analysis: dict) -> ScoreResult:
    """Build the factor set from a forex-analysis payload and combine.

    `analysis` is the JSON produced by skills/forex-analysis/scripts/analyze.py.
    The entry timeframe is 15min (PLAN.md A5); trend alignment reads the higher
    timeframes when present.
    """
    by_tf = {block["interval"]: block for block in analysis.get("timeframes", [])}
    entry = by_tf.get("15min") or next(iter(by_tf.values()), None)
    if entry is None:
        raise ValueError("analysis has no timeframes")

    regimes = {tf: block["regime"]["regime"] for tf, block in by_tf.items()}
    indicators = entry["indicators"]
    levels = entry["levels"]

    factors = [
        factor_trend_alignment(regimes),
        factor_momentum(indicators.get("rsi_14"), indicators.get("macd_histogram")),
        factor_pattern_at_level(
            entry.get("patterns_at_level", []), entry.get("failed_breakout")
        ),
        factor_volume(),
        factor_sr_proximity(
            levels.get("distance_to_support_pips"),
            levels.get("distance_to_resistance_pips"),
        ),
    ]
    return combine(factors)
