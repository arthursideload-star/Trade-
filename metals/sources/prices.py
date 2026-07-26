"""Price and candle providers with an automatic fallback chain.

Every provider function returns a CandleSeries or a Quote so the caller never
learns which one answered. `fetch_candles` walks the chain in priority order
and reports which source won, so the recommendation card can cite its data.
"""

from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from ..candles import CandleSeries, build_series, normalise_timeframe
from ..specs import get_spec
from .http import FetchError, HttpClient, try_sources


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    bid: float | None
    ask: float | None
    ts: datetime
    source: str

    @property
    def spread(self) -> float | None:
        if self.bid is not None and self.ask is not None:
            return self.ask - self.bid
        return None


# --- Symbol translation -----------------------------------------------------
#
# Every provider spells gold differently. Resolving this in one table beats
# discovering it one 404 at a time.

SYMBOL_MAP: dict[str, dict[str, str]] = {
    "twelvedata": {"XAUUSD": "XAU/USD", "XAGUSD": "XAG/USD"},
    "yahoo_chart": {"XAUUSD": "GC=F", "XAGUSD": "SI=F"},
    "stooq": {"XAUUSD": "xauusd", "XAGUSD": "xagusd"},
    "alphavantage": {"XAUUSD": "XAU", "XAGUSD": "XAG"},
    "finnhub": {"XAUUSD": "OANDA:XAU_USD", "XAGUSD": "OANDA:XAG_USD"},
    "goldapi_io": {"XAUUSD": "XAU", "XAGUSD": "XAG"},
    "gold_api_com": {"XAUUSD": "XAU", "XAGUSD": "XAG"},
}

TWELVEDATA_INTERVAL = {
    "1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
    "1h": "1h", "4h": "4h", "1d": "1day", "1w": "1week",
}

YAHOO_INTERVAL = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "4h": "1h", "1d": "1d", "1w": "1wk",
}

# Yahoo caps intraday history by interval; asking for more returns an error.
YAHOO_RANGE = {
    "1m": "5d", "5m": "1mo", "15m": "1mo", "30m": "1mo",
    "1h": "2y", "4h": "2y", "1d": "5y", "1w": "10y",
}


def _resolve(provider: str, symbol: str) -> str:
    canonical = get_spec(symbol).symbol
    mapping = SYMBOL_MAP.get(provider, {})
    if canonical not in mapping:
        raise FetchError(provider, f"{provider} has no mapping for {canonical}")
    return mapping[canonical]


# --- Providers: candles -----------------------------------------------------

def twelvedata_candles(client: HttpClient, symbol: str, timeframe: str,
                       limit: int = 300, api_key: str | None = None) -> CandleSeries:
    key = api_key or os.environ.get("TWELVEDATA_API_KEY")
    if not key:
        raise FetchError("twelvedata", "TWELVEDATA_API_KEY is not set")
    tf = normalise_timeframe(timeframe)
    data = client.get_json(
        "https://api.twelvedata.com/time_series",
        params={
            "symbol": _resolve("twelvedata", symbol),
            "interval": TWELVEDATA_INTERVAL[tf],
            "outputsize": limit,
            "apikey": key,
            "format": "JSON",
            "timezone": "UTC",
        },
    )
    if isinstance(data, dict) and data.get("status") == "error":
        raise FetchError("twelvedata", str(data.get("message", "error")))
    values = data.get("values") if isinstance(data, dict) else None
    if not values:
        raise FetchError("twelvedata", "no values in response")
    return build_series(
        get_spec(symbol).symbol, tf,
        [
            {"ts": v["datetime"], "open": v["open"], "high": v["high"],
             "low": v["low"], "close": v["close"], "volume": v.get("volume")}
            for v in values
        ],
        source="twelvedata",
    )


def yahoo_candles(client: HttpClient, symbol: str, timeframe: str,
                  limit: int = 300) -> CandleSeries:
    tf = normalise_timeframe(timeframe)
    ticker = _resolve("yahoo_chart", symbol)
    data = client.get_json(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
        params={"interval": YAHOO_INTERVAL[tf], "range": YAHOO_RANGE[tf]},
    )
    try:
        result = data["chart"]["result"][0]
        stamps = result["timestamp"]
        q = result["indicators"]["quote"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise FetchError("yahoo_chart", f"unexpected response shape: {exc}") from exc

    rows = []
    for i, ts in enumerate(stamps):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue  # Yahoo pads gaps with nulls
        rows.append({"ts": ts, "open": o, "high": h, "low": l, "close": c,
                     "volume": (q.get("volume") or [None] * len(stamps))[i]})

    series = build_series(get_spec(symbol).symbol, tf, rows, source="yahoo_chart")
    if tf == "4h":
        series = resample(series, "4h")
    return series.tail(limit)


def stooq_candles(client: HttpClient, symbol: str,
                  timeframe: str = "1d", limit: int = 500) -> CandleSeries:
    tf = normalise_timeframe(timeframe)
    if tf != "1d":
        raise FetchError("stooq", "stooq provides daily bars only")
    text = client.get_text(
        "https://stooq.com/q/d/l/",
        params={"s": _resolve("stooq", symbol), "i": "d"},
        cache_ttl=3600,
    )
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for r in reader:
        if not r.get("Date") or r.get("Close") in (None, "", "N/D"):
            continue
        rows.append({"ts": r["Date"], "open": r["Open"], "high": r["High"],
                     "low": r["Low"], "close": r["Close"],
                     "volume": r.get("Volume")})
    if not rows:
        raise FetchError("stooq", "empty CSV")
    return build_series(get_spec(symbol).symbol, tf, rows,
                        source="stooq").tail(limit)


def finnhub_candles(client: HttpClient, symbol: str, timeframe: str,
                    limit: int = 300, api_key: str | None = None) -> CandleSeries:
    key = api_key or os.environ.get("FINNHUB_API_KEY")
    if not key:
        raise FetchError("finnhub", "FINNHUB_API_KEY is not set")
    tf = normalise_timeframe(timeframe)
    resolution = {"1m": "1", "5m": "5", "15m": "15", "30m": "30",
                  "1h": "60", "4h": "60", "1d": "D", "1w": "W"}[tf]
    now = int(datetime.now(timezone.utc).timestamp())
    from ..candles import TIMEFRAME_SECONDS
    span = TIMEFRAME_SECONDS[tf] * limit * 3  # slack for weekends and the daily break
    data = client.get_json(
        "https://finnhub.io/api/v1/forex/candle",
        params={"symbol": _resolve("finnhub", symbol), "resolution": resolution,
                "from": now - span, "to": now, "token": key},
    )
    if data.get("s") != "ok":
        raise FetchError("finnhub", f"status {data.get('s')!r}")
    rows = [
        {"ts": t, "open": o, "high": h, "low": l, "close": c, "volume": v}
        for t, o, h, l, c, v in zip(
            data["t"], data["o"], data["h"], data["l"], data["c"],
            data.get("v") or [None] * len(data["t"]),
        )
    ]
    series = build_series(get_spec(symbol).symbol, tf, rows, source="finnhub")
    if tf == "4h":
        series = resample(series, "4h")
    return series.tail(limit)


# --- Providers: spot quote --------------------------------------------------

def gold_api_com_quote(client: HttpClient, symbol: str) -> Quote:
    metal = _resolve("gold_api_com", symbol)
    data = client.get_json(f"https://api.gold-api.com/price/{metal}", cache_ttl=30)
    price = data.get("price")
    if price is None:
        raise FetchError("gold_api_com", "no price in response")
    return Quote(get_spec(symbol).symbol, float(price), None, None,
                 datetime.now(timezone.utc), "gold_api_com")


def goldapi_io_quote(client: HttpClient, symbol: str,
                     api_key: str | None = None) -> Quote:
    key = api_key or os.environ.get("GOLDAPI_KEY")
    if not key:
        raise FetchError("goldapi_io", "GOLDAPI_KEY is not set")
    metal = _resolve("goldapi_io", symbol)
    data = client.get_json(
        f"https://www.goldapi.io/api/{metal}/USD",
        headers={"x-access-token": key, "Content-Type": "application/json"},
        cache_ttl=30,
    )
    price = data.get("price")
    if price is None:
        raise FetchError("goldapi_io", "no price in response")
    ts = data.get("timestamp")
    return Quote(
        get_spec(symbol).symbol, float(price),
        _opt_float(data.get("bid")), _opt_float(data.get("ask")),
        datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc),
        "goldapi_io",
    )


def yahoo_quote(client: HttpClient, symbol: str) -> Quote:
    ticker = _resolve("yahoo_chart", symbol)
    data = client.get_json(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
        params={"interval": "1m", "range": "1d"}, cache_ttl=30,
    )
    try:
        meta = data["chart"]["result"][0]["meta"]
    except (KeyError, IndexError, TypeError) as exc:
        raise FetchError("yahoo_chart", f"unexpected response shape: {exc}") from exc
    price = meta.get("regularMarketPrice")
    if price is None:
        raise FetchError("yahoo_chart", "no regularMarketPrice")
    ts = meta.get("regularMarketTime")
    return Quote(
        get_spec(symbol).symbol, float(price), None, None,
        datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc),
        "yahoo_chart",
    )


# --- Fallback orchestration -------------------------------------------------

@dataclass
class FetchResult:
    series: CandleSeries
    source: str
    failures: list[tuple[str, str]]

    @property
    def degraded(self) -> bool:
        """True when the preferred source failed and a fallback answered."""
        return bool(self.failures)

    def provenance(self) -> str:
        note = f"data: {self.source}"
        if self.failures:
            note += " (fallback; " + ", ".join(n for n, _ in self.failures) + " unavailable)"
        return note


def fetch_candles(symbol: str, timeframe: str, limit: int = 300,
                  client: HttpClient | None = None) -> FetchResult:
    """Fetch candles from the best available provider.

    Order is deliberate: a keyed provider built for this purpose first, then
    the free unofficial one, then daily-only history as a last resort. The
    caller is told which one answered so the recommendation can be honest
    about its inputs.
    """
    client = client or HttpClient()
    tf = normalise_timeframe(timeframe)

    attempts: list[tuple[str, object]] = []
    if os.environ.get("TWELVEDATA_API_KEY"):
        attempts.append(("twelvedata",
                         lambda: twelvedata_candles(client, symbol, tf, limit)))
    if os.environ.get("FINNHUB_API_KEY"):
        attempts.append(("finnhub",
                         lambda: finnhub_candles(client, symbol, tf, limit)))
    attempts.append(("yahoo_chart", lambda: yahoo_candles(client, symbol, tf, limit)))
    if tf == "1d":
        attempts.append(("stooq", lambda: stooq_candles(client, symbol, tf, limit)))

    series, source, failures = try_sources(attempts)  # type: ignore[arg-type]
    return FetchResult(series, source, failures)


def fetch_quote(symbol: str, client: HttpClient | None = None) -> Quote:
    """Current spot, from whichever source answers first."""
    client = client or HttpClient()
    attempts: list[tuple[str, object]] = []
    if os.environ.get("GOLDAPI_KEY"):
        attempts.append(("goldapi_io", lambda: goldapi_io_quote(client, symbol)))
    attempts.append(("gold_api_com", lambda: gold_api_com_quote(client, symbol)))
    attempts.append(("yahoo_chart", lambda: yahoo_quote(client, symbol)))
    quote, _, _ = try_sources(attempts)  # type: ignore[arg-type]
    return quote


def cross_check(quotes: list[Quote], tolerance_pct: float = 0.5
                ) -> tuple[bool, str]:
    """Compare independent price sources before trusting either.

    A feed that is stale or quoting a different contract month will disagree
    with the others by more than the market's own spread. Catching that before
    sizing a position is cheap; catching it afterwards is not.
    """
    prices = [q.price for q in quotes if q.price > 0]
    if len(prices) < 2:
        return True, "only one source available -- no cross-check possible"
    lo, hi = min(prices), max(prices)
    spread_pct = (hi - lo) / lo * 100.0
    if spread_pct > tolerance_pct:
        detail = ", ".join(f"{q.source}={q.price:g}" for q in quotes)
        return False, (
            f"sources disagree by {spread_pct:.2f}% ({detail}). Spot and "
            f"futures legitimately differ by the basis, but a gap this wide "
            f"usually means one feed is stale or quoting a different contract."
        )
    return True, f"sources agree within {spread_pct:.2f}%"


# --- Resampling -------------------------------------------------------------

def resample(series: CandleSeries, target: str) -> CandleSeries:
    """Aggregate candles up to a higher timeframe.

    Needed because several free providers offer 1h but not 4h. Buckets are
    anchored to 00:00 UTC, which is the convention MT5 uses for H4 on a
    UTC server -- a broker on a different server time will bucket
    differently, and the resulting levels will not match the user's chart.
    That mismatch is worth knowing about, so it is stated here rather than
    hidden.
    """
    from ..candles import Candle, TIMEFRAME_SECONDS

    tf = normalise_timeframe(target)
    step = TIMEFRAME_SECONDS[tf]
    src_step = TIMEFRAME_SECONDS[series.timeframe]
    if step <= src_step:
        return series

    buckets: dict[int, list[Candle]] = {}
    for c in series:
        key = int(c.ts.timestamp()) // step * step
        buckets.setdefault(key, []).append(c)

    out: list[Candle] = []
    for key in sorted(buckets):
        group = buckets[key]
        vols = [c.volume for c in group if c.volume is not None]
        out.append(Candle(
            ts=datetime.fromtimestamp(key, tz=timezone.utc),
            open=group[0].open,
            high=max(c.high for c in group),
            low=min(c.low for c in group),
            close=group[-1].close,
            volume=sum(vols) if vols else None,
        ))
    return CandleSeries(series.symbol, tf, out, f"{series.source}+resampled")


def _opt_float(value) -> float | None:  # type: ignore[no-untyped-def]
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None
