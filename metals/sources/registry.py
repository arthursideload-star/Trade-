"""Catalogue of every data source the metals assistant can draw on.

This is the machine-readable index behind docs/DATENQUELLEN.md. It exists so
that the assistant can answer "where would I get X" and "what is still
missing" without a human going through documentation.

Honesty about tiers matters here: several of these are free only up to a
point, and one silently degrading to stale data at 15:00 UTC on an NFP Friday
is worse than one that fails loudly. Every entry records what breaks and how
it fails.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Category(str, Enum):
    PRICE = "price"                # spot and futures quotes, candles
    MACRO = "macro"                # real yields, dollar, inflation expectations
    POSITIONING = "positioning"    # COT, futures open interest
    PHYSICAL = "physical"          # ETF holdings, warehouse stocks, premiums
    NEWS = "news"                  # headlines and wire copy
    CALENDAR = "calendar"          # scheduled releases
    FUNDAMENTAL = "fundamental"    # supply/demand research


class Auth(str, Enum):
    NONE = "none"                  # no key, no account
    FREE_KEY = "free_key"          # free account, key required
    PAID = "paid"


@dataclass(frozen=True)
class Source:
    key: str
    name: str
    category: Category
    url: str
    auth: Auth
    # What the assistant actually gets from it.
    provides: tuple[str, ...]
    # Free-tier limit in plain words; None where there is no meaningful cap.
    limit: str | None = None
    # How the assistant should treat it when several sources disagree.
    priority: int = 50            # lower number = tried first
    latency: str = "unknown"      # "realtime" | "minutes" | "daily" | "weekly"
    docs: str = ""
    caveat: str = ""
    env_var: str | None = None

    @property
    def needs_key(self) -> bool:
        return self.auth is not Auth.NONE


SOURCES: dict[str, Source] = {}


def _add(src: Source) -> Source:
    SOURCES[src.key] = src
    return src


# ---------------------------------------------------------------------------
# 1. Price and candle data
# ---------------------------------------------------------------------------

_add(Source(
    key="twelvedata",
    name="Twelve Data",
    category=Category.PRICE,
    url="https://api.twelvedata.com",
    auth=Auth.FREE_KEY,
    env_var="TWELVEDATA_API_KEY",
    provides=("XAU/USD candles", "XAG/USD candles", "DXY", "multi-timeframe OHLCV"),
    limit="800 API credits per day, 8 requests per minute on the free tier",
    priority=10,
    latency="realtime",
    docs="https://twelvedata.com/docs",
    caveat=(
        "One multi-timeframe analysis of both metals costs roughly 8-10 "
        "credits, so the daily budget is generous but not unlimited -- cache "
        "aggressively and prefer one large request over several small ones."
    ),
))

_add(Source(
    key="yahoo_chart",
    name="Yahoo Finance chart endpoint",
    category=Category.PRICE,
    url="https://query1.finance.yahoo.com/v8/finance/chart",
    auth=Auth.NONE,
    provides=("GC=F gold futures", "SI=F silver futures", "DX-Y.NYB dollar index",
              "GLD/SLV/GDX", "^TNX yields", "intraday and daily candles"),
    limit="undocumented; polite use only",
    priority=20,
    latency="realtime",
    caveat=(
        "Unofficial and unsupported. It has changed shape before and will "
        "again. Excellent as a free cross-check and as a fallback, but the "
        "assistant must never depend on it alone for a sizing decision."
    ),
))

_add(Source(
    key="stooq",
    name="Stooq CSV",
    category=Category.PRICE,
    url="https://stooq.com/q/d/l/",
    auth=Auth.NONE,
    provides=("XAUUSD daily history", "XAGUSD daily history", "long history, free"),
    limit="no published limit; daily bars only",
    priority=35,
    latency="daily",
    caveat="Daily resolution only. Good for seasonality and regime work, "
           "useless for an intraday entry.",
))

_add(Source(
    key="alphavantage",
    name="Alpha Vantage",
    category=Category.PRICE,
    url="https://www.alphavantage.co/query",
    auth=Auth.FREE_KEY,
    env_var="ALPHAVANTAGE_API_KEY",
    provides=("FX and commodity series", "50+ built-in indicators", "news sentiment"),
    limit="25 requests per day on the free tier",
    priority=40,
    latency="minutes",
    docs="https://www.alphavantage.co/documentation/",
    caveat="25 requests a day is enough for a daily briefing and nothing more. "
           "Reserve it for the one thing it does best rather than candles.",
))

_add(Source(
    key="finnhub",
    name="Finnhub",
    category=Category.PRICE,
    url="https://finnhub.io/api/v1",
    auth=Auth.FREE_KEY,
    env_var="FINNHUB_API_KEY",
    provides=("forex candles", "market news", "economic calendar", "websocket feed"),
    limit="60 requests per minute on the free tier",
    priority=25,
    latency="realtime",
    docs="https://finnhub.io/docs/api",
    caveat="Metals coverage depends on the forex feed and the exact symbol "
           "spelling varies by venue prefix -- resolve the symbol once and "
           "store it rather than guessing per call.",
))

_add(Source(
    key="goldapi_io",
    name="GoldAPI.io",
    category=Category.PRICE,
    url="https://www.goldapi.io/api",
    auth=Auth.FREE_KEY,
    env_var="GOLDAPI_KEY",
    provides=("XAU/XAG spot with bid/ask", "LBMA AM fix history"),
    limit="free tier is request-capped per month",
    priority=45,
    latency="realtime",
    caveat="Spot quote only, no candles. Useful as a price sanity check "
           "against the candle provider.",
))

_add(Source(
    key="metalpriceapi",
    name="MetalpriceAPI",
    category=Category.PRICE,
    url="https://api.metalpriceapi.com/v1",
    auth=Auth.FREE_KEY,
    env_var="METALPRICE_API_KEY",
    provides=("XAU/XAG/XPT/XPD spot", "historical daily", "multi-currency"),
    limit="free tier is request-capped per month",
    priority=48,
    latency="minutes",
))

_add(Source(
    key="gold_api_com",
    name="gold-api.com",
    category=Category.PRICE,
    url="https://api.gold-api.com/price",
    auth=Auth.NONE,
    provides=("XAU spot", "XAG spot"),
    limit="free, no key",
    priority=30,
    latency="minutes",
    caveat="Simplest possible fallback: one number, no history, no bid/ask. "
           "Worth having precisely because it has nothing to go wrong.",
))

# ---------------------------------------------------------------------------
# 2. Macro drivers -- the layer that actually explains gold
# ---------------------------------------------------------------------------

_add(Source(
    key="fred",
    name="FRED (St. Louis Fed)",
    category=Category.MACRO,
    url="https://api.stlouisfed.org/fred/series/observations",
    auth=Auth.FREE_KEY,
    env_var="FRED_API_KEY",
    provides=(
        "DFII10 -- 10y TIPS real yield, the single most important gold driver",
        "DGS10 -- 10y nominal yield",
        "T10YIE -- 10y breakeven inflation",
        "DTWEXBGS -- broad trade-weighted dollar index",
        "VIXCLS -- volatility index",
        "T10Y2Y -- yield curve",
    ),
    limit="free key, generous limits",
    priority=10,
    latency="daily",
    docs="https://fred.stlouisfed.org/docs/api/fred/",
    caveat="Daily frequency and published with a lag. This sets the bias for "
           "the week, not the entry for the hour.",
))

_add(Source(
    key="fred_csv",
    name="FRED public CSV (no key)",
    category=Category.MACRO,
    url="https://fred.stlouisfed.org/graph/fredgraph.csv",
    auth=Auth.NONE,
    provides=("same series as the FRED API, as CSV, without a key",),
    limit="undocumented; intended for chart downloads",
    priority=15,
    latency="daily",
    caveat="Convenient for a first run before a key exists. Move to the "
           "keyed API once the project is past the first week.",
))

# ---------------------------------------------------------------------------
# 3. Positioning
# ---------------------------------------------------------------------------

_add(Source(
    key="cftc_cot",
    name="CFTC Commitments of Traders",
    category=Category.POSITIONING,
    url="https://publicreporting.cftc.gov/resource/6dca-aqww.json",
    auth=Auth.NONE,
    provides=(
        "commercial (producer/merchant) net position in gold and silver",
        "managed money net position",
        "open interest",
    ),
    limit="Socrata open data, free; rate-limited without an app token",
    priority=20,
    latency="weekly",
    docs="https://publicreporting.cftc.gov/",
    caveat=(
        "Published each Friday 15:30 ET for the *prior Tuesday* -- the data "
        "is three days stale the moment it lands. It is a positioning-extreme "
        "signal on a multi-week horizon, never an entry trigger."
    ),
))

# ---------------------------------------------------------------------------
# 4. Physical market
# ---------------------------------------------------------------------------

_add(Source(
    key="wgc_etf",
    name="World Gold Council Goldhub",
    category=Category.PHYSICAL,
    url="https://www.gold.org/goldhub/data/gold-etfs-holdings-and-flows",
    auth=Auth.NONE,
    provides=("global gold ETF holdings in tonnes", "regional flows",
              "central bank net purchases"),
    limit="page-published data, not a documented API",
    priority=40,
    latency="daily",
    caveat="Published as reports and downloads rather than as an API. Treat "
           "as a weekly context read, not an automated feed.",
))

_add(Source(
    key="etf_proxy",
    name="ETF share-count proxy (GLD/SLV via Yahoo)",
    category=Category.PHYSICAL,
    url="https://query1.finance.yahoo.com/v8/finance/chart",
    auth=Auth.NONE,
    provides=("GLD and SLV price and volume as a same-day flow proxy",),
    limit="see yahoo_chart",
    priority=45,
    latency="realtime",
    caveat="Volume is a proxy for flow, not a measurement of it. Directionally "
           "useful, quantitatively not.",
))

_add(Source(
    key="miners_proxy",
    name="Miners as a leading proxy (GDX, HUI)",
    category=Category.PHYSICAL,
    url="https://query1.finance.yahoo.com/v8/finance/chart/GDX",
    auth=Auth.NONE,
    provides=("GDX gold miners ETF", "SIL silver miners ETF"),
    limit="see yahoo_chart",
    priority=50,
    latency="realtime",
    caveat=(
        "Miners are levered to the metal, roughly 2-3x, and their divergence "
        "from spot is sometimes an early signal. They also carry equity-market "
        "beta, so a GDX move during an equity selloff says nothing about gold."
    ),
))

_add(Source(
    key="sge_premium",
    name="Shanghai Gold Exchange premium",
    category=Category.PHYSICAL,
    url="https://www.sge.com.cn/",
    auth=Auth.NONE,
    provides=("SGE benchmark price, convertible to a premium over London spot",),
    limit="published on the exchange site",
    priority=60,
    latency="daily",
    caveat=(
        "Needs a CNY/USD conversion and a grams-to-ounces conversion before it "
        "means anything. A premium of 15-30 USD/oz signals strong Chinese "
        "physical demand; a spike above 100 has historically clustered near "
        "blow-off tops rather than at the start of moves."
    ),
))

# ---------------------------------------------------------------------------
# 5. News
# ---------------------------------------------------------------------------

_add(Source(
    key="kitco_rss",
    name="Kitco News RSS",
    category=Category.NEWS,
    url="https://www.kitco.com/news/category/mining/rss",
    auth=Auth.NONE,
    provides=("precious metals headlines", "mining sector news"),
    limit="free RSS",
    priority=20,
    latency="minutes",
    caveat="Metals-specific and fast. Editorial mixed with wire copy -- the "
           "assistant should weight headlines, not opinion pieces.",
))

_add(Source(
    key="goldseek_rss",
    name="GoldSeek RSS",
    category=Category.NEWS,
    url="https://news.goldseek.com/newsRSS.xml",
    auth=Auth.NONE,
    provides=("gold market headlines and commentary",),
    limit="free RSS",
    priority=35,
    latency="minutes",
    caveat="Heavily commentary-weighted and structurally bullish. Useful for "
           "what the physical market is talking about, not for direction.",
))

_add(Source(
    key="mining_rss",
    name="Mining.com RSS",
    category=Category.NEWS,
    url="https://www.mining.com/feed/",
    auth=Auth.NONE,
    provides=("supply-side news: mine output, strikes, closures",),
    limit="free RSS",
    priority=45,
    latency="minutes",
    caveat="Supply news moves silver more than gold, because silver's "
           "industrial demand makes supply disruption a real price input.",
))

_add(Source(
    key="fed_press_rss",
    name="Federal Reserve press releases RSS",
    category=Category.NEWS,
    url="https://www.federalreserve.gov/feeds/press_all.xml",
    auth=Auth.NONE,
    provides=("FOMC statements", "speeches", "monetary policy releases"),
    limit="free RSS",
    priority=10,
    latency="realtime",
    caveat="The primary source rather than a report about it. Nothing moves "
           "gold faster than a change in rate expectations.",
))

_add(Source(
    key="ecb_rss",
    name="ECB press releases RSS",
    category=Category.NEWS,
    url="https://www.ecb.europa.eu/rss/press.html",
    auth=Auth.NONE,
    provides=("ECB policy statements",),
    limit="free RSS",
    priority=30,
    latency="realtime",
    caveat="Matters via EUR/USD, which is the largest component of the dollar "
           "index, which prices gold.",
))

_add(Source(
    key="gdelt",
    name="GDELT 2.0 document API",
    category=Category.NEWS,
    url="https://api.gdeltproject.org/api/v2/doc/doc",
    auth=Auth.NONE,
    provides=("global news volume and tone by keyword",
              "geopolitical event detection across languages"),
    limit="free, undocumented soft limits",
    priority=25,
    latency="minutes",
    docs="https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/",
    caveat=(
        "This is the source that answers 'has something happened in the world'. "
        "It measures coverage volume and tone, not market impact -- a spike in "
        "coverage is a reason to look, not a reason to trade."
    ),
))

_add(Source(
    key="marketaux",
    name="Marketaux",
    category=Category.NEWS,
    url="https://api.marketaux.com/v1/news/all",
    auth=Auth.FREE_KEY,
    env_var="MARKETAUX_API_KEY",
    provides=("entity-tagged financial news", "directional sentiment"),
    limit="100 requests per day on the free tier",
    priority=40,
    latency="minutes",
))

_add(Source(
    key="newsapi",
    name="NewsAPI.org",
    category=Category.NEWS,
    url="https://newsapi.org/v2/everything",
    auth=Auth.FREE_KEY,
    env_var="NEWSAPI_KEY",
    provides=("broad news search",),
    limit="100 requests per day; free tier is delayed by 24h and "
          "development-use only",
    priority=70,
    latency="daily",
    caveat="The 24-hour delay on the free tier makes it useless for trading "
           "decisions. Listed for completeness, deliberately deprioritised.",
))

# ---------------------------------------------------------------------------
# 6. Economic calendar
# ---------------------------------------------------------------------------

_add(Source(
    key="finnhub_calendar",
    name="Finnhub economic calendar",
    category=Category.CALENDAR,
    url="https://finnhub.io/api/v1/calendar/economic",
    auth=Auth.FREE_KEY,
    env_var="FINNHUB_API_KEY",
    provides=("scheduled releases with impact rating, actual, forecast, prior",),
    limit="shares the Finnhub free-tier quota",
    priority=20,
    latency="daily",
    caveat="Calendar access has moved between tiers before. If it 403s, fall "
           "back to the static high-impact schedule in metals.calendar.",
))

_add(Source(
    key="static_calendar",
    name="Built-in high-impact schedule",
    category=Category.CALENDAR,
    url="(local)",
    auth=Auth.NONE,
    provides=("NFP, CPI, PPI, PCE, FOMC and ECB dates derived from their "
              "published release rules",),
    limit="none -- computed locally",
    priority=15,
    latency="realtime",
    caveat=(
        "Computed from the publication rules (NFP on the first Friday, FOMC on "
        "its published schedule) rather than fetched. It cannot know about a "
        "surprise emergency meeting, which is exactly when it matters most -- "
        "so it is a floor under the news veto, not a replacement for a feed."
    ),
))

# ---------------------------------------------------------------------------
# 7. Fundamentals and research
# ---------------------------------------------------------------------------

_add(Source(
    key="wgc_demand",
    name="World Gold Council Gold Demand Trends",
    category=Category.FUNDAMENTAL,
    url="https://www.gold.org/goldhub/research",
    auth=Auth.NONE,
    provides=("quarterly supply and demand by segment",
              "central bank purchase totals"),
    limit="quarterly publication",
    priority=60,
    latency="quarterly",
    caveat="Quarterly and backward-looking. Sets the structural frame for the "
           "year; irrelevant to this afternoon.",
))

_add(Source(
    key="silver_institute",
    name="The Silver Institute World Silver Survey",
    category=Category.FUNDAMENTAL,
    url="https://silverinstitute.org/",
    auth=Auth.NONE,
    provides=("annual silver supply/demand balance",
              "industrial demand by sector: solar, electronics, EV"),
    limit="annual publication",
    priority=65,
    latency="annual",
    caveat="The authority on silver's structural deficit, which is the single "
           "biggest difference between silver and gold as instruments.",
))

_add(Source(
    key="lbma",
    name="LBMA precious metal prices",
    category=Category.FUNDAMENTAL,
    url="https://www.lbma.org.uk/prices-and-data/lbma-precious-metal-prices",
    auth=Auth.PAID,
    provides=("official twice-daily auction benchmark for gold, "
              "once-daily for silver"),
    limit="historical tables require an IBA licence",
    priority=80,
    latency="daily",
    caveat="The benchmark itself is public; the historical series behind it is "
           "licensed. Third-party APIs redistribute it -- check their terms "
           "before relying on it commercially.",
))


# --- Query helpers ----------------------------------------------------------

def by_category(category: Category) -> list[Source]:
    return sorted(
        (s for s in SOURCES.values() if s.category is category),
        key=lambda s: s.priority,
    )


def keyless() -> list[Source]:
    """Sources usable before the user has registered for anything."""
    return sorted(
        (s for s in SOURCES.values() if s.auth is Auth.NONE),
        key=lambda s: s.priority,
    )


def required_env_vars() -> dict[str, list[str]]:
    """Map each env var to the sources that unlock when it is set."""
    out: dict[str, list[str]] = {}
    for s in SOURCES.values():
        if s.env_var:
            out.setdefault(s.env_var, []).append(s.name)
    return out


def coverage_report(available_env: dict[str, str]) -> dict[str, object]:
    """What the assistant can and cannot see with the keys currently present."""
    active, blocked = [], []
    for s in sorted(SOURCES.values(), key=lambda x: (x.category.value, x.priority)):
        if s.auth is Auth.NONE:
            active.append(s)
        elif s.env_var and available_env.get(s.env_var):
            active.append(s)
        else:
            blocked.append(s)

    covered = {s.category for s in active}
    missing = [c for c in Category if c not in covered]
    return {
        "active": [s.key for s in active],
        "blocked": [(s.key, s.env_var) for s in blocked],
        "categories_covered": sorted(c.value for c in covered),
        "categories_missing": sorted(c.value for c in missing),
    }
