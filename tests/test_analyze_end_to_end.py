"""End-to-end analysis with the whole network stack mocked.

These tests exist to check the parts that only appear when everything is
wired together: that the veto layer can override a strong technical signal,
that data gaps reduce confidence rather than being ignored, and that the
rendered card never claims more than the inputs support.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from metals.analyze import DataQuality, analyse, gather_context
from metals.risk import AccountState
from metals.sources.http import HttpClient
from tests.helpers import FakeFetcher, FRED_CSV, RSS_SAMPLE, make_series

UTC = timezone.utc
MOMENT = datetime(2026, 7, 21, 14, 0, tzinfo=UTC)   # Tuesday, LDN/NY overlap


def _yahoo_payload(series, price: float) -> dict:
    return {
        "chart": {
            "result": [{
                "meta": {"symbol": "GC=F", "regularMarketPrice": price,
                         "regularMarketTime": int(MOMENT.timestamp())},
                "timestamp": [int(c.ts.timestamp()) for c in series],
                "indicators": {"quote": [{
                    "open": [c.open for c in series],
                    "high": [c.high for c in series],
                    "low": [c.low for c in series],
                    "close": [c.close for c in series],
                    "volume": [c.volume for c in series],
                }]},
            }],
            "error": None,
        }
    }


def build_fetcher(*, quiet_news: bool = True, macro: bool = True,
                  news_reachable: bool = True) -> FakeFetcher:
    """A fetcher wired for a plausible, complete market snapshot."""
    fetcher = FakeFetcher()

    gold = make_series("XAUUSD", "1h", n=300, start_price=4500.0,
                       drift=0.6, noise=2.5,
                       start=MOMENT - timedelta(hours=300))
    fetcher.add("query1.finance.yahoo.com",
                _yahoo_payload(gold, gold.last.close))

    if macro:
        fetcher.add("fredgraph.csv", FRED_CSV)
    else:
        fetcher.fail("fredgraph.csv", "network down")
    fetcher.fail("api.stlouisfed.org", "no key")

    if news_reachable:
        feed = RSS_SAMPLE
        if not quiet_news:
            feed = RSS_SAMPLE.replace(
                "Gold miners report higher output in Q2",
                "FOMC announces emergency rate decision",
            )
        for host in ("federalreserve.gov", "kitco.com", "goldseek.com",
                     "mining.com", "ecb.europa.eu"):
            fetcher.add(host, feed)
    else:
        for host in ("federalreserve.gov", "kitco.com", "goldseek.com",
                     "mining.com", "ecb.europa.eu"):
            fetcher.fail(host, "timeout")

    fetcher.add("gdeltproject.org", {"articles": []})
    fetcher.fail("finnhub.io", "no key")
    fetcher.fail("stooq.com", "not needed")
    return fetcher


def client_with(fetcher: FakeFetcher) -> HttpClient:
    return HttpClient(fetcher=fetcher, retries=0, cache_ttl=0)


class TestGatherContext(unittest.TestCase):
    def test_builds_a_complete_context(self):
        client = client_with(build_fetcher())
        ctx = gather_context("XAUUSD", MOMENT, client)
        self.assertEqual(ctx.symbol, "XAUUSD")
        self.assertGreater(ctx.price, 0)
        self.assertIsNotNone(ctx.h1)
        self.assertIsNotNone(ctx.levels)
        self.assertGreater(ctx.atr_h1, 0)
        self.assertIn(ctx.regime, ("trending", "trending_volatile", "ranging",
                                   "ranging_quiet", "transitional", "unknown"))

    def test_missing_macro_is_recorded_not_hidden(self):
        client = client_with(build_fetcher(macro=False))
        ctx = gather_context("XAUUSD", MOMENT, client)
        self.assertIsNotNone(ctx.macro)
        self.assertTrue(ctx.macro.missing)
        self.assertEqual(ctx.macro.bias, "unknown")

    def test_unreachable_news_is_recorded(self):
        client = client_with(build_fetcher(news_reachable=False))
        ctx = gather_context("XAUUSD", MOMENT, client)
        self.assertIsNotNone(ctx.news)
        self.assertFalse(ctx.news.reachable)

    def test_no_candles_at_all_raises_rather_than_guessing(self):
        fetcher = FakeFetcher()
        fetcher.fail("query1.finance.yahoo.com", "down")
        fetcher.fail("stooq.com", "down")
        with self.assertRaises(RuntimeError) as ctx:
            gather_context("XAUUSD", MOMENT, client_with(fetcher))
        self.assertIn("cannot proceed", str(ctx.exception))


class TestDataQuality(unittest.TestCase):
    def test_penalty_scales_with_gaps(self):
        clean = DataQuality()
        degraded = DataQuality(degraded=["candles 4h"])
        broken = DataQuality(degraded=["candles 4h"], missing=["macro", "news"])
        self.assertEqual(clean.penalty, 1.0)
        self.assertLess(degraded.penalty, clean.penalty)
        self.assertLess(broken.penalty, degraded.penalty)

    def test_penalty_has_a_floor(self):
        awful = DataQuality(degraded=["a"] * 10, missing=["b"] * 10)
        self.assertGreaterEqual(awful.penalty, 0.35)


class TestAnalyse(unittest.TestCase):
    def test_produces_a_renderable_recommendation(self):
        client = client_with(build_fetcher())
        rec = analyse("XAUUSD", AccountState(equity=10_000.0),
                      MOMENT, client)
        self.assertIn(rec.action, ("long", "short", "no_trade"))
        card = rec.render()
        self.assertIn("XAUUSD", card)
        self.assertIn("DATA", card)
        self.assertIn("Execution is manual", card)

    def test_daily_loss_limit_blocks_regardless_of_signal(self):
        client = client_with(build_fetcher())
        account = AccountState(equity=9_600.0, realised_pnl_today=-400.0,
                               starting_equity_today=10_000.0)
        rec = analyse("XAUUSD", account, MOMENT, client)
        self.assertEqual(rec.action, "no_trade")
        self.assertTrue(any("R2" in b for b in rec.blocks))

    def test_high_impact_headline_vetoes(self):
        """A fresh FOMC headline must block even a clean technical setup."""
        client = client_with(build_fetcher(quiet_news=False))
        rec = analyse("XAUUSD", AccountState(equity=10_000.0), MOMENT, client)
        self.assertEqual(rec.action, "no_trade")
        self.assertTrue(
            any("R4" in b for b in rec.blocks),
            f"expected a news veto, got blocks={rec.blocks}",
        )

    def test_unreachable_news_fails_closed(self):
        client = client_with(build_fetcher(news_reachable=False))
        rec = analyse("XAUUSD", AccountState(equity=10_000.0), MOMENT, client)
        self.assertEqual(rec.action, "no_trade")
        self.assertTrue(any("R4" in b or "news" in b.lower() for b in rec.blocks))

    def test_rollover_window_blocks(self):
        rollover_moment = datetime(2026, 7, 21, 21, 30, tzinfo=UTC)
        fetcher = build_fetcher()
        client = client_with(fetcher)
        rec = analyse("XAUUSD", AccountState(equity=10_000.0),
                      rollover_moment, client)
        self.assertEqual(rec.action, "no_trade")
        self.assertTrue(any("R5" in b for b in rec.blocks))

    def test_missing_macro_reduces_confidence(self):
        with_macro = analyse("XAUUSD", AccountState(equity=10_000.0), MOMENT,
                             client_with(build_fetcher(macro=True)))
        without = analyse("XAUUSD", AccountState(equity=10_000.0), MOMENT,
                          client_with(build_fetcher(macro=False)))
        # Either both found no setup, or the degraded one is not more confident.
        self.assertLessEqual(without.confidence, with_macro.confidence + 1e-9)

    def test_actionable_requires_an_approved_plan(self):
        client = client_with(build_fetcher())
        rec = analyse("XAUUSD", AccountState(equity=10_000.0), MOMENT, client)
        if rec.actionable:
            self.assertIsNotNone(rec.plan)
            self.assertTrue(rec.plan.approved)
            self.assertGreater(rec.plan.lots, 0)
            self.assertGreaterEqual(rec.plan.reward_risk, 2.0)
            self.assertGreaterEqual(rec.confidence, 0.55)

    def test_card_always_states_its_data_sources(self):
        client = client_with(build_fetcher())
        rec = analyse("XAUUSD", AccountState(equity=10_000.0), MOMENT, client)
        self.assertTrue(rec.context.quality.describe())
        self.assertIn("candles 1h", " ".join(rec.context.quality.sources_used))

    def test_no_setup_is_explained_rather_than_left_blank(self):
        """Flat, structureless data should produce a clear 'no trade', not an
        empty card."""
        flat = make_series("XAUUSD", "1h", n=300, start_price=4500.0,
                           drift=0.0, noise=0.02,
                           start=MOMENT - timedelta(hours=300))
        fetcher = build_fetcher()
        fetcher.add("query1.finance.yahoo.com",
                    _yahoo_payload(flat, flat.last.close))
        rec = analyse("XAUUSD", AccountState(equity=10_000.0), MOMENT,
                      client_with(fetcher))
        self.assertTrue(rec.reasons)
        card = rec.render()
        self.assertIn("WHY", card)

    def test_small_account_gets_a_useful_refusal(self):
        client = client_with(build_fetcher())
        rec = analyse("XAUUSD", AccountState(equity=150.0), MOMENT, client)
        if rec.plan is not None and rec.plan.lots == 0:
            self.assertTrue(any("account-size" in b or "minimum" in b
                                for b in rec.blocks))


class TestRequestBudget(unittest.TestCase):
    def test_one_analysis_stays_within_a_sane_request_count(self):
        """Free tiers are metered. An analysis that costs 60 requests would
        exhaust the daily budget in a morning."""
        fetcher = build_fetcher()
        client = HttpClient(fetcher=fetcher, retries=0, cache_ttl=300)
        analyse("XAUUSD", AccountState(equity=10_000.0), MOMENT, client)
        self.assertLess(client.request_count, 25,
                        f"analysis made {client.request_count} requests")


if __name__ == "__main__":
    unittest.main()
