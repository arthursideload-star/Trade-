"""Load real historical gold candles from downloaded files.

The backtest is only worth running on real data, and real M5 gold history for
a multi-year window is not available from any free live API -- every one of
them caps intraday history at 30-60 days. It has to come from a file you
download once.

This module reads the formats those downloads actually arrive in, normalises
everything to UTC, and validates the result before letting a backtest touch
it.

**Timezone is the trap.** The sources disagree, and a misaligned series
silently corrupts every session-based rule in the package -- the London-open
sweep setups would fire in the middle of the Asian session and nobody would
notice from the numbers alone.

    Dukascopy, EODHD, Polygon, Twelve Data  ->  UTC
    HistData                                ->  US Eastern, no DST applied
    MetaTrader exports, Kaggle/HF bulk sets ->  broker server time, undocumented
                                                (commonly UTC+2/+3)

`load()` therefore requires the source timezone to be stated. There is no
"guess" default, because a wrong guess is worse than an error.

**Getting the data** (see docs/DATENQUELLEN.md for the full comparison):

    Free, reproducible provenance -- Dukascopy:
        pip install dukascopy-python
        # fetch XAU/USD M5 for the window, df.to_csv("xauusd_m5.csv")

    Free, fastest -- Kaggle novandraanugrah "XAU/USD Gold Price Historical
    Data" (CC0), file XAU_5m_data.csv, columns Date,Open,High,Low,Close,Volume,
    timestamps in MetaTrader format and broker time.

    From your own broker (matches your live fills most closely):
        MT5 -> Tools -> Options -> Charts -> raise the bar limit, then
        right-click the chart -> Save As, or use the MetaTrader5 Python
        package on Windows.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from ..candles import Candle, CandleSeries, normalise_timeframe

# Named timezone offsets, in hours from UTC. Deliberately a small explicit
# table rather than a tz database: the sources that matter use fixed offsets,
# and the one that does not (broker server time with its own DST) cannot be
# resolved correctly by any library either -- it has to be measured.
KNOWN_OFFSETS: dict[str, float] = {
    "utc": 0.0,
    "gmt": 0.0,
    "us_eastern_no_dst": -5.0,   # HistData: EST year-round, DST NOT applied
    "broker_gmt2": 2.0,          # common MT5 winter offset
    "broker_gmt3": 3.0,          # common MT5 summer offset
}


class HistoryError(RuntimeError):
    """A file could not be loaded, or loaded into something untrustworthy."""


@dataclass
class LoadReport:
    """What was loaded and what is wrong with it."""

    path: str
    rows_read: int = 0
    rows_used: int = 0
    detected_format: str = "unknown"
    source_timezone: str = "unknown"
    first_bar: datetime | None = None
    last_bar: datetime | None = None
    duplicates_dropped: int = 0
    invalid_dropped: int = 0
    gaps: list[tuple[datetime, datetime, float]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.rows_used > 100

    def render(self) -> str:
        lines = [
            "=" * 70,
            "  HISTORY LOAD REPORT",
            "=" * 70,
            f"  file            {os.path.basename(self.path)}",
            f"  format          {self.detected_format}",
            f"  source timezone {self.source_timezone}",
            f"  rows read       {self.rows_read:,}",
            f"  rows used       {self.rows_used:,}",
        ]
        if self.first_bar and self.last_bar:
            span_days = (self.last_bar - self.first_bar).days
            lines.append(f"  range           {self.first_bar:%Y-%m-%d %H:%M} "
                         f"to {self.last_bar:%Y-%m-%d %H:%M} UTC "
                         f"({span_days} days)")
        if self.duplicates_dropped:
            lines.append(f"  duplicates      {self.duplicates_dropped:,} dropped")
        if self.invalid_dropped:
            lines.append(f"  invalid rows    {self.invalid_dropped:,} dropped")

        if self.gaps:
            lines.append(f"\n  GAPS ({len(self.gaps)} longer than expected)")
            lines.append("  " + "-" * 66)
            for start, end, hours in self.gaps[:8]:
                lines.append(f"    {start:%Y-%m-%d %H:%M} -> {end:%Y-%m-%d %H:%M}"
                             f"  ({hours:.1f}h)")
            if len(self.gaps) > 8:
                lines.append(f"    ... and {len(self.gaps) - 8} more")

        if self.warnings:
            lines.append("\n  WARNINGS")
            lines.append("  " + "-" * 66)
            for w in self.warnings:
                lines.append(f"    ! {w}")

        lines.append("=" * 70)
        return "\n".join(lines)


# --- Format detection -------------------------------------------------------

def detect_format(header: list[str], sample_row: list[str]) -> str:
    """Identify which download this file came from.

    Matching on the header alone is not enough -- several sources use
    Date,Open,High,Low,Close,Volume -- so the timestamp shape decides.
    """
    lowered = [h.strip().lower().lstrip("﻿") for h in header]

    if not sample_row:
        return "unknown"
    first = sample_row[0].strip()

    # HistData Generic ASCII: "20240102 170000;2062.31;2062.71;..." -- often
    # semicolon-separated with the date and time fused.
    if len(first) >= 15 and first[:8].isdigit() and " " in first:
        return "histdata"

    # MetaTrader / Kaggle export: "2024.01.02 07:15"
    if "." in first[:10] and ":" in first:
        return "metatrader"

    if {"timestamp"} & set(lowered):
        return "dukascopy"
    if {"date", "open", "high", "low", "close"} <= set(lowered):
        # ISO-ish date with a dash is the generic case.
        if "-" in first:
            return "generic_iso"
        return "generic"
    if {"time"} & set(lowered):
        return "generic_iso"
    return "unknown"


_TIMESTAMP_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y.%m.%d %H:%M:%S",
    "%Y.%m.%d %H:%M",      # MetaTrader / Kaggle
    "%Y%m%d %H%M%S",       # HistData
    "%d.%m.%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%Y-%m-%d",
)


def parse_timestamp(value: str) -> datetime:
    """Parse the timestamp shapes these downloads use. Returns a naive datetime.

    Naive on purpose: the offset is applied once, by the caller, from the
    stated source timezone. Attaching a timezone here would invite a second
    conversion later.
    """
    text = value.strip().replace("﻿", "")
    if not text:
        raise ValueError("empty timestamp")

    # Epoch seconds or milliseconds.
    if text.isdigit() and len(text) in (10, 13):
        seconds = int(text) / (1000.0 if len(text) == 13 else 1.0)
        return datetime.utcfromtimestamp(seconds)

    for fmt in _TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", ""))
    except ValueError as exc:
        raise ValueError(f"cannot parse timestamp {value!r}") from exc


def _sniff_delimiter(sample: str) -> str:
    counts = {d: sample.count(d) for d in (",", ";", "\t")}
    return max(counts, key=counts.get) if any(counts.values()) else ","


# --- Loading ----------------------------------------------------------------

def load(
    path: str,
    source_timezone: str,
    symbol: str = "XAUUSD",
    timeframe: str = "5m",
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    max_rows: int | None = None,
) -> tuple[CandleSeries, LoadReport]:
    """Load a downloaded candle file and normalise it to UTC.

    `source_timezone` is required and must be a key of KNOWN_OFFSETS or a
    signed offset in hours as a string ("+2", "-5", "3"). There is no default:
    a wrong timezone corrupts every session-based rule silently, so it has to
    be a decision rather than an accident.
    """
    offset_hours = _resolve_offset(source_timezone)
    tf = normalise_timeframe(timeframe)
    report = LoadReport(path=path, source_timezone=source_timezone)

    if not os.path.exists(path):
        raise HistoryError(f"no such file: {path}")

    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        head = fh.read(8192)
        fh.seek(0)
        delimiter = _sniff_delimiter(head)
        reader = csv.reader(fh, delimiter=delimiter)
        rows = list(reader)

    if not rows:
        raise HistoryError(f"{path} is empty")

    header = rows[0]
    has_header = not _looks_numeric(header)
    body = rows[1:] if has_header else rows
    if not body:
        raise HistoryError(f"{path} has a header but no data rows")

    report.detected_format = detect_format(header if has_header else [], body[0])
    columns = _column_map(header if has_header else [], report)

    candles: list[Candle] = []
    seen: set[datetime] = set()
    shift = timedelta(hours=offset_hours)

    for row in body:
        report.rows_read += 1
        if max_rows and report.rows_used >= max_rows:
            break
        try:
            raw_ts = row[columns["ts"]]
            # HistData fuses date and time with a space inside one field, but
            # some exports split them across two columns.
            if columns.get("time") is not None:
                raw_ts = f"{raw_ts} {row[columns['time']]}"
            naive = parse_timestamp(raw_ts)
            o = float(row[columns["open"]])
            h = float(row[columns["high"]])
            lo = float(row[columns["low"]])
            c = float(row[columns["close"]])
            v = None
            if columns.get("volume") is not None:
                vt = row[columns["volume"]].strip()
                v = float(vt) if vt not in ("", "-") else None
        except (IndexError, ValueError, KeyError):
            report.invalid_dropped += 1
            continue

        ts = (naive - shift).replace(tzinfo=timezone.utc)

        if start and ts < start:
            continue
        if end and ts > end:
            continue
        if ts in seen:
            report.duplicates_dropped += 1
            continue

        # Reject rows whose OHLC cannot be a candle. These do occur in
        # community datasets and a single one propagates into a false ATR.
        if not (lo <= o <= h and lo <= c <= h and lo <= h):
            report.invalid_dropped += 1
            continue
        if o <= 0 or h <= 0 or lo <= 0 or c <= 0:
            report.invalid_dropped += 1
            continue

        seen.add(ts)
        candles.append(Candle(ts=ts, open=o, high=h, low=lo, close=c, volume=v))
        report.rows_used += 1

    if not candles:
        raise HistoryError(
            f"{path}: no usable rows. Detected format {report.detected_format!r}, "
            f"{report.invalid_dropped} rows rejected. Check the column layout "
            f"and that the file really contains OHLC data."
        )

    series = CandleSeries(symbol, tf, candles, source=f"file:{os.path.basename(path)}")
    _validate(series, report, offset_hours)
    return series, report


def _resolve_offset(source_timezone: str) -> float:
    key = source_timezone.strip().lower()
    if key in KNOWN_OFFSETS:
        return KNOWN_OFFSETS[key]
    try:
        return float(key.replace("utc", "").replace("gmt", "") or 0.0)
    except ValueError as exc:
        raise HistoryError(
            f"unknown source timezone {source_timezone!r}. Use one of "
            f"{sorted(KNOWN_OFFSETS)} or a signed hour offset like '+2'. "
            f"This has no default on purpose: the wrong value silently "
            f"corrupts every session-based rule."
        ) from exc


def _looks_numeric(row: list[str]) -> bool:
    hits = 0
    for cell in row[:6]:
        try:
            float(cell)
            hits += 1
        except ValueError:
            pass
    return hits >= 3


def _column_map(header: list[str], report: LoadReport) -> dict[str, int]:
    """Map logical fields to column indices."""
    if not header:
        # Headerless: assume the near-universal ts,o,h,l,c[,v] ordering.
        report.warnings.append(
            "file has no header row; assuming the column order is "
            "timestamp, open, high, low, close, volume"
        )
        return {"ts": 0, "open": 1, "high": 2, "low": 3, "close": 4, "volume": 5}

    lowered = [h.strip().lower().lstrip("﻿") for h in header]

    def find(*names: str) -> int | None:
        for n in names:
            if n in lowered:
                return lowered.index(n)
        return None

    ts = find("timestamp", "date", "time", "datetime", "date_time", "gmt time")
    if ts is None:
        ts = 0
        report.warnings.append("no timestamp column recognised; using column 0")

    mapping: dict[str, int] = {"ts": ts}
    for field_name, names in (
        ("open", ("open", "o", "<open>")),
        ("high", ("high", "h", "<high>")),
        ("low", ("low", "l", "<low>")),
        ("close", ("close", "c", "<close>", "price")),
    ):
        idx = find(*names)
        if idx is None:
            raise HistoryError(
                f"no {field_name!r} column found. Header was: {header}"
            )
        mapping[field_name] = idx

    vol = find("volume", "v", "<vol>", "tickvol", "<tickvol>")
    if vol is not None:
        mapping["volume"] = vol

    # A separate time column next to a date column.
    if "date" in lowered and "time" in lowered and lowered.index("date") == ts:
        mapping["time"] = lowered.index("time")

    return mapping


def _validate(series: CandleSeries, report: LoadReport, offset_hours: float) -> None:
    """Check the loaded series for the problems these files actually have."""
    report.first_bar = series[0].ts
    report.last_bar = series.last.ts

    from ..candles import TIMEFRAME_SECONDS
    step = TIMEFRAME_SECONDS[series.timeframe]

    # Weekends and the daily break are expected gaps; anything longer than a
    # weekend inside the data is a hole worth knowing about.
    for prev, nxt in zip(series.candles, series.candles[1:]):
        delta = (nxt.ts - prev.ts).total_seconds()
        if delta > step * 12 and delta > 4 * 3600:
            weekend = prev.ts.weekday() >= 4 and delta < 72 * 3600
            if not weekend:
                report.gaps.append((prev.ts, nxt.ts, delta / 3600.0))

    if len(report.gaps) > 50:
        report.warnings.append(
            f"{len(report.gaps)} non-weekend gaps. This much missing data will "
            f"distort session statistics and ATR. Consider a different source."
        )

    # Timezone sanity: gold's activity peaks in the London/NY overlap. If the
    # busiest hours in the data are not roughly 12:00-17:00 UTC, the offset is
    # probably wrong -- and a wrong offset is invisible in the price series.
    by_hour: dict[int, float] = {}
    for c in series:
        by_hour[c.ts.hour] = by_hour.get(c.ts.hour, 0.0) + c.range
    if len(by_hour) >= 20:
        busiest = sorted(by_hour, key=lambda h: by_hour[h], reverse=True)[:4]
        if not any(12 <= h <= 17 for h in busiest):
            report.warnings.append(
                f"the most volatile hours in this data are {sorted(busiest)} UTC, "
                f"but gold's are normally 12:00-17:00 UTC (the London/NY "
                f"overlap). The source timezone ({report.source_timezone}, "
                f"{offset_hours:+.0f}h) looks wrong. Every session rule depends "
                f"on this -- fix it before backtesting."
            )

    # Weekend bars should not exist on a spot metal.
    weekend_bars = sum(1 for c in series if c.ts.weekday() == 5)
    if weekend_bars > len(series) * 0.005:
        report.warnings.append(
            f"{weekend_bars} Saturday bars. Spot gold does not trade then -- "
            f"either the timezone is wrong or the file contains synthetic rows."
        )

    # Implausible single-bar moves point at a decimal or a bad tick.
    closes = series.closes
    jumps = sum(1 for i in range(1, len(closes))
                if abs(closes[i] / closes[i - 1] - 1) > 0.05)
    if jumps:
        report.warnings.append(
            f"{jumps} bars move more than 5% from the previous close. On M5 "
            f"gold that is almost always a bad tick or a decimal error."
        )


# --- Resampling -------------------------------------------------------------

def resample(series: CandleSeries, target: str) -> CandleSeries:
    """Aggregate up a timeframe, e.g. M1 downloads to M5.

    HistData ships 1-minute bars only, so this is the standard step after
    loading it.
    """
    from .prices import resample as _resample
    return _resample(series, target)


def to_csv(series: CandleSeries, path: str) -> None:
    """Write a normalised UTC series back out, so the slow load happens once."""
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for c in series:
            writer.writerow([
                c.ts.strftime("%Y-%m-%d %H:%M:%S"),
                f"{c.open:.3f}", f"{c.high:.3f}", f"{c.low:.3f}", f"{c.close:.3f}",
                "" if c.volume is None else f"{c.volume:.0f}",
            ])
