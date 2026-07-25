from typing import Optional

from pydantic import BaseModel, Field


class Candle(BaseModel):
    datetime: str
    open: float
    high: float
    low: float
    close: float
    # None when the feed reports no volume. Forex has no exchange volume, and a
    # fabricated 0.0 would read as a real measurement downstream.
    volume: Optional[float] = None


class TimeSeriesResponse(BaseModel):
    symbol: str
    interval: str
    currency_base: str = ""
    currency_quote: str = ""
    order: str = "ascending (oldest first)"
    from_cache: bool = False
    warnings: list[str] = Field(default_factory=list)
    candles: list[Candle]


class PriceResponse(BaseModel):
    symbol: str
    price: float
    as_of: str
    note: str = "latest close of the 15min candle, not a live tick"
