"""World Monitor as a data source.

World Monitor (worldmonitor.app, AGPL-3.0-only, by Elie Habib) aggregates 65+
providers behind one REST API. The full source sits on its own branch of this
repository; this module talks to the **network API** instead of importing any
of it, for three reasons that are worth stating rather than assuming:

* It is a TypeScript/Vercel/Convex application. Nothing in it runs in this
  Python package, which is standard-library only and installs nowhere.
* AGPL-3.0 copyleft attaches to a combined work. Calling a public HTTP API
  over the network does not create one; vendoring and linking the source
  would raise a question this project has no reason to raise.
* 5,055 files of a web app in a trading repository is the exact thing the
  audit exists to catch.

What that buys, and what it does not
------------------------------------
Read this before wiring anything to it. The endpoints below are genuinely
useful for **context** and useless for **execution**:

* `list-commodity-quotes` returns `{symbol, name, price, change}` from Yahoo
  Finance. No bid, no ask, no day high, no day low, no intraday bars. So it
  can tell you roughly where gold is; it **cannot** supply `--price/--high/
  --low/--spread` for a paper session. After A19 that matters: the spread
  decides the sign of the expectancy and this endpoint does not have one.
  It is also a futures quote (GC=F), not spot, and the two differ by carry.
* `get-economic-calendar` returns events dated to the **day**, with no time
  of day. R4 blocks 30 minutes around a release *time*, so this cannot drive
  R4 directly. It can say "today is a CPI day", which is worth knowing.
* `get-cot-positioning`, `get-ecb-fx-rates` and `get-fred-series` overlap
  with sources this package already has (`cot.py`, `macro.py`). Their value
  here is as a second opinion when the primary is down, not as a new fact.

Every call needs an API key (`WORLDMONITOR_API_KEY`), sent as
`X-WorldMonitor-Key`. There is no anonymous tier for the REST API.

Not verified live
-----------------
The container this was written in reaches worldmonitor.app through a proxy
that returns 403 for every host outside its allowlist, so **no call in this
module has been executed against the real service.** The parsing is written
against the published OpenAPI schemas and the handler source, and is tested
against recorded payload shapes offline. Treat the first live run as the
actual test, and expect field names to be the thing that is wrong.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timezone

from .http import FetchError, HttpClient

BASE_URL = "https://api.worldmonitor.app"
API_KEY_ENV = "WORLDMONITOR_API_KEY"
KEY_HEADER = "X-WorldMonitor-Key"

# Yahoo's symbol for the front-month COMEX gold future. Not spot: the future
# trades at a carry premium to spot that widens with rates and time to expiry,
# so this is a sanity check on the spot quote, never a substitute for one.
GOLD_FUTURES_SYMBOL = "GC=F"
SILVER_FUTURES_SYMBOL = "SI=F"

# Calendar rows carry a date and no clock time. Where the release has a
# published, fixed publication time, it is known here rather than guessed
# from the feed -- and where it is not, the day is reported without one.
# ET/CET conversion is deliberately left to metals.sources.calendar, which
# already owns the daylight-saving rules.
KNOWN_RELEASE_TIMES_ET: dict[str, tuple[int, int]] = {
    "CPI": (8, 30),
    "Nonfarm Payrolls": (8, 30),
    "PCE": (8, 30),
    "Retail Sales": (8, 30),
    "GDP": (8, 30),
}


@dataclass(frozen=True)
class CommodityQuote:
    symbol: str
    name: str
    price: float
    change_pct: float | None = None

    @property
    def is_gold(self) -> bool:
        return self.symbol.upper().startswith(("GC", "XAU"))


@dataclass(frozen=True)
class EconomicDay:
    """One calendar row. Dated to the day, because that is all it has.

    `release_time_et` is filled only for releases whose publication time is
    published and fixed. It stays None otherwise, and a None here must never
    be turned into a default time -- a blackout aimed at the wrong half-hour
    is worse than no blackout, because it looks like protection.
    """

    day: date
    event: str
    country: str = ""
    actual: str = ""
    estimate: str = ""
    release_time_et: tuple[int, int] | None = None

    @property
    def has_a_time(self) -> bool:
        return self.release_time_et is not None


def api_key(explicit: str | None = None) -> str:
    key = explicit or os.environ.get(API_KEY_ENV)
    if not key:
        raise FetchError(BASE_URL, f"{API_KEY_ENV} is not set")
    return key


def _get(client: HttpClient, path: str, params: dict | None = None,
         key: str | None = None, cache_ttl: float = 300.0):
    return client.get_json(f"{BASE_URL}{path}", params=params,
                           headers={KEY_HEADER: api_key(key)},
                           cache_ttl=cache_ttl)


def _as_float(value) -> float | None:  # type: ignore[no-untyped-def]
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def commodity_quotes(client: HttpClient, symbols: tuple[str, ...] = (),
                     api_key_value: str | None = None) -> list[CommodityQuote]:
    """Commodity prices. Price only -- see the module docstring."""
    params = {"symbols": list(symbols)} if symbols else None
    data = _get(client, "/api/market/v1/list-commodity-quotes", params,
                api_key_value)
    rows = data.get("quotes") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise FetchError(BASE_URL, "no quotes array in response")

    out: list[CommodityQuote] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        price = _as_float(r.get("price"))
        symbol = str(r.get("symbol") or "").strip()
        if price is None or not symbol:
            continue
        out.append(CommodityQuote(
            symbol=symbol,
            name=str(r.get("name") or symbol),
            price=price,
            change_pct=_as_float(r.get("change")),
        ))
    return out


def gold_quote(client: HttpClient, api_key_value: str | None = None
               ) -> CommodityQuote:
    """The gold future, as a cross-check against the spot quote.

    Raises rather than returning None: a caller asking for gold and getting
    silence would carry on with whatever it had, which is how a stale price
    reaches a ledger row.
    """
    quotes = commodity_quotes(client, (GOLD_FUTURES_SYMBOL,), api_key_value)
    for q in quotes:
        if q.is_gold:
            return q
    raise FetchError(BASE_URL, f"no gold quote in response for "
                               f"{GOLD_FUTURES_SYMBOL}")


def economic_calendar(client: HttpClient, api_key_value: str | None = None
                      ) -> list[EconomicDay]:
    """Scheduled releases, dated to the day.

    The handler serves a cached seed and answers `{"unavailable": true}` when
    the cache is cold. That is reported as a failure rather than as an empty
    calendar: "nothing scheduled" and "I could not look" are the distinction
    A20 was built on.
    """
    data = _get(client, "/api/economic/v1/get-economic-calendar",
                key=api_key_value, cache_ttl=1800.0)
    if not isinstance(data, dict):
        raise FetchError(BASE_URL, "calendar response is not an object")
    if data.get("unavailable"):
        raise FetchError(BASE_URL, "calendar cache is cold (unavailable=true) "
                                   "-- this is not an empty calendar")
    rows = data.get("events")
    if not isinstance(rows, list):
        raise FetchError(BASE_URL, "no events array in response")

    out: list[EconomicDay] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        day = _parse_day(r.get("date"))
        event = str(r.get("event") or "").strip()
        if day is None or not event:
            continue
        out.append(EconomicDay(
            day=day,
            event=event,
            country=str(r.get("country") or ""),
            actual=str(r.get("actual") or ""),
            estimate=str(r.get("estimate") or ""),
            release_time_et=_known_time(event),
        ))
    return sorted(out, key=lambda e: (e.day, e.event))


def high_impact_days(events: list[EconomicDay]) -> set[date]:
    """Days carrying at least one release this project treats as high impact.

    Coarser than R4 by design. R4 needs a minute; this knows a day. Used to
    answer "should this session run at all", not "stand aside now".
    """
    return {e.day for e in events if _known_time(e.event) is not None
            or "FOMC" in e.event.upper() or "ECB" in e.event.upper()}


def eur_usd(client: HttpClient, api_key_value: str | None = None) -> float:
    """The ECB reference rate for EUR/USD.

    Every euro figure in the paper chain is a USD result divided by a rate
    that is currently a constant. This is the endpoint that could replace
    that constant with a reading.
    """
    data = _get(client, "/api/economic/v1/get-ecb-fx-rates",
                key=api_key_value, cache_ttl=3600.0)
    rate = _find_usd_rate(data)
    if rate is None:
        raise FetchError(BASE_URL, "no USD rate in the ECB FX response")
    return rate


def _find_usd_rate(data) -> float | None:  # type: ignore[no-untyped-def]
    """Pull USD out of whatever shape the response uses.

    Written defensively on purpose: this is the one function here whose
    payload shape could not be pinned down from the OpenAPI example, and a
    wrong FX rate silently rescales every euro number in the journal.
    """
    if isinstance(data, dict):
        for key in ("rates", "data", "fxRates"):
            inner = data.get(key)
            rate = _find_usd_rate(inner)
            if rate is not None:
                return rate
        if str(data.get("currency") or data.get("code") or "").upper() == "USD":
            return _as_float(data.get("rate") or data.get("value"))
        direct = data.get("USD")
        value = _as_float(direct)
        if value is not None:
            return value
    elif isinstance(data, list):
        for item in data:
            rate = _find_usd_rate(item)
            if rate is not None:
                return rate
    return None


def _parse_day(value) -> date | None:  # type: ignore[no-untyped-def]
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(
            timezone.utc).date()
    except ValueError:
        return None


def _known_time(event: str) -> tuple[int, int] | None:
    lowered = event.lower()
    for name, when in KNOWN_RELEASE_TIMES_ET.items():
        if name.lower() in lowered:
            return when
    return None


# --- What this source can honestly be used for ------------------------------

CAPABILITIES: dict[str, str] = {
    "gold price": "yes, but the front-month future (GC=F), not spot, and "
                  "without bid/ask or a day range",
    "spread": "no. The quote carries no bid and no ask. A19 measured that "
              "the spread decides the sign of the expectancy in a one-day "
              "session, so this gap is disqualifying for session input",
    "day high/low": "no. Price and change only, no OHLC",
    "intraday history": "no",
    "release times for R4": "no. The calendar is dated to the day with no "
                            "clock time; the 30-minute window needs a minute",
    "which days carry a release": "yes, and that is the useful part",
    "COT positioning": "yes, duplicating metals.sources.cot",
    "EUR/USD reference rate": "yes, and it is the one number the paper chain "
                              "currently assumes rather than reads",
}


def cannot_run_a_session() -> str:
    """One sentence for anyone tempted to wire this into `paper`."""
    return ("World Monitor cannot supply a paper session: no bid/ask (so no "
            "spread, see A19) and no day high/low (so no day range, which is "
            "the entire strategy). It supplies context around a session, not "
            "the session's inputs.")
