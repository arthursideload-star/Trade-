#!/usr/bin/env python3
"""Fetch forex candles from Twelve Data.

Writes JSON to stdout and diagnostics to stderr, so the output can be piped
into the analysis scripts of later sprints.

Examples:
  python fetch_candles.py --symbol EUR/USD --interval 15min
  python fetch_candles.py --symbol EURUSD --interval 5m,15m,1h,4h
  python fetch_candles.py --symbol EUR/USD --interval 1h --format text
  python fetch_candles.py --symbol EUR/USD --interval 15min --no-cache
"""

import argparse
import json
import sys
from pathlib import Path

# Allow running as a script from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import twelvedata_client as td  # noqa: E402


def parse_intervals(raw: str) -> list[str]:
    """Split a comma-separated interval list and normalize each entry."""
    intervals = [part.strip() for part in raw.split(",") if part.strip()]
    if not intervals:
        raise td.TwelveDataError("No interval given")

    normalized: list[str] = []
    for interval in intervals:
        value = td.normalize_interval(interval)
        if value not in normalized:
            normalized.append(value)
    return normalized


def format_text(results: list[td.CandleSeries]) -> str:
    """Render a compact human-readable summary."""
    lines: list[str] = []
    for series in results:
        source = "cache" if series.from_cache else "API"
        lines.append(f"{series.symbol}  {series.interval}  ({len(series.candles)} candles, {source})")
        lines.append("=" * 72)

        for candle in series.candles[-10:]:
            volume = "-" if candle.volume is None else f"{candle.volume:g}"
            lines.append(
                f"{candle.datetime}  O {candle.open:<10g} H {candle.high:<10g} "
                f"L {candle.low:<10g} C {candle.close:<10g} V {volume}"
            )

        if len(series.candles) > 10:
            lines.append(f"... {len(series.candles) - 10} older candles not shown")

        for warning in series.warnings:
            lines.append(f"WARNING: {warning}")

        last = series.candles[-1]
        lines.append(f"Latest close: {last.close:g} at {last.datetime} UTC")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch forex candles from Twelve Data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--symbol",
        required=True,
        help=f"Forex pair, e.g. EUR/USD. Supported: {', '.join(td.SUPPORTED_PAIRS)}",
    )
    parser.add_argument(
        "--interval",
        default="15min",
        help="Interval or comma-separated list, e.g. 15min or 5m,15m,1h,4h (default: 15min)",
    )
    parser.add_argument(
        "--outputsize",
        type=int,
        default=td.DEFAULT_OUTPUTSIZE,
        help=f"Number of candles (default: {td.DEFAULT_OUTPUTSIZE}, enough for EMA200 warmup)",
    )
    parser.add_argument("--api-key", help="Overrides the TWELVEDATA_API_KEY environment variable")
    parser.add_argument("--no-cache", action="store_true", help="Force a fresh API request")
    parser.add_argument("--format", choices=["json", "text"], default="json", help="Output format")
    parser.add_argument("--output", "-o", help="Write to a file instead of stdout")

    args = parser.parse_args()

    try:
        intervals = parse_intervals(args.interval)

        results: list[td.CandleSeries] = []
        for interval in intervals:
            print(f"Fetching {args.symbol} {interval} ...", file=sys.stderr)
            series = td.fetch_candles(
                symbol=args.symbol,
                interval=interval,
                outputsize=args.outputsize,
                api_key=args.api_key,
                use_cache=not args.no_cache,
            )
            results.append(series)

            source = "cache" if series.from_cache else "API"
            print(
                f"  {len(series.candles)} candles from {source}, "
                f"latest {series.candles[-1].datetime} UTC",
                file=sys.stderr,
            )
            for warning in series.warnings:
                print(f"  WARNING: {warning}", file=sys.stderr)

    except td.RateLimitError as exc:
        print(f"Rate limit: {exc}", file=sys.stderr)
        return 2
    except td.TwelveDataError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        payload = results[0].to_dict() if len(results) == 1 else [s.to_dict() for s in results]
        output = json.dumps(payload, indent=2)
    else:
        output = format_text(results)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
