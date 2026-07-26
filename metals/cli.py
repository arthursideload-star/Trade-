"""Command line interface.

    python -m metals analyse XAUUSD --equity 10000
    python -m metals quote XAGUSD
    python -m metals ratio
    python -m metals sources
    python -m metals check
    python -m metals rules
    python -m metals size XAUUSD --entry 4500 --stop 4488 --target 4530 --equity 10000
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

from .risk import (MAX_RISK_PER_TRADE_PCT, RULES, AccountState,
                   size_position)
from .sessions import classify
from .sources.http import HttpClient
from .sources.registry import SOURCES, coverage_report
from .specs import SPECS, get_vol_profile


def cmd_analyse(args: argparse.Namespace) -> int:
    from .analyze import analyse

    account = AccountState(
        equity=args.equity,
        realised_pnl_today=args.pnl_today,
        open_positions=args.open_positions,
        open_risk_pct=args.open_risk,
    )
    client = HttpClient(cache_ttl=args.cache_ttl)
    try:
        rec = analyse(args.symbol, account, client=client,
                      spread_usd_oz=args.spread)
    except Exception as exc:  # noqa: BLE001 - the CLI reports, it does not crash
        print(f"analysis failed: {exc}", file=sys.stderr)
        print("\nMost common causes:", file=sys.stderr)
        print("  - no network access from this environment", file=sys.stderr)
        print("  - TWELVEDATA_API_KEY not set and the fallback provider is "
              "unreachable", file=sys.stderr)
        return 1
    print(rec.render())
    print(f"\n({client.request_count} HTTP request(s) made)")
    return 0 if rec.actionable or rec.action == "no_trade" else 1


def cmd_quote(args: argparse.Namespace) -> int:
    from .sources.prices import cross_check, fetch_quote

    client = HttpClient()
    quotes = []
    for symbol in args.symbols:
        try:
            q = fetch_quote(symbol, client)
            quotes.append(q)
            spread = f"  spread {q.spread:.3f}" if q.spread is not None else ""
            print(f"{q.symbol:8s} {q.price:>12,.3f}  ({q.source}){spread}")
        except Exception as exc:  # noqa: BLE001
            print(f"{symbol:8s} unavailable: {exc}", file=sys.stderr)
    if len(quotes) >= 2 and len({q.symbol for q in quotes}) == 1:
        ok, note = cross_check(quotes)
        print(f"\ncross-check: {'OK' if ok else 'MISMATCH'} -- {note}")
    return 0 if quotes else 1


def cmd_ratio(args: argparse.Namespace) -> int:
    from . import gsr
    from .sources.prices import fetch_candles

    client = HttpClient()
    try:
        gold = fetch_candles("XAUUSD", "1d", 250, client).series
        silver = fetch_candles("XAGUSD", "1d", 250, client).series
        state = gsr.analyse(gold, silver)
    except Exception as exc:  # noqa: BLE001
        print(f"ratio unavailable: {exc}", file=sys.stderr)
        return 1

    print(f"Gold/Silver ratio: {state.ratio:.2f}  [{state.band}]")
    print(f"  20-period trend: {state.trend_20}  (leader: {state.leader})")
    print(f"  regime:          {state.regime}")
    if state.zscore is not None:
        print(f"  z-score:         {state.zscore:+.2f}")
    if state.percentile is not None:
        print(f"  percentile:      {state.percentile:.0f}")
    for note in state.notes:
        print(f"\n  {note}")
    pair = gsr.pair_trade_note(state)
    if pair:
        print(f"\n  {pair}")
    return 0


def cmd_sources(args: argparse.Namespace) -> int:
    by_cat: dict[str, list] = {}
    for s in SOURCES.values():
        by_cat.setdefault(s.category.value, []).append(s)

    for cat in sorted(by_cat):
        print(f"\n{cat.upper()}")
        print("-" * 68)
        for s in sorted(by_cat[cat], key=lambda x: x.priority):
            mark = {"none": "free ", "free_key": "key  ", "paid": "paid "}[s.auth.value]
            ready = ""
            if s.env_var:
                ready = " [READY]" if os.environ.get(s.env_var) else f" [needs {s.env_var}]"
            print(f"  [{mark}] {s.name}{ready}")
            print(f"           {s.url}")
            if s.limit:
                print(f"           limit: {s.limit}")
            for p in s.provides:
                print(f"           - {p}")
            if s.caveat and args.verbose:
                print(f"           caveat: {s.caveat}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Report what the assistant can currently see, and what is missing."""
    report = coverage_report(dict(os.environ))
    print("DATA COVERAGE")
    print("-" * 68)
    print(f"active sources:    {len(report['active'])}")
    print(f"blocked sources:   {len(report['blocked'])}")
    print(f"categories covered: {', '.join(report['categories_covered'])}")
    if report["categories_missing"]:
        print(f"categories MISSING: {', '.join(report['categories_missing'])}")

    blocked = report["blocked"]
    if blocked:
        print("\nSet these to unlock more sources:")
        seen: set[str] = set()
        for key, env in blocked:
            if env and env not in seen:
                seen.add(env)
                names = [s.name for s in SOURCES.values() if s.env_var == env]
                print(f"  {env:24s} -> {', '.join(names)}")

    print("\nSESSION")
    print("-" * 68)
    state = classify(datetime.now(timezone.utc))
    print(f"  {state.session.value} ({state.quality.value})")
    for r in state.reasons:
        print(f"  - {r}")

    if not args.no_network:
        print("\nLIVE REACHABILITY")
        print("-" * 68)
        client = HttpClient(cache_ttl=0, retries=0, timeout=8.0)
        _probe(client)
    return 0


def _probe(client: HttpClient) -> None:
    from .sources.news import FEEDS, fetch_feed
    from .sources.prices import fetch_quote

    checks: list[tuple[str, object]] = [
        ("gold spot", lambda: fetch_quote("XAUUSD", client)),
        ("silver spot", lambda: fetch_quote("XAGUSD", client)),
    ]
    for key in list(FEEDS)[:3]:
        checks.append((f"news:{key}", lambda k=key: fetch_feed(client, k)))

    try:
        from .sources.macro import fetch_series
        checks.append(("macro:DFII10", lambda: fetch_series("DFII10", client)))
    except Exception:  # noqa: BLE001
        pass

    for name, fn in checks:
        try:
            result = fn()  # type: ignore[operator]
            detail = ""
            if isinstance(result, list):
                detail = f" ({len(result)} items)"
            print(f"  OK    {name}{detail}")
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL  {name}: {str(exc)[:90]}")


def cmd_backtest(args: argparse.Namespace) -> int:
    from .backtest import BacktestConfig, report, run
    from . import simulate

    cfg = BacktestConfig(
        symbol=args.symbol,
        spread_usd_oz=args.spread,
        slippage_fraction=args.slippage,
        style=args.style,
        min_confidence=args.min_confidence,
        max_trades_per_day=args.max_trades,
    )

    if args.source == "file":
        from .sources.history import HistoryError, load, resample
        if not args.file:
            print("--source file needs --file <path>", file=sys.stderr)
            return 1
        if not args.tz:
            print("--source file needs --tz. There is no default on purpose: "
                  "the wrong timezone silently corrupts every session rule.\n"
                  "  Dukascopy / EODHD / Twelve Data -> utc\n"
                  "  HistData                        -> us_eastern_no_dst\n"
                  "  MetaTrader or Kaggle bulk export -> broker_gmt2 / broker_gmt3\n"
                  "  or a signed offset such as '+3'", file=sys.stderr)
            return 1
        try:
            m5, load_report = load(args.file, args.tz, args.symbol,
                                   args.file_timeframe)
        except HistoryError as exc:
            print(f"could not load {args.file}: {exc}", file=sys.stderr)
            return 1
        print(load_report.render())
        print()
        if args.file_timeframe != "5m":
            m5 = resample(m5, "5m")
            print(f"resampled {args.file_timeframe} -> 5m, {len(m5)} bars\n")
        if load_report.warnings:
            print("Proceeding despite the warnings above. Read them -- a "
                  "timezone or gap problem produces a plausible-looking "
                  "backtest that is wrong.\n")
        source_label = f"REAL data from {args.file} ({len(m5)} bars, {args.tz})"

    elif args.source == "live":
        from .sources.prices import fetch_candles
        client = HttpClient()
        try:
            m5 = fetch_candles(args.symbol, "5m", args.bars, client).series
        except Exception as exc:  # noqa: BLE001
            print(f"could not fetch live candles: {exc}", file=sys.stderr)
            print("\nNote that free live APIs cap intraday history at 30-60 "
                  "days, so --source live cannot produce a multi-year window. "
                  "For that, download a file and use --source file (see "
                  "docs/DATENQUELLEN.md).", file=sys.stderr)
            return 1
        source_label = f"live ({m5.source}, {len(m5)} bars)"
    else:
        m5 = simulate.generate(bars=args.bars, timeframe="5m", seed=args.seed)
        source_label = f"SIMULATED (seed {args.seed}) -- NOT real gold"
        stats = simulate.describe(m5)
        print("Simulated market properties:")
        print(f"  bars {stats['bars']:.0f}, price {stats['start_price']:.0f} -> "
              f"{stats['end_price']:.0f} ({stats['total_move_pct']:+.1f}%)")
        print(f"  mean ATR(14) {stats['mean_atr_usd']:.2f} USD/oz = "
              f"{stats['mean_atr_pct']:.3f}% of price")
        print(f"  excess kurtosis {stats['excess_kurtosis']:.1f} (fat tails), "
              f"vol clustering {stats['vol_clustering']:.2f}")
        print()

    result = run(m5, cfg, data_source=source_label)
    print(report(result))

    if args.source == "sim":
        print("\n" + "!" * 72)
        print("These numbers come from a SIMULATED market. They show whether")
        print("the machinery works -- signals fire, R multiples and costs are")
        print("computed correctly, exits behave. They are NOT a measured hit")
        print("rate for real gold and must not be used to size a position.")
        print("Run with --source live for real candles.")
        print("!" * 72)
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    """Should I keep trading right now?"""
    from .exits import DayState, session_advice

    account = AccountState(
        equity=args.equity,
        realised_pnl_today=args.pnl_today,
        open_positions=args.open_positions,
    )
    day = DayState(
        trades_taken=args.trades_today,
        consecutive_losses=args.consecutive_losses,
        last_trade_was_loss=args.last_was_loss,
        last_trade_closed_at=(
            datetime.now(timezone.utc) - timedelta(minutes=args.minutes_since_last)
            if args.minutes_since_last is not None else None
        ),
    )
    advice = session_advice(account, day)
    print(f"{advice.headline()}")
    print("-" * 68)
    for r in advice.reasons:
        print(f"  {r}")
    if advice.minutes_of_good_session_left is not None:
        print(f"\n  Gutes Fenster noch etwa "
              f"{advice.minutes_of_good_session_left} Minuten.")
    return 1 if advice.should_stop else 0


def cmd_setups(args: argparse.Namespace) -> int:
    from .scalping import CATALOGUE as SCALP
    from .setups import CATALOGUE as SWING

    if args.kind in ("scalp", "all"):
        print("SCALPING SETUPS (M5 with M1 confirmation)")
        print("=" * 72)
        for key, s in SCALP.items():
            print(f"\n  {key} -- {s.name}   (base confidence {s.base_confidence:.2f})")
            print(f"     idea:    {s.idea}")
            print(f"     phases:  {s.phases}")
            print(f"     entry:   {s.entry_rule}")
            print(f"     stop:    {s.stop_rule}")
            print(f"     exit:    {s.exit_rule}")
            print(f"     FAILS:   {s.failure_mode}")
            print(f"     window:  {s.best_window}")

    if args.kind in ("swing", "all"):
        print("\n\nSWING / INTRADAY SETUPS (H4 context, H1 setup, M15 trigger)")
        print("=" * 72)
        for key, s in SWING.items():
            print(f"\n  {key} -- {s.name}   (base confidence {s.base_confidence:.2f})")
            print(f"     idea:    {s.idea}")
            print(f"     entry:   {s.entry_rule}")
            print(f"     stop:    {s.stop_rule}")
            print(f"     target:  {s.target_rule}")
            print(f"     FAILS:   {s.failure_mode}")
    return 0


def cmd_minimum(args: argparse.Namespace) -> int:
    """What account size does this instrument need to be tradable at all?

    Exists because "the account is too small" is the single most common
    reason a plan fails before it starts, and it is far more convincing as a
    table than as advice.
    """
    from .specs import get_spec, get_vol_profile

    spec = get_spec(args.symbol)
    vol = get_vol_profile(args.symbol)
    low, typical, high = vol.band(args.timeframe)
    min_lot = args.min_lot

    print(f"MINIMUM ACCOUNT SIZE FOR {spec.symbol}")
    print("=" * 72)
    print(f"  1 lot = {spec.contract_size_oz:,.0f} oz, so the smallest position "
          f"({min_lot} lots) is {min_lot * spec.contract_size_oz:.0f} oz.")
    print(f"  A 1.00 USD/oz move on that position is "
          f"{min_lot * spec.contract_size_oz:.2f} USD.")
    print(f"  {args.timeframe.upper()} ATR band for {spec.symbol}: "
          f"{low:g} - {high:g} USD/oz (typical {typical:g}).")
    print()
    print(f"  Risk limit is {MAX_RISK_PER_TRADE_PCT:.0f}% per trade (rule R1), "
          f"and rule M1 puts the stop at no less than 1.0x ATR.")
    print()
    print(f"  {'stop (USD/oz)':>14}  {'risk at min lot':>16}  "
          f"{'account needed':>16}")
    print("  " + "-" * 68)

    stops = args.stops or [round(typical * m, 1) for m in (0.8, 1.0, 1.5, 2.0, 3.0)]
    for stop in stops:
        risk = stop * min_lot * spec.contract_size_oz
        needed = risk / (MAX_RISK_PER_TRADE_PCT / 100.0)
        print(f"  {stop:>14.2f}  {risk:>15.2f} USD  {needed:>12,.0f} USD")

    if args.equity:
        print()
        print(f"  YOUR ACCOUNT: {args.equity:,.2f}")
        print("  " + "-" * 68)
        blocked = 0
        for stop in stops:
            risk = stop * min_lot * spec.contract_size_oz
            pct = risk / args.equity * 100.0
            verdict = ("OK" if pct <= MAX_RISK_PER_TRADE_PCT
                       else "REFUSED -- over the 1% limit")
            if pct > MAX_RISK_PER_TRADE_PCT:
                blocked += 1
            print(f"  stop {stop:>6.2f} USD/oz -> risk {pct:>6.2f}% of equity"
                  f"   {verdict}")
        if blocked == len(stops):
            print()
            print("  Every realistic stop is refused at this balance. That is "
                  "an account-size\n  constraint, not a signal problem, and it "
                  "cannot be solved by picking a\n  tighter stop -- rule M1 "
                  "floors the stop at 1.0x ATR because anything\n  tighter is "
                  "taken out by normal noise before the idea resolves.")
            print()
            print("  The two honest options are a larger balance, or a demo "
                  "account funded\n  with a realistic figure so the sizing "
                  "behaves the way it would live.")
    return 0


def cmd_journal(args: argparse.Namespace) -> int:
    """What has the EA actually done, and what does it prove?

    The second half of that question is the reason this command exists. A
    list of trades invites the reader to draw a conclusion from it; the
    renderer says out loud how much of a conclusion the sample supports,
    which is usually none.
    """
    from .journal import JournalError, load, render, summarise

    try:
        entries = load(args.file)
    except JournalError as exc:
        print(f"cannot read the journal: {exc}", file=sys.stderr)
        return 1

    summary = summarise(entries)
    print(render(summary))

    if args.csv:
        # For pasting into a spreadsheet, one row per closed trade.
        print()
        print("timestamp,setup,session,direction,exit,r_multiple")
        for t in summary.trades:
            print(f"{t.timestamp:%Y-%m-%d %H:%M},{t.setup},{t.session},"
                  f"{t.direction},{t.exit_reason},{t.r_multiple:+.3f}")

    # A non-zero exit when the record shows a discipline failure, so this can
    # be wired into a scheduled check that only speaks up when it matters.
    return 1 if summary.discipline_breaches else 0


def cmd_rules(args: argparse.Namespace) -> int:
    print("HARD RISK RULES (in code, not configuration -- changing one "
          "requires a commit)")
    print("=" * 68)
    for key, text in RULES.items():
        print(f"  {key:4s} {text}")
    print("\nCONTRACT SPECIFICATIONS")
    print("=" * 68)
    for sym in ("XAUUSD", "XAGUSD"):
        spec = SPECS[sym]
        vol = get_vol_profile(sym)
        print(f"  {spec.symbol}: 1 lot = {spec.contract_size_oz:,.0f} oz, "
              f"1.00 USD/oz move = {spec.value_per_dollar_move:,.0f} USD/lot")
        print(f"    typical H1 ATR band: {vol.band('h1')[0]:g} - "
              f"{vol.band('h1')[2]:g} USD/oz")
        print(f"    {spec.notes}")
    return 0


def cmd_size(args: argparse.Namespace) -> int:
    account = AccountState(equity=args.equity, realised_pnl_today=args.pnl_today)
    atr_value = args.atr
    if atr_value is None:
        vol = get_vol_profile(args.symbol)
        atr_value = vol.band("h1")[1]
        print(f"note: no --atr given, using the typical H1 value "
              f"({atr_value:g} USD/oz) from the reference profile. Pass the "
              f"real ATR from your chart for an accurate check.\n")

    direction = "long" if args.target > args.entry else "short"
    plan = size_position(
        args.symbol, direction, args.entry, args.stop, args.target,
        account, atr_value, risk_pct=args.risk, spread_usd_oz=args.spread,
    )
    print(plan.summary())
    if plan.warnings:
        print("\nWARNINGS")
        for w in plan.warnings:
            print(f"  ! {w}")
    if plan.blocks:
        print("\nBLOCKED")
        for b in plan.blocks:
            print(f"  x {b}")
    return 0 if plan.approved else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="metals",
        description="Gold and silver trading assistant -- deterministic "
                    "calculators for XAU/USD and XAG/USD.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyse", help="full top-down analysis")
    a.add_argument("symbol", nargs="?", default="XAUUSD")
    a.add_argument("--equity", type=float, default=10_000.0)
    a.add_argument("--risk", type=float, default=1.0)
    a.add_argument("--pnl-today", type=float, default=0.0)
    a.add_argument("--open-positions", type=int, default=0)
    a.add_argument("--open-risk", type=float, default=0.0)
    a.add_argument("--spread", type=float, default=None,
                   help="current spread in USD per ounce, from your platform")
    a.add_argument("--cache-ttl", type=float, default=60.0)
    a.set_defaults(func=cmd_analyse)

    q = sub.add_parser("quote", help="current spot price")
    q.add_argument("symbols", nargs="*", default=["XAUUSD", "XAGUSD"])
    q.set_defaults(func=cmd_quote)

    r = sub.add_parser("ratio", help="gold/silver ratio state")
    r.set_defaults(func=cmd_ratio)

    s = sub.add_parser("sources", help="list every data source")
    s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(func=cmd_sources)

    c = sub.add_parser("check", help="what the assistant can currently see")
    c.add_argument("--no-network", action="store_true")
    c.set_defaults(func=cmd_check)

    j = sub.add_parser("journal",
                       help="what the EA did, and what it proves (usually "
                            "less than it looks)")
    j.add_argument("--file", default="GoldScalpAssistant.csv",
                   help="the CSV the EA writes into MQL5/Files "
                        "(MetaTrader: File -> Open Data Folder)")
    j.add_argument("--csv", action="store_true",
                   help="also print one row per closed trade, for a "
                        "spreadsheet")
    j.set_defaults(func=cmd_journal)

    ru = sub.add_parser("rules", help="the hard risk rules and contract specs")
    ru.set_defaults(func=cmd_rules)

    mn = sub.add_parser("minimum",
                        help="what account size does this instrument need?")
    mn.add_argument("symbol", nargs="?", default="XAUUSD")
    mn.add_argument("--equity", type=float, default=None,
                    help="check a specific balance against the limits")
    mn.add_argument("--timeframe", default="m5",
                    choices=("m5", "m15", "h1", "h4", "d1"))
    mn.add_argument("--min-lot", type=float, default=0.01,
                    help="your broker's minimum volume")
    mn.add_argument("--stops", type=float, nargs="*", default=None,
                    help="specific stop distances in USD per ounce")
    mn.set_defaults(func=cmd_minimum)

    b = sub.add_parser("backtest", help="run the scalping setups over history")
    b.add_argument("symbol", nargs="?", default="XAUUSD")
    b.add_argument("--source", choices=("sim", "live", "file"), default="sim",
                   help="'file' reads a downloaded history file (the only way "
                        "to get a multi-year M5 window); 'live' fetches recent "
                        "candles from an API; 'sim' uses the synthetic market "
                        "(machinery test only -- see simulate.py)")
    b.add_argument("--file", default=None,
                   help="path to a downloaded OHLCV file")
    b.add_argument("--tz", default=None,
                   help="source timezone: utc | us_eastern_no_dst | "
                        "broker_gmt2 | broker_gmt3 | a signed offset like '+3'")
    b.add_argument("--file-timeframe", default="5m",
                   help="timeframe of the file; anything higher-resolution is "
                        "resampled to 5m")
    b.add_argument("--bars", type=int, default=5000)
    b.add_argument("--seed", type=int, default=42)
    b.add_argument("--spread", type=float, default=0.20,
                   help="spread in USD per ounce")
    b.add_argument("--slippage", type=float, default=0.5,
                   help="extra adverse fill as a fraction of the spread")
    b.add_argument("--style", choices=("scalp", "intraday", "swing"),
                   default="scalp")
    b.add_argument("--min-confidence", type=float, default=0.60)
    b.add_argument("--max-trades", type=int, default=4)
    b.set_defaults(func=cmd_backtest)

    st = sub.add_parser("stop", help="should I keep trading right now?")
    st.add_argument("--equity", type=float, default=10_000.0)
    st.add_argument("--pnl-today", type=float, default=0.0)
    st.add_argument("--trades-today", type=int, default=0)
    st.add_argument("--consecutive-losses", type=int, default=0)
    st.add_argument("--last-was-loss", action="store_true")
    st.add_argument("--minutes-since-last", type=int, default=None)
    st.add_argument("--open-positions", type=int, default=0)
    st.set_defaults(func=cmd_stop)

    se = sub.add_parser("setups", help="print the setup catalogue")
    se.add_argument("kind", nargs="?", choices=("scalp", "swing", "all"),
                    default="all")
    se.set_defaults(func=cmd_setups)

    z = sub.add_parser("size", help="size a trade you already have levels for")
    z.add_argument("symbol")
    z.add_argument("--entry", type=float, required=True)
    z.add_argument("--stop", type=float, required=True)
    z.add_argument("--target", type=float, required=True)
    z.add_argument("--equity", type=float, required=True)
    z.add_argument("--risk", type=float, default=1.0)
    z.add_argument("--atr", type=float, default=None)
    z.add_argument("--spread", type=float, default=None)
    z.add_argument("--pnl-today", type=float, default=0.0)
    z.set_defaults(func=cmd_size)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
