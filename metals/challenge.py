"""Prop-firm challenges, turned from a pitch into arithmetic.

A funded-trading challenge is a bet with a fixed stake: you pay a fee, you
must reach a profit target before you breach a loss limit, and if you fail
the fee is gone. Everything about how that bet is sold obscures the one
question that decides it -- **how likely is passing, given the edge you
actually have?** -- because that question has an answer, and the answer is
usually no.

This module answers it by simulation. Give it the challenge's published rules
and an honest description of your edge, and it plays the challenge tens of
thousands of times and counts the outcomes.

Two things it is built to make impossible to miss:

*The fee is your capital at risk.* Challenges are marketed as trading
"without your own risk". That is true of the notional account and false of
your money: the fee is yours, you pay it up front, and you lose it when you
breach. Published industry data puts the share of challenge buyers who ever
receive a payout at roughly 7%, and the average number of attempts before
passing at about three. A model that ignores the fee is modelling a
different product.

*Without an edge, no amount of discipline passes.* A challenge asks for a
profit target with a drawdown ceiling. If your expectancy per trade is zero,
your equity is a random walk, and a random walk hits a nearer barrier first
far more often than a farther one. Discipline changes the variance, not the
sign. The simulation shows this directly, which is more convincing than
saying it.

    from metals.challenge import Edge, ChallengeRules, simulate, render
    print(render(simulate(ChallengeRules.ftmo_style(100_000), Edge(...))))
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

# Published industry figures, used only for comparison against a simulated
# result. Sources are named in docs/FREMDKAPITAL.md -- they are vendor and
# aggregator numbers, not peer-reviewed, and are treated as such.
INDUSTRY_PAYOUT_RATE = 0.07        # share of challenge buyers ever paid out
INDUSTRY_TYPICAL_ATTEMPTS = 3.0    # average attempts before a pass


@dataclass(frozen=True)
class ChallengeRules:
    """The published rules of one evaluation phase."""

    account_size: float
    profit_target_pct: float = 10.0
    max_daily_loss_pct: float = 5.0
    max_total_drawdown_pct: float = 10.0
    # A trailing drawdown follows the equity high-water mark upward, so a
    # profitable run tightens the floor beneath it. It is the single most
    # common reason challenges are breached, and firms that use it are not
    # always loud about it.
    trailing_drawdown: bool = False
    min_trading_days: int = 4
    max_trading_days: int = 30
    fee: float = 0.0
    profit_split: float = 0.80

    @classmethod
    def two_step_phase_one(cls, account_size: float, fee: float = 0.0,
                           **kw) -> "ChallengeRules":
        """The shape most two-step evaluations publish for phase one."""
        return cls(account_size=account_size, profit_target_pct=10.0,
                   max_daily_loss_pct=5.0, max_total_drawdown_pct=10.0,
                   min_trading_days=4, max_trading_days=30, fee=fee, **kw)

    @classmethod
    def two_step_phase_two(cls, account_size: float, fee: float = 0.0,
                           **kw) -> "ChallengeRules":
        """Phase two: half the target, the same loss limits, more time."""
        return cls(account_size=account_size, profit_target_pct=5.0,
                   max_daily_loss_pct=5.0, max_total_drawdown_pct=10.0,
                   min_trading_days=4, max_trading_days=60, fee=fee, **kw)


@dataclass(frozen=True)
class Edge:
    """What your trading actually does, expressed per trade in R.

    `win_r` and `loss_r` are magnitudes: a loss of one R is `loss_r = 1.0`.
    The defaults describe this project's exit plan -- 60% off at 0.5R and a
    runner at 2.5R blends to 1.3R on a win -- at the win rate where those
    payoffs exactly break even.

    That break-even default is deliberate. "50%" reads like a neutral
    assumption and is not: with a 1.3R win against a 1R loss it is an
    expectancy of +0.15R per trade, which is a *strong* edge, and it makes
    almost any challenge look passable. The honest starting point for a
    strategy nobody has yet shown to be profitable is zero, and the caller
    has to say otherwise on purpose.
    """

    win_rate: float = 1.0 / 2.3     # break-even against 1.3R / 1.0R
    win_r: float = 1.3
    loss_r: float = 1.0
    risk_pct: float = 1.0
    trades_per_day: int = 4
    # Spread and slippage, as a fraction of the stop distance. Every trade
    # pays it, win or lose, and leaving it out was the second modelling error
    # this file made: without costs a zero-edge trader has *positive*
    # expected value on a funded account, because the downside is capped by
    # the drawdown floor while withdrawals bank the upside. That free option
    # is real, and transaction costs are most of what closes it.
    # 0.05 is half the ceiling rule S6 permits (10% of the stop).
    cost_r: float = 0.05

    @classmethod
    def break_even(cls, win_r: float = 1.3, loss_r: float = 1.0,
                   **kw) -> "Edge":
        """The win rate at which these payoffs come out exactly flat."""
        return cls(win_rate=loss_r / (win_r + loss_r), win_r=win_r,
                   loss_r=loss_r, **kw)

    @property
    def gross_expectancy_r(self) -> float:
        """Before costs -- the number strategy pitches quote."""
        return self.win_rate * self.win_r - (1 - self.win_rate) * self.loss_r

    @property
    def expectancy_r(self) -> float:
        """After costs -- the number the account actually experiences."""
        return self.gross_expectancy_r - self.cost_r

    @property
    def sd_r(self) -> float:
        """Standard deviation of a single trade's R, for a two-point outcome."""
        mean = self.expectancy_r
        var = (self.win_rate * (self.win_r - mean) ** 2
               + (1 - self.win_rate) * (-self.loss_r - mean) ** 2)
        return var ** 0.5


PASSED = "passed"
BREACHED_DAILY = "breached_daily_loss"
BREACHED_TOTAL = "breached_max_drawdown"
RAN_OUT_OF_TIME = "ran_out_of_days"


@dataclass
class Outcome:
    rules: ChallengeRules
    edge: Edge
    runs: int
    counts: dict[str, int] = field(default_factory=dict)
    days_to_pass: list[int] = field(default_factory=list)

    def rate(self, key: str) -> float:
        return self.counts.get(key, 0) / self.runs if self.runs else 0.0

    @property
    def pass_rate(self) -> float:
        return self.rate(PASSED)

    @property
    def breach_rate(self) -> float:
        return self.rate(BREACHED_DAILY) + self.rate(BREACHED_TOTAL)

    @property
    def median_days_to_pass(self) -> int | None:
        if not self.days_to_pass:
            return None
        ordered = sorted(self.days_to_pass)
        return ordered[len(ordered) // 2]

    @property
    def expected_attempts(self) -> float | None:
        """How many fees you would expect to pay for one pass."""
        return 1.0 / self.pass_rate if self.pass_rate > 0 else None

    @property
    def expected_fee_per_pass(self) -> float | None:
        att = self.expected_attempts
        return None if att is None else att * self.rules.fee

    # Note what is deliberately absent: any property that treats the profit
    # made during an evaluation as income. It is not. The evaluation runs on
    # a demo account -- passing it buys access, not money. Crediting that
    # profit was the first modelling error this file made, and it turned a
    # losing proposition into an apparently good one.


def simulate(rules: ChallengeRules, edge: Edge, runs: int = 20_000,
             seed: int = 7) -> Outcome:
    """Play the challenge `runs` times, trade by trade.

    Risk is a fixed percentage of the *starting* balance rather than of
    current equity. That is what a fixed-fractional rule on a challenge
    account looks like in practice, and it avoids flattering the result:
    compounding down after losses would make breaches artificially rare.
    """
    rng = random.Random(seed)
    out = Outcome(rules=rules, edge=edge, runs=runs)

    risk = rules.account_size * edge.risk_pct / 100.0
    target = rules.account_size * (1 + rules.profit_target_pct / 100.0)
    floor_static = rules.account_size * (1 - rules.max_total_drawdown_pct / 100.0)
    daily_allowance = rules.account_size * rules.max_daily_loss_pct / 100.0

    for _ in range(runs):
        equity = rules.account_size
        peak = equity
        verdict = RAN_OUT_OF_TIME
        day = 0

        while day < rules.max_trading_days:
            day += 1
            day_start = equity

            for _ in range(edge.trades_per_day):
                if rng.random() < edge.win_rate:
                    equity += risk * edge.win_r
                else:
                    equity -= risk * edge.loss_r
                equity -= risk * edge.cost_r      # spread, every trade
                peak = max(peak, equity)

                floor_ = (peak * (1 - rules.max_total_drawdown_pct / 100.0)
                          if rules.trailing_drawdown else floor_static)
                if equity <= floor_:
                    verdict = BREACHED_TOTAL
                    break
                if day_start - equity >= daily_allowance:
                    verdict = BREACHED_DAILY
                    break
                if equity >= target and day >= rules.min_trading_days:
                    verdict = PASSED
                    break

            if verdict != RAN_OUT_OF_TIME:
                break

        out.counts[verdict] = out.counts.get(verdict, 0) + 1
        if verdict == PASSED:
            out.days_to_pass.append(day)

    return out


@dataclass
class FundedOutcome:
    """What a funded account actually pays before it dies."""

    mean_payout: float
    ruin_rate: float
    median_days: int
    horizon_days: int


def simulate_funded(rules: ChallengeRules, edge: Edge, runs: int = 20_000,
                    horizon_days: int = 250, payout_every: int = 20,
                    seed: int = 11) -> FundedOutcome:
    """Trade a funded account until it breaches, banking profits as you go.

    This is the only stage that pays anything, so it is the only stage whose
    output belongs in an expected value. Profits above the starting balance
    are withdrawn every `payout_every` trading days and the split is banked;
    the account is not reset after a withdrawal, which is what makes the
    drawdown floor bite.

    At zero expectancy the answer is not merely small, it is zero: equity is
    a martingale, the floor is absorbing, and no withdrawal schedule creates
    drift that is not there. The simulation is here to show that rather than
    assert it.
    """
    rng = random.Random(seed)
    risk = rules.account_size * edge.risk_pct / 100.0
    daily_allowance = rules.account_size * rules.max_daily_loss_pct / 100.0

    total_paid = 0.0
    ruined = 0
    survived: list[int] = []

    for _ in range(runs):
        equity = rules.account_size
        peak = equity
        banked = 0.0
        day = 0
        alive = True

        while day < horizon_days and alive:
            day += 1
            day_start = equity
            for _ in range(edge.trades_per_day):
                equity += risk * edge.win_r if rng.random() < edge.win_rate \
                    else -risk * edge.loss_r
                equity -= risk * edge.cost_r      # spread, every trade
                peak = max(peak, equity)
                floor_ = (peak * (1 - rules.max_total_drawdown_pct / 100.0)
                          if rules.trailing_drawdown
                          else rules.account_size *
                               (1 - rules.max_total_drawdown_pct / 100.0))
                if equity <= floor_ or day_start - equity >= daily_allowance:
                    alive = False
                    break
            if alive and day % payout_every == 0 and equity > rules.account_size:
                banked += (equity - rules.account_size) * rules.profit_split
                equity = rules.account_size
                peak = max(peak, equity)

        total_paid += banked
        if not alive:
            ruined += 1
            survived.append(day)

    ordered = sorted(survived)
    return FundedOutcome(
        mean_payout=total_paid / runs,
        ruin_rate=ruined / runs,
        median_days=ordered[len(ordered) // 2] if ordered else horizon_days,
        horizon_days=horizon_days,
    )


@dataclass
class Program:
    """The whole path: evaluation, second phase, then the funded account."""

    phase1: Outcome
    phase2: Outcome
    funded: FundedOutcome
    total_fee: float

    @property
    def reach_funded(self) -> float:
        return self.phase1.pass_rate * self.phase2.pass_rate

    @property
    def expected_payout(self) -> float:
        return self.reach_funded * self.funded.mean_payout

    @property
    def expected_value(self) -> float:
        return self.expected_payout - self.total_fee


def evaluate_program(account_size: float, fee: float, edge: Edge,
                     runs: int = 20_000, trailing_drawdown: bool = False,
                     horizon_days: int = 250) -> Program:
    p1 = ChallengeRules.two_step_phase_one(account_size, fee=fee,
                                           trailing_drawdown=trailing_drawdown)
    p2 = ChallengeRules.two_step_phase_two(account_size, fee=0.0,
                                           trailing_drawdown=trailing_drawdown)
    return Program(
        phase1=simulate(p1, edge, runs=runs, seed=7),
        phase2=simulate(p2, edge, runs=runs, seed=13),
        funded=simulate_funded(p1, edge, runs=runs, horizon_days=horizon_days),
        total_fee=fee,
    )


def render_program(p: Program) -> str:
    e = p.phase1.edge
    r = p.phase1.rules
    out: list[str] = []
    out.append("FREMDKAPITAL — DER GANZE WEG, NICHT NUR PHASE 1")
    out.append("=" * 72)
    out.append(f"  Konto {r.account_size:,.0f} · Gebuehr {p.total_fee:,.0f} · "
               f"Split {r.profit_split * 100:.0f}%")
    out.append(f"  Kante: {e.win_rate * 100:.1f}% Trefferquote, {e.win_r:g}R / "
               f"{e.loss_r:g}R → Erwartungswert {e.expectancy_r:+.3f}R")
    out.append("")
    out.append(f"  Phase 1 bestanden          {p.phase1.pass_rate * 100:>6.1f}%")
    out.append(f"  Phase 2 bestanden          {p.phase2.pass_rate * 100:>6.1f}%")
    out.append(f"  ueberhaupt finanziert      {p.reach_funded * 100:>6.1f}%")
    out.append("")
    out.append(f"  Finanziertes Konto ueber {p.funded.horizon_days} Handelstage:")
    out.append(f"    reisst irgendwann        {p.funded.ruin_rate * 100:>6.1f}%")
    out.append(f"    Median bis dahin         {p.funded.median_days} Tage")
    out.append(f"    mittlere Auszahlung      {p.funded.mean_payout:>8,.0f}")
    out.append("")
    out.append("  " + "-" * 68)
    out.append(f"  Erwartete Auszahlung       {p.expected_payout:>8,.0f}")
    out.append(f"  Gebuehr                    {-p.total_fee:>8,.0f}")
    out.append(f"  ERWARTUNGSWERT             {p.expected_value:>+8,.0f}")
    out.append("")
    out.append(f"  Brutto-Erwartungswert {e.gross_expectancy_r:+.3f}R, "
               f"Kosten {e.cost_r:g}R je Trade,")
    out.append(f"  netto {e.expectancy_r:+.3f}R. Der Kostenposten entscheidet hier,")
    out.append("  nicht die Trefferquote.")
    out.append("")
    if e.gross_expectancy_r <= 1e-9 and e.expectancy_r < 0:
        # Worth stating plainly, because the naive intuition is wrong and the
        # simulation says so: a capped downside plus banked withdrawals is a
        # free option, and without costs it is worth money even to a coin
        # flipper. Costs are most of what closes it -- which is also why the
        # firms that survive use trailing drawdowns and consistency rules.
        out.append("  Ohne Handelskosten waere dieser Kauf sogar bei Trefferquote")
        out.append("  null leicht positiv — der Verlust ist bei der Schwelle")
        out.append("  gedeckelt, die Auszahlungen sind es nicht. Das ist eine echte")
        out.append("  Freikarte, und genau deshalb arbeiten die Anbieter mit")
        out.append("  nachziehenden Schwellen und Konsistenzregeln.")
        out.append("  Der Spread allein kippt sie ins Minus. Er ist der Posten,")
        out.append("  den in Werbevideos niemand nennt.")
    elif e.expectancy_r <= 0:
        out.append("  Netto negativ. Damit ist der Rest eine Frage der Zeit,")
        out.append("  nicht des Ausgangs.")
    else:
        out.append("  Diese Zahl steht und faellt mit der angenommenen Kante.")
        out.append("  Setz dort deine eigenen gemessenen Werte ein, nicht die")
        out.append("  aus einem Werbevideo.")

    out.append("")
    out.append(f"  Zur Einordnung: veroeffentlichte Branchenzahlen nennen "
               f"{INDUSTRY_PAYOUT_RATE * 100:.0f}% aller")
    out.append(f"  Kaeufer, die je eine Auszahlung sehen. Die Simulation oben "
               f"kommt auf")
    out.append(f"  {p.reach_funded * 100:.0f}% bis zur Finanzierung — sie ist also "
               f"noch zu optimistisch,")
    out.append("  weil Konsistenzregeln, Nachrichtensperren und menschliche")
    out.append("  Regelbrueche gar nicht modelliert sind.")
    return "\n".join(out)


def render(o: Outcome) -> str:
    r, e = o.rules, o.edge
    lines: list[str] = []
    lines.append("FREMDKAPITAL-CHALLENGE — DIE RECHNUNG")
    lines.append("=" * 72)
    lines.append(f"  Konto {r.account_size:,.0f} · Ziel +{r.profit_target_pct:g}% · "
                 f"Tagesverlust max {r.max_daily_loss_pct:g}% · "
                 f"Gesamtverlust max {r.max_total_drawdown_pct:g}%"
                 f"{' (nachziehend)' if r.trailing_drawdown else ''}")
    lines.append(f"  {r.max_trading_days} Handelstage, mindestens "
                 f"{r.min_trading_days} · Gebuehr {r.fee:,.0f}")
    lines.append("")
    lines.append(f"  Angenommene Kante: {e.win_rate * 100:.0f}% Trefferquote, "
                 f"Gewinn {e.win_r:g}R / Verlust {e.loss_r:g}R, "
                 f"{e.risk_pct:g}% Risiko, {e.trades_per_day} Trades/Tag")
    lines.append(f"  → Erwartungswert {e.expectancy_r:+.3f}R pro Trade "
                 f"(Streuung {e.sd_r:.2f}R)")

    lines.append("")
    lines.append(f"ERGEBNIS AUS {o.runs:,} SIMULIERTEN DURCHLAEUFEN")
    lines.append("-" * 72)
    lines.append(f"  bestanden                 {o.pass_rate * 100:>6.1f}%")
    lines.append(f"  Tagesverlust gerissen     {o.rate(BREACHED_DAILY) * 100:>6.1f}%")
    lines.append(f"  Gesamtverlust gerissen    {o.rate(BREACHED_TOTAL) * 100:>6.1f}%")
    lines.append(f"  Zeit abgelaufen           {o.rate(RAN_OUT_OF_TIME) * 100:>6.1f}%")
    if o.median_days_to_pass is not None:
        lines.append(f"  Median bis zum Bestehen   {o.median_days_to_pass} Handelstage")

    lines.append("")
    lines.append("WAS DAS KOSTET")
    lines.append("-" * 72)
    if r.fee <= 0:
        lines.append("  Keine Gebuehr angegeben (--fee), also keine Kostenrechnung.")
        lines.append("  Die Gebuehr ist der Punkt: sie ist dein Geld, und sie ist weg,")
        lines.append("  wenn du reisst. Trag sie ein.")
    else:
        att = o.expected_attempts
        if att is None:
            lines.append("  Kein einziger Durchlauf hat bestanden. Es gibt keine")
            lines.append("  Anzahl an Versuchen, die das im Mittel aufwiegt.")
        else:
            lines.append(f"  Erwartete Versuche bis zum Bestehen   {att:>8.1f}")
            lines.append(f"  Erwartete Gebuehren bis dahin         "
                         f"{o.expected_fee_per_pass:>8,.0f}")
        lines.append("")
        lines.append("  Achtung: Bestehen ist keine Auszahlung. Die Evaluierung")
        lines.append("  laeuft auf einem Demokonto — der Gewinn darin wird nicht")
        lines.append("  ausgezahlt, er schaltet nur die naechste Stufe frei.")
        lines.append("  Was am Ende herauskommt, rechnet `metals challenge --programm`.")

    lines.append("")
    lines.append("EINORDNUNG")
    lines.append("-" * 72)
    if e.expectancy_r <= 0:
        lines.append("  Der angenommene Erwartungswert ist nicht positiv. Dann ist der")
        lines.append("  Kontostand ein Zufallspfad, und ein Zufallspfad trifft die")
        lines.append("  naehere Schranke oefter als die fernere. Genau das steht oben.")
        lines.append("  Disziplin aendert hier die Streuung, nicht das Vorzeichen —")
        lines.append("  ein Bot, der sich perfekt an Regeln haelt, besteht deshalb")
        lines.append("  nicht haeufiger, wenn die Strategie keine Kante hat.")
    else:
        lines.append("  Der angenommene Erwartungswert ist positiv. Diese Annahme ist")
        lines.append("  der ganze Hebel der Rechnung — und sie ist genau die, die noch")
        lines.append("  niemand belegt hat. Fuer den Nachweis siehe docs/LERNEN.md:")
        lines.append("  eine Kante von 0,1R braucht rund 385 Trades, bis man sie")
        lines.append("  ueberhaupt von null unterscheiden kann.")
    lines.append("")
    lines.append(f"  Zum Vergleich, veroeffentlichte Branchenzahlen: rund "
                 f"{INDUSTRY_PAYOUT_RATE * 100:.0f}% aller Kaeufer")
    lines.append(f"  einer Challenge erhalten jemals eine Auszahlung, im Schnitt "
                 f"nach {INDUSTRY_TYPICAL_ATTEMPTS:g} Versuchen.")
    lines.append("  Das sind Anbieter- und Aggregatorzahlen, keine geprueften Daten —")
    lines.append("  aber sie zeigen in dieselbe Richtung wie die Simulation oben.")
    return "\n".join(lines)
