#!/usr/bin/env python3
"""Regime classification: trend, range or volatile.

Implements the table in PLAN.md section A5. The regime decides which trades are
even allowed downstream — an up-trend permits only longs, a range warns against
trend trades — so it is deliberately conservative: a bar is only called
"trending" when the EMA fan and ADX agree.

Standard library only. Consumes the indicator series from indicators.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import indicators as ind

# --- thresholds (from PLAN.md A5) ------------------------------------------
# These are classification thresholds, not risk limits, but they still live in
# code so a change is a reviewable commit rather than a silent config edit.
ADX_TREND = 25.0  # above this the market is trending
ADX_RANGE = 20.0  # below this the market is ranging
ATR_VOLATILE_MULTIPLE = 1.5  # ATR above this multiple of its own average = volatile
ATR_AVERAGE_PERIOD = 50  # window for the "normal" ATR baseline

TREND_UP = "trend_up"
TREND_DOWN = "trend_down"
RANGE = "range"
VOLATILE = "volatile"
UNDEFINED = "undefined"

# Which directions the regime permits. forex-signal enforces this.
ALLOWED_DIRECTION = {
    TREND_UP: "long_only",
    TREND_DOWN: "short_only",
    RANGE: "both_cautious",
    VOLATILE: "reduced_size",
    UNDEFINED: "none",
}


@dataclass
class RegimeResult:
    regime: str
    allowed_direction: str
    adx: Optional[float]
    ema_fan: str  # "bullish", "bearish" or "mixed"
    atr: Optional[float]
    atr_baseline: Optional[float]
    volatile: bool
    reason: str

    def to_dict(self) -> dict:
        return {
            "regime": self.regime,
            "allowed_direction": self.allowed_direction,
            "adx": _round(self.adx),
            "ema_fan": self.ema_fan,
            "atr": _round(self.atr, 6),
            "atr_baseline": _round(self.atr_baseline, 6),
            "volatile": self.volatile,
            "reason": self.reason,
        }


def _round(value: Optional[float], digits: int = 2) -> Optional[float]:
    return None if value is None else round(value, digits)


def classify_ema_fan(
    ema_fast: Optional[float],
    ema_mid: Optional[float],
    ema_slow: Optional[float],
) -> str:
    """Describe the stack of the three EMAs."""
    if None in (ema_fast, ema_mid, ema_slow):
        return "mixed"
    if ema_fast > ema_mid > ema_slow:
        return "bullish"
    if ema_fast < ema_mid < ema_slow:
        return "bearish"
    return "mixed"


def detect_regime(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    ema_fast_period: int = 21,
    ema_mid_period: int = 55,
    ema_slow_period: int = 200,
) -> RegimeResult:
    """Classify the most recent bar's regime from raw OHLC."""
    if not closes:
        raise ValueError("closes must not be empty")

    ema_fast = ind.last_defined(ind.ema(closes, ema_fast_period))
    ema_mid = ind.last_defined(ind.ema(closes, ema_mid_period))
    ema_slow = ind.last_defined(ind.ema(closes, ema_slow_period))
    fan = classify_ema_fan(ema_fast, ema_mid, ema_slow)

    adx_series = ind.adx(highs, lows, closes, 14)
    adx_value = ind.last_defined(adx_series["adx"])

    atr_series = ind.atr(highs, lows, closes, 14)
    atr_value = ind.last_defined(atr_series)
    atr_baseline = _atr_baseline(atr_series)
    is_volatile = (
        atr_value is not None
        and atr_baseline is not None
        and atr_value > ATR_VOLATILE_MULTIPLE * atr_baseline
    )

    regime, reason = _decide(adx_value, fan, is_volatile)
    return RegimeResult(
        regime=regime,
        allowed_direction=ALLOWED_DIRECTION[regime],
        adx=adx_value,
        ema_fan=fan,
        atr=atr_value,
        atr_baseline=atr_baseline,
        volatile=is_volatile,
        reason=reason,
    )


def _atr_baseline(atr_series: ind.Series) -> Optional[float]:
    """Average of the defined ATR values over the recent window."""
    defined = [v for v in atr_series if v is not None]
    if not defined:
        return None
    window = defined[-ATR_AVERAGE_PERIOD:]
    return sum(window) / len(window)


def _decide(adx_value: Optional[float], fan: str, is_volatile: bool) -> tuple[str, str]:
    """Combine the signals into one regime label with a short reason.

    Volatility is reported as a modifier but a clean trend still wins the label,
    so a strong trending move on high ATR stays tradable in its own direction
    rather than being demoted to a blanket "volatile, stay out".
    """
    if adx_value is None:
        return UNDEFINED, "Not enough history for ADX"

    trending = adx_value > ADX_TREND

    if trending and fan == "bullish":
        label = TREND_UP
        reason = f"ADX {adx_value:.0f} > {ADX_TREND:.0f} and EMA 21>55>200 (bullish fan)"
    elif trending and fan == "bearish":
        label = TREND_DOWN
        reason = f"ADX {adx_value:.0f} > {ADX_TREND:.0f} and EMA 21<55<200 (bearish fan)"
    elif adx_value < ADX_RANGE:
        label = RANGE
        reason = f"ADX {adx_value:.0f} < {ADX_RANGE:.0f}, no directional trend"
    elif is_volatile:
        label = VOLATILE
        reason = "Elevated ATR without a clean trend"
    else:
        # ADX between the two thresholds, or trending ADX but a mixed fan.
        label = RANGE
        reason = f"ADX {adx_value:.0f} inconclusive or EMA fan mixed ({fan})"

    if is_volatile and label in (TREND_UP, TREND_DOWN):
        reason += "; ATR elevated, reduce size"

    return label, reason
