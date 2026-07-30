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


def run_session(gold_price: float, day_high: float, day_low: float,
                price_source: str, start_equity_eur: float | None = None,
                cfg: DayRangeConfig | None = None,
                seed: int | None = None,
                spread_usd_oz: float | None = None) -> Session:
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


def render(s: Session) -> str:
    lines = [f"PAPIER-LAUF — SITZUNG {s.index + 1}", "=" * 68]
    lines.append(f"  {s.date_utc} UTC")
    lines.append(f"  Gold {s.gold_price:,.2f} $/oz  ·  Tagesspanne "
                 f"{s.day_low:,.2f}–{s.day_high:,.2f} "
                 f"({s.day_high - s.day_low:,.2f} $)")
    lines.append(f"  Spread {s.spread_usd_oz:.2f} $/oz")
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
        lines.append("  ACHTUNG: die Einsaetze liegen weit auseinander. Bei")
        lines.append("  fester Losgroesse riskiert jeder Trade so viel, wie die")
        lines.append("  vorhergesagte Bewegung gross war — unkontrolliert.")
        lines.append("  Das Ergebnis der Sitzung haengt dann daran, WELCHE")
        lines.append("  Trades gewonnen haben, nicht wie viele.")
    if s.stopped_out:
        lines.append("  BROKER-STOP-OUT in dieser Sitzung.")
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
    lines.append(f"  Groesster Rueckgang vom Hoch   {max_dd * 100:>6.1f} %")
    lines.append(f"  Sitzungen im Plus              "
                 f"{sum(1 for p in pnls if p > 0):>6} von {len(pnls)}")
    if traded:
        lines.append(f"  Trades gesamt                  "
                     f"{sum(e['trades'] for e in traded):>6}")
        risks = [e["forced_risk_pct"] for e in traded if e["forced_risk_pct"]]
        if risks:
            lines.append(f"  Risiko je Trade im Mittel      "
                         f"{statistics.fmean(risks):>6.1f} %")
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
            lines.append(f"  Ergebnis gegen Erwartungswert  {disagreed:>6} von "
                         f"{len(traded)}")
    idle = [e for e in ledger if e["could_not_trade"]]
    if idle:
        lines.append(f"  Sitzungen ohne Trade           {len(idle):>6}")
    lines.append("")
    if len(ledger) < 20:
        lines.append("  Unter zwanzig Sitzungen ist das eine Anekdote. Eine")
        lines.append("  Kette sagt, wie sich die Streuung anfuehlt, nicht ob")
        lines.append("  die Strategie einen Vorteil hat.")
    return "\n".join(lines)
