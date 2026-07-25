from fastapi import APIRouter, HTTPException, Query

from backend.models.market import (
    SUPPORTED_INTERVALS,
    SUPPORTED_PAIRS,
    PriceResponse,
    TimeSeriesResponse,
)
from backend.services.twelvedata import TwelveDataError, fetch_price, fetch_time_series

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/pairs")
async def list_pairs() -> list[str]:
    return SUPPORTED_PAIRS


@router.get("/candles", response_model=TimeSeriesResponse)
async def get_candles(
    symbol: str = Query(description="Forex pair, e.g. EUR/USD"),
    interval: str = Query(default="15min", description="Candle interval"),
    outputsize: int = Query(default=100, ge=1, le=500),
) -> TimeSeriesResponse:
    if symbol not in SUPPORTED_PAIRS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported pair: {symbol}. Supported: {SUPPORTED_PAIRS}",
        )
    if interval not in SUPPORTED_INTERVALS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported interval: {interval}. Supported: {SUPPORTED_INTERVALS}",
        )

    try:
        return await fetch_time_series(symbol, interval, outputsize)
    except TwelveDataError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/price", response_model=PriceResponse)
async def get_price(
    symbol: str = Query(description="Forex pair, e.g. EUR/USD"),
) -> PriceResponse:
    if symbol not in SUPPORTED_PAIRS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported pair: {symbol}. Supported: {SUPPORTED_PAIRS}",
        )

    try:
        return await fetch_price(symbol)
    except TwelveDataError as e:
        raise HTTPException(status_code=502, detail=str(e))
