import asyncio
import time

import httpx

from backend.config import settings
from backend.models.market import Candle, PriceResponse, TimeSeriesResponse


class RateLimiter:
    """Enforces the Twelve Data free-tier limit of 8 requests per minute."""

    def __init__(self, max_calls: int, period: float = 60.0):
        self._max_calls = max_calls
        self._period = period
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._timestamps = [
                t for t in self._timestamps if now - t < self._period
            ]
            if len(self._timestamps) >= self._max_calls:
                wait = self._period - (now - self._timestamps[0])
                await asyncio.sleep(wait)
            self._timestamps.append(time.monotonic())


_rate_limiter = RateLimiter(settings.twelvedata_max_calls_per_minute)


async def fetch_time_series(
    symbol: str,
    interval: str,
    outputsize: int = 100,
) -> TimeSeriesResponse:
    """Fetch OHLCV candle data from Twelve Data."""
    await _rate_limiter.acquire()

    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": settings.twelvedata_api_key,
        "timezone": "UTC",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{settings.twelvedata_base_url}/time_series", params=params
        )
        resp.raise_for_status()
        data = resp.json()

    if data.get("status") == "error":
        raise TwelveDataError(data.get("message", "Unknown API error"))

    meta = data.get("meta", {})
    raw_values = data.get("values", [])

    candles = [
        Candle(
            datetime=v["datetime"],
            open=float(v["open"]),
            high=float(v["high"]),
            low=float(v["low"]),
            close=float(v["close"]),
            volume=float(v.get("volume", 0)),
        )
        for v in raw_values
    ]

    return TimeSeriesResponse(
        symbol=meta.get("symbol", symbol),
        interval=meta.get("interval", interval),
        currency_base=meta.get("currency_base", ""),
        currency_quote=meta.get("currency_quote", ""),
        candles=candles,
    )


async def fetch_price(symbol: str) -> PriceResponse:
    """Fetch the current price for a symbol."""
    await _rate_limiter.acquire()

    params = {
        "symbol": symbol,
        "apikey": settings.twelvedata_api_key,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.twelvedata_base_url}/price", params=params
        )
        resp.raise_for_status()
        data = resp.json()

    if "price" not in data:
        raise TwelveDataError(data.get("message", "No price returned"))

    return PriceResponse(symbol=symbol, price=float(data["price"]))


class TwelveDataError(Exception):
    pass
