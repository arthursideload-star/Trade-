"""Data source connectors, exercised offline against recorded payload shapes.

The point of these tests is the failure paths. A provider that returns clean
JSON is easy; the cases that matter are the rate-limit response that looks
like success, the nulls Yahoo pads gaps with, and the fallback chain when the
preferred provider is down.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

from metals.sources.cot import (CotReport, analyse_cot, fetch_cot,
                                gold_silver_positioning_divergence)
from metals.sources.http import FetchError, try_sources
from metals.sources.macro import (build_macro_context, correlation_check,
                                  fred_csv)
from metals.sources.news import (NewsContext, NewsItem, build_news_context,
                                 gdelt_search, parse_feed)
from metals.sources.prices import (cross_check, resample, stooq_candles,
                                   twelvedata_candles, yahoo_candles,
                                   yahoo_quote)
from metals.sources.registry import (Auth, Category, SOURCES, coverage_report,
                                     keyless, required_env_vars)
from tests.helpers import (ATOM_SAMPLE, CFTC_ROWS, FRED_CSV, GDELT_OK,
                           RSS_SAMPLE, STOOQ_CSV, TWELVEDATA_ERROR,
                           TWELVEDATA_OK, YAHOO_OK, YAHOO_WITH_NULLS,
                           fake_client, make_series)

UTC = timezone.utc


class TestHttpClient(unittest.TestCase):
    def test_caches_within_ttl(self):
        client, fetcher = fake_client()
        client.cache_ttl = 60
        fetcher.add("example", b'{"a":1}')
        client.get_json("https://example.invalid/x")
        client.get_json("https://example.invalid/x")
        self.assertEqual(len(fetcher.calls), 1)

    def test_params_are_encoded(self):
        client, fetcher = fake_client()
        fetcher.add("example", b"{}")
        client.get_json("https://example.invalid/x", {"a": 1, "b": "two"})
        self.assertIn("a=1", fetcher.calls[0])
        self.assertIn("b=two", fetcher.calls[0])

    def test_none_params_are_dropped(self):
        client, fetcher = fake_client()
        fetcher.add("example", b"{}")
        client.get_json("https://example.invalid/x", {"a": 1, "b": None})
        self.assertNotIn("b=", fetcher.calls[0])

    def test_non_json_response_is_reported_with_a_snippet(self):
        client, fetcher = fake_client()
        fetcher.add("example", b"<html>rate limited</html>")
        with self.assertRaises(FetchError) as ctx:
            client.get_json("https://example.invalid/x")
        self.assertIn("not JSON", str(ctx.exception))

    def test_try_sources_falls_through(self):
        calls: list[str] = []

        def bad():
            calls.append("bad")
            raise FetchError("bad", "down")

        def good():
            calls.append("good")
            return "value"

        value, name, failures = try_sources([("bad", bad), ("good", good)])
        self.assertEqual(value, "value")
        self.assertEqual(name, "good")
        self.assertEqual(len(failures), 1)

    def test_try_sources_raises_when_all_fail(self):
        with self.assertRaises(FetchError) as ctx:
            try_sources([
                ("a", lambda: (_ for _ in ()).throw(FetchError("a", "x"))),
                ("b", lambda: (_ for _ in ()).throw(FetchError("b", "y"))),
            ])
        self.assertIn("all sources failed", str(ctx.exception))

    def test_request_count_tracks_real_calls_only(self):
        client, fetcher = fake_client()
        client.cache_ttl = 60
        fetcher.add("example", b"{}")
        for _ in range(5):
            client.get_json("https://example.invalid/x")
        self.assertEqual(client.request_count, 1)


class TestPriceProviders(unittest.TestCase):
    def test_twelvedata_parses_and_sorts_ascending(self):
        client, fetcher = fake_client()
        fetcher.add("twelvedata.com", TWELVEDATA_OK)
        series = twelvedata_candles(client, "XAUUSD", "1h", api_key="test")
        self.assertEqual(len(series), 3)
        # The provider returns newest-first; the series must come back oldest-first.
        self.assertLess(series[0].ts, series[-1].ts)
        self.assertAlmostEqual(series.last.close, 4506.30)
        self.assertEqual(series.source, "twelvedata")

    def test_twelvedata_rate_limit_raises_instead_of_returning_empty(self):
        """The rate-limit response is HTTP 200 with an error body.

        Treating it as success would produce an empty series and, downstream,
        an analysis with no data that still looks like an analysis.
        """
        client, fetcher = fake_client()
        fetcher.add("twelvedata.com", TWELVEDATA_ERROR)
        with self.assertRaises(FetchError) as ctx:
            twelvedata_candles(client, "XAUUSD", "1h", api_key="test")
        self.assertIn("credits", str(ctx.exception))

    def test_twelvedata_without_key_raises_clearly(self):
        client, _ = fake_client()
        with self.assertRaises(FetchError) as ctx:
            twelvedata_candles(client, "XAUUSD", "1h", api_key=None)
        self.assertIn("TWELVEDATA_API_KEY", str(ctx.exception))

    def test_yahoo_parses(self):
        client, fetcher = fake_client()
        fetcher.add("query1.finance.yahoo.com", YAHOO_OK)
        series = yahoo_candles(client, "XAUUSD", "1h")
        self.assertEqual(len(series), 3)
        self.assertAlmostEqual(series.last.close, 4506.3)

    def test_yahoo_nulls_are_skipped_not_zero_filled(self):
        client, fetcher = fake_client()
        fetcher.add("query1.finance.yahoo.com", YAHOO_WITH_NULLS)
        series = yahoo_candles(client, "XAUUSD", "1h")
        self.assertEqual(len(series), 2)
        for c in series:
            self.assertGreater(c.low, 0)

    def test_yahoo_quote(self):
        client, fetcher = fake_client()
        fetcher.add("query1.finance.yahoo.com", YAHOO_OK)
        q = yahoo_quote(client, "XAUUSD")
        self.assertAlmostEqual(q.price, 4506.3)
        self.assertEqual(q.symbol, "XAUUSD")

    def test_stooq_csv(self):
        client, fetcher = fake_client()
        fetcher.add("stooq.com", STOOQ_CSV)
        series = stooq_candles(client, "XAUUSD")
        self.assertEqual(len(series), 3)
        self.assertAlmostEqual(series.last.close, 4506.0)

    def test_stooq_refuses_intraday(self):
        client, fetcher = fake_client()
        fetcher.add("stooq.com", STOOQ_CSV)
        with self.assertRaises(FetchError):
            stooq_candles(client, "XAUUSD", "15m")

    def test_cross_check_detects_a_stale_feed(self):
        from metals.sources.prices import Quote
        now = datetime.now(UTC)
        ok, note = cross_check([
            Quote("XAUUSD", 4500.0, None, None, now, "a"),
            Quote("XAUUSD", 4502.0, None, None, now, "b"),
        ])
        self.assertTrue(ok)

        bad, note = cross_check([
            Quote("XAUUSD", 4500.0, None, None, now, "a"),
            Quote("XAUUSD", 4200.0, None, None, now, "b"),
        ])
        self.assertFalse(bad)
        self.assertIn("disagree", note)

    def test_cross_check_with_one_source_is_honest_about_it(self):
        from metals.sources.prices import Quote
        ok, note = cross_check([
            Quote("XAUUSD", 4500.0, None, None, datetime.now(UTC), "a")
        ])
        self.assertTrue(ok)
        self.assertIn("no cross-check", note)


class TestResampling(unittest.TestCase):
    def test_h1_to_h4_aggregates_correctly(self):
        h1 = make_series(timeframe="1h", n=48,
                         start=datetime(2026, 7, 1, 0, 0, tzinfo=UTC))
        h4 = resample(h1, "4h")
        self.assertEqual(h4.timeframe, "4h")
        self.assertEqual(len(h4), 12)
        first = h4[0]
        source = h1.candles[:4]
        self.assertAlmostEqual(first.open, source[0].open)
        self.assertAlmostEqual(first.close, source[-1].close)
        self.assertAlmostEqual(first.high, max(c.high for c in source))
        self.assertAlmostEqual(first.low, min(c.low for c in source))

    def test_resample_to_a_lower_timeframe_is_a_no_op(self):
        h4 = make_series(timeframe="4h", n=20)
        self.assertIs(resample(h4, "1h"), h4)


class TestMacro(unittest.TestCase):
    def test_fred_csv_skips_holiday_dots(self):
        client, fetcher = fake_client()
        fetcher.add("fredgraph.csv", FRED_CSV)
        series = fred_csv(client, "DFII10")
        self.assertEqual(len(series.points), 3)   # the "." row is dropped
        self.assertAlmostEqual(series.latest.value, 1.82)

    def test_change_over_a_covered_window(self):
        client, fetcher = fake_client()
        fetcher.add("fredgraph.csv", FRED_CSV)
        series = fred_csv(client, "DFII10")
        # Latest point is 2026-07-20; 30 days back reaches the 2026-06-01 point.
        change = series.change(30)
        self.assertIsNotNone(change)
        self.assertAlmostEqual(change, 1.82 - 2.10, places=6)

    def test_change_returns_none_when_the_window_predates_the_data(self):
        """Returning None rather than silently using the oldest point.

        A macro score built on "the change over 20 days" must not quietly
        become "the change over however much history happens to exist".
        """
        client, fetcher = fake_client()
        fetcher.add("fredgraph.csv", FRED_CSV)
        series = fred_csv(client, "DFII10")
        self.assertIsNone(series.change(3650))

    def test_macro_context_degrades_without_crashing(self):
        client, fetcher = fake_client()
        fetcher.fail("fredgraph.csv", "network down")
        fetcher.fail("stlouisfed.org", "network down")
        ctx = build_macro_context(client)
        self.assertEqual(ctx.bias, "unknown")
        self.assertTrue(ctx.missing)
        self.assertTrue(any("unavailable" in e for e in ctx.explain()))

    def test_macro_bias_is_bullish_on_falling_yields(self):
        from metals.sources.macro import MacroContext
        ctx = MacroContext(real_yield=0.4, real_yield_change_20d=-0.35,
                           dollar=100.0, dollar_change_20d=-2.5, vix=30.0)
        self.assertEqual(ctx.bias, "bullish")

    def test_macro_bias_is_bearish_on_rising_yields_and_dollar(self):
        from metals.sources.macro import MacroContext
        ctx = MacroContext(real_yield=3.0, real_yield_change_20d=0.40,
                           dollar=110.0, dollar_change_20d=3.0, vix=12.0)
        self.assertEqual(ctx.bias, "bearish")

    def test_correlation_check_flags_a_broken_relationship(self):
        gold = [float(x) for x in range(60)]
        dollar = [float(x) for x in range(60)]   # moving together: abnormal
        note = correlation_check(gold, dollar, "DXY", "negative")
        self.assertIsNotNone(note)
        self.assertIn("positive where it is normally", note)

    def test_correlation_check_is_quiet_when_normal(self):
        gold = [float(x) for x in range(60)]
        dollar = [float(-x) for x in range(60)]
        self.assertIsNone(correlation_check(gold, dollar, "DXY", "negative"))


class TestCot(unittest.TestCase):
    def test_fetch_and_parse(self):
        client, fetcher = fake_client()
        fetcher.add("publicreporting.cftc.gov", CFTC_ROWS)
        reports = fetch_cot("XAUUSD", client)
        self.assertEqual(len(reports), len(CFTC_ROWS))
        self.assertEqual(reports[0].symbol, "XAUUSD")

    def test_net_positions(self):
        r = CotReport("XAUUSD", date(2026, 7, 21), 120_000, 300_000,
                      150_000, 40_000, 500_000)
        self.assertEqual(r.commercial_net, -180_000)
        self.assertEqual(r.managed_net, 110_000)
        self.assertAlmostEqual(r.managed_net_pct_oi, 22.0)

    def test_analyse_detects_crowded_long(self):
        client, fetcher = fake_client()
        fetcher.add("publicreporting.cftc.gov", CFTC_ROWS)
        reports = fetch_cot("XAUUSD", client)
        signal = analyse_cot(reports)
        # The fixture ramps managed longs monotonically, so the last is the max.
        self.assertEqual(signal.reading, "crowded_long")
        self.assertEqual(signal.contrarian_bias, "bearish")
        self.assertTrue(any("percentile" in n for n in signal.notes))

    def test_analyse_always_states_the_lag(self):
        client, fetcher = fake_client()
        fetcher.add("publicreporting.cftc.gov", CFTC_ROWS)
        signal = analyse_cot(fetch_cot("XAUUSD", client))
        self.assertTrue(any("days old" in n for n in signal.notes))

    def test_positioning_divergence(self):
        from metals.sources.cot import CotSignal
        r = CotReport("XAUUSD", date(2026, 7, 21), 1, 1, 1, 1, 100)
        gold = CotSignal("XAUUSD", r, 95.0, 5.0, "crowded_long", 0.9, [])
        silver = CotSignal("XAGUSD", r, 20.0, 80.0, "neutral", 0.0, [])
        note = gold_silver_positioning_divergence(gold, silver)
        self.assertIsNotNone(note)
        self.assertIn("diverged", note)


class TestNews(unittest.TestCase):
    def test_parses_rss(self):
        items = parse_feed(RSS_SAMPLE.encode(), "test")
        self.assertEqual(len(items), 3)
        self.assertIn("Fed holds rates", items[0].title)
        self.assertIsNotNone(items[0].published)

    def test_parses_atom(self):
        items = parse_feed(ATOM_SAMPLE.encode(), "test")
        self.assertEqual(len(items), 1)
        self.assertIn("CPI", items[0].title)
        self.assertIsNotNone(items[0].published)

    def test_malformed_xml_raises_rather_than_returning_empty(self):
        with self.assertRaises(FetchError):
            parse_feed(b"<not xml", "test")

    def test_impact_scoring(self):
        items = parse_feed(RSS_SAMPLE.encode(), "test")
        fed = items[0]
        miners = items[1]
        self.assertGreater(fed.impact_score(), 0.8)
        self.assertLess(miners.impact_score(), fed.impact_score())

    def test_direction_hints(self):
        ceasefire = NewsItem("Ceasefire agreed in regional conflict", "", None, "t")
        war = NewsItem("Invasion escalates, safe haven demand surges", "", None, "t")
        self.assertEqual(ceasefire.direction_hint(), -1)
        self.assertEqual(war.direction_hint(), +1)

    def test_veto_fires_on_a_fresh_high_impact_headline(self):
        now = datetime.now(UTC)
        ctx = NewsContext(
            items=[NewsItem("FOMC rate decision: Fed cuts by 50bp", "", now,
                            "fed_press")],
            feeds_ok=["fed_press"], fetched_at=now,
        )
        vetoed, why = ctx.veto()
        self.assertTrue(vetoed)
        self.assertIn("high-impact", why)

    def test_veto_fails_closed_when_no_feed_is_reachable(self):
        ctx = NewsContext(items=[], feeds_ok=[],
                          feeds_failed=[("kitco", "timeout")])
        vetoed, why = ctx.veto()
        self.assertTrue(vetoed)
        self.assertIn("no curated news feed could be reached", why)

    def test_gdelt_alone_does_not_satisfy_the_veto(self):
        """GDELT reports coverage volume, not policy headlines.

        A run where only GDELT answered has no sight of an FOMC statement, so
        treating it as sufficient would let a trade through minutes after a
        rate decision.
        """
        now = datetime.now(UTC)
        ctx = NewsContext(
            items=[NewsItem("Some world story", "", now, "gdelt:example.invalid")],
            feeds_ok=["gdelt"],
            feeds_failed=[("fed_press", "timeout"), ("kitco", "timeout")],
            fetched_at=now,
        )
        self.assertFalse(ctx.reachable)
        self.assertTrue(ctx.world_coverage_ok)
        vetoed, why = ctx.veto()
        self.assertTrue(vetoed)
        self.assertIn("GDELT answered", why)

    def test_veto_is_quiet_when_nothing_is_happening(self):
        now = datetime.now(UTC)
        ctx = NewsContext(
            items=[NewsItem("Gold miners report higher output", "", now,
                            "kitco")],
            feeds_ok=["kitco"], fetched_at=now,
        )
        vetoed, _ = ctx.veto()
        self.assertFalse(vetoed)

    def test_syndicated_headlines_are_deduplicated(self):
        """One wire story reaching four feeds must count once.

        Otherwise the directional lean is inflated by syndication rather than
        by how many distinct things actually happened.
        """
        client, fetcher = fake_client()
        for host in ("federalreserve.gov", "kitco.com", "goldseek.com",
                     "mining.com", "ecb.europa.eu"):
            fetcher.add(host, RSS_SAMPLE)
        fetcher.add("gdeltproject.org", {"articles": []})
        ctx = build_news_context(client)
        titles = [i.title for i in ctx.items]
        self.assertEqual(len(titles), len(set(titles)))
        self.assertEqual(len(titles), 3)   # the sample feed has 3 stories

    def test_deduplication_keeps_the_earliest_timestamp(self):
        from metals.sources.news import _deduplicate
        early = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)
        late = datetime(2026, 7, 26, 12, 40, tzinfo=UTC)
        items = [
            NewsItem("FOMC holds rates", "", late, "kitco"),
            NewsItem("FOMC holds rates!", "", early, "fed_press"),
        ]
        out = _deduplicate(items)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].published, early)

    def test_build_context_survives_partial_feed_failure(self):
        client, fetcher = fake_client()
        fetcher.add("federalreserve.gov", RSS_SAMPLE)
        fetcher.fail("kitco.com", "timeout")
        fetcher.fail("goldseek.com", "timeout")
        fetcher.fail("mining.com", "timeout")
        fetcher.fail("ecb.europa.eu", "timeout")
        fetcher.fail("gdeltproject.org", "timeout")
        ctx = build_news_context(client)
        self.assertTrue(ctx.reachable)
        self.assertTrue(ctx.items)
        self.assertTrue(ctx.feeds_failed)

    def test_gdelt_parsing(self):
        client, fetcher = fake_client()
        fetcher.add("gdeltproject.org", GDELT_OK)
        items = gdelt_search(client)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].published.year, 2026)


class TestRegistry(unittest.TestCase):
    def test_every_source_has_provides_and_a_url(self):
        for key, s in SOURCES.items():
            self.assertTrue(s.provides, f"{key} declares nothing it provides")
            self.assertTrue(s.url, f"{key} has no url")
            self.assertIsInstance(s.category, Category)

    def test_keyed_sources_declare_their_env_var(self):
        for key, s in SOURCES.items():
            if s.auth is Auth.FREE_KEY:
                self.assertTrue(s.env_var, f"{key} needs a key but names no env var")

    def test_keyless_sources_cover_the_essentials(self):
        cats = {s.category for s in keyless()}
        for needed in (Category.PRICE, Category.MACRO, Category.NEWS,
                       Category.POSITIONING, Category.CALENDAR):
            self.assertIn(needed, cats,
                          f"nothing keyless covers {needed.value}")

    def test_coverage_report_with_no_keys(self):
        report = coverage_report({})
        self.assertTrue(report["active"])
        self.assertTrue(report["blocked"])
        self.assertEqual(report["categories_missing"], [])

    def test_coverage_report_activates_with_a_key(self):
        without = coverage_report({})
        with_key = coverage_report({"TWELVEDATA_API_KEY": "x"})
        self.assertGreater(len(with_key["active"]), len(without["active"]))

    def test_required_env_vars_is_a_usable_map(self):
        env_map = required_env_vars()
        self.assertIn("TWELVEDATA_API_KEY", env_map)
        self.assertIn("FRED_API_KEY", env_map)


if __name__ == "__main__":
    unittest.main()
