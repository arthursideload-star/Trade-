from fastapi import APIRouter, HTTPException, Query

from backend.models.market import PriceResponse, TimeSeriesResponse
from backend.services.twelvedata import (
    SUPPORTED_INTERVALS,
    SUPPORTED_PAIRS,
    RateLimitError,
    TwelveDataError,
    fetch_time_series,
)

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/pairs")
async def list_pairs() -> dict:
    return {"pairs": SUPPORTED_PAIRS, "intervals": SUPPORTED_INTERVALS}


@router.get("/candles", response_model=TimeSeriesResponse)
async def get_candles(
    symbol: str = Query(description="Forex pair, e.g. EUR/USD"),
    interval: str = Query(default="15min", description="5min, 15min, 1h or 4h"),
    outputsize: int = Query(default=300, ge=1, le=5000),
) -> TimeSeriesResponse:
    # The client normalizes and validates the arguments, so the route does not
    # duplicate those rules.
    try:
        return await fetch_time_series(symbol, interval, outputsize)
    except RateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except TwelveDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/price", response_model=PriceResponse)
async def get_price(
    symbol: str = Query(description="Forex pair, e.g. EUR/USD"),
) -> PriceResponse:
    """Latest close, derived from the 15min series so the cache is reused."""
    try:
        series = await fetch_time_series(symbol, "15min")
    except RateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except TwelveDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    latest = series.candles[-1]
    return PriceResponse(symbol=series.symbol, price=latest.close, as_of=latest.datetime)
