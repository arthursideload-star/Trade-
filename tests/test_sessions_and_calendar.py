"""Session windows, daylight saving, and the news blackout.

Daylight saving gets its own tests because getting it wrong shifts every
session window by an hour twice a year -- a silent failure that would make
the London-open setups fire at the wrong time for weeks.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone

from metals.sessions import (Quality, Session, classify, eu_dst_active,
                             london_offset_hours, market_open,
                             new_york_offset_hours, next_window,
                             us_dst_active, window, windows_for_day)
from metals.sources.calendar import (ECB_DECISION_DATES, FOMC_DECISION_DATES,
                                     StaticCalendar, _match_note, first_friday,
                                     known_through, nfp_dates,
                                     finnhub_calendar)
from tests.helpers import fake_client, FINNHUB_CALENDAR

UTC = timezone.utc


class TestDaylightSaving(unittest.TestCase):
    def test_eu_summer_time_boundaries_2026(self):
        # Last Sunday in March 2026 is the 29th.
        self.assertFalse(eu_dst_active(datetime(2026, 3, 29, 0, 30, tzinfo=UTC)))
        self.assertTrue(eu_dst_active(datetime(2026, 3, 29, 1, 30, tzinfo=UTC)))
        # Last Sunday in October 2026 is the 25th.
        self.assertTrue(eu_dst_active(datetime(2026, 10, 25, 0, 30, tzinfo=UTC)))
        self.assertFalse(eu_dst_active(datetime(2026, 10, 25, 1, 30, tzinfo=UTC)))

    def test_us_daylight_time_boundaries_2026(self):
        # Second Sunday in March 2026 is the 8th.
        self.assertFalse(us_dst_active(datetime(2026, 3, 8, 6, 30, tzinfo=UTC)))
        self.assertTrue(us_dst_active(datetime(2026, 3, 8, 7, 30, tzinfo=UTC)))
        # First Sunday in November 2026 is the 1st.
        self.assertTrue(us_dst_active(datetime(2026, 11, 1, 5, 30, tzinfo=UTC)))
        self.assertFalse(us_dst_active(datetime(2026, 11, 1, 6, 30, tzinfo=UTC)))

    def test_offsets_flip_with_the_season(self):
        summer = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
        winter = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
        self.assertEqual(london_offset_hours(summer), 1)
        self.assertEqual(london_offset_hours(winter), 0)
        self.assertEqual(new_york_offset_hours(summer), -4)
        self.assertEqual(new_york_offset_hours(winter), -5)

    def test_ny_killzone_shifts_with_dst(self):
        """08:00 New York is 12:00 UTC in summer and 13:00 UTC in winter.

        Hard-coding the UTC hour would break this for half the year.
        """
        summer = window("ny_killzone", datetime(2026, 7, 15, 12, 0, tzinfo=UTC))
        winter = window("ny_killzone", datetime(2026, 1, 15, 12, 0, tzinfo=UTC))
        self.assertEqual(summer.start_utc.hour, 12)
        self.assertEqual(winter.start_utc.hour, 13)


class TestMarketHours(unittest.TestCase):
    def test_closed_on_saturday(self):
        self.assertFalse(market_open(datetime(2026, 7, 25, 12, 0, tzinfo=UTC)))

    def test_closed_sunday_morning_open_sunday_night(self):
        self.assertFalse(market_open(datetime(2026, 7, 26, 12, 0, tzinfo=UTC)))
        self.assertTrue(market_open(datetime(2026, 7, 26, 22, 30, tzinfo=UTC)))

    def test_closed_after_friday_evening(self):
        self.assertTrue(market_open(datetime(2026, 7, 24, 15, 0, tzinfo=UTC)))
        self.assertFalse(market_open(datetime(2026, 7, 24, 21, 30, tzinfo=UTC)))


class TestClassification(unittest.TestCase):
    def test_overlap_is_prime(self):
        # Tuesday 14:00 UTC in July: London 15:00, New York 10:00.
        state = classify(datetime(2026, 7, 21, 14, 0, tzinfo=UTC))
        self.assertEqual(state.quality, Quality.PRIME)
        self.assertTrue(state.tradable)

    def test_rollover_is_avoid(self):
        state = classify(datetime(2026, 7, 21, 21, 30, tzinfo=UTC))
        self.assertEqual(state.session, Session.ROLLOVER)
        self.assertEqual(state.quality, Quality.AVOID)
        self.assertFalse(state.tradable)

    def test_closed_market_is_avoid(self):
        state = classify(datetime(2026, 7, 25, 12, 0, tzinfo=UTC))
        self.assertEqual(state.session, Session.CLOSED)
        self.assertFalse(state.tradable)

    def test_asia_is_marginal(self):
        state = classify(datetime(2026, 7, 21, 2, 0, tzinfo=UTC))
        self.assertEqual(state.quality, Quality.MARGINAL)

    def test_friday_late_is_downgraded(self):
        state = classify(datetime(2026, 7, 24, 18, 0, tzinfo=UTC))
        self.assertEqual(state.quality, Quality.MARGINAL)
        self.assertTrue(any("weekend gap" in r for r in state.reasons))

    def test_wednesday_mentions_triple_swap(self):
        state = classify(datetime(2026, 7, 22, 14, 0, tzinfo=UTC))
        self.assertTrue(any("triple swap" in r for r in state.reasons))

    def test_naive_datetime_is_rejected(self):
        with self.assertRaises(ValueError):
            classify(datetime(2026, 7, 21, 14, 0))


class TestWindows(unittest.TestCase):
    def test_every_window_has_a_positive_duration(self):
        for w in windows_for_day(date(2026, 7, 21)):
            self.assertLess(w.start_utc, w.end_utc, f"{w.name} is inverted")

    def test_next_window_looks_forward(self):
        moment = datetime(2026, 7, 21, 20, 0, tzinfo=UTC)
        nxt = next_window("london_killzone", moment)
        self.assertIsNotNone(nxt)
        self.assertGreaterEqual(nxt.start_utc, moment)

    def test_london_fix_windows_exist(self):
        names = {w.name for w in windows_for_day(date(2026, 7, 21))}
        self.assertIn("london_fix_am", names)
        self.assertIn("london_fix_pm", names)


class TestStaticCalendar(unittest.TestCase):
    def test_first_friday_calculation(self):
        self.assertEqual(first_friday(2026, 8), date(2026, 8, 7))
        self.assertEqual(first_friday(2026, 5), date(2026, 5, 1))

    def test_nfp_dates_are_fridays(self):
        for d in nfp_dates(date(2026, 7, 1), months=6):
            self.assertEqual(d.weekday(), 4)

    def test_calendar_produces_high_impact_events(self):
        cal = StaticCalendar()
        events = cal.events(date(2026, 8, 1), days=14)
        self.assertTrue(any(e.name.startswith("Non-Farm") for e in events))
        self.assertTrue(any(e.impact == "high" for e in events))

    def test_nfp_lands_at_0830_new_york(self):
        cal = StaticCalendar()
        events = [e for e in cal.events(date(2026, 8, 1), 10)
                  if e.name.startswith("Non-Farm")]
        self.assertTrue(events)
        # August is US daylight time: 08:30 ET = 12:30 UTC.
        self.assertEqual(events[0].when.hour, 12)
        self.assertEqual(events[0].when.minute, 30)

    def test_blackout_fires_around_an_event(self):
        cal = StaticCalendar()
        nfp = [e for e in cal.events(date(2026, 8, 1), 10)
               if e.name.startswith("Non-Farm")][0]
        inside = nfp.when - timedelta(minutes=10)
        outside = nfp.when - timedelta(hours=4)
        self.assertTrue(cal.blackout(inside)[0])
        self.assertFalse(cal.blackout(outside)[0])

    def test_caveats_are_documented(self):
        cal = StaticCalendar()
        self.assertGreaterEqual(len(cal.caveats), 3)
        self.assertTrue(any("emergency" in c for c in cal.caveats))


class TestCentralBankDecisionsAreInTheSchedule(unittest.TestCase):
    """A20: the module promised FOMC coverage and never emitted a single one.

    The docstring said "FOMC statements at 14:00 ET on their published
    schedule", IMPACT_NOTES carried an FOMC entry and the alias table matched
    four spellings of it -- but `events()` only ever produced NFP, CPI windows
    and jobless claims. On 29 July 2026, an FOMC decision day, a seven-day
    window returned exactly one event (jobless claims) and `blackout()` was
    False at 14:00 ET.

    That is audit finding A7's session 6 with the fix applied to the wrong
    layer: A7 made `news_times_utc` reach the strategy, but the calendar that
    was supposed to supply the time still had nothing to supply. A blackout
    with no events in it does not look broken. It looks like a quiet week.
    """

    def setUp(self):
        self.cal = StaticCalendar()

    def test_an_fomc_day_produces_events(self):
        events = self.cal.events(date(2026, 7, 27), days=7)
        self.assertTrue(any("FOMC" in e.name for e in events),
                        "29 July 2026 is an FOMC decision day")

    def test_the_blackout_fires_at_the_statement(self):
        """The regression itself: 14:00 ET on 29 July 2026 = 18:00 UTC."""
        moment = datetime(2026, 7, 29, 18, 0, tzinfo=timezone.utc)
        fired, reason = self.cal.blackout(moment)
        self.assertTrue(fired)
        self.assertIn("FOMC", reason)

    def test_the_statement_and_the_presser_merge_into_one_stand_aside(self):
        """Two events 30 minutes apart with a 30-minute window either side
        leave no tradable gap between them -- which is the point, because the
        press conference routinely reverses the statement's move."""
        for minute in (0, 10, 20, 30, 40, 50):
            gap = datetime(2026, 7, 29, 18, minute, tzinfo=timezone.utc)
            with self.subTest(minute=minute):
                self.assertTrue(self.cal.blackout(gap)[0])

    def test_the_window_ends_where_it_should(self):
        before = datetime(2026, 7, 29, 17, 0, tzinfo=timezone.utc)   # -60 min
        after = datetime(2026, 7, 29, 19, 5, tzinfo=timezone.utc)    # +35 min
        self.assertFalse(self.cal.blackout(before)[0])
        self.assertFalse(self.cal.blackout(after)[0])

    def test_the_decision_lands_at_1400_new_york(self):
        fomc = [e for e in self.cal.events(date(2026, 7, 27), 7)
                if e.name == "FOMC rate decision"][0]
        self.assertEqual((fomc.when.hour, fomc.when.minute), (18, 0))

    def test_a_winter_decision_shifts_with_new_york_time(self):
        """9 December 2026 is standard time: 14:00 ET = 19:00 UTC, not 18:00.
        Getting this wrong moves the blackout a full hour off the release."""
        fomc = [e for e in self.cal.events(date(2026, 12, 8), 3)
                if e.name == "FOMC rate decision"][0]
        self.assertEqual((fomc.when.hour, fomc.when.minute), (19, 0))

    def test_the_ecb_is_covered_too_and_in_frankfurt_time(self):
        """23 July 2026, 14:15 CEST = 12:15 UTC. The account is in euro, so
        an ECB decision changes the result without gold moving."""
        ecb = [e for e in self.cal.events(date(2026, 7, 20), 7)
               if e.name == "ECB rate decision"]
        self.assertTrue(ecb)
        self.assertEqual((ecb[0].when.hour, ecb[0].when.minute), (12, 15))
        self.assertEqual(ecb[0].currency, "EUR")

    def test_a_winter_ecb_decision_shifts_too(self):
        """17 December 2026, 14:15 CET = 13:15 UTC."""
        ecb = [e for e in self.cal.events(date(2026, 12, 16), 3)
               if e.name == "ECB rate decision"][0]
        self.assertEqual((ecb.when.hour, ecb.when.minute), (13, 15))

    def test_every_listed_date_parses_and_is_ordered(self):
        for values in (FOMC_DECISION_DATES, ECB_DECISION_DATES):
            parsed = [date.fromisoformat(v) for v in values]
            self.assertEqual(parsed, sorted(parsed))
            self.assertEqual(len(parsed), len(set(parsed)))

    def test_fomc_decisions_are_on_a_weekday(self):
        for v in FOMC_DECISION_DATES:
            self.assertLess(date.fromisoformat(v).weekday(), 5, v)

    def test_ecb_decisions_are_on_a_thursday(self):
        """The Governing Council announces on Thursday. A date that is not one
        is a transcription error, and the whole point of listing them is that
        they cannot be re-derived."""
        for v in ECB_DECISION_DATES:
            self.assertEqual(date.fromisoformat(v).weekday(), 3, v)

    def test_2027_dates_are_marked_tentative(self):
        events = [e for e in self.cal.events(date(2027, 1, 25), 7)
                  if e.name == "FOMC rate decision"]
        self.assertTrue(events)
        self.assertIn("tentative", events[0].note)

    def test_2026_dates_are_not_marked_tentative(self):
        events = [e for e in self.cal.events(date(2026, 7, 27), 7)
                  if e.name == "FOMC rate decision"]
        self.assertNotIn("tentative", events[0].note)


class TestTheScheduleAdmitsWhereItStops(unittest.TestCase):
    """A listed schedule runs out. A silent one that has run out answers
    "no high-impact release" for a date it cannot speak for -- which is the
    same failure as A20, just deferred to the year the list ends.
    """

    def setUp(self):
        self.cal = StaticCalendar()

    def test_a_window_inside_the_horizon_is_not_warned_about(self):
        self.assertIsNone(self.cal.horizon_gap(date(2026, 7, 27), 7))

    def test_a_window_past_the_horizon_says_so(self):
        warning = self.cal.horizon_gap(date(2027, 6, 1), 30)
        self.assertIsNotNone(warning)
        self.assertIn(known_through().isoformat(), warning)

    def test_the_horizon_is_the_earlier_of_the_two_lists(self):
        """Whichever bank's list ends first ends the coverage -- claiming the
        later date would promise ECB events that are not there."""
        last_fomc = max(date.fromisoformat(v) for v in FOMC_DECISION_DATES)
        last_ecb = max(date.fromisoformat(v) for v in ECB_DECISION_DATES)
        self.assertEqual(known_through(), min(last_fomc, last_ecb))

    def test_the_caveats_point_at_the_horizon(self):
        self.assertTrue(any("horizon" in c for c in self.cal.caveats))


class TestTheImpactNoteMatchesTheRightBank(unittest.TestCase):
    """"Rate decision" belongs to whichever bank the row names.

    The alias table is scanned in order and the first match wins, so with
    FOMC owning the bare phrase "rate decision" a live feed row called
    "ECB Rate Decision" was handed the Fed's note: wrong bank, wrong
    currency, wrong expected move. Order is the fix, and order is easy to
    undo by accident, so it is pinned here.
    """

    def test_an_ecb_row_gets_the_ecb_note(self):
        self.assertIn("euro", _match_note("ECB Rate Decision"))

    def test_a_fed_row_still_gets_the_fed_note(self):
        for name in ("FOMC Rate Decision", "Fed Interest Rate Decision",
                     "Interest Rate Decision"):
            with self.subTest(name=name):
                self.assertIn("press conference", _match_note(name))

    def test_an_unknown_row_gets_nothing_rather_than_a_guess(self):
        self.assertEqual(_match_note("Tertiary Industry Index"), "")


class TestFinnhubCalendar(unittest.TestCase):
    def test_parses_recorded_payload(self):
        client, fetcher = fake_client()
        fetcher.add("calendar/economic", FINNHUB_CALENDAR)
        events = finnhub_calendar(client, date(2026, 7, 26), date(2026, 8, 10),
                                  api_key="test")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].impact, "medium")   # sorted by time
        high = [e for e in events if e.impact == "high"]
        self.assertEqual(len(high), 1)
        self.assertIn("80-200", high[0].typical_gold_move)

    def test_missing_key_raises_clearly(self):
        client, _ = fake_client()
        with self.assertRaises(Exception) as ctx:
            finnhub_calendar(client, date(2026, 7, 26), date(2026, 8, 1),
                             api_key=None)
        self.assertIn("FINNHUB_API_KEY", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
