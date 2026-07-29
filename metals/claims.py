"""What the gold-bot videos and articles claim -- and what survives a test.

The research pass behind this module read through the public material on
gold scalping bots: YouTube EA reviews and "90% win rate" strategy videos,
vendor product pages, broker and prop-firm education blogs, the MQL5 forums,
regulator disclosures and the academic literature on day-trading outcomes.

Taking that "into the bot's knowledge" as prose would be worthless, because
almost all of it is marketing and marketing is not knowledge. What is worth
keeping is the subset that makes a **falsifiable statement** -- and every one
of those is measured here rather than repeated.

Three source classes, kept apart on purpose:

``vendor``
    The seller of the thing. A backtest curve on a product page, a YouTube
    thumbnail with a win rate on it. Treated as a hypothesis, never a fact.
``editorial``
    Broker blogs, trading-education sites, forum posts. Often correct on
    mechanics (spreads, sessions, execution) because those are checkable,
    and unreliable on outcomes because nobody audits them.
``regulatory`` / ``academic``
    Numbers somebody was legally or professionally accountable for. These
    are the only ones quoted as fact -- and even then as a base rate about a
    population, not a prediction about one account.

The single most useful finding is C1, and it is the reason this module
exists: **a 90% win rate is purchasable**. Widen the stop, shrink the target,
and the win rate goes wherever you want it while the expectancy does not
improve at all. Every headline number in that genre of video is therefore
uninformative on its own, and `measure_win_rate_is_not_an_edge` demonstrates
this on demand rather than asserting it.

    python -m metals claims

**What these measurements are worth.** They run on the synthetic market in
`metals.simulate`, which reproduces documented statistical properties of gold
and not gold itself. That is enough to settle claims about *arithmetic and
cost* -- C1, C2 and C4 are true of any market with a spread -- and not enough
to settle claims about *behaviour*. C3 is flagged accordingly: the simulator
was built with a session volatility profile in it, so finding one there is
partly finding what was placed.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, replace

from . import simulate
from .candles import resample
from .dayrange import DayRangeConfig, Sweep, run, sweep

# The London/New York overlap in UTC. Quoted everywhere as 8:00-12:00 ET,
# which is 12:00-16:00 UTC outside the daylight-saving mismatch weeks.
OVERLAP_HOURS_UTC: tuple[int, ...] = (12, 13, 14, 15)
# The Asian session, the hours the same articles say to avoid.
ASIA_HOURS_UTC: tuple[int, ...] = (0, 1, 2, 3, 4, 5)

# Spread in USD per ounce. The trade press quotes gold spreads in "pips" of
# 0.01 USD: 12-17 pips on an ECN account, 30-50 on a standard one.
ECN_SPREAD_USD_OZ = 0.15
STANDARD_SPREAD_USD_OZ = 0.40


@dataclass(frozen=True)
class Claim:
    id: str
    text: str
    source: str
    kind: str            # vendor | editorial | regulatory | academic
    testable: bool
    note: str = ""


# The catalogue. Deliberately includes the untestable ones: knowing that a
# claim cannot be checked here is itself worth recording, and it stops the
# same claim being quietly promoted to a fact later.
CLAIMS: tuple[Claim, ...] = (
    Claim("C1", "90% win rate scalping bot / strategy",
          "YouTube EA and strategy videos, passim", "vendor", True,
          "The claim is usually true and always uninformative."),
    Claim("C2", "A gold scalper loses its edge on a wide-spread account; "
                "ECN 12-17 pips vs standard 30-50 pips",
          "Broker and EA-review blogs", "editorial", True),
    Claim("C3", "Trade the London/New York overlap, avoid the Asian session",
          "Broker education blogs, near-unanimous", "editorial", True,
          "Partly circular here: the simulator has a session profile in it."),
    Claim("C4", "M1 is too noisy; M5 or M15 is the better scalping chart",
          "Trading-education sites", "editorial", True),
    Claim("C5", "Grid and martingale EAs produce long winning streaks and "
                "then take the account to zero",
          "MQL5 forum posts, EA reviews", "editorial", True,
          "Measured in metals/microscalp.py, not repeated here."),
    Claim("C6", "74-89% of retail CFD accounts lose money",
          "ESMA product intervention, broker risk warnings", "regulatory",
          False, "A base rate for the population, not a forecast for one."),
    Claim("C7", "About 1% of day traders are persistently profitable net of "
                "costs; of Brazilian futures day traders who persisted past "
                "300 sessions, 97% lost money",
          "Barber/Lee/Liu/Odean (Taiwan, 1992-2006); Chague/De-Losso/"
          "Giovannetti (Brazil, 2013-2015)", "academic", False,
          "Equities and index futures, not gold CFDs, and about humans "
          "rather than about a bot. Carried as the base rate it is."),
    Claim("C8", "Gold spreads widen from 1-2 to 15-20 pips in the first "
                "minute after CPI/NFP, with slippage on top",
          "Broker education blogs, consistent across sources", "editorial",
          False, "Needs tick data with a news calendar; the news block "
                 "(rule R4) already assumes it."),
    Claim("C9", "'99% modelling quality' in the MT5 tester does not mean "
                "the result is realistic; generated ticks flatter entries "
                "that touch a price",
          "MQL5 forums, tester guides", "editorial", False,
          "Applies to the EA's own backtest, once run on the PC."),
    Claim("C10", "A minimum deposit around 1,000 USD is needed for gold "
                 "scalping at 0.01-0.10 lot",
          "EA product pages", "vendor", True,
          "Checkable as arithmetic: margin at the legal leverage cap."),
)


def find(claim_id: str) -> Claim:
    for c in CLAIMS:
        if c.id == claim_id:
            return c
    raise KeyError(claim_id)


# --------------------------------------------------------------------------
# C1 -- a win rate is a dial, not a result
# --------------------------------------------------------------------------

@dataclass
class WinRateFinding:
    best_win_rate: float
    its_expectancy_r: float
    its_median_return_pct: float
    its_take: float
    its_stop: float
    its_worst_return_pct: float
    baseline_win_rate: float
    baseline_expectancy_r: float
    baseline_worst_return_pct: float

    @property
    def buying_a_win_rate_costs_expectancy(self) -> bool:
        return self.its_expectancy_r <= self.baseline_expectancy_r

    @property
    def buying_a_win_rate_costs_tail(self) -> bool:
        """The part a win rate actively hides.

        Pushing the win rate up means a distant stop, so the rare loser is
        enormous. The average can survive that; the worst market does not.
        """
        return self.its_worst_return_pct < self.baseline_worst_return_pct


def measure_win_rate_is_not_an_edge(markets: int = 20, bars: int = 12_000,
                                    seed_base: int = 7_000) -> WinRateFinding:
    """Search for the highest win rate the same strategy can be made to show.

    Nothing about the market changes. Only the ratio between target and stop
    moves, which is the one dial that trades win rate against reward per
    trade. If the highest win rate available also has the worst expectancy,
    then a headline win rate carries no information about whether a bot
    makes money -- which is the claim.
    """
    base = DayRangeConfig()
    baseline = sweep(base, markets=markets, bars=bars, seed_base=seed_base)

    best: tuple[float, Sweep, float, float] | None = None
    for take in (0.05, 0.10, 0.20, 0.35, 0.50):
        for stop in (1.00, 1.50, 2.00, 3.00):
            cfg = replace(base, take_fraction=take, stop_fraction=stop)
            s = sweep(cfg, markets=markets, bars=bars, seed_base=seed_base)
            if s.mean_trades < 5:
                continue
            if best is None or s.mean_win_rate > best[0]:
                best = (s.mean_win_rate, s, take, stop)

    assert best is not None, "no configuration produced enough trades"
    rate, s, take, stop = best
    return WinRateFinding(
        best_win_rate=rate,
        its_expectancy_r=s.mean_expectancy_r,
        its_median_return_pct=s.median_return_pct,
        its_take=take, its_stop=stop,
        its_worst_return_pct=s.worst_return_pct,
        baseline_win_rate=baseline.mean_win_rate,
        baseline_expectancy_r=baseline.mean_expectancy_r,
        baseline_worst_return_pct=baseline.worst_return_pct)


# --------------------------------------------------------------------------
# C2 -- the spread the account pays decides whether there is anything left
# --------------------------------------------------------------------------

@dataclass
class SpreadFinding:
    points: list[tuple[float, float, float]]     # spread, expectancy, trades
    break_even_spread_usd_oz: float | None
    ecn_expectancy_r: float
    standard_expectancy_r: float
    mean_target_usd: float

    @property
    def share_lost_to_the_standard_account(self) -> float:
        """How much of the ECN result the wider spread removes."""
        if self.ecn_expectancy_r <= 0:
            return 0.0
        gone = self.ecn_expectancy_r - self.standard_expectancy_r
        return max(0.0, gone / self.ecn_expectancy_r)

    @property
    def standard_spread_as_share_of_target(self) -> float:
        """The number that decides whether the spread matters at all.

        This is why the same claim is true for one strategy and false for
        another. A tick scalper aiming at 10 cents pays four times its target
        in spread on a standard account. A strategy aiming at half a day's
        range pays a couple of percent.
        """
        if self.mean_target_usd <= 0:
            return 0.0
        return STANDARD_SPREAD_USD_OZ / self.mean_target_usd


def measure_break_even_spread(markets: int = 20, bars: int = 12_000,
                              seed_base: int = 8_000) -> SpreadFinding:
    """Find the spread at which the strategy stops paying for itself.

    This is the number to take to a broker comparison, and it is the one
    quantity in this file that transfers directly to a real account: the
    spread is charged the same way whatever the market does.
    """
    base = DayRangeConfig()
    grid = (0.0, 0.10, 0.15, 0.20, 0.30, 0.40, 0.60, 0.80, 1.20)

    points: list[tuple[float, float, float]] = []
    target_usd = 0.0
    for spread in grid:
        s = sweep(replace(base, spread_usd_oz=spread), markets=markets,
                  bars=bars, seed_base=seed_base)
        points.append((spread, s.mean_expectancy_r, s.mean_trades))
        if spread == STANDARD_SPREAD_USD_OZ:
            target_usd = s.mean_target_usd

    break_even = None
    for (s0, e0, _), (s1, e1, _) in zip(points, points[1:]):
        if e0 > 0 >= e1:
            # Linear between the two measured points; the curve is smooth
            # here because the spread enters the P&L linearly.
            break_even = s0 + (s1 - s0) * (e0 / (e0 - e1))
            break

    def at(target: float) -> float:
        return min(points, key=lambda p: abs(p[0] - target))[1]

    return SpreadFinding(points=points, break_even_spread_usd_oz=break_even,
                         ecn_expectancy_r=at(ECN_SPREAD_USD_OZ),
                         standard_expectancy_r=at(STANDARD_SPREAD_USD_OZ),
                         mean_target_usd=target_usd)


# --------------------------------------------------------------------------
# C3 -- the session filter
# --------------------------------------------------------------------------

@dataclass
class SessionFinding:
    all_hours: tuple[float, float, float]        # expectancy, trades, win rate
    overlap: tuple[float, float, float]
    asia: tuple[float, float, float]

    @property
    def overlap_beats_all_hours(self) -> bool:
        return self.overlap[0] > self.all_hours[0]

    @property
    def trades_given_up(self) -> float:
        if not self.all_hours[1]:
            return 0.0
        return 1.0 - self.overlap[1] / self.all_hours[1]


def measure_session_filter(markets: int = 20, bars: int = 12_000,
                           seed_base: int = 9_000) -> SessionFinding:
    """Restrict entries to a session and see what changes.

    Read this one with the caveat attached: the simulator was given a session
    volatility profile because gold has one. Recovering it is a check that
    the filter works, not evidence about real gold. What does transfer is the
    *mechanism* -- the spread is a fixed cost per trade, so it eats a larger
    share of a small move than of a large one, and quiet hours produce small
    moves.
    """
    base = DayRangeConfig()

    def measured(hours: tuple[int, ...]) -> tuple[float, float, float]:
        s = sweep(replace(base, trade_hours_utc=hours), markets=markets,
                  bars=bars, seed_base=seed_base)
        return s.mean_expectancy_r, s.mean_trades, s.mean_win_rate

    return SessionFinding(all_hours=measured(()),
                          overlap=measured(OVERLAP_HOURS_UTC),
                          asia=measured(ASIA_HOURS_UTC))


# --------------------------------------------------------------------------
# C4 -- the timeframe
# --------------------------------------------------------------------------

@dataclass
class TimeframeFinding:
    rows: list[tuple[str, float, float, float]]  # label, expectancy, trades, wins

    @property
    def best_label(self) -> str:
        return max(self.rows, key=lambda r: r[1])[0]


def measure_timeframe(markets: int = 12, bars: int = 20_000,
                      seed_base: int = 10_000) -> TimeframeFinding:
    """The same markets at M1, M5 and M15.

    The M5 and M15 series are built by aggregating the very M1 bars the M1
    run used, so a difference cannot come from having seen a different
    market. Every bar-counted parameter is scaled with the timeframe, so
    "the day's range" stays a day and the time stop stays four hours.
    """
    base = DayRangeConfig()
    rows: list[tuple[str, float, float, float]] = []

    for label, factor in (("1m", 1), ("5m", 5), ("15m", 15)):
        cfg = replace(base,
                      bars_per_day=base.bars_per_day // factor,
                      min_bars_for_range=max(12, base.min_bars_for_range // factor),
                      time_stop_bars=max(8, base.time_stop_bars // factor))
        exps, trades, wins = [], [], []
        for i in range(markets):
            seed = seed_base + i
            series = simulate.generate(bars=bars, timeframe="1m", seed=seed)
            r = run(cfg, series=resample(series, factor), seed=seed)
            trades.append(r.trades)
            if r.trades:
                exps.append(r.expectancy_r)
                wins.append(r.win_rate)
        rows.append((label,
                     statistics.fmean(exps) if exps else 0.0,
                     statistics.fmean(trades),
                     statistics.fmean(wins) if wins else 0.0))
    return TimeframeFinding(rows=rows)


# --------------------------------------------------------------------------
# C10 -- what a "minimum deposit" actually has to be
# --------------------------------------------------------------------------

def margin_required(price: float, lot: float, leverage: float) -> float:
    """One ounce of arithmetic that settles a whole genre of claim."""
    from .specs import get_spec
    return lot * get_spec("XAUUSD").contract_size_oz * price / leverage


# --------------------------------------------------------------------------
# A1 -- how much account the strategy actually needs
# --------------------------------------------------------------------------

# The account is funded in euro and the contract settles in dollars. Stated
# as an assumption rather than fetched, because the rate moves and the
# conclusion here does not turn on the third decimal.
ASSUMED_EUR_USD = 1.08


@dataclass
class AccountRow:
    equity_eur: float
    # Under the 1% rule: how much of its own signal flow the account can act
    # on at all.
    disciplined_trades: float
    share_of_signals_taken: float
    # Ignoring the rule and simply trading the broker minimum, which is what
    # every small account actually ends up doing.
    minlot_trades: float
    minlot_median_pct: float
    minlot_worst_pct: float
    minlot_ruin_rate: float
    # The risk per trade that the minimum lot forces on this account. This
    # is the number the whole question reduces to.
    forced_risk_pct: float

    @property
    def rule_permits_trading(self) -> bool:
        return self.disciplined_trades > 0


@dataclass
class AccountFinding:
    rows: list[AccountRow]
    smallest_viable_eur: float
    mean_stop_usd: float

    def at(self, equity_eur: float) -> AccountRow | None:
        for row in self.rows:
            if abs(row.equity_eur - equity_eur) < 0.5:
                return row
        return None


def measure_account_sizes(equities_eur: tuple[float, ...] = (100, 200, 400,
                                                             1_000, 2_000,
                                                             5_000),
                          markets: int = 12, bars: int = 12_000,
                          seed_base: int = 11_000) -> AccountFinding:
    """Run the strategy at each account size, twice.

    Once under the 1% rule, where the answer is not a return figure but how
    many signals the account is too small to act on -- a strategy that
    refuses 99% of its own trades has not been tested at that size, it has
    been switched off.

    And once the way a small account actually gets traded: the broker
    minimum, 0.01 lot, rule or no rule. That second run is the honest
    forecast, and `forced_risk_pct` is the reason it looks the way it does.
    """
    from .specs import get_spec
    from .risk import MAX_RISK_PER_TRADE_PCT

    oz = get_spec("XAUUSD").contract_size_oz
    base = DayRangeConfig(risk_pct=MAX_RISK_PER_TRADE_PCT)

    # Measure the typical stop distance once, on a well-funded account, so
    # the figure is not itself distorted by trades being refused.
    probe = sweep(replace(base, risk_pct=None), markets=markets, bars=bars,
                  seed_base=seed_base)
    mean_target = probe.mean_target_usd
    # take_fraction and stop_fraction are both applied to the same predicted
    # move, so the stop sits at target * (stop/take).
    mean_stop = mean_target * (base.stop_fraction / base.take_fraction)

    rows: list[AccountRow] = []
    for eur in equities_eur:
        usd = eur * ASSUMED_EUR_USD

        disciplined = sweep(replace(base, start_equity=usd), markets=markets,
                            bars=bars, seed_base=seed_base)
        taken = statistics.fmean([r.signals_acted_on for r in disciplined.runs])

        minlot = sweep(replace(base, start_equity=usd, risk_pct=None,
                               lot=base.min_lot),
                       markets=markets, bars=bars, seed_base=seed_base)
        ruined = sum(1 for r in minlot.runs
                     if r.stopped_out or r.end_equity <= 0) / len(minlot.runs)

        rows.append(AccountRow(
            equity_eur=eur,
            disciplined_trades=disciplined.mean_trades,
            share_of_signals_taken=taken,
            minlot_trades=minlot.mean_trades,
            minlot_median_pct=minlot.median_return_pct,
            minlot_worst_pct=minlot.worst_return_pct,
            minlot_ruin_rate=ruined,
            forced_risk_pct=base.min_lot * oz * mean_stop / usd * 100.0,
        ))

    # The equity at which one minimum lot risks exactly the limit.
    smallest_usd = (base.min_lot * oz * mean_stop
                    / (MAX_RISK_PER_TRADE_PCT / 100.0))
    return AccountFinding(rows=rows,
                          smallest_viable_eur=smallest_usd / ASSUMED_EUR_USD,
                          mean_stop_usd=mean_stop)


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def render_catalogue() -> str:
    kinds = {"vendor": "Anbieter", "editorial": "Fachpresse",
             "regulatory": "Aufsicht", "academic": "Wissenschaft"}
    lines = ["RECHERCHE — WAS BEHAUPTET WIRD", "=" * 68, ""]
    for c in CLAIMS:
        mark = "messbar" if c.testable else "nicht hier messbar"
        lines.append(f"  {c.id:<4}[{kinds[c.kind]:>12}]  {mark}")
        for chunk in _wrap(c.text, 62):
            lines.append(f"        {chunk}")
        for n, chunk in enumerate(_wrap(c.source, 54)):
            lines.append(f"        {'Quelle: ' if n == 0 else ' ' * 8}{chunk}")
        if c.note:
            for chunk in _wrap(c.note, 62):
                lines.append(f"        -> {chunk}")
        lines.append("")
    lines.append("  Anbieterangaben stehen hier als Hypothese, nicht als Zahl.")
    lines.append("  Als Fakt zitiert werden nur Aufsicht und Wissenschaft.")
    return "\n".join(lines)


def _wrap(text: str, width: int) -> list[str]:
    out, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out


def render_measurements(markets: int = 20, bars: int = 12_000) -> str:
    lines = ["RECHERCHE — WAS DAVON HAELT", "=" * 68, ""]

    w = measure_win_rate_is_not_an_edge(markets=markets, bars=bars)
    lines.append("  C1  Eine Trefferquote ist eine Stellschraube, kein Ergebnis")
    lines.append(f"      Standardregeln       {w.baseline_win_rate * 100:>5.1f}% Treffer  "
                 f"{w.baseline_expectancy_r:>+7.3f}R")
    lines.append(f"      Auf Quote gedreht    {w.best_win_rate * 100:>5.1f}% Treffer  "
                 f"{w.its_expectancy_r:>+7.3f}R")
    lines.append(f"      (Mitnahme {w.its_take:.0%} der Vorhersage, "
                 f"Stop {w.its_stop:.0%})")
    lines.append(f"      Median-Rendite dieser Variante: "
                 f"{w.its_median_return_pct:+.1f}%")
    lines.append(f"      Schlechtester Markt: {w.baseline_worst_return_pct:+.1f}% "
                 f"mit Standardregeln, {w.its_worst_return_pct:+.1f}% "
                 f"auf Quote gedreht")
    if w.buying_a_win_rate_costs_expectancy:
        lines.append("      BELEGT: die hoehere Quote bringt keinen besseren")
        lines.append("      Erwartungswert. Eine Quote allein sagt nichts.")
    else:
        lines.append("      In diesem Lauf ging die Quote NICHT auf Kosten des")
        lines.append("      Erwartungswerts — genauer ansehen.")
    if w.buying_a_win_rate_costs_tail:
        lines.append("      Und sie versteckt das Risiko: der weite Stop macht")
        lines.append("      den seltenen Verlierer entsprechend gross.")
    lines.append("")

    s = measure_break_even_spread(markets=markets, bars=bars)
    lines.append("  C2  Der Spread entscheidet, ob etwas uebrig bleibt")
    lines.append(f"      {'Spread':>8} {'Erwartung':>11} {'Trades':>8}")
    lines.append("      " + "-" * 29)
    for spread, exp, trades in s.points:
        lines.append(f"      {spread:>7.2f}$ {exp:>+10.3f}R {trades:>8.0f}")
    if s.break_even_spread_usd_oz is not None:
        lines.append(f"      Nulllinie bei {s.break_even_spread_usd_oz:.2f} $/oz "
                     f"({s.break_even_spread_usd_oz * 100:.0f} Punkte)")
    else:
        lines.append("      Keine Nulllinie im geprueften Bereich — die")
        lines.append("      Behauptung gilt fuer DIESE Strategie nicht.")
    lines.append(f"      ECN {ECN_SPREAD_USD_OZ:.2f}$ -> {s.ecn_expectancy_r:+.3f}R  ·  "
                 f"Standard {STANDARD_SPREAD_USD_OZ:.2f}$ -> "
                 f"{s.standard_expectancy_r:+.3f}R")
    lines.append(f"      Grund: das Ziel liegt im Schnitt {s.mean_target_usd:.2f} $/oz "
                 f"entfernt.")
    lines.append(f"      Ein Standard-Spread ist davon "
                 f"{s.standard_spread_as_share_of_target * 100:.1f}%.")
    tick_target = 0.10
    lines.append(f"      Zum Vergleich ein Tick-Scalper mit "
                 f"{tick_target:.2f} $ Ziel: derselbe")
    lines.append(f"      Spread waere {STANDARD_SPREAD_USD_OZ / tick_target:.0f}x "
                 f"das Ziel. Dort stimmt die Behauptung — und genau")
    lines.append("      deshalb gilt sie fuer uns nicht.")
    lines.append("")

    ses = measure_session_filter(markets=markets, bars=bars)
    lines.append("  C3  Handelszeit  (Vorbehalt: Sessionprofil steckt im Simulator)")
    lines.append(f"      {'Fenster':>14} {'Erwartung':>11} {'Trades':>8} {'Treffer':>9}")
    lines.append("      " + "-" * 44)
    for label, row in (("alle Stunden", ses.all_hours),
                       ("Overlap 12-16", ses.overlap),
                       ("Asien 0-6", ses.asia)):
        lines.append(f"      {label:>14} {row[0]:>+10.3f}R {row[1]:>8.0f} "
                     f"{row[2] * 100:>8.1f}%")
    lines.append(f"      Der Filter kostet {ses.trades_given_up * 100:.0f}% "
                 f"der Trades.")
    if not ses.overlap_beats_all_hours:
        lines.append("      Der Filter bringt hier nichts. Mechanismus: unser")
        lines.append("      Stop skaliert mit der vorhergesagten Bewegung, also")
        lines.append("      kuerzt sich die Sessionvolatilitaet aus dem R heraus.")
        lines.append("      Die uebliche Empfehlung stammt von Strategien mit")
        lines.append("      festem Pip-Ziel, wo sie sich nicht auskuerzt.")
    lines.append("")

    tf = measure_timeframe(markets=max(8, markets // 2), bars=20_000)
    lines.append("  C4  Zeiteinheit  (dieselben Maerkte, nur andere Kerzen)")
    lines.append(f"      {'TF':>6} {'Erwartung':>11} {'Trades':>8} {'Treffer':>9}")
    lines.append("      " + "-" * 36)
    for label, exp, trades, wins in tf.rows:
        lines.append(f"      {label:>6} {exp:>+10.3f}R {trades:>8.0f} "
                     f"{wins * 100:>8.1f}%")
    lines.append(f"      Bestes Ergebnis: {tf.best_label}")
    if tf.best_label == "1m":
        lines.append("      ACHTUNG, das Ergebnis ist voreingenommen: der")
        lines.append("      Simulator kennt weder Requotes noch Slippage noch")
        lines.append("      einen schwankenden Spread. Genau das macht M1 in")
        lines.append("      der Realitaet teuer. Der Vorsprung von M1 ist hier")
        lines.append("      also eine Obergrenze, kein Befund.")
    lines.append("")

    lines.append("  C10 Mindesteinlage — reine Arithmetik, kein Testlauf")
    for lot in (0.01, 0.10):
        need = margin_required(4_100.0, lot, 20.0)
        lines.append(f"      {lot:.2f} Lot bei 1:20 und 4.100 $/oz: "
                     f"{need:,.0f} $ Margin")
    lines.append("      Fuer 0,10 Lot als Retail-Kunde in der EU ist die")
    lines.append("      1.000-$-Angabe der Anbieter deutlich zu niedrig.")
    lines.append("")

    acc = measure_account_sizes(markets=max(8, markets // 2), bars=bars)
    lines.append("  A1  Was das Konto hergibt")
    lines.append(f"      Typischer Stop dieser Strategie: "
                 f"{acc.mean_stop_usd:.1f} $/oz.")
    lines.append(f"      Die kleinste handelbare Position (0,01 Lot = 1 Unze)")
    lines.append(f"      riskiert damit {acc.mean_stop_usd:.0f} $ — egal wie "
                 f"gross das Konto ist.")
    lines.append("")
    lines.append("      Mit der 1%-Regel:")
    lines.append(f"      {'Konto':>8} {'erzwungenes Risiko':>20} "
                 f"{'Trades':>8} {'genutzt':>9}")
    lines.append("      " + "-" * 48)
    for r in acc.rows:
        used = "—" if r.disciplined_trades == 0 else \
            f"{r.share_of_signals_taken * 100:.1f}%"
        lines.append(f"      {r.equity_eur:>7.0f}€ {r.forced_risk_pct:>19.1f}% "
                     f"{r.disciplined_trades:>8.1f} {used:>9}")
    lines.append(f"      Damit die 32 $ ein Prozent sind, braucht es "
                 f"{acc.smallest_viable_eur:,.0f} €.")
    lines.append("")
    lines.append("      Ohne die Regel, einfach 0,01 Lot handeln:")
    lines.append(f"      {'Konto':>8} {'Trades':>8} {'Median':>9} "
                 f"{'schlechtester':>14} {'Stop-out':>9}")
    lines.append("      " + "-" * 52)
    for r in acc.rows:
        lines.append(f"      {r.equity_eur:>7.0f}€ {r.minlot_trades:>8.0f} "
                     f"{r.minlot_median_pct:>+8.1f}% "
                     f"{r.minlot_worst_pct:>+13.1f}% "
                     f"{r.minlot_ruin_rate * 100:>8.0f}%")
    lines.append("      Nicht die Strategie ist hier das Problem, sondern dass")
    lines.append("      die kleinste Goldposition fuer das Konto zu gross ist.")
    lines.append("")
    lines.append("  Gemessen auf dem Simulator. C1, C2 und C4 sind Aussagen")
    lines.append("  ueber Kosten und Arithmetik und gelten fuer jeden Markt")
    lines.append("  mit Spread. C3 ist hier teilweise zirkulaer.")
    return "\n".join(lines)
