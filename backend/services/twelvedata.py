"""Async adapter around the forex-data skill client.

The skill script under skills/forex-data/scripts/ is the single place in this
project that talks to Twelve Data. The optional dashboard backend delegates to
it instead of keeping a second implementation, so the guarantees the analysis
relies on (ascending order, honest volume, validation) hold in both entry
points.

The skill directory carries a hyphen and therefore cannot be imported as a
package; the path insert below is what the skills repo does in its own conftest.
"""

import asyncio
import sys
from pathlib import Path

_SKILL_SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "forex-data" / "scripts"
if str(_SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SKILL_SCRIPTS))

import twelvedata_client as _client  # noqa: E402

from backend.config import settings  # noqa: E402
from backend.models.market import Candle, TimeSeriesResponse  # noqa: E402

# Re-exported so the routers can handle them without reaching into the skill.
TwelveDataError = _client.TwelveDataError
RateLimitError = _client.RateLimitError

SUPPORTED_PAIRS = list(_client.SUPPORTED_PAIRS)
# Shortest first, so the list reads like the top-down workflow.
SUPPORTED_INTERVALS = sorted(_client.INTERVAL_SECONDS, key=_client.INTERVAL_SECONDS.get)


async def fetch_time_series(
    symbol: str,
    interval: str,
    outputsize: int = _client.DEFAULT_OUTPUTSIZE,
) -> TimeSeriesResponse:
    """Fetch OHLC candles, oldest first. Runs the blocking client off-loop."""
    series = await asyncio.to_thread(
        _client.fetch_candles,
        symbol=symbol,
        interval=interval,
        outputsize=outputsize,
        api_key=settings.twelvedata_api_key,
    )

    return TimeSeriesResponse(
        symbol=series.symbol,
        interval=series.interval,
        currency_base=series.currency_base,
        currency_quote=series.currency_quote,
        from_cache=series.from_cache,
        warnings=series.warnings,
        candles=[
            Candle(
                datetime=c.datetime,
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=c.volume,
            )
            for c in series.candles
        ],
    )
