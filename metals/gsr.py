"""The gold/silver ratio: how many ounces of silver buy one ounce of gold.

Why it earns its own module: it is the one relationship that is genuinely
specific to trading these two metals together, and it is the main reason to
watch both rather than one.

What it is good for:

* **Regime read.** A rising ratio means gold is outperforming, which usually
  means the bid is defensive (safe-haven, central bank). A falling ratio means
  silver is leading, which usually means the bid is cyclical (industrial,
  risk-seeking). That distinction changes which setups to trust.
* **Relative value over months.** Extremes have historically reverted.

What it is not good for:

* **Timing.** The ratio has stayed at extremes for a year or more. The 2020
  spike above 120 took more than a year to compress. Anyone treating a reading
  of 80 as an entry signal is taking a position with an unbounded holding
  period, which is not compatible with a 1%-risk stop.

Range history, for calibration: a long-run average in the 50-60 area, with
documented spikes to roughly 100 in 1991, 93 in 2019, above 120 in 2020, and
105 in April 2025, compressing back to the high 50s by early 2026.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .candles import CandleSeries
from .indicators import sma, zscore

# Reference bands, from the historical record rather than from theory.
EXTREME_HIGH = 90.0     # silver cheap relative to gold
HIGH = 80.0
LONG_RUN_MEAN = 65.0
LOW = 55.0
EXTREME_LOW = 45.0      # gold cheap relative to silver


@dataclass
class RatioState:
    ratio: float
    zscore: float | None
    percentile: float | None
    trend_20: str            # "rising" | "falling" | "flat"
    band: str                # "extreme_high" | "high" | "normal" | "low" | "extreme_low"
    regime: str              # "defensive" | "cyclical" | "mixed"
    notes: list[str] = field(default_factory=list)

    @property
    def leader(self) -> str:
        if self.trend_20 == "rising":
            return "gold"
        if self.trend_20 == "falling":
            return "silver"
        return "neither"


def compute_ratio(gold_price: float, silver_price: float) -> float:
    if silver_price <= 0:
        raise ValueError("silver price must be positive")
    return gold_price / silver_price


def ratio_series(gold: CandleSeries, silver: CandleSeries) -> list[float]:
    """Ratio series from two aligned candle series.

    Aligns on timestamp rather than on index: the two feeds do not always
    return the same bar count, and silently zipping mismatched series produces
    a ratio history that looks fine and is wrong.
    """
    silver_by_ts = {c.ts: c.close for c in silver}
    return [
        c.close / silver_by_ts[c.ts]
        for c in gold
        if c.ts in silver_by_ts and silver_by_ts[c.ts] > 0
    ]


def classify(ratio: float) -> str:
    if ratio >= EXTREME_HIGH:
        return "extreme_high"
    if ratio >= HIGH:
        return "high"
    if ratio <= EXTREME_LOW:
        return "extreme_low"
    if ratio <= LOW:
        return "low"
    return "normal"


def analyse(gold: CandleSeries, silver: CandleSeries,
            zscore_period: int = 100) -> RatioState:
    """Full ratio read from two candle series."""
    values = ratio_series(gold, silver)
    if not values:
        raise ValueError(
            "no overlapping timestamps between the gold and silver series -- "
            "check that both came from the same provider and timeframe"
        )

    current = values[-1]
    z = None
    if len(values) >= zscore_period:
        z_series = zscore(values, zscore_period)
        z = z_series[-1]

    percentile = None
    if len(values) >= 30:
        percentile = sum(1 for v in values if v < current) / len(values) * 100.0

    trend = "flat"
    if len(values) >= 21:
        ma = sma(values, 20)
        recent, earlier = ma[-1], ma[-11] if len(ma) > 11 else None
        if recent is not None and earlier is not None:
            change_pct = (recent - earlier) / earlier * 100.0
            if change_pct > 0.8:
                trend = "rising"
            elif change_pct < -0.8:
                trend = "falling"

    band = classify(current)
    regime = {"rising": "defensive", "falling": "cyclical"}.get(trend, "mixed")

    notes: list[str] = []
    if trend == "rising":
        notes.append(
            "the ratio is rising: gold is outperforming silver. That is the "
            "signature of a defensive bid -- safe-haven flows, central bank "
            "buying, risk-off. In this regime gold's trend setups are more "
            "reliable than silver's, and silver breakouts fail more often."
        )
    elif trend == "falling":
        notes.append(
            "the ratio is falling: silver is outperforming. That is a cyclical "
            "bid -- industrial demand, risk appetite, reflation. Silver leads "
            "in this regime and its moves extend further than gold's, but it "
            "also gives back more when the move ends."
        )

    if band == "extreme_high":
        notes.append(
            f"at {current:.1f} the ratio is above the {EXTREME_HIGH:.0f} level "
            f"that has historically marked silver being cheap against gold. "
            f"Over a horizon of months this has favoured silver. It is not a "
            f"trade signal: the ratio spent more than a year above 100 after "
            f"the 2020 spike, and no 1%-risk stop survives that."
        )
    elif band == "extreme_low":
        notes.append(
            f"at {current:.1f} the ratio is below {EXTREME_LOW:.0f}, "
            f"historically the zone where gold is cheap against silver. Same "
            f"caveat about horizon."
        )
    elif band == "high":
        notes.append(f"ratio {current:.1f} is above the {HIGH:.0f} threshold "
                     f"commonly cited as silver being relatively cheap")
    elif band == "low":
        notes.append(f"ratio {current:.1f} is below {LOW:.0f}, the zone where "
                     f"silver has historically been relatively expensive")

    if z is not None and abs(z) >= 2.0:
        notes.append(
            f"the ratio is {z:+.1f} standard deviations from its "
            f"{zscore_period}-period mean -- a genuine statistical extreme "
            f"rather than an eyeballed one"
        )

    return RatioState(current, z, percentile, trend, band, regime, notes)


def which_metal(state: RatioState, direction: str) -> tuple[str, str]:
    """Given a directional view, say which metal expresses it better.

    Both metals will move the same way most days. The question is which one
    gives a better payoff for the same risk, and the ratio's trend answers it.
    """
    if direction == "long":
        if state.trend_20 == "falling":
            return "XAGUSD", (
                "silver is leading the move up. In a falling-ratio regime "
                "silver's advance extends further than gold's for the same "
                "macro impulse -- the higher beta works in your favour."
            )
        if state.trend_20 == "rising":
            return "XAUUSD", (
                "gold is leading. A rising ratio during a rally means the bid "
                "is defensive, and defensive bids do not carry silver -- "
                "silver longs underperform and fail more often here."
            )
    else:
        if state.trend_20 == "rising":
            return "XAGUSD", (
                "in a rising-ratio selloff silver falls harder than gold. If "
                "the view is down, silver expresses it with more range -- and "
                "with more risk of being stopped on the way, so size down."
            )
        if state.trend_20 == "falling":
            return "XAUUSD", (
                "gold is the cleaner short while silver is being bid "
                "industrially; silver shorts fight a separate buyer."
            )
    return "XAUUSD", (
        "the ratio is not trending, so it gives no preference. Gold is the "
        "default: tighter spreads, deeper liquidity, cleaner structure."
    )


def pair_trade_note(state: RatioState) -> str | None:
    """Explain the ratio pair trade honestly, including why not to take it here.

    Long silver / short gold at a high ratio is a real institutional trade. It
    is also a poor fit for a small semi-automatic account, and saying so is
    more useful than describing the mechanics.
    """
    if state.band not in ("extreme_high", "extreme_low"):
        return None
    cheap = "silver" if state.band == "extreme_high" else "gold"
    expensive = "gold" if cheap == "silver" else "silver"
    return (
        f"The classic trade at this reading is long {cheap} / short "
        f"{expensive}, sized so the two legs carry equal dollar risk. Reasons "
        f"not to take it on this account: it needs two positions and therefore "
        f"two spreads and two swaps; the convergence horizon is months, so "
        f"swap costs compound; and no stop can be placed sensibly on a spread "
        f"whose historical extremes lasted over a year. The useful form of "
        f"this information is directional -- prefer {cheap} when going long "
        f"the sector -- not the spread itself."
    )
