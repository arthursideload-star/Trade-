from pydantic import BaseModel


class Candle(BaseModel):
    datetime: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class TimeSeriesResponse(BaseModel):
    symbol: str
    interval: str
    currency_base: str = ""
    currency_quote: str = ""
    candles: list[Candle]


class PriceResponse(BaseModel):
    symbol: str
    price: float


SUPPORTED_PAIRS = [
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "USD/CHF",
    "AUD/USD",
    "EUR/GBP",
    "EUR/JPY",
]

SUPPORTED_INTERVALS = ["5min", "15min", "1h", "4h"]
