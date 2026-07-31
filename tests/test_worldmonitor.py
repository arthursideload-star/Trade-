"""The World Monitor adapter.

Two things are being tested and they are not the same thing.

The first is parsing: given the payload shapes published in World Monitor's
OpenAPI schemas, does this module pull the right numbers out. That is
ordinary and is done offline against recorded shapes, like every other source
in this package.

The second matters more. This source is attractive precisely because it looks
like it could feed the paper chain -- it has a gold price and an economic
calendar, which is most of what a session needs. It cannot: the quote has no
bid/ask and no day range, and the calendar has no clock time. Those absences
are asserted here, because the failure mode is not a crash. It is someone
wiring it in, getting plausible numbers, and only finding out later that the
spread was invented.

Nothing here has run against the live service: the container's proxy returns
403 for worldmonitor.app. These tests pin the parsing, not the contract.
"""

from __future__ import annotations

import unittest
from datetime import date

from metals.sources import worldmonitor as wm
from metals.sources.http import FetchError
from tests.helpers import (WORLDMONITOR_CALENDAR, WORLDMONITOR_CALENDAR_COLD,
                           WORLDMONITOR_COMMODITIES, WORLDMONITOR_ECB_FX,
                           fake_client)

KEY = "wm_test"


class TestCommodityQuotes(unittest.TestCase):
    def _client(self):
        client, fetcher = fake_client()
        fetcher.add("list-commodity-quotes", WORLDMONITOR_COMMODITIES)
        return client

    def test_it_parses_the_published_shape(self):
        quotes = wm.commodity_quotes(self._client(), api_key_value=KEY)
        self.assertEqual(len(quotes), 3)
        self.assertEqual(quotes[0].symbol, "GC=F")
        self.assertAlmostEqual(quotes[0].price, 4051.8)
        self.assertAlmostEqual(quotes[0].change_pct, -0.42)

    def test_gold_is_found_by_symbol_not_by_position(self):
        gold = wm.gold_quote(self._client(), api_key_value=KEY)
        self.assertEqual(gold.symbol, "GC=F")
        self.assertTrue(gold.is_gold)

    def test_a_row_without_a_price_is_dropped_not_defaulted(self):
        client, fetcher = fake_client()
        fetcher.add("list-commodity-quotes",
                    {"quotes": [{"symbol": "GC=F", "name": "Gold"},
                                {"symbol": "SI=F", "price": 52.1}]})
        quotes = wm.commodity_quotes(client, api_key_value=KEY)
        self.assertEqual([q.symbol for q in quotes], ["SI=F"])

    def test_a_missing_gold_row_raises_rather_than_returning_none(self):
        """A caller that asked for gold and got silence carries on with
        whatever it had. That is how a stale price reaches a ledger row."""
        client, fetcher = fake_client()
        fetcher.add("list-commodity-quotes", {"quotes": [
            {"symbol": "CL=F", "name": "Crude", "price": 71.0}]})
        with self.assertRaises(FetchError):
            wm.gold_quote(client, api_key_value=KEY)

    def test_a_malformed_response_raises(self):
        client, fetcher = fake_client()
        fetcher.add("list-commodity-quotes", {"error": "nope"})
        with self.assertRaises(FetchError):
            wm.commodity_quotes(client, api_key_value=KEY)


class TestTheQuoteCannotFeedASession(unittest.TestCase):
    """The absences, asserted.

    A19: the spread decides whether a one-day session has a positive or a
    negative expectancy. This endpoint has no bid and no ask. The day range
    is the entire day-range strategy, and this endpoint has no high and no
    low. Both gaps are silent -- the response parses fine and yields a
    perfectly plausible price.
    """

    def test_the_quote_carries_no_bid_or_ask(self):
        client, fetcher = fake_client()
        fetcher.add("list-commodity-quotes", WORLDMONITOR_COMMODITIES)
        gold = wm.gold_quote(client, api_key_value=KEY)
        for absent in ("bid", "ask", "spread"):
            self.assertFalse(hasattr(gold, absent),
                             f"if {absent} ever appears, A19 needs revisiting")

    def test_the_quote_carries_no_day_range(self):
        client, fetcher = fake_client()
        fetcher.add("list-commodity-quotes", WORLDMONITOR_COMMODITIES)
        gold = wm.gold_quote(client, api_key_value=KEY)
        for absent in ("high", "low", "day_high", "day_low"):
            self.assertFalse(hasattr(gold, absent))

    def test_the_module_says_so_in_one_sentence(self):
        sentence = wm.cannot_run_a_session()
        self.assertIn("spread", sentence)
        self.assertIn("day high/low", sentence.replace("high/low", "high/low"))

    def test_the_capability_table_does_not_overstate(self):
        """A catalogue that claims more than it delivers is A20's shape --
        the static calendar advertised FOMC for months without emitting one."""
        self.assertTrue(wm.CAPABILITIES["spread"].startswith("no"))
        self.assertTrue(wm.CAPABILITIES["day high/low"].startswith("no"))
        self.assertTrue(
            wm.CAPABILITIES["release times for R4"].startswith("no"))


class TestTheEconomicCalendar(unittest.TestCase):
    def _client(self, payload=WORLDMONITOR_CALENDAR):
        client, fetcher = fake_client()
        fetcher.add("get-economic-calendar", payload)
        return client

    def test_it_parses_and_sorts_by_day(self):
        events = wm.economic_calendar(self._client(), api_key_value=KEY)
        self.assertEqual([e.day for e in events], sorted(e.day for e in events))
        self.assertEqual(events[0].day, date(2026, 8, 3))

    def test_a_cold_cache_is_a_failure_not_an_empty_calendar(self):
        """`unavailable: true` means "I could not look". Returning [] would
        make it mean "nothing is scheduled" -- the A20 confusion exactly."""
        with self.assertRaises(FetchError) as ctx:
            wm.economic_calendar(self._client(WORLDMONITOR_CALENDAR_COLD),
                                 api_key_value=KEY)
        self.assertIn("unavailable", str(ctx.exception))

    def test_a_release_with_a_published_time_gets_one(self):
        events = wm.economic_calendar(self._client(), api_key_value=KEY)
        nfp = [e for e in events if "Nonfarm" in e.event][0]
        self.assertEqual(nfp.release_time_et, (8, 30))
        self.assertTrue(nfp.has_a_time)

    def test_a_release_without_one_is_left_without_one(self):
        """No default. A blackout aimed at the wrong half-hour is worse than
        none, because it looks like protection."""
        events = wm.economic_calendar(self._client(), api_key_value=KEY)
        fomc = [e for e in events if "FOMC" in e.event][0]
        self.assertIsNone(fomc.release_time_et)
        self.assertFalse(fomc.has_a_time)

    def test_high_impact_days_collects_the_days_worth_knowing(self):
        events = wm.economic_calendar(self._client(), api_key_value=KEY)
        days = wm.high_impact_days(events)
        self.assertIn(date(2026, 8, 7), days)    # NFP
        self.assertIn(date(2026, 8, 12), days)   # CPI
        self.assertIn(date(2026, 9, 16), days)   # FOMC

    def test_an_undated_row_is_dropped(self):
        client, fetcher = fake_client()
        fetcher.add("get-economic-calendar",
                    {"events": [{"event": "Something", "country": "US"},
                                {"date": "2026-08-07", "event": "CPI"}]})
        events = wm.economic_calendar(client, api_key_value=KEY)
        self.assertEqual(len(events), 1)

    def test_several_date_notations_parse(self):
        for text in ("2026-08-07", "2026/08/07", "07.08.2026",
                     "2026-08-07T00:00:00Z"):
            with self.subTest(text=text):
                self.assertEqual(wm._parse_day(text), date(2026, 8, 7))

    def test_nonsense_dates_return_none_rather_than_raising(self):
        for text in ("", None, "not a date", "2026-13-45"):
            with self.subTest(text=text):
                self.assertIsNone(wm._parse_day(text))


class TestTheEurUsdRate(unittest.TestCase):
    """The one number worth taking from here.

    Every euro figure in the paper chain is a dollar result divided by a
    constant 1.08. This endpoint could replace the constant with a reading.
    """

    def test_it_finds_usd_in_the_rates_list(self):
        client, fetcher = fake_client()
        fetcher.add("get-ecb-fx-rates", WORLDMONITOR_ECB_FX)
        self.assertAlmostEqual(wm.eur_usd(client, api_key_value=KEY), 1.1632)

    def test_it_survives_a_different_response_shape(self):
        """The payload shape could not be pinned down from the OpenAPI
        example, and a wrong FX rate silently rescales the whole journal."""
        for payload in (
            {"rates": {"USD": 1.1632}},
            {"data": {"rates": [{"code": "USD", "value": 1.1632}]}},
            {"fxRates": [{"currency": "usd", "rate": 1.1632}]},
        ):
            with self.subTest(payload=payload):
                client, fetcher = fake_client()
                fetcher.add("get-ecb-fx-rates", payload)
                self.assertAlmostEqual(wm.eur_usd(client, api_key_value=KEY),
                                       1.1632)

    def test_no_usd_anywhere_raises(self):
        client, fetcher = fake_client()
        fetcher.add("get-ecb-fx-rates", {"rates": [{"currency": "GBP",
                                                    "rate": 0.857}]})
        with self.assertRaises(FetchError):
            wm.eur_usd(client, api_key_value=KEY)


class TestAuthentication(unittest.TestCase):
    def test_a_missing_key_fails_before_the_request(self):
        import os
        from unittest import mock
        client, fetcher = fake_client()
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(FetchError) as ctx:
                wm.commodity_quotes(client)
        self.assertIn(wm.API_KEY_ENV, str(ctx.exception))
        self.assertEqual(fetcher.calls, [],
                         "no request should leave the process without a key")

    def test_the_key_travels_in_the_documented_header(self):
        seen: dict = {}

        def fetcher(url, *, headers=None, timeout=None):
            seen.update(headers or {})
            import json
            return json.dumps(WORLDMONITOR_COMMODITIES).encode()

        from metals.sources.http import HttpClient
        wm.commodity_quotes(HttpClient(fetcher=fetcher, retries=0,
                                       cache_ttl=0), api_key_value=KEY)
        self.assertEqual(seen.get(wm.KEY_HEADER), KEY)

    def test_the_environment_variable_is_used_when_no_key_is_passed(self):
        import os
        from unittest import mock
        client, fetcher = fake_client()
        fetcher.add("list-commodity-quotes", WORLDMONITOR_COMMODITIES)
        with mock.patch.dict(os.environ, {wm.API_KEY_ENV: "from_env"}):
            quotes = wm.commodity_quotes(client)
        self.assertTrue(quotes)


if __name__ == "__main__":
    unittest.main()
