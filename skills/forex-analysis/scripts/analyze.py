#!/usr/bin/env python3
"""Full deterministic analysis of a forex pair (Sprints B2 + B3).

Fetches candles via the forex-data skill and computes, per timeframe, the
indicators, regime, levels and level-confirmed patterns. Writes JSON to stdout
and progress to stderr, so the output can feed the recommendation step.

This script computes numbers only. It states no direction and makes no
recommendation — that is forex-signal (B4).

Examples:
  python analyze.py --symbol EUR/USD
  python analyze.py --symbol EUR/USD --interval 15min --format text
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
# The single Twelve Data client lives in the forex-data skill.
sys.path.insert(0, str(_HERE.parents[1] / "forex-data" / "scripts"))

import indicators as ind  # noqa: E402
import levels as levels_mod  # noqa: E402
import patterns as pt  # noqa: E402
import regime as rg  # noqa: E402
import twelvedata_client as td  # noqa: E402

DEFAULT_INTERVALS = ["5min", "15min", "1h", "4h"]


def analyze_series(series: td.CandleSeries) -> dict:
    """Compute every deterministic block for one timeframe."""
    highs = [c.high for c in series.candles]
    lows = [c.low for c in series.candles]
    opens = [c.open for c in series.candles]
    closes = [c.close for c in series.candles]
    symbol = series.symbol

    regime = rg.detect_regime(highs, lows, closes)
    level_report = levels_mod.analyze_levels(highs, lows, closes, symbol)
    confirmed = pt.patterns_at_level(highs, lows, opens, closes, level_report, symbol)
    failed = pt.detect_failed_breakout(highs, lows, opens, closes, level_report, symbol)

    macd = ind.macd(closes)
    stoch = ind.stochastic(highs, lows, closes)
    adx = ind.adx(highs, lows, closes, 14)
    bb = ind.bollinger_bands(closes, 20, 2.0)

    return {
        "interval": series.interval,
        "candle_count": len(series.candles),
        "last_close": closes[-1],
        "last_datetime": series.candles[-1].datetime,
        "indicators": {
            "ema_21": _r(ind.last_defined(ind.ema(closes, 21)), 6),
            "ema_55": _r(ind.last_defined(ind.ema(closes, 55)), 6),
            "ema_200": _r(ind.last_defined(ind.ema(closes, 200)), 6),
            "rsi_14": _r(ind.last_defined(ind.rsi(closes, 14))),
            "macd": _r(ind.last_defined(macd["macd"]), 6),
            "macd_signal": _r(ind.last_defined(macd["signal"]), 6),
            "macd_histogram": _r(ind.last_defined(macd["histogram"]), 6),
            "atr_14": _r(ind.last_defined(ind.atr(highs, lows, closes, 14)), 6),
            "adx_14": _r(ind.last_defined(adx["adx"])),
            "plus_di": _r(ind.last_defined(adx["plus_di"])),
            "minus_di": _r(ind.last_defined(adx["minus_di"])),
            "stoch_k": _r(ind.last_defined(stoch["k"])),
            "stoch_d": _r(ind.last_defined(stoch["d"])),
            "bb_upper": _r(ind.last_defined(bb["upper"]), 6),
            "bb_middle": _r(ind.last_defined(bb["middle"]), 6),
            "bb_lower": _r(ind.last_defined(bb["lower"]), 6),
        },
        "regime": regime.to_dict(),
        "levels": level_report.to_dict(),
        "patterns_at_level": [p.to_dict() for p in confirmed],
        "failed_breakout": failed.to_dict() if failed else None,
        "warnings": series.warnings,
    }


def _r(value, digits=2):
    return None if value is None else round(value, digits)


def format_text(symbol: str, blocks: list[dict]) -> str:
    lines = [f"Analysis {symbol}", "=" * 60]
    for block in blocks:
        ind_ = block["indicators"]
        reg = block["regime"]
        lines.append(f"\n[{block['interval']}]  close {block['last_close']:g}  ({block['last_datetime']} UTC)")
        lines.append(f"  Regime: {reg['regime']} ({reg['allowed_direction']}) - {reg['reason']}")
        lines.append(
            f"  RSI {ind_['rsi_14']}  ADX {ind_['adx_14']}  "
            f"MACD hist {ind_['macd_histogram']}  ATR {ind_['atr_14']}"
        )
        lines.append(f"  EMA 21/55/200: {ind_['ema_21']} / {ind_['ema_55']} / {ind_['ema_200']}")
        lv = block["levels"]
        if lv["nearest_support"]:
            lines.append(
                f"  Support {lv['nearest_support']['price']} "
                f"({lv['distance_to_support_pips']} pips below)"
            )
        if lv["nearest_resistance"]:
            lines.append(
                f"  Resistance {lv['nearest_resistance']['price']} "
                f"({lv['distance_to_resistance_pips']} pips above)"
            )
        for p in block["patterns_at_level"]:
            lines.append(f"  Pattern at level: {p['name']} ({p['direction']}) @ {p['level_price']}")
        if block["failed_breakout"]:
            fb = block["failed_breakout"]
            lines.append(f"  Failed breakout: {fb['direction']} - {fb['reason']}")
        for w in block["warnings"]:
            lines.append(f"  WARNING: {w}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic forex analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--symbol", required=True, help="Forex pair, e.g. EUR/USD")
    parser.add_argument(
        "--interval",
        default=",".join(DEFAULT_INTERVALS),
        help="Interval or comma list (default: all four timeframes)",
    )
    parser.add_argument("--outputsize", type=int, default=td.DEFAULT_OUTPUTSIZE)
    parser.add_argument("--api-key")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--format", choices=["json", "text"], default="json")

    args = parser.parse_args()
    intervals = [i.strip() for i in args.interval.split(",") if i.strip()]

    try:
        blocks = []
        for interval in intervals:
            print(f"Analyzing {args.symbol} {interval} ...", file=sys.stderr)
            series = td.fetch_candles(
                symbol=args.symbol,
                interval=interval,
                outputsize=args.outputsize,
                api_key=args.api_key,
                use_cache=not args.no_cache,
            )
            blocks.append(analyze_series(series))
    except td.RateLimitError as exc:
        print(f"Rate limit: {exc}", file=sys.stderr)
        return 2
    except td.TwelveDataError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    symbol = td.normalize_symbol(args.symbol)
    if args.format == "json":
        payload = {"symbol": symbol, "timeframes": blocks}
        print(json.dumps(payload, indent=2))
    else:
        print(format_text(symbol, blocks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
