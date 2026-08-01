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


class TestPersistenceMeasures(unittest.TestCase):
    """The variance ratio, checked against series whose answer is known.

    A statistic nobody has validated is a decoration. These build a random
    walk, a persistent series and a mean-reverting one out of an AR(1) on
    the returns, and require the test to sort them correctly.

    The first version had an extra factor of T in the heteroskedasticity
    correction. Every variance ratio came out right and every z came out
    roughly thirty times too small -- z = +0.28 for a series with an AR(1)
    coefficient of 0.3 in it, which fails to reject anything at all. The
    ratios looked perfect, so nothing but a test with a known answer would
    have caught it.
    """

    @staticmethod
    def _ar1(n: int, seed: int, phi: float) -> list[float]:
        import random
        rng = random.Random(seed)
        prices, r = [0.0], 0.0
        for _ in range(n):
            r = phi * r + rng.gauss(0.0, 0.001)
            prices.append(prices[-1] + r)
        return prices

    def test_a_random_walk_is_not_rejected(self):
        from metals.persistence import variance_ratio
        rejects = sum(variance_ratio(self._ar1(4_000, s, 0.0), 4)
                      .rejects_random_walk for s in range(12))
        self.assertLessEqual(rejects, 2, "a 5% test should reject a true "
                                         "random walk about once in twenty")

    def test_a_persistent_series_is_rejected_upward(self):
        from metals.persistence import variance_ratio
        for s in range(4):
            with self.subTest(seed=s):
                v = variance_ratio(self._ar1(4_000, s, 0.3), 4)
                self.assertTrue(v.rejects_random_walk)
                self.assertGreater(v.ratio, 1.0)
                self.assertEqual(v.verdict, "persistent")

    def test_a_mean_reverting_series_is_rejected_downward(self):
        from metals.persistence import variance_ratio
        for s in range(4):
            with self.subTest(seed=s):
                v = variance_ratio(self._ar1(4_000, s, -0.3), 4)
                self.assertTrue(v.rejects_random_walk)
                self.assertLess(v.ratio, 1.0)
                self.assertEqual(v.verdict, "mean reverting")

    def test_the_z_statistic_is_the_right_order_of_magnitude(self):
        """The regression. A clear AR(1) must produce a large z, not 0.28."""
        from metals.persistence import variance_ratio
        v = variance_ratio(self._ar1(4_000, 1, 0.3), 4)
        self.assertGreater(abs(v.z), 8.0)

    def test_hurst_alone_would_have_got_it_wrong(self):
        """Why the variance ratio is reported and R/S is only shown.

        On 4,000 observations the rescaled range reads about 0.51 for a
        strongly mean-reverting series -- above 0.5, i.e. the wrong side --
        while the variance ratio separates the same series cleanly.
        """
        from metals.persistence import hurst_rescaled_range, variance_ratio
        prices = self._ar1(4_000, 1, -0.3)
        self.assertGreater(hurst_rescaled_range(prices), 0.45)
        self.assertLess(variance_ratio(prices, 4).ratio, 0.8)

    def test_too_little_data_returns_the_neutral_answer(self):
        from metals.persistence import hurst_rescaled_range, variance_ratio
        short = self._ar1(40, 1, 0.3)
        self.assertEqual(hurst_rescaled_range(short), 0.5)
        v = variance_ratio(short, 4)
        self.assertEqual(v.ratio, 1.0)
        self.assertFalse(v.rejects_random_walk)

    def test_the_verdict_does_not_lean_on_hurst_when_nothing_rejected(self):
        """An H of 0.55 with every z inside the band is a random walk with a
        decorative decimal on it."""
        from metals.persistence import Persistence, VarianceRatio
        p = Persistence(hurst=0.62,
                        ratios=(VarianceRatio(2, 1.05, 1.1, 5_000),
                                VarianceRatio(4, 1.09, 1.5, 5_000)),
                        observations=5_000)
        self.assertEqual(p.verdict, "random walk")
        self.assertIn("random walk", p.target_advice.lower())
