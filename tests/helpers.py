"""Shared test fixtures: synthetic candles and a fake HTTP layer.

Every test in this suite runs offline. The HTTP fetcher is replaced with a
dict lookup so the parsing and interpretation logic is exercised against
recorded payload shapes without touching the network.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from metals.candles import Candle, CandleSeries
from metals.sources.http import FetchError, HttpClient

UTC = timezone.utc


def make_series(
    symbol: str = "XAUUSD",
    timeframe: str = "1h",
    n: int = 200,
    start_price: float = 4500.0,
    drift: float = 0.0,
    noise: float = 3.0,
    start: datetime | None = None,
    seed: int = 7,
) -> CandleSeries:
    """Deterministic pseudo-random candles with a controllable drift.

    Uses a simple LCG rather than `random` so the sequence is stable across
    Python versions and does not depend on global state.
    """
    start = start or datetime(2026, 7, 1, 0, 0, tzinfo=UTC)
    step = {"5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}[timeframe]

    state = seed
    def rnd() -> float:
        nonlocal state
        state = (1103515245 * state + 12345) % (2 ** 31)
        return state / (2 ** 31) - 0.5

    candles: list[Candle] = []
    price = start_price
    for i in range(n):
        price += drift + rnd() * noise
        o = price
        c = price + rnd() * noise
        h = max(o, c) + abs(rnd()) * noise * 0.8
        l = min(o, c) - abs(rnd()) * noise * 0.8
        candles.append(Candle(
            ts=start + timedelta(minutes=step * i),
            open=round(o, 2), high=round(h, 2),
            low=round(l, 2), close=round(c, 2),
            volume=1000 + abs(rnd()) * 500,
        ))
        price = c
    return CandleSeries(symbol, timeframe, candles, source="synthetic")


def series_from_ohlc(rows: list[tuple[float, float, float, float]],
                     symbol: str = "XAUUSD", timeframe: str = "1h",
                     start: datetime | None = None) -> CandleSeries:
    """Build an exact series from hand-written OHLC values.

    Used wherever a test needs a specific shape rather than plausible noise.
    """
    start = start or datetime(2026, 7, 1, 0, 0, tzinfo=UTC)
    step = {"5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}[timeframe]
    candles = [
        Candle(ts=start + timedelta(minutes=step * i),
               open=o, high=h, low=l, close=c, volume=1000.0)
        for i, (o, h, l, c) in enumerate(rows)
    ]
    return CandleSeries(symbol, timeframe, candles, source="handmade")


class FakeFetcher:
    """Fetcher stub. Matches by substring so query params do not matter."""

    def __init__(self, routes: dict[str, bytes | Exception] | None = None):
        self.routes = routes or {}
        self.calls: list[str] = []

    def add(self, needle: str, payload) -> "FakeFetcher":
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload).encode()
        elif isinstance(payload, str):
            payload = payload.encode()
        self.routes[needle] = payload
        return self

    def fail(self, needle: str, reason: str = "boom") -> "FakeFetcher":
        self.routes[needle] = FetchError(needle, reason)
        return self

    def __call__(self, url: str, *, headers=None, timeout=None) -> bytes:
        self.calls.append(url)
        for needle, payload in self.routes.items():
            if needle in url:
                if isinstance(payload, Exception):
                    raise payload
                return payload
        raise FetchError(url, "no route registered in FakeFetcher")


def fake_client(routes: dict | None = None, **kwargs) -> tuple[HttpClient, FakeFetcher]:
    fetcher = FakeFetcher(routes)
    client = HttpClient(fetcher=fetcher, retries=0, cache_ttl=0, **kwargs)
    return client, fetcher


# --- Recorded payload shapes ------------------------------------------------

TWELVEDATA_OK = {
    "meta": {"symbol": "XAU/USD", "interval": "1h", "currency": "USD"},
    "values": [
        {"datetime": "2026-07-26 12:00:00", "open": "4500.10", "high": "4508.40",
         "low": "4498.20", "close": "4506.30", "volume": "1200"},
        {"datetime": "2026-07-26 11:00:00", "open": "4495.00", "high": "4502.00",
         "low": "4492.10", "close": "4500.10", "volume": "1100"},
        {"datetime": "2026-07-26 10:00:00", "open": "4490.00", "high": "4497.50",
         "low": "4487.00", "close": "4495.00", "volume": "900"},
    ],
    "status": "ok",
}

TWELVEDATA_ERROR = {
    "code": 429,
    "message": "You have run out of API credits for the current minute.",
    "status": "error",
}

YAHOO_OK = {
    "chart": {
        "result": [{
            "meta": {"symbol": "GC=F", "regularMarketPrice": 4506.3,
                     "regularMarketTime": 1785000000},
            "timestamp": [1784989200, 1784992800, 1784996400],
            "indicators": {"quote": [{
                "open": [4490.0, 4495.0, 4500.1],
                "high": [4497.5, 4502.0, 4508.4],
                "low": [4487.0, 4492.1, 4498.2],
                "close": [4495.0, 4500.1, 4506.3],
                "volume": [900, 1100, 1200],
            }]},
        }],
        "error": None,
    }
}

YAHOO_WITH_NULLS = {
    "chart": {
        "result": [{
            "meta": {"symbol": "GC=F", "regularMarketPrice": 4506.3,
                     "regularMarketTime": 1785000000},
            "timestamp": [1784989200, 1784992800, 1784996400],
            "indicators": {"quote": [{
                "open": [4490.0, None, 4500.1],
                "high": [4497.5, None, 4508.4],
                "low": [4487.0, None, 4498.2],
                "close": [4495.0, None, 4506.3],
                "volume": [900, None, 1200],
            }]},
        }],
        "error": None,
    }
}

STOOQ_CSV = (
    "Date,Open,High,Low,Close,Volume\n"
    "2026-07-23,4470.00,4489.00,4462.00,4485.00,0\n"
    "2026-07-24,4485.00,4499.00,4478.00,4492.00,0\n"
    "2026-07-25,4492.00,4510.00,4488.00,4506.00,0\n"
)

FRED_CSV = (
    "observation_date,DFII10\n"
    "2026-06-01,2.10\n"
    "2026-06-15,.\n"
    "2026-07-01,1.95\n"
    "2026-07-20,1.82\n"
)

CFTC_ROWS = [
    {
        "report_date_as_yyyy_mm_dd": f"2026-{m:02d}-{d:02d}T00:00:00.000",
        "prod_merc_positions_long_all": "120000",
        "prod_merc_positions_short_all": str(300000 + i * 2000),
        "m_money_positions_long_all": str(150000 + i * 3000),
        "m_money_positions_short_all": "40000",
        "open_interest_all": "500000",
    }
    for i, (m, d) in enumerate(
        [(1, 6), (1, 13), (1, 20), (1, 27), (2, 3), (2, 10), (2, 17), (2, 24),
         (3, 3), (3, 10), (3, 17), (3, 24), (3, 31), (4, 7), (4, 14), (4, 21),
         (4, 28), (5, 5), (5, 12), (5, 19), (5, 26), (6, 2), (6, 9), (6, 16),
         (6, 23), (6, 30), (7, 7), (7, 14), (7, 21)]
    )
]

RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Fed holds rates steady, Powell signals patience on cuts</title>
      <link>https://example.invalid/a</link>
      <pubDate>Sun, 26 Jul 2026 12:00:00 +0000</pubDate>
      <description>The FOMC left the federal funds rate unchanged.</description>
    </item>
    <item>
      <title>Gold miners report higher output in Q2</title>
      <link>https://example.invalid/b</link>
      <pubDate>Sun, 26 Jul 2026 09:30:00 +0000</pubDate>
      <description>Production rose across major producers.</description>
    </item>
    <item>
      <title>Ceasefire agreed, risk appetite returns to markets</title>
      <link>https://example.invalid/c</link>
      <pubDate>Sun, 26 Jul 2026 08:00:00 +0000</pubDate>
      <description>Equities rallied on the news.</description>
    </item>
  </channel>
</rss>
"""

ATOM_SAMPLE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Test</title>
  <entry>
    <title>CPI comes in hotter than expected</title>
    <link href="https://example.invalid/atom1"/>
    <updated>2026-07-26T13:30:00Z</updated>
    <summary>Consumer prices rose more than forecast.</summary>
  </entry>
</feed>
"""

GDELT_OK = {
    "articles": [
        {"title": "Central bank buying lifts gold demand",
         "url": "https://example.invalid/g1",
         "domain": "example.invalid",
         "seendate": "20260726T110000Z"},
    ]
}

FINNHUB_CALENDAR = {
    "economicCalendar": [
        {"event": "Non-Farm Payrolls", "time": "2026-08-07 12:30:00",
         "impact": "high", "country": "US"},
        {"event": "Initial Jobless Claims", "time": "2026-07-30 12:30:00",
         "impact": "medium", "country": "US"},
    ]
}

WORLDMONITOR_COMMODITIES = {
    "quotes": [
        {"symbol": "GC=F", "name": "Gold", "price": 4051.8, "change": -0.42,
         "display": "4,051.80"},
        {"symbol": "SI=F", "name": "Silver", "price": 52.14, "change": 0.31},
        {"symbol": "CL=F", "name": "Crude Oil", "price": 71.05, "change": 1.2},
    ]
}

WORLDMONITOR_CALENDAR = {
    "events": [
        {"date": "2026-08-07", "event": "Nonfarm Payrolls", "country": "US",
         "actual": "", "estimate": "150K"},
        {"date": "2026-08-12", "event": "CPI", "country": "US",
         "actual": "", "estimate": "2.6%"},
        {"date": "2026-09-16", "event": "FOMC Rate Decision", "country": "US"},
        {"date": "2026-08-03", "event": "EU HICP (CPI)", "country": "EU"},
    ],
    "fromDate": "2026-08-01",
    "toDate": "2026-09-30",
    "total": 4,
}

WORLDMONITOR_CALENDAR_COLD = {
    "events": [], "fromDate": "", "toDate": "", "total": 0,
    "unavailable": True,
}

WORLDMONITOR_ECB_FX = {
    "rates": [
        {"currency": "USD", "rate": 1.1632},
        {"currency": "GBP", "rate": 0.8571},
        {"currency": "CHF", "rate": 0.9284},
    ],
    "date": "2026-07-31",
}
