#!/usr/bin/env python3
"""Twelve Data client for forex candles.

Single source of truth for Twelve Data access in this project. Standard library
only, so the skill scripts run without any installed package.

Four decisions here exist to protect the downstream analysis:

1. Candles are always returned oldest -> newest. Twelve Data answers newest
   first by default, which silently reverses every indicator built on top.
2. Volume is None when the feed does not report it. Forex has no central
   exchange volume; storing 0.0 would look like a real reading and corrupt
   volume-based indicators.
3. The default outputsize is 300 so an EMA200 has warmup room. A request costs
   one credit regardless of size, so a small default only buys trouble later.
4. OHLC relations are validated before the data leaves this module.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import cache

BASE_URL = "https://api.twelvedata.com"
REQUEST_TIMEOUT_SECONDS = 15
MAX_OUTPUTSIZE = 5000
DEFAULT_OUTPUTSIZE = 300

SUPPORTED_PAIRS = (
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "USD/CHF",
    "AUD/USD",
    "EUR/GBP",
    "EUR/JPY",
)

# Maps the vocabulary used in the plan documents (5m, 1h) onto the API's own
# interval names, and records the candle length used for cache TTLs.
INTERVAL_SECONDS = {
    "5min": 300,
    "15min": 900,
    "1h": 3600,
    "4h": 14400,
}

_INTERVAL_ALIASES = {
    "5m": "5min",
    "5min": "5min",
    "15m": "15min",
    "15min": "15min",
    "1h": "1h",
    "60min": "1h",
    "4h": "4h",
    "240min": "4h",
}


class TwelveDataError(RuntimeError):
    """The API reported an error or returned unusable data."""


class RateLimitError(TwelveDataError):
    """The API credit or request-rate limit is exhausted."""


@dataclass(frozen=True)
class Candle:
    """One OHLCV bar. `volume` is None when the feed reports none."""

    datetime: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "datetime": self.datetime,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


@dataclass(frozen=True)
class CandleSeries:
    """Candles for one symbol and interval, ordered oldest -> newest."""

    symbol: str
    interval: str
    candles: list[Candle]
    currency_base: str = ""
    currency_quote: str = ""
    from_cache: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "interval": self.interval,
            "currency_base": self.currency_base,
            "currency_quote": self.currency_quote,
            "order": "ascending (oldest first)",
            "count": len(self.candles),
            "from_cache": self.from_cache,
            "warnings": self.warnings,
            "candles": [c.to_dict() for c in self.candles],
        }


def get_api_key(explicit: Optional[str] = None) -> str:
    """Return the API key from the argument or TWELVEDATA_API_KEY."""
    api_key = explicit or os.environ.get("TWELVEDATA_API_KEY")
    if not api_key:
        raise TwelveDataError(
            "No API key. Set TWELVEDATA_API_KEY or pass --api-key. "
            "A free key is available at https://twelvedata.com/pricing"
        )
    return api_key


def normalize_symbol(symbol: str) -> str:
    """Accept EURUSD, eur/usd or EUR/USD and return the API spelling."""
    cleaned = symbol.strip().upper().replace("-", "/").replace("_", "/")
    if "/" not in cleaned and len(cleaned) == 6:
        cleaned = f"{cleaned[:3]}/{cleaned[3:]}"
    if cleaned not in SUPPORTED_PAIRS:
        raise TwelveDataError(
            f"Unsupported pair: {symbol}. Supported: {', '.join(SUPPORTED_PAIRS)}"
        )
    return cleaned


def normalize_interval(interval: str) -> str:
    """Accept the plan vocabulary (5m, 4h) and return the API spelling."""
    key = interval.strip().lower()
    if key not in _INTERVAL_ALIASES:
        raise TwelveDataError(
            f"Unsupported interval: {interval}. Supported: {', '.join(sorted(INTERVAL_SECONDS))}"
        )
    return _INTERVAL_ALIASES[key]


def _http_get_json(url: str) -> dict:
    """Fetch and decode a JSON document. Tests replace this function."""
    request = urllib.request.Request(url, headers={"User-Agent": "trade-forex-data/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc.reason)
        if exc.code == 429:
            raise RateLimitError(
                "Twelve Data rate limit reached (8 requests/minute, 800 credits/day "
                f"on the free tier). Wait a minute and retry. Details: {details}"
            ) from exc
        raise TwelveDataError(f"HTTP {exc.code} from Twelve Data: {details}") from exc
    except urllib.error.URLError as exc:
        raise TwelveDataError(f"Network error reaching Twelve Data: {exc.reason}") from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise TwelveDataError(f"Twelve Data returned no valid JSON: {body[:200]}") from exc

    if not isinstance(payload, dict):
        raise TwelveDataError(f"Unexpected response type: {type(payload).__name__}")
    return payload


def _to_float(value: Any, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise TwelveDataError(f"Candle field '{label}' is not a number: {value!r}") from exc


def parse_time_series(payload: dict, symbol: str, interval: str) -> CandleSeries:
    """Turn a raw API payload into a validated, ascending CandleSeries."""
    if payload.get("status") == "error":
        message = payload.get("message", "unknown error")
        if payload.get("code") == 429:
            raise RateLimitError(f"Twelve Data rate limit reached: {message}")
        raise TwelveDataError(f"Twelve Data error: {message}")

    values = payload.get("values")
    if not isinstance(values, list) or not values:
        raise TwelveDataError(
            f"No candles for {symbol} {interval}. The market may be closed "
            "(forex trades Sunday 22:00 to Friday 22:00 UTC)."
        )

    candles = []
    for entry in values:
        if not isinstance(entry, dict):
            raise TwelveDataError(f"Unexpected candle entry: {entry!r}")
        raw_volume = entry.get("volume")
        candles.append(
            Candle(
                datetime=str(entry.get("datetime", "")),
                open=_to_float(entry.get("open"), "open"),
                high=_to_float(entry.get("high"), "high"),
                low=_to_float(entry.get("low"), "low"),
                close=_to_float(entry.get("close"), "close"),
                # Absent volume stays None; forex has no exchange volume and a
                # fabricated 0.0 would be read as a real value downstream.
                volume=None if raw_volume in (None, "") else _to_float(raw_volume, "volume"),
            )
        )

    # Guarantee oldest -> newest regardless of what the API sent.
    candles.sort(key=lambda c: c.datetime)

    meta = payload.get("meta") or {}
    return CandleSeries(
        symbol=meta.get("symbol") or symbol,
        interval=meta.get("interval") or interval,
        candles=candles,
        currency_base=meta.get("currency_base", ""),
        currency_quote=meta.get("currency_quote", ""),
        warnings=validate_candles(candles),
    )


def validate_candles(candles: list[Candle]) -> list[str]:
    """Report data-quality problems instead of passing them downstream."""
    warnings: list[str] = []

    for candle in candles:
        if candle.high < candle.low:
            warnings.append(f"{candle.datetime}: high {candle.high} below low {candle.low}")
        elif candle.high < max(candle.open, candle.close) or candle.low > min(
            candle.open, candle.close
        ):
            warnings.append(f"{candle.datetime}: open/close outside the high-low range")

    timestamps = [c.datetime for c in candles]
    duplicates = {t for t in timestamps if timestamps.count(t) > 1}
    if duplicates:
        warnings.append(f"duplicate timestamps: {', '.join(sorted(duplicates)[:5])}")

    return warnings


def fetch_candles(
    symbol: str,
    interval: str,
    outputsize: int = DEFAULT_OUTPUTSIZE,
    api_key: Optional[str] = None,
    use_cache: bool = True,
    cache_dir: Optional[Path] = None,
    http_get: Optional[Callable[[str], dict]] = None,
) -> CandleSeries:
    """Fetch OHLC candles for one pair and interval, oldest first."""
    symbol = normalize_symbol(symbol)
    interval = normalize_interval(interval)

    if outputsize < 1 or outputsize > MAX_OUTPUTSIZE:
        raise TwelveDataError(f"outputsize must be between 1 and {MAX_OUTPUTSIZE}, got {outputsize}")

    key = get_api_key(api_key)
    getter = http_get or _http_get_json

    ttl = cache.ttl_for_interval(INTERVAL_SECONDS[interval])
    entry_key = cache.cache_key("time_series", symbol, interval, outputsize)

    if use_cache:
        cached = cache.read(entry_key, ttl, cache_dir)
        if cached is not None:
            series = parse_time_series(cached, symbol, interval)
            return CandleSeries(
                symbol=series.symbol,
                interval=series.interval,
                candles=series.candles,
                currency_base=series.currency_base,
                currency_quote=series.currency_quote,
                from_cache=True,
                warnings=series.warnings,
            )

    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        # Ask for ascending order explicitly; parse_time_series sorts anyway.
        "order": "ASC",
        "timezone": "UTC",
        "apikey": key,
    }
    url = f"{BASE_URL}/time_series?{urllib.parse.urlencode(params)}"

    payload = getter(url)
    series = parse_time_series(payload, symbol, interval)

    if use_cache:
        cache.write(entry_key, payload, cache_dir)

    return series
