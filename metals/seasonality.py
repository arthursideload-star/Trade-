"""Seasonal tendencies in gold and silver.

Read the health warning before using any of this.

Seasonality in metals is a weak, unstable effect measured on a small sample.
Fifty years of monthly data is 50 observations per month, which is not enough
to separate a real pattern from noise, and the published figures disagree with
each other -- some sources put gold's best month as January, others September,
others August, depending on the window measured and whether returns are
nominal or real.

The honest use is as a **tiebreaker at the margin**, never as a reason to take
a trade. A setup that is otherwise good does not become bad in a weak month,
and a bad setup does not become good in a strong one. The weight assigned in
metals.setups reflects that: seasonality contributes at most a few percent of
the confidence score.

The underlying stories are more durable than the statistics:
* Indian wedding and festival buying concentrates physical demand in autumn.
* Chinese New Year buying pulls demand into January and February.
* Western portfolio rebalancing lands in January.
* Summer is thin: desks are away, ranges narrow, breakouts fail more often.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# Directional tendency by month, on a -2..+2 scale rather than as a return
# figure. Using a coarse scale is deliberate: publishing "+1.8% in January"
# implies a precision the underlying sample does not support.
GOLD_MONTHS: dict[int, tuple[int, str]] = {
    1:  (+2, "January is consistently among the stronger months across most "
             "published windows. Western rebalancing after December tax-loss "
             "selling plus Chinese New Year physical buying."),
    2:  (+1, "Chinese New Year demand continues; generally mildly positive."),
    3:  (-1, "March is among the weaker months in most long-run studies."),
    4:  (0,  "Mixed. Some studies show mild weakness."),
    5:  (0,  "Neutral, with the start of the summer liquidity drain."),
    6:  (-1, "June is among the weakest months in the long-run data."),
    7:  (+1, "The seasonal low often forms in early July; several studies date "
             "the start of the autumn advance to around 6 July."),
    8:  (+1, "August is strong in several studies, ahead of the Indian "
             "festival season."),
    9:  (+2, "September is the strongest month in some 50-year studies, driven "
             "by Indian festival and wedding-season physical buying."),
    10: (-1, "October is weak in the long-run data despite the festival "
             "narrative -- the physical buying is already in the price."),
    11: (+1, "Mildly positive; the run into year-end."),
    12: (+1, "Generally positive, though tax-loss selling can produce a dip "
             "before the January rebound."),
}

SILVER_MONTHS: dict[int, tuple[int, str]] = {
    1:  (+2, "Silver follows gold's January strength and amplifies it."),
    2:  (+1, "Continued strength, higher beta than gold."),
    3:  (-1, "Weak alongside gold."),
    4:  (0,  "Mixed."),
    5:  (-1, "Silver's summer weakness starts earlier than gold's; industrial "
             "demand slows with the northern-hemisphere production calendar."),
    6:  (-1, "Weak."),
    7:  (+1, "Turning point, alongside gold."),
    8:  (+1, "Positive."),
    9:  (+1, "Positive but less reliably so than gold -- silver's industrial "
             "half does not follow the Indian wedding calendar."),
    10: (0,  "Mixed."),
    11: (+1, "Mildly positive."),
    12: (+1, "Mildly positive."),
}

# Intra-week tendencies. Better evidenced than the monthly pattern because the
# sample is far larger, and mechanically explainable.
WEEKDAY_NOTES: dict[int, str] = {
    0: "Monday: the weekend gap resolves and the Asian session sets the week's "
       "first range. Thinner than mid-week; breakouts fail more often.",
    1: "Tuesday: the week's cleanest trend day in most session studies. The "
       "COT snapshot is taken today.",
    2: "Wednesday: FOMC statement days land here. Triple swap is charged at "
       "rollover on anything held overnight.",
    3: "Thursday: jobless claims at 08:30 ET; ECB decisions land here.",
    4: "Friday: NFP on the first of the month. Position squaring from the "
       "afternoon distorts structure, and anything held over carries weekend "
       "gap risk that a stop does not cover.",
}


@dataclass(frozen=True)
class SeasonalRead:
    symbol: str
    month: int
    score: int              # -2..+2
    weekday_note: str
    month_note: str
    confidence_weight: float = 0.05   # deliberately tiny

    @property
    def lean(self) -> str:
        if self.score >= 2:
            return "supportive"
        if self.score == 1:
            return "mildly supportive"
        if self.score == -1:
            return "mildly negative"
        if self.score <= -2:
            return "negative"
        return "neutral"

    def explain(self) -> str:
        return (
            f"Seasonality ({self.lean}): {self.month_note} {self.weekday_note} "
            f"Weighting this at {self.confidence_weight:.0%} of the confidence "
            f"score -- the monthly sample is roughly 50 observations and the "
            f"published studies disagree with each other, so it breaks ties "
            f"and nothing more."
        )


def read(symbol: str, day: date | None = None) -> SeasonalRead:
    from .specs import get_spec

    day = day or date.today()
    canonical = get_spec(symbol).symbol
    table = SILVER_MONTHS if canonical in ("XAGUSD", "SI", "SIL") else GOLD_MONTHS
    score, note = table[day.month]
    return SeasonalRead(
        symbol=canonical,
        month=day.month,
        score=score,
        weekday_note=WEEKDAY_NOTES.get(day.weekday(), ""),
        month_note=note,
    )


def summer_doldrums(day: date | None = None) -> bool:
    """Mid-June to mid-August: thin books, narrow ranges, more false breaks.

    The practical consequence is not "do not trade" but "expect breakout
    setups to fail more often and range setups to work better".
    """
    day = day or date.today()
    return (day.month == 6 and day.day >= 15) or day.month == 7 or \
        (day.month == 8 and day.day <= 15)


def year_end_illiquidity(day: date | None = None) -> bool:
    """Last two weeks of December: moves are real but the depth behind them is not."""
    day = day or date.today()
    return day.month == 12 and day.day >= 18
