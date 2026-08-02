"""One command that answers the only question that matters.

Everything measured in this repository ran on `metals/simulate.py`, and audit
finding A27 established what that is worth: switch off one parameter of the
generator -- `MarketParams.reversion`, whose own comment says it exists to
"prevent random walk blowups" -- and the measured edge goes from +0.099 R to
+0.007 R with a band across zero. The simulator cannot answer whether the
strategy works. Only a downloaded history can.

That answer used to require five separate commands, two of which test
different strategies and are easy to confuse, plus a hand-typed `python -c`
block. Somebody arriving at their PC with a CSV and half an hour should not
have to assemble a research programme out of a documentation page.

    python -m metals verdict --file XAU_5m_data.csv --tz broker_gmt3

Five checks, in the order in which a failure makes the rest pointless:

1. **Does the file load, and is the timezone right?** A wrong offset moves
   every session rule and produces a plausible, wrong backtest. The loader
   checks the hourly volatility profile against gold's known shape.
2. **Does gold come back to the middle of its day?** The cheapest possible
   test of the assumption the whole edge rests on, and it needs only daily
   OHLC. Simulator reference: 32% of days close mid-range with the reversion
   at full strength, 23% with it off.
3. **Does gold reject the random walk?** The variance ratio, which is the
   version of question 2 with a test statistic attached.
4. **What does the day-range strategy earn on this history?** With a
   confidence band, at the account size actually being considered.
5. **What do the scalping setups S1-S6 earn?** The ones the expert advisor
   trades by default, which is a different strategy from 4 and gets confused
   with it constantly.

Then one verdict, in plain words, that is allowed to say "do not install
this".
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

# How the day-close statistic reads against the simulator, measured over 120
# days per row in docs/PC-SETUP.md. These are the yardstick for step 2.
MID_CLOSE_WITH_FULL_REVERSION = 0.32
MID_CLOSE_WITHOUT_REVERSION = 0.23

# A day-range expectancy needs to clear this before the strategy is worth
# running with money. Deliberately not zero: an edge whose band touches zero
# has not been shown to exist, and the cost of being wrong is the account.
MEANINGFUL_EDGE_R = 0.05


@dataclass
class Step:
    name: str
    status: str          # "ok" | "warn" | "fail" | "info"
    headline: str
    detail: list[str] = field(default_factory=list)

    @property
    def mark(self) -> str:
        return {"ok": "JA ", "warn": "?  ", "fail": "NEIN", "info": "   "}[
            self.status]


@dataclass
class Verdict:
    steps: list[Step] = field(default_factory=list)
    recommendation: str = ""
    reasoning: list[str] = field(default_factory=list)

    def step(self, name: str) -> Step | None:
        for s in self.steps:
            if s.name == name:
                return s
        return None

    @property
    def failed(self) -> bool:
        return any(s.status == "fail" for s in self.steps)


def _band(values: list[float]) -> tuple[float, float, float]:
    if len(values) < 2:
        return 0.0, 0.0, 0.0
    mean = statistics.fmean(values)
    se = statistics.stdev(values) / math.sqrt(len(values))
    return mean, mean - 1.96 * se, mean + 1.96 * se


def run_verdict(series, equity_eur: float = 400.0, eur_usd: float = 1.1476,
                spread_usd_oz: float = 0.34,
                load_warnings: tuple[str, ...] = ()) -> Verdict:
    """Every check, in order, on one loaded history."""
    from .claims import close_position_stats
    from .dayrange import DayRangeConfig, run as run_dayrange
    from .persistence import measure as measure_persistence

    v = Verdict()

    # --- 1. the data itself -------------------------------------------------
    bars = len(series.candles)
    first = series.candles[0].ts if bars else None
    last = series.candles[-1].ts if bars else None
    detail = [f"{bars:,} Kerzen"]
    if first and last:
        detail.append(f"{first:%d.%m.%Y} bis {last:%d.%m.%Y}")
    if load_warnings:
        detail.extend(load_warnings)
        v.steps.append(Step(
            "daten", "warn",
            "Datei geladen, aber der Lader warnt — bitte lesen", detail))
    else:
        v.steps.append(Step("daten", "ok", "Datei geladen, Zeitzone plausibel",
                            detail))

    # --- 2. does gold come back to the middle of its day? -------------------
    # A28: reported, not trusted. This statistic is not monotone in the thing
    # it claims to measure -- on 5-minute bars it moves the WRONG WAY as the
    # generator's reversion is turned up (40.9% -> 27.3%) while on 1-minute
    # bars it moves the right way (36.4% -> 61.4%). Same generator, same
    # days, opposite answers. Step 3 carries the question instead.
    stats = close_position_stats(series)
    share = stats.share_closing_mid
    detail = [
        f"{stats.days:,} Handelstage",
        f"{share:.1%} schliessen im mittleren Drittel ihrer eigenen Spanne",
        "ACHTUNG: Diese Zahl haengt an der Zeitebene und ist NICHT monoton",
        "in der Rueckkehr — auf 5m-Balken faellt sie, wenn die Rueckkehr",
        "steigt, auf 1m-Balken steigt sie (A28). Deshalb entscheidet sie",
        "hier nichts; Schritt 3 beantwortet dieselbe Frage mit einem Test,",
        "der eine Nullverteilung hat.",
    ]
    v.steps.append(Step("rueckkehr", "info",
                        "Zur Einordnung, nicht als Beleg", detail))

    # --- 3. the random walk test -------------------------------------------
    p = measure_persistence(series)
    detail = [f"Hurst (R/S) {p.hurst:.3f} — allein ohne Aussagekraft"]
    for r in p.ratios:
        detail.append(f"q={r.q:<4d} VR={r.ratio:6.3f}  z={r.z:+6.2f}  "
                      f"{r.verdict}")
    if p.verdict == "mean reverting":
        status, headline = "ok", ("Der Zufallspfad wird verworfen, und in die "
                                  "richtige Richtung: rueckkehrend")
    elif p.verdict == "persistent":
        status, headline = "warn", ("Verworfen, aber in die FALSCHE Richtung: "
                                    "Bewegungen laufen weiter. Diese Strategie "
                                    "setzt auf Rueckkehr")
    elif p.verdict == "mixed":
        status, headline = "warn", "Uneinheitlich ueber die Horizonte"
    else:
        status, headline = "warn", ("Kein Horizont verwirft den Zufallspfad. "
                                    "Das ist kein Nachweis gegen die "
                                    "Strategie, aber auch keiner dafuer")
    v.steps.append(Step("zufallspfad", status, headline, detail))

    # --- 4. the day-range strategy -----------------------------------------
    cfg = DayRangeConfig(risk_pct=None, lot=0.01,
                         start_equity=equity_eur * eur_usd,
                         spread_usd_oz=spread_usd_oz)
    res = run_dayrange(cfg, series=series, seed=1)
    rs = list(res.r_multiples)
    mean, lo, hi = _band(rs)
    detail = [
        f"{res.trades:,} Trades aus {res.signals:,} Signalen",
        f"Erwartung {mean:+.3f} R   95%-Band {lo:+.3f} … {hi:+.3f}",
        f"Konto {equity_eur:,.0f} € bei EUR/USD {eur_usd:.4f}, "
        f"Spread {spread_usd_oz:.2f} $/oz, 0,01 Lot",
    ]
    if res.skipped_too_small:
        detail.append(f"{res.skipped_too_small:,} Signale abgelehnt, weil die "
                      f"kleinste Position zu viel riskiert haette")
    if res.trades < 30:
        status, headline = "warn", (f"Nur {res.trades} Trades — zu wenig fuer "
                                    f"ein Urteil")
    elif lo > MEANINGFUL_EDGE_R:
        status, headline = "ok", "Band klar ueber der Null. Das ist eine Kante"
    elif hi < 0:
        status, headline = "fail", ("Band klar unter der Null. Die Strategie "
                                    "verliert auf echten Daten")
    else:
        status, headline = "warn", ("Band schneidet die Null — kein Nachweis "
                                    "in die eine oder andere Richtung")
    v.steps.append(Step("tagesspanne", status, headline, detail))

    # --- 5. the setups the EA actually trades ------------------------------
    try:
        from .backtest import BacktestConfig, run as run_backtest
        from .candles import resample
        m5 = series if series.timeframe == "5m" else resample(series, "5m")
        bt = run_backtest(m5, BacktestConfig(spread_usd_oz=spread_usd_oz))
        rs2 = [t.net_r for t in bt.trades]
        mean2, lo2, hi2 = _band(rs2)
        detail = [f"{bt.n:,} Trades aus {bt.signals_generated:,} Signalen",
                  f"Erwartung {mean2:+.3f} R   95%-Band {lo2:+.3f} … {hi2:+.3f}"]
        if bt.n < 30:
            status, headline = "warn", f"Nur {bt.n} Trades — zu wenig"
        elif lo2 > MEANINGFUL_EDGE_R:
            status, headline = "ok", "Band ueber der Null"
        elif hi2 < 0:
            status, headline = "fail", "Band unter der Null — sie verlieren"
        else:
            status, headline = "warn", "Band schneidet die Null"
        v.steps.append(Step("scalping", status, headline, detail))
    except Exception as exc:  # noqa: BLE001 - a failed step must not kill the run
        v.steps.append(Step("scalping", "warn",
                            f"Konnte nicht gemessen werden: {exc}", []))

    _decide(v)
    return v


def _decide(v: Verdict) -> None:
    """The recommendation, and it is allowed to say no."""
    rueck = v.step("rueckkehr")
    walk = v.step("zufallspfad")
    day = v.step("tagesspanne")
    scalp = v.step("scalping")

    # The random-walk test carries the A27 question, not the day-close
    # statistic -- see A28 for why that one was demoted to context.
    #
    # And the condition below is deliberately narrow. "The test did not
    # reject" is NOT "gold does not revert": absence of evidence is not
    # evidence of absence, and an install tool that treats them as the same
    # thing has encoded the exact error this project spends its audit
    # entries guarding against. Only a rejection in the WRONG direction --
    # moves that continue, when the strategy is built on moves that come
    # back -- contradicts the premise. Everything else is inconclusive and
    # lands in the "not yet" branch further down.
    premise_contradicted = bool(walk and "FALSCHE Richtung" in walk.headline)
    if premise_contradicted and day and day.status != "ok":
        v.recommendation = "NICHT INSTALLIEREN"
        v.reasoning = [
            "Auf dieser Historie laufen Bewegungen weiter, statt "
            "zurueckzukommen —",
            "der Varianztest verwirft den Zufallspfad in die dem Ansatz",
            "entgegengesetzte Richtung. Die Strategie handelt gegen die",
            "Bewegung, und auf denselben Daten zeigt sie keine Kante.",
            "",
            "Das bestaetigt, was A27 vermutet hat: Die gemessene Kante war",
            "eine Eigenschaft des Simulators, nicht von Gold.",
            "",
            "Das ist ein gutes Ergebnis. Es hat nichts gekostet ausser einer",
            "halben Stunde, und es verhindert eine Demo-Phase, die Wochen",
            "gedauert und dasselbe herausgefunden haette.",
            "",
            "Die Arbeit gehoert jetzt in die Einstiegsregel — und zwar in",
            "eine, die MIT der Bewegung geht statt gegen sie.",
        ]
        return

    if day and day.status == "fail":
        v.recommendation = "NICHT INSTALLIEREN"
        v.reasoning = [
            "Die Tagesspanne-Strategie verliert auf echten Daten, und das",
            "Band ist eindeutig. Ein Expert Advisor waere hier ein sehr",
            "disziplinierter Weg, Geld zu verlieren.",
        ]
        return

    if day and day.status == "ok":
        v.recommendation = "INSTALLIEREN — im Advisor-Modus"
        v.reasoning = [
            "Die Kante ist auf echten Daten messbar. Das ist der erste Beleg",
            "dieses Projekts, der nicht vom Simulator kommt.",
            "",
            "Trotzdem im Advisor-Modus starten: Ein Backtest auf einer Datei",
            "kennt keinen Slippage-Ausreisser, keine Requotes und keinen",
            "Broker, der um 22:00 den Spread auf 5 $/oz stellt. Lass ihn",
            "zeichnen und rechnen, vergleiche seine Einschaetzung mit deiner,",
            "und schalte erst um, wenn du beides eine Woche gesehen hast.",
        ]
        if scalp and scalp.status == "fail":
            v.reasoning.append("")
            v.reasoning.append(
                "Achtung: Das gilt fuer die Tagesspanne-Strategie (Setup DR). "
                "Die Scalping-Setups S1-S6, die der EA standardmaessig "
                "handelt, verlieren auf denselben Daten — die muessen "
                "abgeschaltet bleiben.")
        return

    v.recommendation = "NOCH NICHT INSTALLIEREN"
    v.reasoning = [
        "Kein Ergebnis in die eine oder andere Richtung. Das ist der",
        "haeufigste Ausgang und kein Grund zur Eile: Was hier nicht als Kante",
        "sichtbar ist, wird es durch eine Demo-Phase nicht.",
        "",
        "Sinnvoll als naechstes:",
        "  * mehr Historie, falls die Datei kurz ist",
        "  * `python -m metals dayrange --file ... --risk 1` mit anderen",
        "    Konto-Groessen, um zu sehen, ob die 1-%-Regel die Stichprobe",
        "    frisst",
        "  * die Einstiegsregel ueberarbeiten statt den Ausstieg",
    ]
    if walk and walk.status == "warn" and "Zufallspfad" in walk.headline:
        v.reasoning.append("")
        v.reasoning.append(
            "Und der Varianztest sagt: Auf dieser Historie ist Gold von "
            "einem Zufallspfad nicht zu unterscheiden. Auf einem Zufallspfad "
            "hat jede Ausstiegsregel denselben Erwartungswert — der Hebel "
            "waere dann nicht das Ziel, sondern die Zahl der Trades und was "
            "jeder kostet.")


def render(v: Verdict) -> str:
    lines = ["", "=" * 74,
             "  URTEIL AUF ECHTEN DATEN",
             "=" * 74, ""]
    titles = {
        "daten": "1. Die Datei",
        "rueckkehr": "2. Kehrt Gold zur Tagesmitte zurueck?",
        "zufallspfad": "3. Ist Gold von einem Zufallspfad zu unterscheiden?",
        "tagesspanne": "4. Was verdient die Tagesspanne-Strategie?",
        "scalping": "5. Was verdienen die Scalping-Setups S1-S6?",
    }
    for s in v.steps:
        lines.append(f"  [{s.mark}] {titles.get(s.name, s.name)}")
        lines.append(f"         {s.headline}")
        for d in s.detail:
            lines.append(f"           {d}")
        lines.append("")

    lines.append("=" * 74)
    lines.append(f"  EMPFEHLUNG: {v.recommendation}")
    lines.append("=" * 74)
    for line in v.reasoning:
        lines.append(f"  {line}")
    lines.append("")
    return "\n".join(lines)
