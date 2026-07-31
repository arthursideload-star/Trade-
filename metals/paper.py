"""A compounding paper-trading run, one session at a time.

Each session is one trading day. The account starts at whatever the previous
session ended with, so a run of sessions is a single account followed forward
rather than a set of independent samples -- which is the point: independent
samples tell you the distribution, a compounded chain tells you what living
with the distribution feels like.

**What is real here and what is not.** Before each session the current gold
price and the day's actual high/low are looked up, and the generated market is
calibrated to both: it starts at the real price, and its volatility is scaled
so its daily range matches the real one. What is *not* real is the path in
between. Nothing in this environment can reach an intraday price feed -- the
providers return 403 through the proxy -- so the minute-by-minute sequence is
generated.

That distinction decides what a result from this module is worth:

* The **cost arithmetic** is real. Margin, what a minimum lot risks against
  this account, how much of the account one stop is -- all computed from
  today's actual price.
* The **volatility scale** is real, to the extent one day's range describes
  it.
* The **outcome** is not a forecast. It is what these rules would have done
  on *a* day that moved as much as today did.

A chain of sessions therefore answers "is this account size survivable" much
better than it answers "will this make money".

Position sizing follows what a small account actually faces. `metals.risk`
caps risk at 1% per trade, and on a 400-euro account the smallest lot gold
allows breaks that cap several times over -- so `forced_risk_pct` is recorded
for every session and is the first number to read in the ledger.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import time
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone

from . import simulate
from .dayrange import DayRangeConfig, run
from .risk import MAX_RISK_PER_TRADE_PCT
from .specs import get_spec

LEDGER_DIR = "training"
LEDGER_PATH = os.path.join(LEDGER_DIR, "paper-ledger.jsonl")

# The account is funded in euro, the contract settles in dollars. Written down
# rather than fetched: the rate moves, and nothing here turns on its third
# decimal.
ASSUMED_EUR_USD = 1.08

# Expected range of a driftless random walk over n steps, in units of the
# per-step standard deviation: E[range] = 2 sigma sqrt(2n/pi).
_RANGE_OVER_SIGMA = 2.0 * math.sqrt(2.0 / math.pi)

BARS_PER_DAY = 1_440
MIN_LOT = 0.01

# A typical daily range for gold, as a share of price. Derived from an
# observed weekly range rather than quoted: 143.97 USD over five sessions at
# ~4,103, and for a random walk the range over n days scales with sqrt(n),
# so one day is 143.97/sqrt(5) = 64.39 USD = 1.57%.
#
# It matters because the calibration takes whatever range it is given. The
# first eleven sessions of this chain all used 30 July -- an FOMC day at
# 2.23%, or 1.42 times typical -- which lifted the median return from about
# +7.4% to +9.4%. Repeating one unusually wide day and calling the result a
# forecast is the kind of mistake that looks like data.
TYPICAL_DAY_RANGE_PCT = 1.57


# Seeds used only for calibration. Fixed, so the same observed range always
# yields the same volatility, and disjoint from the seeds sessions trade on,
# so no session is measured on a market that was used to tune it.
_CALIBRATION_SEEDS = tuple(range(900_001, 900_009))


def _median_range(price: float, base_vol: float, bars: int) -> float:
    ranges = []
    for seed in _CALIBRATION_SEEDS:
        s = simulate.generate(
            bars=bars, timeframe="1m", seed=seed,
            params=simulate.MarketParams(start_price=price, base_vol=base_vol))
        ranges.append(max(c.high for c in s.candles)
                      - min(c.low for c in s.candles))
    return statistics.median(ranges)


def calibrate_vol(price: float, day_high: float, day_low: float,
                  bars: int = BARS_PER_DAY, rounds: int = 3) -> float:
    """Per-bar volatility that reproduces the observed daily range.

    Calibrating to the real range is what makes "today's data" mean anything
    here: a quiet day and a violent one produce genuinely different markets
    rather than the same generator with a different starting price.

    The random-walk formula only gives the first guess, and it comes out
    about 18% low -- the generator also has a session profile, mean reversion
    toward a slow anchor, and jumps, none of which that formula knows about.
    So the guess is then corrected against what the generator actually does,
    which is both more honest and less fragile than deriving a constant that
    would silently rot the next time the generator changes.
    """
    observed = max(0.0, day_high - day_low)
    if observed <= 0 or price <= 0:
        return simulate.MarketParams().base_vol

    sigma_abs = observed / (_RANGE_OVER_SIGMA * math.sqrt(bars))
    base_vol = sigma_abs / price

    for _ in range(rounds):
        produced = _median_range(price, base_vol, bars)
        if produced <= 0:
            break
        base_vol *= observed / produced
    return base_vol


@dataclass
class Session:
    index: int
    timestamp: float
    date_utc: str

    # What was looked up before the session, and where it came from.
    gold_price: float
    day_high: float
    day_low: float
    price_source: str

    start_equity_eur: float
    end_equity_eur: float
    lot: float

    # Risk per trade as a share of the account. Three numbers rather than
    # one, because with a fixed lot the amount risked is whatever the
    # predicted move happened to be -- measured at ten to one between the
    # smallest and largest trade in a single session. A mean alone hides
    # that, and the spread is the more dangerous fact.
    forced_risk_pct: float

    # The spread actually charged. Taken from an observed bid/ask when the
    # lookup gives one, because it is the one cost that is directly visible
    # in a quote -- and guessing it is unnecessary when it is right there.
    spread_usd_oz: float = 0.0
    # Slippage as a fraction of the spread. Recorded per session because it
    # changed mid-chain: sessions 1-9 were run before dayrange was brought
    # into line with the backtest engine and charged spread only. A ledger
    # that does not say which cost model produced a row cannot be compared
    # across the change.
    slippage_fraction: float = 0.0
    risk_pct_min: float = 0.0
    risk_pct_max: float = 0.0

    trades: int = 0
    wins: int = 0
    losses: int = 0
    signals: int = 0
    exits: dict[str, int] = field(default_factory=dict)
    expectancy_r: float = 0.0
    stopped_out: bool = False
    could_not_trade: str = ""
    # Release times the session stood aside for, as UTC (hour, minute).
    # Recorded because "the bot traded through FOMC" is only visible after
    # the fact if the session says which releases it knew about.
    news_times_utc: list[list[int]] = field(default_factory=list)
    # Every trade's R multiple, not just the session mean. Kept because the
    # session mean cannot be turned back into a confidence interval, and the
    # whole point of a chain is that the trades accumulate into a sample the
    # project's own statistics can then judge.
    r_multiples: list[float] = field(default_factory=list)
    # The largest drop from a running high *inside* the session. The chain's
    # own drawdown figure is measured close to close and therefore cannot
    # see any of this -- it reports what the account looked like once the
    # positions had resolved, not what holding them felt like.
    intraday_drawdown_pct: float = 0.0

    @property
    def pnl_eur(self) -> float:
        return self.end_equity_eur - self.start_equity_eur

    @property
    def return_pct(self) -> float:
        if self.start_equity_eur <= 0:
            return 0.0
        return self.pnl_eur / self.start_equity_eur * 100.0

    @property
    def breaks_the_risk_rule(self) -> bool:
        return self.forced_risk_pct > MAX_RISK_PER_TRADE_PCT

    @property
    def risk_spread_ratio(self) -> float:
        """How many times larger the biggest risk was than the smallest.

        With risk-based sizing this is 1.0 by construction. With a fixed lot
        it is whatever the market offered, and a session where it reaches
        ten means the account's result was decided by which trades happened
        to win, not by how many.
        """
        if self.risk_pct_min <= 0:
            return 1.0
        return self.risk_pct_max / self.risk_pct_min

    @property
    def expectancy_and_return_disagree(self) -> bool:
        """The session made money while trading badly, or the reverse.

        With every stake the same size these two cannot disagree: positive
        expectancy is positive money. They disagree exactly when the stakes
        differ, and then the account's result was set by which trades landed
        rather than by how the rules performed. Session 2 was +16.5% on
        +0.064R; session 4 was -2.5% on +0.050R. Same defect, both signs.
        """
        if not self.trades:
            return False
        return (self.expectancy_r > 0) != (self.pnl_eur > 0)


def sessions_so_far() -> int:
    if not os.path.exists(LEDGER_PATH):
        return 0
    with open(LEDGER_PATH, encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


def load_ledger() -> list[dict]:
    if not os.path.exists(LEDGER_PATH):
        return []
    out = []
    with open(LEDGER_PATH, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def current_equity_eur(start: float = 400.0) -> float:
    """Where the account stands. The compounding, in one function."""
    ledger = load_ledger()
    return ledger[-1]["end_equity_eur"] if ledger else start


def append(session: Session) -> None:
    os.makedirs(LEDGER_DIR, exist_ok=True)
    with open(LEDGER_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(session)) + "\n")


def check_quotes(quotes: dict[str, float],
                 tolerance_pct: float = 0.5) -> tuple[bool, str]:
    """Compare the prices several lookups returned before using one.

    Reuses `sources.prices.cross_check` rather than re-deriving the rule, so
    there is one definition of "these feeds disagree" in the project.

    This is not hypothetical here. One lookup in this session returned
    4114.79 from a CFD quote, 4047.47 from a physical dealer stamped hours
    earlier, and 4011.13 flagged as previous data -- a spread of over 100
    dollars. Picking one silently would have put a stale number into the
    ledger with no trace of the choice.
    """
    from .sources.prices import Quote, cross_check
    now = datetime.now(timezone.utc)
    return cross_check([Quote(symbol="XAUUSD", price=price, bid=None,
                              ask=None, ts=now, source=name)
                        for name, price in quotes.items()],
                       tolerance_pct=tolerance_pct)


def run_session(gold_price: float, day_high: float, day_low: float,
                price_source: str, start_equity_eur: float | None = None,
                cfg: DayRangeConfig | None = None,
                seed: int | None = None,
                spread_usd_oz: float | None = None,
                news_times_utc: tuple[tuple[int, int], ...] = ()) -> Session:
    """One trading day on an account carried forward from the last one."""
    index = sessions_so_far()
    equity_eur = (current_equity_eur() if start_equity_eur is None
                  else start_equity_eur)
    equity_usd = equity_eur * ASSUMED_EUR_USD
    oz = get_spec("XAUUSD").contract_size_oz

    # A fresh market every session, and never one seen before.
    seed = seed if seed is not None else 500_000 + index * 97

    base = cfg or DayRangeConfig()
    if spread_usd_oz is not None:
        base = replace(base, spread_usd_oz=spread_usd_oz)
    if news_times_utc:
        base = replace(base, news_times_utc=news_times_utc)
    params = simulate.MarketParams(
        start_price=gold_price,
        base_vol=calibrate_vol(gold_price, day_high, day_low),
    )
    series = simulate.generate(bars=BARS_PER_DAY, timeframe="1m", seed=seed,
                               params=params)

    # What a 400-euro account actually does: the broker minimum, because the
    # rule-abiding size is below it. Recorded, not hidden.
    session_cfg = replace(base, start_equity=equity_usd, lot=MIN_LOT,
                          risk_pct=None)

    margin_needed = MIN_LOT * oz * gold_price / session_cfg.leverage
    typical_stop_usd = 0.0
    could_not = ""

    stops_usd: list[float] = []
    if equity_usd < margin_needed:
        could_not = (f"margin {margin_needed:.0f} USD > equity "
                     f"{equity_usd:.0f} USD")
        result = None
    else:
        result = run(session_cfg, series=series, seed=seed)
        stops_usd = [d * base.stop_fraction / base.take_fraction
                     for d in result.target_distances]
        typical_stop_usd = statistics.fmean(stops_usd) if stops_usd else 0.0

    end_usd = result.end_equity if result else equity_usd

    def as_pct(stop_usd: float) -> float:
        return (MIN_LOT * oz * stop_usd / equity_usd * 100.0
                if equity_usd > 0 else 0.0)

    forced = as_pct(typical_stop_usd) if typical_stop_usd else 0.0
    risk_min = as_pct(min(stops_usd)) if stops_usd else 0.0
    risk_max = as_pct(max(stops_usd)) if stops_usd else 0.0

    return Session(
        index=index,
        timestamp=time.time(),
        date_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        gold_price=gold_price, day_high=day_high, day_low=day_low,
        price_source=price_source, spread_usd_oz=base.spread_usd_oz,
        slippage_fraction=base.slippage_fraction,
        start_equity_eur=round(equity_eur, 2),
        end_equity_eur=round(end_usd / ASSUMED_EUR_USD, 2),
        lot=MIN_LOT,
        forced_risk_pct=round(forced, 2),
        risk_pct_min=round(risk_min, 2),
        risk_pct_max=round(risk_max, 2),
        trades=result.trades if result else 0,
        wins=result.wins if result else 0,
        losses=result.losses if result else 0,
        signals=result.signals if result else 0,
        exits=dict(result.exits) if result else {},
        expectancy_r=round(result.expectancy_r, 4) if result else 0.0,
        stopped_out=bool(result.stopped_out) if result else False,
        could_not_trade=could_not,
        news_times_utc=[list(pair) for pair in base.news_times_utc],
        r_multiples=[round(x, 6) for x in result.r_multiples] if result else [],
        intraday_drawdown_pct=round(result.max_drawdown_pct, 2) if result else 0.0,
    )


@dataclass
class Distribution:
    returns_pct: list[float]
    equity_eur: float

    @property
    def median_pct(self) -> float:
        return statistics.median(self.returns_pct)

    @property
    def mean_pct(self) -> float:
        return statistics.fmean(self.returns_pct)

    @property
    def sd_points(self) -> float:
        return statistics.pstdev(self.returns_pct)

    @property
    def share_positive(self) -> float:
        return sum(1 for r in self.returns_pct if r > 0) / len(self.returns_pct)

    def percentile(self, q: float) -> float:
        ordered = sorted(self.returns_pct)
        idx = min(len(ordered) - 1, max(0, int(len(ordered) * q)))
        return ordered[idx]

    @property
    def streak_probability_3(self) -> float:
        """How ordinary a run of three winning days actually is.

        Worth computing before reading anything into one. At a 78% daily win
        rate three in a row happens about half the time, which is not
        evidence of anything at all.
        """
        return self.share_positive ** 3

    @property
    def implied_days_to_double(self) -> float | None:
        """The sanity check on the measurement, not on the strategy.

        If a daily median compounds to doubling the account inside a
        fortnight, the honest conclusion is that the market being measured
        is too easy -- not that a money machine has been found.
        """
        if self.median_pct <= 0:
            return None
        return math.log(2) / math.log(1 + self.median_pct / 100.0)


def distribution(gold_price: float, day_high: float, day_low: float,
                 equity_eur: float = 400.0, days: int = 60,
                 seed_base: int = 700_000) -> Distribution:
    """Many independent single days, rather than the few that happened.

    A compounded chain is one path. It cannot say whether a good run was
    typical, and the temptation to read a trend into three green days is
    exactly what this exists to defuse.
    """
    returns = [run_session(gold_price=gold_price, day_high=day_high,
                           day_low=day_low, price_source="distribution",
                           start_equity_eur=equity_eur,
                           seed=seed_base + i * 13).return_pct
               for i in range(days)]
    return Distribution(returns_pct=returns, equity_eur=equity_eur)


@dataclass
class VolatilityDependence:
    """How the day's range maps onto the day's result."""

    rows: list[tuple[float, float, float, float]]
    # range as % of price, median return %, mean return %, share positive

    @property
    def quietest(self) -> tuple[float, float, float, float]:
        return self.rows[0]

    @property
    def wildest(self) -> tuple[float, float, float, float]:
        return self.rows[-1]

    @property
    def return_multiple(self) -> float:
        """How many times larger the wide-day median is."""
        if self.quietest[1] <= 0:
            return float("inf")
        return self.wildest[1] / self.quietest[1]

    @property
    def range_multiple(self) -> float:
        return self.wildest[0] / self.quietest[0]

    @property
    def grows_faster_than_the_range(self) -> bool:
        """The signature that matters.

        A strategy whose return merely tracks volatility is sizing off
        volatility. One whose return grows *faster* than volatility is
        harvesting range -- and range is harvestable in a generator that
        mean-reverts within the day in a way real gold does not oblige.
        """
        return self.return_multiple > self.range_multiple


def volatility_dependence(
        gold_price: float,
        range_pcts: tuple[float, ...] = (0.6, 0.9, 1.2, 1.6, 2.0, 2.6, 3.2),
        equity_eur: float = 400.0, days: int = 40,
        seed_base: int = 800_000) -> VolatilityDependence:
    """Same rules, same account, only the day's range changed.

    This exists because the chain spent its first eleven sessions on 30 July
    -- an FOMC day with a 2.23% range against a typical 1.57% -- and the
    question "how much of the result was that choice" deserved a number
    rather than a caveat.
    """
    rows = []
    for i, pct in enumerate(range_pcts):
        span = gold_price * pct / 100.0
        d = distribution(gold_price=gold_price,
                         day_high=gold_price + span / 2,
                         day_low=gold_price - span / 2,
                         equity_eur=equity_eur, days=days,
                         seed_base=seed_base + i * 5_000)
        rows.append((pct, d.median_pct, d.mean_pct, d.share_positive))
    return VolatilityDependence(rows=rows)


def observed_ranges() -> list[tuple[str, float, int]]:
    """The distinct daily ranges this chain has actually looked up.

    Not a model of gold's volatility and not an assumption -- just the days
    whose high and low were fetched before a session and written into the
    ledger. Thin by construction, and it grows as the chain runs.

    Grouped by the range itself rather than by the quoted price: the same
    day gets looked up at slightly different prices as the session moves,
    and three rows for one day would read as three days of evidence.

    Returned as (date, range as % of price, how many sessions used it).
    """
    groups: dict[float, tuple[str, int]] = {}
    for e in load_ledger():
        price = e["gold_price"]
        if price <= 0:
            continue
        pct = round((e["day_high"] - e["day_low"]) / price * 100.0, 2)
        day, count = groups.get(pct, (e["date_utc"][:10], 0))
        groups[pct] = (day, count + 1)
    return sorted(((day, pct, n) for pct, (day, n) in groups.items()),
                  key=lambda row: row[1])


def project(days: int = 21, equity_eur: float | None = None,
            trials: int = 30) -> str:
    """What a month would look like -- for each kind of day seen so far.

    Deliberately not one number. The chain has established that the day's
    range is the largest single lever on the result, so a single projection
    would be a claim about which days happen next, which nobody has. What
    can honestly be given is the span: if every day were like this one, and
    if every day were like that one.
    """
    ranges = observed_ranges()
    if not ranges:
        return "Noch keine beobachteten Tagesspannen im Journal."

    start = current_equity_eur() if equity_eur is None else equity_eur
    lines = [f"HOCHRECHNUNG UEBER {days} HANDELSTAGE", "=" * 68]
    lines.append(f"  Start {start:,.2f} €")
    lines.append(f"  Grundlage: {len(ranges)} unterschiedliche Tagesspannen "
                 f"aus {sum(n for _, _, n in ranges)} Sitzungen")
    lines.append("")
    lines.append(f"  {'Tag':>12} {'Spanne':>8} {'Sitz.':>6} {'Median/Tag':>12} "
                 f"{'nach ' + str(days) + ' Tagen':>18}")
    lines.append("  " + "-" * 60)

    for day, pct, count in ranges:
        span = 4_100.0 * pct / 100.0
        d = distribution(gold_price=4_100.0, day_high=4_100.0 + span / 2,
                         day_low=4_100.0 - span / 2, equity_eur=start,
                         days=trials, seed_base=950_000)
        ending = start * (1 + d.median_pct / 100.0) ** days
        lines.append(f"  {day:>12} {pct:>7.2f}% {count:>6} "
                     f"{d.median_pct:>+11.2f}% {ending:>17,.0f} €")

    lines.append("")
    lines.append("  Das ist KEINE Prognose. Es ist die Spanne dessen, was")
    lines.append("  herauskaeme, wenn ein ganzer Monat aus lauter Tagen einer")
    lines.append("  Sorte bestuende. Welche Sorte kommt, weiss niemand.")
    lines.append("")
    lines.append("  Und alles davon steht auf dem Simulator. Der reale Test")
    lines.append("  ist der Backtest auf echter Historie.")
    return "\n".join(lines)


def render_volatility_dependence(v: VolatilityDependence) -> str:
    lines = ["ABHAENGIGKEIT VON DER TAGESSPANNE", "=" * 68]
    lines.append(f"  {'Spanne':>8} {'Median':>9} {'Mittel':>9} {'Tage im Plus':>14}")
    lines.append("  " + "-" * 44)
    for pct, median, mean, positive in v.rows:
        lines.append(f"  {pct:>7.1f}% {median:>+8.2f}% {mean:>+8.2f}% "
                     f"{positive * 100:>13.0f}%")
    lines.append("")
    lines.append(f"  Die Spanne waechst um das {v.range_multiple:.1f}-fache,")
    lines.append(f"  der Median um das {v.return_multiple:.1f}-fache.")
    if v.grows_faster_than_the_range:
        lines.append("")
        lines.append("  Der Ertrag waechst SCHNELLER als die Volatilitaet.")
        lines.append("  Das ist die Signatur einer Strategie, die Spanne")
        lines.append("  erntet — und Spanne laesst sich in einem Generator")
        lines.append("  ernten, der innerhalb des Tages zurueckkehrt. Echtes")
        lines.append("  Gold tut das nicht auf Bestellung.")
    lines.append("")
    lines.append("  Folge fuer die Kette: Welchen Tag sie wiederholt, ist")
    lines.append("  keine Nebensache, sondern der groesste einzelne Hebel")
    lines.append("  auf das Ergebnis.")
    return "\n".join(lines)


def render_distribution(d: Distribution) -> str:
    lines = [f"VERTEILUNG — {len(d.returns_pct)} UNABHAENGIGE HANDELSTAGE",
             "=" * 68]
    lines.append(f"  jeweils ab {d.equity_eur:,.2f} €, 0,01 Lot")
    lines.append("")
    lines.append(f"  Median            {d.median_pct:>+7.2f} %")
    lines.append(f"  Mittelwert        {d.mean_pct:>+7.2f} %")
    lines.append(f"  Streuung          {d.sd_points:>7.2f} Punkte")
    lines.append(f"  beste 5 %         {d.percentile(0.95):>+7.2f} %")
    lines.append(f"  schlechteste 5 %  {d.percentile(0.05):>+7.2f} %")
    lines.append(f"  schlechtester Tag {min(d.returns_pct):>+7.2f} %")
    lines.append(f"  Tage im Plus      {d.share_positive * 100:>7.0f} %")
    lines.append("")
    lines.append(f"  Drei Gewinntage in Folge: "
                 f"{d.streak_probability_3 * 100:.0f} % Wahrscheinlichkeit.")
    lines.append("  Eine Siegesserie ist hier also kein Signal, sondern der")
    lines.append("  Normalfall.")
    doubling = d.implied_days_to_double
    if doubling is not None and doubling < 30:
        lines.append("")
        lines.append(f"  WARNUNG: dieser Median verdoppelt das Konto in "
                     f"{doubling:.0f} Tagen.")
        lines.append("  Das tut niemand. Die Zahl sagt nicht, dass der Bot")
        lines.append("  eine Geldmaschine ist — sie sagt, dass der Simulator")
        lines.append("  zu leicht ist. Was hier gemessen wird, ist die")
        lines.append("  Streuung und das Verhalten der Regeln, nicht der")
        lines.append("  Ertrag.")
    return "\n".join(lines)


@dataclass
class VerifyResult:
    sessions: int
    chain_breaks: list[str] = field(default_factory=list)
    equity_mismatches: list[str] = field(default_factory=list)
    trade_mismatches: list[str] = field(default_factory=list)
    final_equity_eur: float = 0.0

    @property
    def ok(self) -> bool:
        return not (self.chain_breaks or self.equity_mismatches
                    or self.trade_mismatches)


def verify(start_equity_eur: float = 400.0,
           tolerance_eur: float = 0.02) -> VerifyResult:
    """Recompute every session from its own recorded inputs.

    A ledger nobody can re-derive is a claim, not a record. Each row stores
    the gold price, the day's range, the costs, the release times and the
    opening equity -- everything the session consumed -- so the whole chain
    can be replayed and checked against what it says happened.

    This matters more here than it would elsewhere: the ledger has been
    backfilled twice, once to add the spread of risk per trade and once
    after the r_multiples bug, and a backfill is exactly the operation that
    can quietly rewrite history into something that no longer follows from
    its inputs.

    Checks three things: that each session opened where the last one closed,
    that replaying it reproduces the recorded equity, and that it produces
    the recorded number of trades.
    """
    ledger = load_ledger()
    result = VerifyResult(sessions=len(ledger))
    if not ledger:
        return result

    base = DayRangeConfig()
    oz_equity = start_equity_eur
    for row in ledger:
        n = row["index"] + 1
        if abs(row["start_equity_eur"] - oz_equity) > tolerance_eur:
            result.chain_breaks.append(
                f"Sitzung {n}: startet bei {row['start_equity_eur']:.2f} €, "
                f"die vorige endete bei {oz_equity:.2f} €")

        params = simulate.MarketParams(
            start_price=row["gold_price"],
            base_vol=calibrate_vol(row["gold_price"], row["day_high"],
                                   row["day_low"]))
        seed = 500_000 + row["index"] * 97
        series = simulate.generate(bars=BARS_PER_DAY, timeframe="1m",
                                   seed=seed, params=params)
        cfg = replace(
            base, start_equity=row["start_equity_eur"] * ASSUMED_EUR_USD,
            lot=MIN_LOT, risk_pct=None,
            spread_usd_oz=row.get("spread_usd_oz") or base.spread_usd_oz,
            slippage_fraction=row.get("slippage_fraction", 0.0),
            news_times_utc=tuple(tuple(x)
                                 for x in row.get("news_times_utc", [])))
        res = run(cfg, series=series, seed=seed)

        recomputed = round(res.end_equity / ASSUMED_EUR_USD, 2)
        if abs(recomputed - row["end_equity_eur"]) > tolerance_eur:
            result.equity_mismatches.append(
                f"Sitzung {n}: protokolliert {row['end_equity_eur']:.2f} €, "
                f"nachgerechnet {recomputed:.2f} €")
        if res.trades != row["trades"]:
            result.trade_mismatches.append(
                f"Sitzung {n}: protokolliert {row['trades']} Trades, "
                f"nachgerechnet {res.trades}")
        oz_equity = row["end_equity_eur"]

    result.final_equity_eur = oz_equity
    return result


def render_verify(v: VerifyResult) -> str:
    lines = [f"PAPIER-LAUF — JOURNAL NACHGERECHNET", "=" * 68]
    if not v.sessions:
        lines.append("  Kein Journal vorhanden.")
        return "\n".join(lines)

    lines.append(f"  {v.sessions} Sitzungen aus ihren eigenen Eingaben "
                 f"neu gerechnet")
    lines.append("")
    for label, items in (("Kette unterbrochen", v.chain_breaks),
                         ("Kontostand weicht ab", v.equity_mismatches),
                         ("Tradezahl weicht ab", v.trade_mismatches)):
        if items:
            lines.append(f"  {label}: {len(items)}")
            for item in items[:5]:
                lines.append(f"    {item}")
            if len(items) > 5:
                lines.append(f"    ... und {len(items) - 5} weitere")
    if v.ok:
        lines.append("  Keine Abweichung. Jede Zeile folgt aus ihren Eingaben,")
        lines.append("  und jede Sitzung beginnt, wo die vorige endete.")
        lines.append("")
        lines.append(f"  Endstand: {v.final_equity_eur:,.2f} €")
    else:
        lines.append("")
        lines.append("  Das Journal beschreibt etwas, das so nicht")
        lines.append("  herausgekommen waere. Vor jeder weiteren Auswertung")
        lines.append("  klaeren.")
    return "\n".join(lines)


def design_effect(groups: list[list[float]]) -> tuple[float, float]:
    """How much the confidence interval is inflated by clustering.

    Every interval in this module treats the trades as independent draws.
    They are not obviously so: trades inside one session share a market, and
    if that made them alike, the effective sample would be smaller than the
    count and the band narrower than it deserves.

    So it is measured rather than assumed, by a one-way analysis of
    variance. Returns (intraclass correlation, design effect); an effect of
    1.0 means the clustering costs nothing and n is n.

    Measured on the chain at twenty sessions: ICC 0.00, effect 1.00. The
    between-session variance came out *below* the within-session variance,
    which is the same mechanism claim C3 found -- R multiples are normalised
    by their own stop, so a session's volatility largely divides out and
    sessions stop being distinguishable.
    """
    groups = [g for g in groups if g]
    n_total = sum(len(g) for g in groups)
    k = len(groups)
    if k < 2 or n_total <= k:
        return 0.0, 1.0

    m = n_total / k
    grand = statistics.fmean([r for g in groups for r in g])
    ss_between = sum(len(g) * (statistics.fmean(g) - grand) ** 2 for g in groups)
    ss_within = sum((r - statistics.fmean(g)) ** 2
                    for g in groups for r in g)
    ms_between = ss_between / (k - 1)
    ms_within = ss_within / (n_total - k)
    if ms_between + (m - 1) * ms_within <= 0:
        return 0.0, 1.0
    icc = max(0.0, (ms_between - ms_within)
              / (ms_between + (m - 1) * ms_within))
    return icc, 1.0 + (m - 1) * icc


def evidence() -> str:
    """What the accumulated trades support, judged by the project's own rules.

    The chain reports euro. Euro on a compounding account flatter a good run
    and cannot be compared across account sizes, so the question "does this
    work" has to be asked of the R multiples -- and asked with a band, using
    the same `metals.journal` statistics the EA's journal is read with. One
    definition of evidence for both, or the paper chain quietly gets an
    easier standard than the live one.
    """
    from .journal import (MIN_TRADES_FOR_A_BREAKDOWN, REFERENCE_EDGE_R,
                          mean_and_sd, mean_interval,
                          multiple_comparison_risk, trades_needed,
                          wilson_interval)

    ledger = load_ledger()
    rs = [r for e in ledger for r in e.get("r_multiples", [])]
    if not rs:
        return "Noch keine Trades mit R-Werten im Journal."

    wins = sum(1 for r in rs if r > 0)
    mean, sd = mean_and_sd(rs)
    lo, hi = mean_interval(rs)
    wlo, whi = wilson_interval(wins, len(rs))

    lines = [f"PAPIER-LAUF — WAS {len(rs)} TRADES BELEGEN", "=" * 68]

    # The sample is only one sample if every trade in it was priced the same
    # way. It was not: dayrange charged spread alone until session 10 and
    # spread x 1.5 after. Small (about 6.5% of expectancy) and disclosed
    # rather than quietly averaged over.
    models = sorted({e.get("slippage_fraction", 0.0)
                     for e in ledger if e.get("r_multiples")})
    if len(models) > 1:
        lines.append(f"  Hinweis: die Stichprobe umfasst "
                     f"{len(models)} Kostenmodelle "
                     f"({', '.join(f'{m:.0%} Slippage' for m in models)}).")
        lines.append("  Sie ist damit streng genommen nicht homogen — der")
        lines.append("  Unterschied liegt bei rund 6,5 % des Erwartungswerts.")
        lines.append("")
    lines.append(f"  Trefferquote      {wins / len(rs) * 100:>6.1f} %   "
                 f"95%-Band {wlo * 100:.0f} bis {whi * 100:.0f} %")
    lines.append(f"  Erwartungswert    {mean:>+6.3f} R   "
                 f"95%-Band {lo:+.3f} bis {hi:+.3f} R")
    lines.append(f"  Streuung          {sd:>6.3f} R")

    icc, deff = design_effect([e.get("r_multiples", []) for e in ledger])
    if deff > 1.2:
        lines.append("")
        lines.append(f"  Trades derselben Sitzung aehneln sich (ICC {icc:.2f}).")
        lines.append(f"  Die effektive Stichprobe ist deshalb nur "
                     f"{len(rs) / deff:.0f} statt {len(rs)},")
        lines.append("  und das Band oben ist entsprechend zu schmal.")
    else:
        lines.append(f"  Sitzungs-Clustering geprueft: ICC {icc:.2f}, "
                     f"Effekt {deff:.2f} — n ist n.")
    lines.append("")

    if lo <= 0 <= hi:
        lines.append("  Das Band schliesst die Null ein. Diese Stichprobe")
        lines.append("  belegt keinen Vorteil — sie schliesst ihn auch nicht")
        lines.append("  aus. Sie sagt nur: noch nicht genug Trades.")
    elif lo > 0:
        lines.append("  Das Band liegt ueber der Null. Auf DIESEN Daten ist")
        lines.append("  der Vorteil messbar — auf dem Simulator, der die")
        lines.append("  Struktur enthaelt, die die Strategie sucht.")
        lines.append("")
        # The band clearing zero right after several looks at a growing
        # sample is the moment to be most careful, not least. Repeatedly
        # checking and stopping when it finally reads well is how a 95%
        # interval stops being 95%.
        looks = len(ledger)
        risk = multiple_comparison_risk(looks)
        lines.append(f"  ABER: diese Auswertung wurde waehrend des Laufs "
                     f"mehrfach")
        lines.append(f"  angesehen. Bei {looks} Gelegenheiten liegt die Chance, "
                     f"dass ein")
        lines.append(f"  Band irgendwann zufaellig ueber der Null steht, bei "
                     f"bis zu")
        lines.append(f"  {risk * 100:.0f} % — nicht bei 5 %. Wer hinschaut, bis "
                     f"es passt, hat")
        lines.append("  nichts gemessen, sondern gewartet.")
        lines.append("")
        lines.append("  Das Gegenmittel ist, die Stichprobengroesse VORHER")
        lines.append("  festzulegen und erst dann zu urteilen.")
    else:
        lines.append("  Das Band liegt unter der Null.")

    need = trades_needed(mean, sd)
    if need is not None:
        per_session = len(rs) / max(1, len(ledger))
        lines.append("")
        lines.append(f"  Fuer einen Nachweis DIESER Kantengroesse braeuchte es")
        lines.append(f"  rund {need:,} Trades. Vorhanden: {len(rs)}.")
        if need > len(rs):
            lines.append(f"  Bei {per_session:.0f} Trades je Sitzung sind das "
                         f"noch etwa {(need - len(rs)) / per_session:.0f} "
                         f"Sitzungen.")

        # The observed mean is upward-biased: a run that happened to go well
        # produces a large mean, and a sample size computed from it says the
        # proof is nearly done. The journal module reports against a modest
        # reference edge for exactly this reason, and the paper chain has to
        # use the same yardstick or it flatters itself in the same way.
        modest = trades_needed(REFERENCE_EDGE_R, sd)
        if modest is not None and modest > need:
            lines.append("")
            lines.append(f"  Vorsicht: {need:,} folgt aus dem BEOBACHTETEN "
                         f"Mittelwert,")
            lines.append(f"  und der ist nach oben verzerrt — ein Lauf, der gut")
            lines.append(f"  lief, laesst den Nachweis fast fertig aussehen.")
            lines.append(f"  Fuer einen nuechternen Vorteil von "
                         f"{REFERENCE_EDGE_R:+.2f}R waeren es")
            remaining = max(0.0, (modest - len(rs)) / per_session)
            if remaining <= 0:
                lines.append(f"  rund {modest:,} Trades — und die sind "
                             f"erreicht.")
            else:
                lines.append(f"  rund {modest:,} Trades, also etwa "
                             f"{remaining:.0f} weitere Sitzungen.")
    if len(rs) < MIN_TRADES_FOR_A_BREAKDOWN:
        lines.append("")
        lines.append(f"  Unter {MIN_TRADES_FOR_A_BREAKDOWN} Trades wird hier")
        lines.append("  bewusst nichts aufgeschluesselt.")
    return "\n".join(lines)


def render(s: Session) -> str:
    lines = [f"PAPIER-LAUF — SITZUNG {s.index + 1}", "=" * 68]
    lines.append(f"  {s.date_utc} UTC")
    span_pct = ((s.day_high - s.day_low) / s.gold_price * 100.0
                if s.gold_price else 0.0)
    lines.append(f"  Gold {s.gold_price:,.2f} $/oz  ·  Tagesspanne "
                 f"{s.day_low:,.2f}–{s.day_high:,.2f} "
                 f"({s.day_high - s.day_low:,.2f} $ = {span_pct:.2f} %)")
    ratio = span_pct / TYPICAL_DAY_RANGE_PCT if TYPICAL_DAY_RANGE_PCT else 1.0
    if ratio >= 1.35 or ratio <= 0.65:
        louder = "volatiler" if ratio > 1 else "ruhiger"
        lines.append(f"  ACHTUNG, untypischer Tag: das {ratio:.2f}-fache "
                     f"eines normalen ({TYPICAL_DAY_RANGE_PCT:.2f} %),")
        lines.append(f"  also deutlich {louder}. Das Ergebnis dieser Sitzung")
        lines.append(f"  beschreibt einen solchen Tag, nicht den Normalfall.")
    lines.append(f"  Spread {s.spread_usd_oz:.2f} $/oz "
                 f"+ {s.slippage_fraction:.0%} Slippage "
                 f"= {s.spread_usd_oz * (1 + s.slippage_fraction):.2f} $ "
                 f"Einstiegskosten")
    if s.news_times_utc:
        times = ", ".join(f"{h:02d}:{m:02d}" for h, m in s.news_times_utc)
        lines.append(f"  Nachrichtensperre (R4) um {times} UTC")
    else:
        lines.append("  Keine Nachrichtensperre gesetzt — R4 greift nicht")
    lines.append(f"  Quelle: {s.price_source}")
    lines.append("")
    if s.could_not_trade:
        lines.append(f"  KEIN TRADE MOEGLICH: {s.could_not_trade}")
        lines.append(f"  Konto unveraendert bei {s.end_equity_eur:,.2f} €")
        return "\n".join(lines)

    lines.append(f"  Start   {s.start_equity_eur:>10,.2f} €")
    lines.append(f"  Ende    {s.end_equity_eur:>10,.2f} €")
    lines.append(f"  Ergebnis{s.pnl_eur:>+10,.2f} € "
                 f"({s.return_pct:+.2f} %)")
    if s.intraday_drawdown_pct > 0:
        lines.append(f"  Unterwegs{-s.intraday_drawdown_pct:>+10.2f} %"
                     f"   groesster Rueckgang vom Hoch innerhalb der Sitzung")
    lines.append("")
    lines.append(f"  Signale {s.signals:>10}")
    lines.append(f"  Trades  {s.trades:>10}   "
                 f"{s.wins} gewonnen / {s.losses} verloren")
    if s.trades:
        lines.append(f"  Treffer {s.wins / s.trades * 100:>9.1f} %")
        lines.append(f"  Erwartung {s.expectancy_r:>+8.3f} R")
    if s.exits:
        lines.append("  Ausstiege: " + ", ".join(
            f"{k} {v}" for k, v in sorted(s.exits.items())))
    lines.append("")
    lines.append(f"  Risiko je Trade  {s.forced_risk_pct:>6.1f} % im Mittel"
                 f"   (Regel R1: {MAX_RISK_PER_TRADE_PCT:.0f} %)")
    if s.risk_pct_max > 0:
        lines.append(f"                   {s.risk_pct_min:>6.1f} % bis "
                     f"{s.risk_pct_max:.1f} %  "
                     f"(Faktor {s.risk_spread_ratio:.1f})")
    if s.breaks_the_risk_rule:
        lines.append("  Ueber dem Limit, und zwar erzwungen: 0,01 Lot ist die")
        lines.append("  kleinste Position, die es auf Gold gibt.")
    if s.expectancy_and_return_disagree:
        lines.append("")
        direction = ("gewonnen, obwohl die Regeln schlecht liefen"
                     if s.pnl_eur > 0 else
                     "verloren, obwohl die Regeln gut liefen")
        lines.append(f"  Das Konto hat {direction}.")
        lines.append("  Erwartungswert und Ergebnis haben verschiedene")
        lines.append("  Vorzeichen — das geht nur, wenn die Einsaetze")
        lines.append("  unterschiedlich gross waren.")
    if s.risk_spread_ratio >= 3.0:
        lines.append("  ACHTUNG, ungleiche Einsaetze: bei")
        lines.append("  fester Losgroesse riskiert jeder Trade so viel, wie die")
        lines.append("  vorhergesagte Bewegung gross war — unkontrolliert.")
        lines.append("  Das Ergebnis der Sitzung haengt dann daran, WELCHE")
        lines.append("  Trades gewonnen haben, nicht wie viele.")
    if s.stopped_out:
        lines.append("  BROKER-STOP-OUT in dieser Sitzung.")
    return "\n".join(lines)


@dataclass
class Block:
    """A group of consecutive sessions, summarised."""

    first: int                 # 1-based session number
    last: int
    start_equity_eur: float
    end_equity_eur: float
    trades: int
    wins: int
    losses: int
    expectancy_r: float
    mean_risk_pct: float
    sessions_up: int

    @property
    def pnl_eur(self) -> float:
        return self.end_equity_eur - self.start_equity_eur

    @property
    def return_pct(self) -> float:
        if self.start_equity_eur <= 0:
            return 0.0
        return self.pnl_eur / self.start_equity_eur * 100.0

    @property
    def win_rate(self) -> float:
        return self.wins / self.trades if self.trades else 0.0


def blocks(size: int = 5) -> list[Block]:
    """The chain in groups, so a trend is visible without reading 36 lines.

    Grouping hides single-session noise, which is the point -- and it also
    hides single-session disasters, which is why the block still carries the
    number of losing sessions inside it.
    """
    ledger = load_ledger()
    out: list[Block] = []
    for start in range(0, len(ledger), size):
        group = ledger[start:start + size]
        trades = sum(e["trades"] for e in group)
        traded = [e for e in group if e["trades"]]
        out.append(Block(
            first=start + 1,
            last=start + len(group),
            start_equity_eur=group[0]["start_equity_eur"],
            end_equity_eur=group[-1]["end_equity_eur"],
            trades=trades,
            wins=sum(e["wins"] for e in group),
            losses=sum(e["losses"] for e in group),
            expectancy_r=(statistics.fmean([e["expectancy_r"] for e in traded])
                          if traded else 0.0),
            mean_risk_pct=(statistics.fmean([e["forced_risk_pct"]
                                             for e in traded])
                           if traded else 0.0),
            sessions_up=sum(1 for e in group
                            if e["end_equity_eur"] > e["start_equity_eur"]),
        ))
    return out


def render_blocks(size: int = 5) -> str:
    bs = blocks(size)
    if not bs:
        return "Noch keine Papier-Sitzungen."

    lines = [f"UEBERBLICK — {bs[-1].last} SITZUNGEN IN {size}er-SCHRITTEN",
             "=" * 78]
    lines.append(f"  {'Sitzungen':>10} {'Konto von':>11} {'auf':>10} "
                 f"{'Ergebnis':>10} {'%':>8} {'Trades':>7} {'Treffer':>8} "
                 f"{'Erwart.':>8}")
    lines.append("  " + "-" * 74)
    for b in bs:
        span = f"{b.first}-{b.last}" if b.last > b.first else f"{b.first}"
        lines.append(
            f"  {span:>10} {b.start_equity_eur:>11,.2f} "
            f"{b.end_equity_eur:>10,.2f} {b.pnl_eur:>+10,.2f} "
            f"{b.return_pct:>+7.1f}% {b.trades:>7} "
            f"{b.win_rate * 100:>7.1f}% {b.expectancy_r:>+7.3f}R")
    lines.append("  " + "-" * 74)
    total_trades = sum(b.trades for b in bs)
    total_wins = sum(b.wins for b in bs)
    first, last = bs[0], bs[-1]
    lines.append(
        f"  {'gesamt':>10} {first.start_equity_eur:>11,.2f} "
        f"{last.end_equity_eur:>10,.2f} "
        f"{last.end_equity_eur - first.start_equity_eur:>+10,.2f} "
        f"{(last.end_equity_eur / first.start_equity_eur - 1) * 100:>+7.1f}% "
        f"{total_trades:>7} {total_wins / total_trades * 100:>7.1f}%")
    lines.append("")
    down = sum(b.last - b.first + 1 - b.sessions_up for b in bs)
    lines.append(f"  Verlustsitzungen: {down} von {bs[-1].last}")
    lines.append(f"  Risiko je Trade: {bs[0].mean_risk_pct:.1f} % im ersten "
                 f"Block, {bs[-1].mean_risk_pct:.1f} % im letzten")
    lines.append("  (faellt, weil 0,01 Lot bei wachsendem Konto ein kleinerer")
    lines.append("   Anteil davon ist — nicht weil der Bot vorsichtiger wird)")
    lines.append("")
    lines.append("  ACHTUNG: Eine Sitzung ist ein simulierter HANDELSTAG, keine")
    lines.append("  Stunde. Und der Markt ist erzeugt, nicht echt. Warum diese")
    lines.append("  Kurve nichts ueber echtes Gold sagt: docs/URTEIL.md.")
    return "\n".join(lines)


def summarise() -> str:
    """The chain so far. The only number that compounds is the last one."""
    ledger = load_ledger()
    if not ledger:
        return "Noch keine Papier-Sitzungen."

    start = ledger[0]["start_equity_eur"]
    end = ledger[-1]["end_equity_eur"]
    pnls = [e["end_equity_eur"] - e["start_equity_eur"] for e in ledger]
    equities = [e["end_equity_eur"] for e in ledger]
    traded = [e for e in ledger if e["trades"]]

    peak, max_dd = start, 0.0
    for eq in equities:
        peak = max(peak, eq)
        if peak > 0:
            max_dd = max(max_dd, (peak - eq) / peak)

    lines = [f"PAPIER-LAUF — {len(ledger)} SITZUNGEN", "=" * 68]
    lines.append(f"  Start   {start:>10,.2f} €")
    lines.append(f"  Jetzt   {end:>10,.2f} €")
    lines.append(f"  Gesamt  {end - start:>+10,.2f} € "
                 f"({(end / start - 1) * 100:+.1f} %)")
    lines.append("")
    lines.append(f"  Groesster Rueckgang vom Hoch   {max_dd * 100:>6.1f} %"
                 f"   (Schluss zu Schluss)")
    intraday = [e.get("intraday_drawdown_pct", 0.0) for e in ledger]
    if any(intraday):
        lines.append(f"  ... innerhalb einer Sitzung     "
                     f"{max(intraday):>6.1f} %   (schlimmster Tag)")
    lines.append(f"  Sitzungen im Plus              "
                 f"{sum(1 for p in pnls if p > 0):>6} von {len(pnls)}")
    if traded:
        lines.append(f"  Trades gesamt                  "
                     f"{sum(e['trades'] for e in traded):>6}")
        risks = [e["forced_risk_pct"] for e in traded if e["forced_risk_pct"]]
        if risks:
            lines.append(f"  Risiko je Trade im Mittel      "
                         f"{statistics.fmean(risks):>6.1f} %")
        if len(traded) >= 3:
            first, last = traded[0], traded[-1]
            if first["forced_risk_pct"] > 0 and last["forced_risk_pct"] > 0:
                lines.append(f"  Risiko am Anfang / zuletzt     "
                             f"{first['forced_risk_pct']:>6.1f} % / "
                             f"{last['forced_risk_pct']:.1f} %")
                if last["forced_risk_pct"] < first["forced_risk_pct"]:
                    lines.append("    Das Lot blieb fest, das Konto wuchs — also")
                    lines.append("    faellt der Einsatzanteil von selbst. Wer das")
                    lines.append("    Lot mitwachsen laesst, gibt genau das auf.")
        lows = [e.get("risk_pct_min", 0.0) for e in traded]
        highs = [e.get("risk_pct_max", 0.0) for e in traded]
        lows = [x for x in lows if x > 0]
        if lows and any(highs):
            lines.append(f"  Kleinster / groesster Einsatz  "
                         f"{min(lows):>6.1f} % / {max(highs):.1f} %")
        disagreed = sum(
            1 for e in traded
            if e["trades"] and (e["expectancy_r"] > 0)
            != (e["end_equity_eur"] > e["start_equity_eur"]))
        if disagreed:
            # The unequal-stakes problem, counted across the whole chain
            # rather than noted session by session. A bare label was not
            # enough: this is the number that says how often the account
            # moved the opposite way to the quality of the trading.
            lines.append(f"  Konto lief gegen die Regelguete  "
                         f"{disagreed:>4} von {len(traded)} "
                         f"({disagreed / len(traded) * 100:.0f} %)")
            lines.append("    In diesen Sitzungen hatten Erwartungswert und")
            lines.append("    Kontostand verschiedene Vorzeichen. Das geht nur")
            lines.append("    bei ungleichen Einsaetzen — es entschied, WELCHE")
            lines.append("    Trades gewannen, nicht wie viele.")
    idle = [e for e in ledger if e["could_not_trade"]]
    if idle:
        lines.append(f"  Sitzungen ohne Trade           {len(idle):>6}")
    lines.append("")
    if len(ledger) < 20:
        lines.append("  Unter zwanzig Sitzungen ist das eine Anekdote. Eine")
        lines.append("  Kette sagt, wie sich die Streuung anfuehlt, nicht ob")
        lines.append("  die Strategie einen Vorteil hat.")
    return "\n".join(lines)
