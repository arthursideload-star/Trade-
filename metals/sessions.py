"""Session, fixing and rollover logic for gold and silver.

All times are UTC. The London and New York clocks shift with daylight saving
independently of each other, so the overlap window is computed from the local
exchange clocks rather than hard-coded to a UTC range -- getting this wrong
by an hour twice a year is a real and avoidable source of bad entries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum


class Session(str, Enum):
    SYDNEY = "sydney"
    TOKYO = "tokyo"
    LONDON = "london"
    NEW_YORK = "new_york"
    OVERLAP = "london_ny_overlap"
    ROLLOVER = "rollover"
    CLOSED = "closed"


class Quality(str, Enum):
    """How tradable the current window is for metals specifically."""

    PRIME = "prime"        # tightest spreads, cleanest structure
    GOOD = "good"
    MARGINAL = "marginal"  # tradable but expect noise and wider spreads
    AVOID = "avoid"        # rollover, deep Asia, Friday late, market closed


# --- Daylight saving without a tz database ---------------------------------
#
# Python's zoneinfo needs tzdata, which is not guaranteed in a minimal
# container. EU and US DST rules are simple enough to compute directly, and
# doing so keeps this module dependency-free and testable.

def _last_sunday(year: int, month: int) -> date:
    d = date(year, month, 31) if month == 12 else date(year, month + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def _nth_sunday(year: int, month: int, n: int) -> date:
    d = date(year, month, 1)
    d += timedelta(days=(6 - d.weekday()) % 7)  # first Sunday
    return d + timedelta(weeks=n - 1)


def eu_dst_active(moment: datetime) -> bool:
    """EU summer time: last Sunday in March 01:00 UTC to last Sunday in Oct 01:00 UTC."""
    y = moment.year
    start = datetime.combine(_last_sunday(y, 3), time(1, 0), tzinfo=timezone.utc)
    end = datetime.combine(_last_sunday(y, 10), time(1, 0), tzinfo=timezone.utc)
    return start <= moment < end


def us_dst_active(moment: datetime) -> bool:
    """US daylight time: 2nd Sunday in March 07:00 UTC to 1st Sunday in Nov 06:00 UTC."""
    y = moment.year
    start = datetime.combine(_nth_sunday(y, 3, 2), time(7, 0), tzinfo=timezone.utc)
    end = datetime.combine(_nth_sunday(y, 11, 1), time(6, 0), tzinfo=timezone.utc)
    return start <= moment < end


def london_offset_hours(moment: datetime) -> int:
    return 1 if eu_dst_active(moment) else 0


def new_york_offset_hours(moment: datetime) -> int:
    return -4 if us_dst_active(moment) else -5


# --- Window definitions -----------------------------------------------------

@dataclass(frozen=True)
class Window:
    name: str
    start_utc: datetime
    end_utc: datetime
    description: str = ""

    def contains(self, moment: datetime) -> bool:
        return self.start_utc <= moment < self.end_utc

    def minutes_until(self, moment: datetime) -> float:
        return (self.start_utc - moment).total_seconds() / 60.0


def _at_local(day: date, hour: int, minute: int, offset_hours: int) -> datetime:
    """Build a UTC datetime from a local wall-clock time and its UTC offset."""
    naive = datetime.combine(day, time(hour, minute))
    return (naive - timedelta(hours=offset_hours)).replace(tzinfo=timezone.utc)


def windows_for_day(day: date) -> list[Window]:
    """All metals-relevant windows for a given UTC calendar day."""
    probe = datetime.combine(day, time(12, 0), tzinfo=timezone.utc)
    ldn = london_offset_hours(probe)
    nyc = new_york_offset_hours(probe)

    def L(h: int, m: int = 0) -> datetime:
        return _at_local(day, h, m, ldn)

    def N(h: int, m: int = 0) -> datetime:
        return _at_local(day, h, m, nyc)

    # The Asian range that matters for metals is the one London reaches for:
    # from the UTC day boundary to the London open. Defining it in Tokyo local
    # time instead would place it on the previous UTC calendar day and shift
    # every sweep level by nine hours.
    day_start = datetime.combine(day, time(0, 0), tzinfo=timezone.utc)

    return [
        Window("asia", day_start, L(7, 0),
               "Asian hours up to the London open. Thin for metals; the range "
               "built here is the liquidity London reaches for."),
        Window("london_killzone", L(7, 0), L(10, 0),
               "London open. The highest-frequency window for a sweep of the "
               "Asian range followed by the real move."),
        Window("london_fix_am", L(10, 30), L(10, 45),
               "LBMA morning auction. Institutional order flow clusters here."),
        Window("ny_killzone", N(8, 0), N(11, 0),
               "New York open including the 08:30 data window. Largest "
               "single-hour ranges of the day on gold."),
        Window("comex_open", N(8, 20), N(8, 35),
               "COMEX floor open. Reliable liquidity sweep window on silver."),
        Window("overlap", max(L(13, 0), N(8, 0)), min(L(17, 0), N(12, 0)),
               "London/New York overlap. Tightest spreads and cleanest "
               "structure of the session."),
        Window("silver_bullet", N(10, 0), N(11, 0),
               "10:00-11:00 New York. Named for how consistently algorithmic "
               "flow breaks structure in this hour."),
        Window("london_fix_pm", L(15, 0), L(15, 15),
               "LBMA afternoon auction, the benchmark most contracts settle "
               "against. Sharp, short-lived moves are normal here."),
        Window("comex_settlement", N(13, 30), N(13, 35),
               "COMEX futures settlement."),
        Window("rollover", _at_local(day, 21, 0, 0), _at_local(day, 23, 0, 0),
               "Daily rollover and Comex close. Spreads widen severalfold and "
               "swap is charged. Not a trading window."),
    ]


def window(name: str, moment: datetime) -> Window | None:
    for w in windows_for_day(moment.date()):
        if w.name == name:
            return w
    return None


# --- Classification ---------------------------------------------------------

@dataclass(frozen=True)
class SessionState:
    moment: datetime
    session: Session
    quality: Quality
    active_windows: list[str]
    reasons: list[str]

    @property
    def tradable(self) -> bool:
        return self.quality in (Quality.PRIME, Quality.GOOD)


def market_open(moment: datetime) -> bool:
    """Metals trade Sunday 22:00 UTC to Friday 21:00 UTC, minus the daily break.

    The exact boundary is broker-specific by up to an hour; this is the
    conservative common denominator.
    """
    wd = moment.weekday()  # Mon=0 .. Sun=6
    hour = moment.hour
    if wd == 5:  # Saturday
        return False
    if wd == 6:  # Sunday
        return hour >= 22
    if wd == 4 and hour >= 21:  # Friday evening
        return False
    return True


def classify(moment: datetime) -> SessionState:
    """Classify a moment into a session and a tradability grade for metals."""
    if moment.tzinfo is None:
        raise ValueError("moment must be timezone-aware UTC")
    moment = moment.astimezone(timezone.utc)

    if not market_open(moment):
        return SessionState(moment, Session.CLOSED, Quality.AVOID, [],
                            ["market closed"])

    wins = windows_for_day(moment.date())
    active = [w.name for w in wins if w.contains(moment)]
    reasons: list[str] = []

    if "rollover" in active:
        return SessionState(moment, Session.ROLLOVER, Quality.AVOID, active,
                            ["daily rollover: spreads widen severalfold, "
                             "swap is charged, liquidity is thin"])

    if "overlap" in active:
        session, quality = Session.OVERLAP, Quality.PRIME
        reasons.append("London/New York overlap: tightest spreads of the day")
    elif "ny_killzone" in active or "silver_bullet" in active:
        session, quality = Session.NEW_YORK, Quality.PRIME
        reasons.append("New York killzone: largest ranges, real participation")
    elif "london_killzone" in active:
        session, quality = Session.LONDON, Quality.PRIME
        reasons.append("London killzone: the session's directional move usually "
                       "starts here")
    elif "asia" in active:
        session, quality = Session.TOKYO, Quality.MARGINAL
        reasons.append("Asian session: thin for metals, ranges are small and "
                       "breakouts fail often; the range built here is best "
                       "used as a level, not as a trade")
    else:
        session, quality = Session.LONDON, Quality.GOOD
        reasons.append("regular session hours")

    # Friday afternoon: position-squaring makes structure unreliable, and any
    # position held into the close carries weekend gap risk.
    if moment.weekday() == 4 and moment.hour >= 17:
        quality = Quality.MARGINAL
        reasons.append("Friday late session: position squaring plus weekend "
                       "gap risk on anything held over")

    # Wednesday triple swap: not a reason to skip a day trade, but it changes
    # the cost of holding overnight by 3x.
    if moment.weekday() == 2:
        reasons.append("Wednesday: triple swap is charged at rollover on "
                       "positions held overnight")

    if "london_fix_am" in active or "london_fix_pm" in active:
        reasons.append("LBMA auction window: short, sharp moves that reverse "
                       "as often as they continue")

    return SessionState(moment, session, quality, active, reasons)


def next_window(name: str, moment: datetime, max_days: int = 7) -> Window | None:
    """The next occurrence of a named window at or after `moment`."""
    for offset in range(max_days):
        day = (moment + timedelta(days=offset)).date()
        for w in windows_for_day(day):
            if w.name == name and w.start_utc >= moment:
                return w
    return None


def asian_range(candles, moment: datetime) -> tuple[float, float] | None:
    """High and low of the Asian session preceding `moment`.

    This is the liquidity pool the London open reaches for. Returns None when
    the series does not cover the window.
    """
    win = window("asia", moment)
    if win is None:
        return None
    if moment < win.end_utc:  # session still forming; use the prior day's
        prev = window("asia", moment - timedelta(days=1))
        if prev is None:
            return None
        win = prev
    inside = [c for c in candles if win.start_utc <= c.ts < win.end_utc]
    if not inside:
        return None
    return max(c.high for c in inside), min(c.low for c in inside)
