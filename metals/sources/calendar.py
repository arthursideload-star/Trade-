"""Economic calendar: what is scheduled, and when to stand aside.

The assistant needs a news blackout that works even when no calendar API is
reachable. Most high-impact US releases follow published, predictable rules
(Non-Farm Payrolls on the first Friday at 08:30 ET, CPI mid-month at 08:30 ET,
FOMC statements at 14:00 ET on their published schedule), so the schedule is
*computed* here rather than fetched.

The limits of that are stated plainly in `StaticCalendar.caveats`: a computed
calendar cannot know about an emergency meeting, a rescheduled release, or a
government shutdown delaying a print -- and those are precisely the situations
where the blackout matters most. It is a floor under the veto, not a
replacement for a live feed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from ..sessions import eu_dst_active, us_dst_active
from .http import FetchError, HttpClient

# --- Central bank decision dates -------------------------------------------
#
# These are the two events the computed schedule could not derive from a rule,
# and the reason it emitted nothing at all on the days that matter most: an
# FOMC decision is not "the first Friday" or "the 10th to the 15th", it is
# whatever the committee published. So they are listed.
#
# Day 2 of each meeting is the decision day. Statement at 14:00 ET, press
# conference at 14:30 ET -- both from the Fed's own meeting pages.
# Source: federalreserve.gov/monetarypolicy/fomccalendars.htm
# Cross-checked against the fallback list in worldmonitor's calendar seeder,
# which scrapes the same page; the two agree for every 2026 date.
FOMC_DECISION_DATES: tuple[str, ...] = (
    # 2026 -- confirmed
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
    # 2027 -- tentative. The Fed marks each date tentative until the meeting
    # before it confirms them, so these can move.
    "2027-01-29", "2027-03-19", "2027-04-28", "2027-06-09",
    "2027-07-28", "2027-09-15", "2027-10-27", "2027-12-08",
)

# ECB Governing Council monetary policy meetings, decision day. Rate decision
# at 14:15 CET/CEST, press conference at 14:45.
# Source: ecb.europa.eu/press/calendars/mgcgc, cross-checked against the ECB's
# own published decisions (ecb.mp260205, ecb.mp260611, ecb.mp260723).
#
# The ECB matters to gold for a reason that is easy to overlook: this account
# is denominated in euro. A euro move changes the account's value without gold
# moving at all.
#
# The first 2026 entry is a correction. Worldmonitor's calendar seeder carries
# a fallback list with 2026-01-30 in this slot, and 30 January 2026 is a
# Friday -- the Governing Council announces on Thursdays. The actual first
# 2026 decision was 5 February (ECB press release ecb.mp260205). The
# weekday invariant is a test, so the same class of transcription error
# cannot enter this list again unnoticed.
ECB_DECISION_DATES: tuple[str, ...] = (
    "2026-02-05", "2026-03-19", "2026-04-30", "2026-06-11",
    "2026-07-23", "2026-09-10", "2026-10-29", "2026-12-17",
)


@dataclass(frozen=True)
class CalendarEvent:
    name: str
    when: datetime           # UTC
    impact: str              # "high" | "medium" | "low"
    currency: str = "USD"
    typical_gold_move: str = ""
    source: str = "static"
    note: str = ""

    def minutes_from(self, moment: datetime) -> float:
        return (self.when - moment).total_seconds() / 60.0

    def in_blackout(self, moment: datetime, minutes: int = 30) -> bool:
        return abs(self.minutes_from(moment)) <= minutes


# What each release typically does to gold. These are the ranges reported
# across broker and educational sources rather than a measurement of our own,
# and they are here to set expectations about position size, not to predict
# direction -- the first move is reported wrong more than 40% of the time.
IMPACT_NOTES: dict[str, str] = {
    "NFP": "80-200 USD/oz-equivalent within minutes on a surprise print; "
           "40-80 on an in-line one",
    "CPI": "comparable to NFP and sometimes larger, because it feeds directly "
           "into the real-yield calculation that prices gold",
    "FOMC": "the statement moves gold, the press conference 30 minutes later "
            "often moves it further and in the opposite direction",
    "ECB": "moves gold in dollars less than the Fed does, but it moves EUR/USD "
           "-- and this account is kept in euro, so the euro result changes "
           "even when gold does not",
    "PPI": "smaller than CPI but same direction of transmission",
    "PCE": "the Fed's preferred inflation measure; matters more than its "
           "media coverage suggests",
    "Retail Sales": "moderate; matters through the growth-and-rates channel",
    "ISM": "moderate; a leading indicator the market watches for turns",
    "Jobless Claims": "usually minor, occasionally sharp when the trend breaks",
}


def _et_to_utc(day: date, hour: int, minute: int) -> datetime:
    """Convert a New York wall-clock time to UTC for that date."""
    probe = datetime.combine(day, time(12, 0), tzinfo=timezone.utc)
    offset = -4 if us_dst_active(probe) else -5
    naive = datetime.combine(day, time(hour, minute))
    return (naive - timedelta(hours=offset)).replace(tzinfo=timezone.utc)


def _ce_to_utc(day: date, hour: int, minute: int) -> datetime:
    """Convert a Frankfurt wall-clock time to UTC for that date."""
    probe = datetime.combine(day, time(12, 0), tzinfo=timezone.utc)
    offset = 2 if eu_dst_active(probe) else 1
    naive = datetime.combine(day, time(hour, minute))
    return (naive - timedelta(hours=offset)).replace(tzinfo=timezone.utc)


def _parse_dates(values: tuple[str, ...]) -> list[date]:
    return sorted(date.fromisoformat(v) for v in values)


def known_through() -> date:
    """The last day this schedule can speak for.

    Beyond it the listed decisions run out, and a calendar that answers
    "no high-impact release" for a date it simply does not cover is worse
    than one that says it does not know. Callers ask; `events` warns.
    """
    return min(_parse_dates(FOMC_DECISION_DATES)[-1],
               _parse_dates(ECB_DECISION_DATES)[-1])


def first_friday(year: int, month: int) -> date:
    d = date(year, month, 1)
    return d + timedelta(days=(4 - d.weekday()) % 7)


def nfp_dates(start: date, months: int = 3) -> list[date]:
    """Non-Farm Payrolls: first Friday of each month.

    The rule has exceptions -- the BLS shifts the date when the first Friday
    falls too early in the month for the reference-week collection to be
    complete. Treated as an approximation, and flagged as one.
    """
    out: list[date] = []
    y, m = start.year, start.month
    for _ in range(months):
        out.append(first_friday(y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return [d for d in out if d >= start - timedelta(days=1)]


def cpi_window(year: int, month: int) -> tuple[date, date]:
    """CPI lands between the 10th and the 15th, on a weekday.

    Without a feed the exact day is unknown, so the whole window is treated as
    elevated risk rather than pretending to a precision the rule does not have.
    """
    return date(year, month, 10), date(year, month, 15)


@dataclass
class StaticCalendar:
    """Locally computed high-impact schedule."""

    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    caveats: tuple[str, ...] = (
        "Computed from publication rules, not fetched. It cannot know about an "
        "emergency FOMC meeting, a rescheduled release, or a shutdown delaying "
        "a print -- which are exactly the cases where a blackout matters most.",
        "CPI and PPI dates are windows, not exact times, without a live feed.",
        "BoE and China data are not covered here and do move metals. FOMC and "
        "ECB decisions are listed rather than derived, so they stop at the "
        "published horizon -- see horizon_gap.",
        "Use this as a floor under the news veto. A live calendar feed replaces "
        "it; it does not replace a live feed.",
    )

    def horizon_gap(self, start: date, days: int = 14) -> str | None:
        """Say so when the window reaches past the listed decisions.

        The silent version of this is the bug that produced A20: a schedule
        with no FOMC in it does not look broken, it looks like a quiet week.
        """
        end = start + timedelta(days=days)
        last = known_through()
        if end <= last:
            return None
        return (f"Central bank decisions are listed only through "
                f"{last.isoformat()}; this window runs to {end.isoformat()}. "
                f"Days after the horizon carry no FOMC or ECB event here, "
                f"which is not the same as there being none.")

    def events(self, start: date, days: int = 14) -> list[CalendarEvent]:
        out: list[CalendarEvent] = []
        end = start + timedelta(days=days)

        # Listed, not derived. Both legs of each decision are emitted: with a
        # 30-minute blackout either side, the statement (14:00 ET) and the
        # press conference (14:30 ET) merge into one continuous stand-aside
        # from 13:30 to 15:00 ET, which is the behaviour the impact note
        # describes and the one that was missing entirely.
        for d in _parse_dates(FOMC_DECISION_DATES):
            if not (start <= d <= end):
                continue
            tentative = d.year >= 2027
            note = ("published FOMC schedule"
                    + (" -- 2027 dates are tentative until the Fed confirms "
                       "them at the preceding meeting" if tentative else ""))
            out.append(CalendarEvent(
                "FOMC rate decision", _et_to_utc(d, 14, 0), "high",
                typical_gold_move=IMPACT_NOTES["FOMC"], note=note))
            out.append(CalendarEvent(
                "FOMC press conference", _et_to_utc(d, 14, 30), "high",
                typical_gold_move=IMPACT_NOTES["FOMC"], note=note))

        for d in _parse_dates(ECB_DECISION_DATES):
            if not (start <= d <= end):
                continue
            out.append(CalendarEvent(
                "ECB rate decision", _ce_to_utc(d, 14, 15), "high",
                currency="EUR", typical_gold_move=IMPACT_NOTES["ECB"],
                note="published ECB Governing Council schedule"))
            out.append(CalendarEvent(
                "ECB press conference", _ce_to_utc(d, 14, 45), "high",
                currency="EUR", typical_gold_move=IMPACT_NOTES["ECB"],
                note="published ECB Governing Council schedule"))

        for d in nfp_dates(start, months=3):
            if start <= d <= end:
                out.append(CalendarEvent(
                    "Non-Farm Payrolls", _et_to_utc(d, 8, 30), "high",
                    typical_gold_move=IMPACT_NOTES["NFP"],
                    note="first Friday rule; the BLS occasionally shifts it",
                ))

        # CPI windows touching the horizon.
        cursor = start
        seen_months: set[tuple[int, int]] = set()
        while cursor <= end:
            key = (cursor.year, cursor.month)
            if key not in seen_months:
                seen_months.add(key)
                lo, hi = cpi_window(*key)
                probe = lo
                while probe <= hi:
                    if probe.weekday() < 5 and start <= probe <= end:
                        out.append(CalendarEvent(
                            "CPI (window)", _et_to_utc(probe, 8, 30), "high",
                            typical_gold_move=IMPACT_NOTES["CPI"],
                            note="exact day unknown without a live feed; the "
                                 "whole 10th-15th window is treated as elevated",
                        ))
                    probe += timedelta(days=1)
            cursor += timedelta(days=1)

        # Weekly jobless claims: Thursday 08:30 ET.
        cursor = start
        while cursor <= end:
            if cursor.weekday() == 3:
                out.append(CalendarEvent(
                    "Initial Jobless Claims", _et_to_utc(cursor, 8, 30),
                    "medium", typical_gold_move=IMPACT_NOTES["Jobless Claims"],
                ))
            cursor += timedelta(days=1)

        return sorted(out, key=lambda e: e.when)

    def next_high_impact(self, moment: datetime) -> CalendarEvent | None:
        upcoming = [e for e in self.events(moment.date(), 21)
                    if e.impact == "high" and e.when >= moment]
        return upcoming[0] if upcoming else None

    def blackout(self, moment: datetime, minutes: int = 30
                 ) -> tuple[bool, str | None]:
        for e in self.events(moment.date() - timedelta(days=1), 3):
            if e.impact == "high" and e.in_blackout(moment, minutes):
                delta = e.minutes_from(moment)
                when = "in" if delta > 0 else "was"
                return True, (
                    f"{e.name} {when} {abs(delta):.0f} minutes -- "
                    f"{e.typical_gold_move}"
                )
        return False, None


def finnhub_calendar(client: HttpClient, start: date, end: date,
                     api_key: str | None = None) -> list[CalendarEvent]:
    """Live calendar from Finnhub, when a key is available."""
    key = api_key or os.environ.get("FINNHUB_API_KEY")
    if not key:
        raise FetchError("finnhub_calendar", "FINNHUB_API_KEY is not set")
    data = client.get_json(
        "https://finnhub.io/api/v1/calendar/economic",
        params={"from": start.isoformat(), "to": end.isoformat(), "token": key},
        cache_ttl=1800,
    )
    rows = data.get("economicCalendar") if isinstance(data, dict) else None
    if rows is None:
        raise FetchError("finnhub_calendar", "no economicCalendar in response")

    out: list[CalendarEvent] = []
    for r in rows:
        when = _parse_when(r.get("time"))
        if when is None:
            continue
        impact = str(r.get("impact", "")).lower()
        if impact not in ("high", "medium", "low"):
            impact = "low"
        name = r.get("event", "unknown")
        out.append(CalendarEvent(
            name=name, when=when, impact=impact,
            currency=r.get("country", "") or "USD",
            typical_gold_move=_match_note(name),
            source="finnhub",
        ))
    return sorted(out, key=lambda e: e.when)


def upcoming_events(moment: datetime | None = None, days: int = 7,
                    client: HttpClient | None = None) -> tuple[list[CalendarEvent], str]:
    """Live calendar if reachable, computed schedule otherwise.

    Returns (events, source_description) so the caller can say which one it
    used -- the difference matters for how much the veto can be trusted.
    """
    moment = moment or datetime.now(timezone.utc)
    client = client or HttpClient()
    start, end = moment.date(), moment.date() + timedelta(days=days)

    if os.environ.get("FINNHUB_API_KEY"):
        try:
            events = finnhub_calendar(client, start, end)
            if events:
                return events, "finnhub (live)"
        except Exception:  # noqa: BLE001 - fall through to the computed schedule
            pass

    static = StaticCalendar()
    return static.events(start, days), (
        "built-in computed schedule (no live calendar feed available -- "
        "see StaticCalendar.caveats)"
    )


def news_blackout(moment: datetime | None = None, minutes: int = 30,
                  client: HttpClient | None = None) -> tuple[bool, str]:
    """Rule R4. True means: do not propose a trade right now."""
    moment = moment or datetime.now(timezone.utc)
    events, source = upcoming_events(moment, days=2, client=client)
    for e in events:
        if e.impact == "high" and e.in_blackout(moment, minutes):
            delta = e.minutes_from(moment)
            phrase = f"in {delta:.0f} min" if delta > 0 else f"{-delta:.0f} min ago"
            return True, (
                f"R4: {e.name} {phrase} (source: {source}). "
                f"{e.typical_gold_move or 'High-impact release.'}"
            )
    return False, f"no high-impact release inside the blackout window ({source})"


def _parse_when(value) -> datetime | None:  # type: ignore[no-untyped-def]
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# Feed providers spell the same release several ways ("Non-Farm Payrolls",
# "Nonfarm Payrolls", "Employment Situation"), so matching on the short key
# alone silently drops the impact note on exactly the events that matter most.
#
# Order matters and is load-bearing: the first match wins, so the specific
# central bank must be tried before the generic "rate decision". With FOMC
# listed first and owning that phrase, a feed row named "ECB Rate Decision"
# was handed the Fed's impact note -- wrong bank, wrong currency, wrong
# expected move.
_NOTE_ALIASES: dict[str, tuple[str, ...]] = {
    "NFP": ("nfp", "non-farm", "nonfarm", "payroll", "employment situation"),
    "CPI": ("cpi", "consumer price"),
    "PPI": ("ppi", "producer price"),
    "PCE": ("pce", "personal consumption"),
    "ECB": ("ecb", "european central bank", "lagarde"),
    "FOMC": ("fomc", "fed interest rate", "federal funds", "rate decision"),
    "Retail Sales": ("retail sales",),
    "ISM": ("ism",),
    "Jobless Claims": ("jobless claims", "initial claims"),
}


def _match_note(name: str) -> str:
    lowered = name.lower()
    for key, aliases in _NOTE_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            return IMPACT_NOTES.get(key, "")
    return ""
