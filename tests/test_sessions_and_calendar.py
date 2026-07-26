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
from metals.sources.calendar import (StaticCalendar, first_friday, nfp_dates,
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
