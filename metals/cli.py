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


def cmd_challenge(args: argparse.Namespace) -> int:
    """Is a funded-trading challenge worth its fee, given a real edge?

    Exists because the pitch for these is built entirely on the size of the
    notional account, and the only number that decides it is the one nobody
    puts on the slide: expectancy per trade, after costs.
    """
    from .challenge import (ChallengeRules, Edge, evaluate_program, render,
                            render_program, simulate)

    edge = Edge(
        win_rate=args.win_rate / 100.0,
        win_r=args.win_r,
        loss_r=args.loss_r,
        risk_pct=args.risk,
        trades_per_day=args.trades_per_day,
        cost_r=args.cost,
    )

    if args.programm:
        print(render_program(evaluate_program(
            args.account, fee=args.fee, edge=edge, runs=args.runs,
            trailing_drawdown=args.trailing, horizon_days=args.horizon)))
    else:
        rules = ChallengeRules(
            account_size=args.account,
            profit_target_pct=args.target,
            max_daily_loss_pct=args.daily_loss,
            max_total_drawdown_pct=args.max_drawdown,
            trailing_drawdown=args.trailing,
            min_trading_days=args.min_days,
            max_trading_days=args.max_days,
            fee=args.fee,
            profit_split=args.split / 100.0,
        )
        print(render(simulate(rules, edge, runs=args.runs)))
    return 0


def cmd_microscalp(args: argparse.Namespace) -> int:
    """Measure the "close it the moment it is green" strategy.

    Implemented as described rather than argued with. The win rate it
    produces is genuinely near 100%, and the question the numbers answer is
    what happens to the rest of the distribution.
    """
    from .microscalp import (MicroConfig, optimise, report, report_sweep, run,
                             sweep)

    cfg = MicroConfig(
        symbol=args.symbol,
        start_equity=args.equity,
        lot=args.lot,
        max_positions=args.max_positions,
        take_profit_usd_oz=args.take_profit,
        stop_loss_usd_oz=args.stop,
        spread_usd_oz=args.spread,
        direction=args.direction,
        cooldown_bars=args.cooldown,
    )

    if args.train:
        rows = optimise(cfg, markets=args.markets, bars=args.bars)
        print("PARAMETERSUCHE — beste 12 nach Median-Rendite")
        print("=" * 78)
        print(f"  {'TP':>5} {'Stop':>6} {'Richtg':>7} {'Pos':>4} {'Treffer':>8} "
              f"{'Median':>9} {'Mittel':>10} {'Stopout':>8}")
        print("  " + "-" * 74)
        for c, s_ in rows[:12]:
            stop = "keiner" if c.stop_loss_usd_oz is None else f"{c.stop_loss_usd_oz:g}"
            print(f"  {c.take_profit_usd_oz:>5g} {stop:>6} {c.direction:>7} "
                  f"{c.max_positions:>4} {s_.mean_win_rate * 100:>7.1f}% "
                  f"{s_.median_return_pct:>+8.1f}% {s_.mean_return_pct:>+9.1f}% "
                  f"{s_.stop_out_rate * 100:>7.0f}%")
        positive = sum(1 for _, s_ in rows if s_.median_return_pct > 0)
        print()
        print(f"  Konfigurationen mit positivem Median: {positive} von {len(rows)}")
        print()
        print("  Sortiert nach Median, nicht nach Mittelwert. Bei dieser")
        print("  Verteilung haengt der Mittelwert daran, ob der Schwanz in der")
        print("  Stichprobe vorkam -- er beschreibt die Ueberlebenden.")
        return 0

    if args.markets > 1:
        print(report_sweep(sweep(cfg, markets=args.markets, bars=args.bars)))
    else:
        print(report(run(cfg, seed=args.seed, bars=args.bars)))
    return 0


def cmd_dayrange(args: argparse.Namespace) -> int:
    """The day-range prediction strategy: predict a move, bank part of it."""
    from .dayrange import DayRangeConfig, optimise, report_sweep, sweep

    cfg = DayRangeConfig(
        symbol=args.symbol, start_equity=args.equity, lot=args.lot,
        spread_usd_oz=args.spread, edge_fraction=args.edge,
        confirm_bars=args.confirm, take_fraction=args.take,
        stop_fraction=args.stop, time_stop_bars=args.time_stop,
        risk_pct=args.risk,
    )
    if args.train:
        rows = optimise(cfg, markets=args.markets, bars=args.bars,
                        seed_base=args.seed)
        print("PARAMETERSUCHE — beste 10 nach Erwartungswert je Trade")
        print("=" * 70)
        print(f"  {'Mitnahme':>9} {'Stop':>6} {'Zone':>6} {'Kerzen':>7} "
              f"{'Trades':>7} {'Treffer':>8} {'Erwartung':>10}")
        print("  " + "-" * 66)
        for c, s_ in rows[:10]:
            print(f"  {c.take_fraction:>9.0%} {c.stop_fraction:>6.0%} "
                  f"{c.edge_fraction:>6.0%} {c.confirm_bars:>7d} "
                  f"{s_.mean_trades:>7.0f} {s_.mean_win_rate * 100:>7.1f}% "
                  f"{s_.mean_expectancy_r:>+9.3f}R")
        return 0
    print(report_sweep(sweep(cfg, markets=args.markets, bars=args.bars,
                             seed_base=args.seed)))
    return 0


def cmd_claims(args: argparse.Namespace) -> int:
    """What the gold-bot material claims, and what survives measurement."""
    from .claims import render_catalogue, render_measurements

    if not args.measure:
        print(render_catalogue())
        print()
        print("  python -m metals claims --measure  misst die pruefbaren "
              "Behauptungen.")
        return 0
    print(render_catalogue())
    print()
    print(render_measurements(markets=args.markets, bars=args.bars))
    return 0


def cmd_paper(args: argparse.Namespace) -> int:
    """One compounding paper session on a market calibrated to today's gold."""
    from .paper import append, current_equity_eur, render, run_session, summarise

    if args.summary:
        print(summarise())
        return 0
    if args.distribution:
        from .paper import distribution, render_distribution
        if args.price is None or args.high is None or args.low is None:
            print("Auch die Verteilung braucht --price, --high und --low.")
            return 2
        print(render_distribution(distribution(
            gold_price=args.price, day_high=args.high, day_low=args.low,
            equity_eur=args.equity or 400.0, days=args.days)))
        return 0
    if args.price is None or args.high is None or args.low is None:
        print("Bitte --price, --high und --low angeben. Sie stammen aus einer "
              "Kursabfrage,\nnicht aus einer Voreinstellung: ohne sie waere "
              "der Lauf nicht an echte\nDaten gebunden und die Zahl waere "
              "wertlos.")
        return 2

    s = run_session(gold_price=args.price, day_high=args.high,
                    day_low=args.low, price_source=args.source,
                    start_equity_eur=args.equity)
    print(render(s))
    if not args.dry_run:
        append(s)
        print()
        print(summarise())
    else:
        print()
        print(f"  (Probelauf — nicht ins Journal geschrieben, Konto bleibt "
              f"bei {current_equity_eur():,.2f} €)")
    return 0


def cmd_train(args: argparse.Namespace) -> int:
    """One training iteration on fresh markets, appended to the log."""
    from .train import append, one_iteration, render, summarise

    if args.summary:
        print(summarise())
        return 0
    it = one_iteration(markets=args.markets, bars=args.bars)
    append(it)
    print(render(it))
    print()
    print(summarise())
    return 0


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

    ch = sub.add_parser("challenge",
                        help="lohnt sich eine Fremdkapital-Challenge? "
                             "(Simulation statt Verkaufsgespraech)")
    ch.add_argument("--account", type=float, default=100_000.0)
    ch.add_argument("--fee", type=float, default=0.0,
                    help="was die Challenge kostet -- der Betrag, der wirklich "
                         "deiner ist")
    ch.add_argument("--programm", action="store_true",
                    help="den ganzen Weg rechnen: Phase 1, Phase 2 und das "
                         "finanzierte Konto")
    ch.add_argument("--win-rate", type=float, default=100.0 / 2.3,
                    help="Trefferquote in Prozent (Standard: der Wert, bei dem "
                         "die Auszahlungsstruktur exakt null ergibt)")
    ch.add_argument("--win-r", type=float, default=1.3)
    ch.add_argument("--loss-r", type=float, default=1.0)
    ch.add_argument("--cost", type=float, default=0.05,
                    help="Spread und Slippage je Trade, als Anteil des Stops")
    ch.add_argument("--risk", type=float, default=1.0)
    ch.add_argument("--trades-per-day", type=int, default=4)
    ch.add_argument("--target", type=float, default=10.0)
    ch.add_argument("--daily-loss", type=float, default=5.0)
    ch.add_argument("--max-drawdown", type=float, default=10.0)
    ch.add_argument("--trailing", action="store_true",
                    help="nachziehende Verlustschwelle (haeufig, und der "
                         "haeufigste Grund fuers Reissen)")
    ch.add_argument("--min-days", type=int, default=4)
    ch.add_argument("--max-days", type=int, default=30)
    ch.add_argument("--split", type=float, default=80.0)
    ch.add_argument("--horizon", type=int, default=250)
    ch.add_argument("--runs", type=int, default=20_000)
    ch.set_defaults(func=cmd_challenge)

    ms = sub.add_parser("microscalp",
                        help="die 'sofort schliessen wenn im Plus'-Strategie "
                             "messen")
    ms.add_argument("--symbol", default="XAUUSD")
    ms.add_argument("--equity", type=float, default=1_000.0)
    ms.add_argument("--lot", type=float, default=0.10)
    ms.add_argument("--max-positions", type=int, default=3)
    ms.add_argument("--take-profit", type=float, default=0.10,
                    help="USD je Unze ueber dem Einstieg, netto nach Spread")
    ms.add_argument("--stop", type=float, default=None,
                    help="Stop in USD je Unze; ohne Angabe kein Stop")
    ms.add_argument("--spread", type=float, default=0.30)
    ms.add_argument("--direction", default="follow",
                    choices=("follow", "fade", "random", "long", "short"))
    ms.add_argument("--cooldown", type=int, default=0)
    ms.add_argument("--markets", type=int, default=1,
                    help="mehr als 1 zeigt die Verteilung statt eines Pfades")
    ms.add_argument("--bars", type=int, default=8_000,
                    help="1-Minuten-Kerzen; der Zeithorizont entscheidet hier")
    ms.add_argument("--seed", type=int, default=42)
    ms.add_argument("--train", action="store_true",
                    help="Parametersuche ueber Ziel, Stop, Richtung, Anzahl")
    ms.set_defaults(func=cmd_microscalp)

    dr = sub.add_parser("dayrange",
                        help="Tagesspanne-Strategie: Bewegung vorhersagen, "
                             "Teil davon mitnehmen")
    dr.add_argument("--symbol", default="XAUUSD")
    dr.add_argument("--equity", type=float, default=20_000.0)
    dr.add_argument("--lot", type=float, default=0.10,
                    help="feste Losgroesse; wird von --risk ueberstimmt")
    dr.add_argument("--risk", type=float, default=None,
                    help="Risiko je Trade in Prozent; leitet die Losgroesse "
                         "aus dem Stop-Abstand ab (gedeckelt auf R1)")
    dr.add_argument("--spread", type=float, default=0.30)
    dr.add_argument("--edge", type=float, default=0.30,
                    help="wie nah am Rand der Tagesspanne eingestiegen wird")
    dr.add_argument("--confirm", type=int, default=3,
                    help="Bestaetigungskerzen in Richtung des Trades")
    dr.add_argument("--take", type=float, default=0.50,
                    help="Anteil der Vorhersage, bei dem geschlossen wird")
    dr.add_argument("--stop", type=float, default=0.50,
                    help="Anteil der Vorhersage als Stop-Abstand")
    dr.add_argument("--time-stop", type=int, default=240)
    dr.add_argument("--markets", type=int, default=30)
    dr.add_argument("--bars", type=int, default=15_000)
    dr.add_argument("--seed", type=int, default=1_000)
    dr.add_argument("--train", action="store_true")
    dr.set_defaults(func=cmd_dayrange)

    cl = sub.add_parser("claims",
                        help="Behauptungen aus der Recherche — und was davon "
                             "einer Messung standhaelt")
    cl.add_argument("--measure", action="store_true",
                    help="die pruefbaren Behauptungen tatsaechlich messen "
                         "(dauert einige Minuten)")
    cl.add_argument("--markets", type=int, default=20)
    cl.add_argument("--bars", type=int, default=12_000)
    cl.set_defaults(func=cmd_claims)

    pa = sub.add_parser("paper",
                        help="eine Papier-Sitzung, Konto laeuft fort")
    pa.add_argument("--price", type=float, default=None,
                    help="aktueller Goldkurs in USD/oz")
    pa.add_argument("--high", type=float, default=None,
                    help="Tageshoch in USD/oz")
    pa.add_argument("--low", type=float, default=None,
                    help="Tagestief in USD/oz")
    pa.add_argument("--source", default="manuell",
                    help="woher der Kurs stammt — wird mitprotokolliert")
    pa.add_argument("--equity", type=float, default=None,
                    help="Startkapital in Euro; ohne Angabe wird der Stand "
                         "der letzten Sitzung fortgeschrieben")
    pa.add_argument("--dry-run", action="store_true",
                    help="rechnen, aber nicht ins Journal schreiben")
    pa.add_argument("--summary", action="store_true",
                    help="nur die Bilanz aller bisherigen Sitzungen")
    pa.add_argument("--distribution", action="store_true",
                    help="viele unabhaengige Handelstage statt der Kette — "
                         "sagt, ob eine Siegesserie etwas bedeutet")
    pa.add_argument("--days", type=int, default=60,
                    help="wie viele Tage die Verteilung umfasst")
    pa.set_defaults(func=cmd_paper)

    tr = sub.add_parser("train",
                        help="ein Trainingsdurchgang auf frischen Maerkten")
    tr.add_argument("--markets", type=int, default=20)
    tr.add_argument("--bars", type=int, default=12_000)
    tr.add_argument("--summary", action="store_true",
                    help="nur die Bilanz aller bisherigen Durchgaenge")
    tr.set_defaults(func=cmd_train)

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
