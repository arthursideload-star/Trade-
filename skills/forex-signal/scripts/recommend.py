#!/usr/bin/env python3
"""Turn the deterministic analysis into a recommendation card (Sprint B4).

Pipeline: fetch + analyse (forex-analysis) -> score (signal_score) -> derive stop
and target from structure -> size the position (position_sizing) -> run the
R1-R8 gate (risk_rules) -> emit a card.

The stop and target come from the chart's own levels, never from a fixed pip
count, so reward:risk is a real measured number that can fail the 1:2 rule (R3)
rather than being set to 2.0 by construction.

The script proposes; Claude disposes. Rules that need data the script does not
have (R2 daily P&L, R4 news) come back as need_input for Claude to resolve.

Examples:
  python recommend.py --symbol EUR/USD --account 10000
  python recommend.py --symbol EUR/USD --format text
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parents[1] / "forex-analysis" / "scripts"))
sys.path.insert(0, str(_HERE.parents[1] / "forex-data" / "scripts"))

import analyze  # noqa: E402
import position_sizing as ps  # noqa: E402
import risk_rules as rr  # noqa: E402
import signal_score as ss  # noqa: E402
import twelvedata_client as td  # noqa: E402

# Buffer placed beyond the structural level so the stop is not sitting exactly
# on it, where a normal wick would trigger it. Expressed as a fraction of ATR.
STOP_ATR_BUFFER = 0.25
# Fallback stop distance when no structural level is available on the stop side.
FALLBACK_STOP_ATR_MULTIPLE = 1.5


@dataclass
class TradeLevels:
    entry: float
    stop: float
    target: Optional[float]
    reward_risk: Optional[float]
    stop_source: str
    target_source: str


def derive_trade_levels(
    direction: str,
    entry: float,
    level_report_dict: dict,
    atr: Optional[float],
    symbol: str,
) -> TradeLevels:
    """Place the stop behind the protecting level and the target at the next one."""
    pip = ps.pip_size(symbol)
    buffer = (atr * STOP_ATR_BUFFER) if atr else 2 * pip

    supports = level_report_dict.get("supports", [])
    resistances = level_report_dict.get("resistances", [])

    if direction == "long":
        below = [lv["price"] for lv in supports + resistances if lv["price"] < entry]
        if below:
            stop = max(below) - buffer
            stop_source = "below nearest support"
        else:
            stop = entry - (atr * FALLBACK_STOP_ATR_MULTIPLE if atr else 20 * pip)
            stop_source = "ATR fallback (no structural support below)"

        above = [lv["price"] for lv in supports + resistances if lv["price"] > entry]
        if above:
            target = min(above)
            target_source = "nearest resistance above"
        else:
            target = None
            target_source = "no structural resistance above"
    else:  # short
        above = [lv["price"] for lv in supports + resistances if lv["price"] > entry]
        if above:
            stop = min(above) + buffer
            stop_source = "above nearest resistance"
        else:
            stop = entry + (atr * FALLBACK_STOP_ATR_MULTIPLE if atr else 20 * pip)
            stop_source = "ATR fallback (no structural resistance above)"

        below = [lv["price"] for lv in supports + resistances if lv["price"] < entry]
        if below:
            target = max(below)
            target_source = "nearest support below"
        else:
            target = None
            target_source = "no structural support below"

    # Round to price precision here so every downstream reader — the card, the
    # sizing and the gate's messages — sees the same clean number.
    stop = round(stop, 6)
    target = None if target is None else round(target, 6)

    reward_risk = None
    if target is not None:
        risk = abs(entry - stop)
        reward_risk = abs(target - entry) / risk if risk else None

    return TradeLevels(entry, stop, target, reward_risk, stop_source, target_source)


def build_recommendation(
    analysis: dict,
    account: Optional[float],
    now: Optional[datetime] = None,
    daily_pnl_pct: Optional[float] = None,
    account_currency: Optional[str] = None,
) -> dict:
    """Assemble the full recommendation card from an analysis payload."""
    now = now or datetime.now(timezone.utc)
    symbol = analysis["symbol"]
    score = ss.score_from_analysis(analysis)

    by_tf = {b["interval"]: b for b in analysis["timeframes"]}
    entry_block = by_tf.get("15min") or analysis["timeframes"][0]
    entry_price = entry_block["last_close"]
    atr = entry_block["indicators"].get("atr_14")
    entry_regime = entry_block["regime"]

    card: dict = {
        "symbol": symbol,
        "as_of": entry_block["last_datetime"],
        "note": "entry uses the last 15min close, not a live tick",
        "direction": score.direction,
        "confidence": round(score.confidence, 1),
        "regime": entry_regime,
        "score": score.to_dict(),
    }

    if score.direction == "wait":
        card["reason"] = "Signal below the confidence threshold; no trade"
        card["trade"] = None
        return card

    levels = derive_trade_levels(
        score.direction, entry_price, entry_block["levels"], atr, symbol
    )

    trade: dict = {
        "entry": round(levels.entry, 6),
        "stop": round(levels.stop, 6),
        "stop_source": levels.stop_source,
        "target": None if levels.target is None else round(levels.target, 6),
        "target_source": levels.target_source,
        "reward_risk": None if levels.reward_risk is None else round(levels.reward_risk, 2),
    }

    sizing = None
    if account is not None:
        try:
            sizing_result = ps.calculate_position(
                symbol=symbol,
                direction=score.direction,
                entry=levels.entry,
                stop=levels.stop,
                account_balance=account,
                target=levels.target,
                account_currency=account_currency,
            )
            sizing = sizing_result.to_dict()
        except ValueError as exc:
            sizing = {"error": str(exc)}
    trade["sizing"] = sizing

    gate = rr.evaluate(
        direction=score.direction,
        entry=levels.entry,
        stop=levels.stop,
        reward_risk=levels.reward_risk,
        risk_pct=ps.MAX_RISK_PCT_PER_TRADE,
        regime_allowed_direction=entry_regime["allowed_direction"],
        now=now,
        daily_pnl_pct=daily_pnl_pct,
        high_impact_news_within_minutes=None,  # wired in B5
    )
    card["trade"] = trade
    card["risk_gate"] = gate.to_dict()
    card["tradeable"] = gate.clear and not gate.blocked
    return card


def format_text(card: dict) -> str:
    arrow = {"long": "LONG ▲", "short": "SHORT ▼", "wait": "WAIT —"}[card["direction"]]
    lines = [
        f"{card['symbol']}   {arrow}   confidence {card['confidence']}%",
        f"as of {card['as_of']} UTC ({card['note']})",
        f"regime: {card['regime']['regime']} ({card['regime']['allowed_direction']})",
        "-" * 60,
    ]
    if card["direction"] == "wait":
        lines.append(card["reason"])
        return "\n".join(lines)

    t = card["trade"]
    lines.append(f"entry  {t['entry']}")
    lines.append(f"stop   {t['stop']}  ({t['stop_source']})")
    lines.append(f"target {t['target']}  ({t['target_source']})")
    lines.append(f"R:R    {t['reward_risk']}")
    if t["sizing"]:
        s = t["sizing"]
        if "error" in s:
            lines.append(f"size   n/a: {s['error']}")
        else:
            lines.append(f"size   {s['units']:.0f} units ({s['lots']:.3f} lots), risk {s['risk_amount']}")
    lines.append("-" * 60)
    lines.append(f"tradeable by the gate: {card['tradeable']}")
    for r in card["risk_gate"]["rules"]:
        mark = {"ok": "OK ", "blocked": "!! ", "need_input": "?? "}[r["status"]]
        lines.append(f"  {mark}{r['rule']}: {r['detail']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Forex recommendation card",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--account", type=float, help="Account balance for position sizing")
    parser.add_argument("--account-currency", help="e.g. USD; flags a mismatch with the quote ccy")
    parser.add_argument("--daily-pnl-pct", type=float, help="Today's realised P&L %% for R2")
    parser.add_argument("--api-key")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--format", choices=["json", "text"], default="json")

    args = parser.parse_args()

    try:
        blocks = []
        for interval in analyze.DEFAULT_INTERVALS:
            print(f"Analyzing {args.symbol} {interval} ...", file=sys.stderr)
            series = td.fetch_candles(
                symbol=args.symbol,
                interval=interval,
                api_key=args.api_key,
                use_cache=not args.no_cache,
            )
            blocks.append(analyze.analyze_series(series))
        analysis = {"symbol": td.normalize_symbol(args.symbol), "timeframes": blocks}
    except td.RateLimitError as exc:
        print(f"Rate limit: {exc}", file=sys.stderr)
        return 2
    except td.TwelveDataError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    card = build_recommendation(
        analysis,
        account=args.account,
        daily_pnl_pct=args.daily_pnl_pct,
        account_currency=args.account_currency,
    )

    if args.format == "json":
        print(json.dumps(card, indent=2))
    else:
        print(format_text(card))
    return 0


if __name__ == "__main__":
    sys.exit(main())
