"""Candle container and normalisation.

Every data source in metals.sources returns a CandleSeries so the rest of the
package never has to care which provider the data came from.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Iterator, Sequence


@dataclass(frozen=True)
class Candle:
    ts: datetime          # bar OPEN time, always tz-aware UTC
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None

    def __post_init__(self) -> None:
        if self.ts.tzinfo is None:
            raise ValueError("candle timestamps must be timezone-aware (UTC)")
        if not (self.low <= self.open <= self.high):
            raise ValueError(f"open {self.open} outside [{self.low}, {self.high}] at {self.ts}")
        if not (self.low <= self.close <= self.high):
            raise ValueError(f"close {self.close} outside [{self.low}, {self.high}] at {self.ts}")

    # --- derived geometry, used all over the pattern code ---

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def bullish(self) -> bool:
        return self.close > self.open

    @property
    def bearish(self) -> bool:
        return self.close < self.open

    @property
    def body_ratio(self) -> float:
        """Body as a fraction of the full range. 0.0 for a doji-ish bar."""
        return self.body / self.range if self.range > 0 else 0.0

    @property
    def close_position(self) -> float:
        """Where the close sits in the range: 0.0 = at the low, 1.0 = at the high."""
        return (self.close - self.low) / self.range if self.range > 0 else 0.5


TIMEFRAME_SECONDS: dict[str, int] = {
    "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "1d": 86400, "1w": 604800,
}

# Provider-independent aliases; sources map their own spellings onto these.
TIMEFRAME_ALIASES: dict[str, str] = {
    "m1": "1m", "m5": "5m", "m15": "15m", "m30": "30m",
    "h1": "1h", "h4": "4h", "d1": "1d", "w1": "1w",
    "1min": "1m", "5min": "5m", "15min": "15m", "30min": "30m",
    "60min": "1h", "1hour": "1h", "4hour": "4h",
    "daily": "1d", "day": "1d", "weekly": "1w",
}


def normalise_timeframe(tf: str) -> str:
    key = tf.strip().lower()
    key = TIMEFRAME_ALIASES.get(key, key)
    if key not in TIMEFRAME_SECONDS:
        raise ValueError(
            f"unknown timeframe {tf!r}; known: {sorted(TIMEFRAME_SECONDS)}"
        )
    return key


@dataclass
class CandleSeries:
    """An ordered, de-duplicated series of candles for one symbol/timeframe."""

    symbol: str
    timeframe: str
    candles: list[Candle]
    source: str = "unknown"

    def __post_init__(self) -> None:
        self.timeframe = normalise_timeframe(self.timeframe)
        # Sort ascending by time and drop duplicate timestamps, keeping the
        # last occurrence -- providers occasionally repeat the forming bar.
        seen: dict[datetime, Candle] = {}
        for c in self.candles:
            seen[c.ts] = c
        self.candles = [seen[k] for k in sorted(seen)]

    def __len__(self) -> int:
        return len(self.candles)

    def __iter__(self) -> Iterator[Candle]:
        return iter(self.candles)

    def __getitem__(self, idx):  # type: ignore[no-untyped-def]
        return self.candles[idx]

    # --- column views, because the indicator code wants plain lists ---

    @property
    def opens(self) -> list[float]:
        return [c.open for c in self.candles]

    @property
    def highs(self) -> list[float]:
        return [c.high for c in self.candles]

    @property
    def lows(self) -> list[float]:
        return [c.low for c in self.candles]

    @property
    def closes(self) -> list[float]:
        return [c.close for c in self.candles]

    @property
    def volumes(self) -> list[float | None]:
        return [c.volume for c in self.candles]

    @property
    def has_volume(self) -> bool:
        """Spot metal CFD feeds usually carry tick volume or nothing at all."""
        return any(c.volume for c in self.candles)

    @property
    def last(self) -> Candle:
        if not self.candles:
            raise IndexError("empty series")
        return self.candles[-1]

    def tail(self, n: int) -> "CandleSeries":
        return CandleSeries(self.symbol, self.timeframe, self.candles[-n:], self.source)

    def drop_forming_bar(self, now: datetime | None = None) -> "CandleSeries":
        """Remove the last bar if it has not closed yet.

        Acting on an unclosed bar is one of the most common ways a backtest
        stops matching live behaviour, so this is explicit rather than implicit.
        """
        if not self.candles:
            return self
        now = now or datetime.now(timezone.utc)
        step = TIMEFRAME_SECONDS[self.timeframe]
        last_close_time = self.candles[-1].ts.timestamp() + step
        if now.timestamp() < last_close_time:
            return CandleSeries(
                self.symbol, self.timeframe, self.candles[:-1], self.source
            )
        return self

    def gaps(self) -> list[tuple[datetime, datetime]]:
        """Return (previous_ts, next_ts) pairs where bars are missing.

        Metals close for an hour daily and for the weekend, so a gap is not
        automatically a data error -- but a gap in the middle of the London
        session is.
        """
        step = TIMEFRAME_SECONDS[self.timeframe]
        out: list[tuple[datetime, datetime]] = []
        for prev, nxt in zip(self.candles, self.candles[1:]):
            delta = (nxt.ts - prev.ts).total_seconds()
            if delta > step * 1.5:
                out.append((prev.ts, nxt.ts))
        return out


def build_series(
    symbol: str,
    timeframe: str,
    rows: Iterable[Sequence[float] | dict],
    source: str = "unknown",
) -> CandleSeries:
    """Build a CandleSeries from loose provider rows.

    Accepts either dicts with the usual key names or (ts, o, h, l, c[, v])
    sequences. Timestamps may be epoch seconds, epoch milliseconds, ISO
    strings, or datetimes -- providers use all four.
    """
    candles: list[Candle] = []
    for row in rows:
        if isinstance(row, dict):
            ts = row.get("ts", row.get("datetime", row.get("time", row.get("date"))))
            o = row.get("open", row.get("o"))
            h = row.get("high", row.get("h"))
            lo = row.get("low", row.get("l"))
            c = row.get("close", row.get("c"))
            v = row.get("volume", row.get("v"))
        else:
            ts, o, h, lo, c = row[0], row[1], row[2], row[3], row[4]
            v = row[5] if len(row) > 5 else None
        if None in (ts, o, h, lo, c):
            continue
        candles.append(
            Candle(
                ts=_to_utc(ts),
                open=float(o),
                high=float(h),
                low=float(lo),
                close=float(c),
                volume=float(v) if v not in (None, "") else None,
            )
        )
    return CandleSeries(symbol, timeframe, candles, source)


def _to_utc(value) -> datetime:  # type: ignore[no-untyped-def]
    """Coerce the timestamp shapes providers actually emit into aware UTC."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        # Epoch milliseconds if the number is far too large to be seconds.
        seconds = value / 1000.0 if value > 1e11 else float(value)
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        # "2026-07-26 13:00:00" without separator variants, and date-only.
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                dt = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"cannot parse timestamp {value!r}")
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
