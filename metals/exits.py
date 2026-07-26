"""Exit management and stop-trading advice.

Two different questions live here, and conflating them is a common way to
give up an edge:

1. **When do I leave this trade?** Partial targets, break-even, trailing,
   time stop.
2. **When do I stop trading for the day?** Loss limit, win limit, session
   end, deterioration in conditions, fatigue proxies.

The second question is the one most systems ignore. On gold it matters more
than on slower instruments: the difference between a good day and a bad month
is usually the four trades taken after the session that should have ended.

Technique credits (ideas studied, code written here from scratch):
* Partial exit at a first target with a trailed remainder is standard scalping
  practice; the 60/40 split is the most commonly published ratio.
* A hard time stop -- close after N minutes regardless of P/L -- comes from
  scalping literature and exists because a scalp that has not worked within
  its expected horizon is no longer the trade that was entered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .candles import Candle
from .risk import DAILY_LOSS_LIMIT_PCT, AccountState
from .sessions import Quality, classify
from .specs import get_spec


class ExitReason(str, Enum):
    TARGET = "target"
    STOP = "stop"
    TRAIL = "trailing_stop"
    TIME = "time_stop"
    SESSION = "session_end"
    STRUCTURE = "structure_broken"
    MANUAL = "manual"
    OPEN = "still_open"


# --- Exit plan --------------------------------------------------------------

@dataclass
class ExitPlan:
    """How a position should be managed after entry.

    Defined *before* entry, because every rule here becomes negotiable once
    the position is open and moving.
    """

    symbol: str
    direction: str
    entry: float
    initial_stop: float
    # First target, taken partially. Expressed in R multiples of the initial risk.
    first_target_r: float = 1.0
    first_target_fraction: float = 0.6
    # Runner target.
    runner_target_r: float = 2.5
    # Move the stop to break-even only after the first target is banked.
    breakeven_after_first_target: bool = True
    # Trail the runner by this ATR multiple once break-even is set.
    trail_atr_multiple: float = 1.5
    # Close regardless of P/L after this many minutes.
    time_stop_minutes: int = 45
    # Never hold past this UTC time on a Friday.
    friday_flat_hour_utc: int = 19

    @property
    def risk_per_unit(self) -> float:
        return abs(self.entry - self.initial_stop)

    def price_at_r(self, r: float) -> float:
        """The price this many R away from entry, in the trade's direction."""
        offset = self.risk_per_unit * r
        return self.entry + offset if self.direction == "long" else self.entry - offset

    @property
    def first_target(self) -> float:
        return self.price_at_r(self.first_target_r)

    @property
    def runner_target(self) -> float:
        return self.price_at_r(self.runner_target_r)

    @property
    def blended_reward_risk(self) -> float:
        """Expected R if both targets are hit -- the honest headline number.

        A plan that takes 60% at 1R and 40% at 2.5R does not have a 1:2.5
        reward/risk. It has 0.6*1.0 + 0.4*2.5 = 1.6. Quoting the runner target
        as "the" R:R overstates the plan by more than half.
        """
        return (self.first_target_fraction * self.first_target_r
                + (1 - self.first_target_fraction) * self.runner_target_r)

    def describe(self) -> list[str]:
        spec = get_spec(self.symbol)
        return [
            f"Stop {spec.round_price(self.initial_stop):g} "
            f"({self.risk_per_unit:.2f} USD/oz = 1R)",
            f"Take {self.first_target_fraction:.0%} at "
            f"{spec.round_price(self.first_target):g} "
            f"({self.first_target_r:.1f}R)",
            f"Runner {1 - self.first_target_fraction:.0%} to "
            f"{spec.round_price(self.runner_target):g} "
            f"({self.runner_target_r:.1f}R), trailed by "
            f"{self.trail_atr_multiple:.1f}x ATR",
            "Break-even stop only after the first target is banked"
            if self.breakeven_after_first_target else
            "Stop stays at the structural level throughout",
            f"Close the whole position after {self.time_stop_minutes} minutes "
            f"regardless of P/L -- a scalp that has not worked inside its own "
            f"horizon is no longer the trade you entered",
            f"Blended reward/risk if both targets fill: "
            f"1:{self.blended_reward_risk:.2f} (not 1:{self.runner_target_r:.1f} "
            f"-- most of the position leaves at the first target)",
        ]


def build_exit_plan(symbol: str, direction: str, entry: float, stop: float,
                    atr_value: float, style: str = "scalp") -> ExitPlan:
    """Exit plan tuned to the trading style.

    Scalps need a tighter time stop and an earlier first target than swing
    trades, because their edge decays with time in the market rather than
    accumulating.
    """
    if style == "scalp":
        return ExitPlan(symbol, direction, entry, stop,
                        first_target_r=1.0, first_target_fraction=0.6,
                        runner_target_r=2.5, trail_atr_multiple=1.2,
                        time_stop_minutes=45)
    if style == "intraday":
        return ExitPlan(symbol, direction, entry, stop,
                        first_target_r=1.5, first_target_fraction=0.5,
                        runner_target_r=3.0, trail_atr_multiple=1.5,
                        time_stop_minutes=240)
    return ExitPlan(symbol, direction, entry, stop,
                    first_target_r=2.0, first_target_fraction=0.5,
                    runner_target_r=4.0, trail_atr_multiple=2.0,
                    time_stop_minutes=1440)


# --- Live position tracking -------------------------------------------------

@dataclass
class PositionState:
    """Mutable state of an open position, advanced bar by bar."""

    plan: ExitPlan
    opened_at: datetime
    remaining_fraction: float = 1.0
    current_stop: float = 0.0
    first_target_hit: bool = False
    best_price: float = 0.0
    worst_price: float = 0.0
    realised_r: float = 0.0
    closed: bool = False
    exit_reason: ExitReason = ExitReason.OPEN
    exit_price: float | None = None
    log: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.current_stop == 0.0:
            self.current_stop = self.plan.initial_stop
        if self.best_price == 0.0:
            self.best_price = self.plan.entry
        if self.worst_price == 0.0:
            self.worst_price = self.plan.entry

    @property
    def long(self) -> bool:
        return self.plan.direction == "long"

    def r_at(self, price: float) -> float:
        move = (price - self.plan.entry) if self.long else (self.plan.entry - price)
        return move / self.plan.risk_per_unit if self.plan.risk_per_unit else 0.0

    @property
    def mfe_r(self) -> float:
        """Maximum favourable excursion in R -- how far it went your way."""
        return self.r_at(self.best_price)

    @property
    def mae_r(self) -> float:
        """Maximum adverse excursion in R -- how far it went against you.

        Measured, not estimated. MAE is what tells you whether a stop was
        genuinely needed where it was: a book of winners whose MAE never
        exceeded -0.3R is a book whose stops are three times wider than they
        need to be.
        """
        return self.r_at(self.worst_price)


def advance(state: PositionState, candle: Candle, atr_value: float,
            worst_first: bool = True) -> PositionState:
    """Advance a position by one candle.

    `worst_first` resolves the ambiguity every bar-based backtest has: when a
    candle's range covers both the stop and the target, which was hit first?
    Assuming the stop is the honest default. Assuming the target inflates
    every result and is the single most common way a backtest lies.
    """
    if state.closed:
        return state

    plan = state.plan
    high, low = candle.high, candle.low

    # Track both excursions for MAE/MFE reporting. These are measured from
    # the bar's extremes, not inferred from the outcome.
    state.best_price = max(state.best_price, high) if state.long \
        else min(state.best_price, low)
    state.worst_price = min(state.worst_price, low) if state.long \
        else max(state.worst_price, high)

    stop_hit = low <= state.current_stop if state.long else high >= state.current_stop
    first_hit = (high >= plan.first_target if state.long
                 else low <= plan.first_target)
    runner_hit = (high >= plan.runner_target if state.long
                  else low <= plan.runner_target)

    if stop_hit and worst_first:
        return _close(state, state.current_stop,
                      ExitReason.TRAIL if state.first_target_hit else ExitReason.STOP,
                      candle.ts)

    # Partial at the first target.
    if first_hit and not state.first_target_hit:
        banked = plan.first_target_fraction
        state.realised_r += banked * plan.first_target_r
        state.remaining_fraction -= banked
        state.first_target_hit = True
        state.log.append(
            f"{candle.ts:%H:%M} banked {banked:.0%} at {plan.first_target:g} "
            f"(+{plan.first_target_r:.1f}R)"
        )
        if plan.breakeven_after_first_target:
            state.current_stop = plan.entry
            state.log.append(
                f"{candle.ts:%H:%M} stop to break-even -- the remainder is now "
                f"a free option, which is the point of taking the partial"
            )

    if runner_hit and state.remaining_fraction > 0:
        state.realised_r += state.remaining_fraction * plan.runner_target_r
        state.log.append(
            f"{candle.ts:%H:%M} runner filled at {plan.runner_target:g} "
            f"(+{plan.runner_target_r:.1f}R)"
        )
        state.remaining_fraction = 0.0
        return _close(state, plan.runner_target, ExitReason.TARGET, candle.ts)

    # Trail the runner once break-even is in place -- but never on the same
    # bar the first target filled. Trailing from the high of the bar that just
    # printed the target leaves the runner no room at all: it lands roughly
    # 0.4R above entry and is taken out on the next pullback, which turns
    # every runner into a small win and destroys the reason for holding one.
    if (state.first_target_hit and atr_value > 0
            and not first_hit):
        distance = atr_value * plan.trail_atr_multiple
        candidate = (high - distance) if state.long else (low + distance)
        improved = candidate > state.current_stop if state.long \
            else candidate < state.current_stop
        if improved:
            state.current_stop = candidate

    if stop_hit and not worst_first:
        return _close(state, state.current_stop,
                      ExitReason.TRAIL if state.first_target_hit else ExitReason.STOP,
                      candle.ts)

    # Time stop.
    age = (candle.ts - state.opened_at).total_seconds() / 60.0
    if age >= plan.time_stop_minutes:
        return _close(state, candle.close, ExitReason.TIME, candle.ts)

    # Friday flat.
    if candle.ts.weekday() == 4 and candle.ts.hour >= plan.friday_flat_hour_utc:
        return _close(state, candle.close, ExitReason.SESSION, candle.ts)

    return state


def _close(state: PositionState, price: float, reason: ExitReason,
           when: datetime) -> PositionState:
    if state.remaining_fraction > 0:
        state.realised_r += state.remaining_fraction * state.r_at(price)
        state.remaining_fraction = 0.0
    state.closed = True
    state.exit_reason = reason
    state.exit_price = price
    state.log.append(f"{when:%H:%M} closed: {reason.value} at {price:g} "
                     f"(total {state.realised_r:+.2f}R)")
    return state


# --- "When should I stop?" --------------------------------------------------

class StopSignal(str, Enum):
    CONTINUE = "continue"
    CAUTION = "caution"
    STOP_NOW = "stop_now"


@dataclass
class SessionAdvice:
    """The answer to 'when should I stop for today'."""

    signal: StopSignal
    reasons: list[str]
    minutes_of_good_session_left: int | None = None

    @property
    def should_stop(self) -> bool:
        return self.signal is StopSignal.STOP_NOW

    def headline(self) -> str:
        return {
            StopSignal.CONTINUE: "Weitermachen",
            StopSignal.CAUTION: "Vorsicht -- Bedingungen verschlechtern sich",
            StopSignal.STOP_NOW: "AUFHOEREN fuer heute",
        }[self.signal]


# A winning day given back is the most common way a good week is lost, so the
# system calls a stop on a large gain as well as on a loss.
DAILY_WIN_TARGET_PCT = 2.0
MAX_TRADES_PER_DAY = 4
MAX_CONSECUTIVE_LOSSES = 2
COOLDOWN_AFTER_LOSS_MINUTES = 20


@dataclass
class DayState:
    """What has happened today, for the stop-trading decision."""

    trades_taken: int = 0
    consecutive_losses: int = 0
    last_trade_closed_at: datetime | None = None
    last_trade_was_loss: bool = False


def session_advice(account: AccountState, day: DayState,
                   moment: datetime | None = None) -> SessionAdvice:
    """Should the user keep trading right now?

    Ordered so that the hard stops come first: once one of them fires, the
    softer signals are irrelevant and listing them only invites negotiation.
    """
    moment = moment or datetime.now(timezone.utc)
    reasons: list[str] = []

    # --- Hard stops --------------------------------------------------------
    if account.daily_stop_hit:
        return SessionAdvice(StopSignal.STOP_NOW, [
            f"Tagesverlust {account.day_pnl_pct:.2f}% hat das "
            f"-{DAILY_LOSS_LIMIT_PCT}%-Limit erreicht (Regel R2). Schluss fuer "
            f"heute. Der Trade, mit dem man einen schlechten Tag zurueckholen "
            f"will, ist der, der aus einem schlechten Tag einen schlechten "
            f"Monat macht.",
        ])

    if day.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
        return SessionAdvice(StopSignal.STOP_NOW, [
            f"{day.consecutive_losses} Verluste in Folge. Zwei Verluste "
            f"hintereinander heissen meist, dass das Marktregime nicht mehr zu "
            f"den Setups passt -- nicht, dass der naechste Trade faellig ist.",
        ])

    if day.trades_taken >= MAX_TRADES_PER_DAY:
        return SessionAdvice(StopSignal.STOP_NOW, [
            f"{day.trades_taken} Trades heute -- das Tageslimit von "
            f"{MAX_TRADES_PER_DAY}. Ab hier handelt man Langeweile, nicht "
            f"Setups.",
        ])

    if account.day_pnl_pct >= DAILY_WIN_TARGET_PCT:
        return SessionAdvice(StopSignal.STOP_NOW, [
            f"+{account.day_pnl_pct:.2f}% am Tag -- Tagesziel erreicht. Einen "
            f"guten Tag zurueckzugeben ist die haeufigste Art, eine gute Woche "
            f"zu verlieren. Der Markt laeuft morgen weiter.",
        ])

    state = classify(moment)
    if state.quality is Quality.AVOID:
        return SessionAdvice(StopSignal.STOP_NOW, [
            "Handelsfenster geschlossen: " + "; ".join(state.reasons),
        ])

    # --- Soft signals ------------------------------------------------------
    signal = StopSignal.CONTINUE

    if day.last_trade_was_loss and day.last_trade_closed_at:
        since = (moment - day.last_trade_closed_at).total_seconds() / 60.0
        if since < COOLDOWN_AFTER_LOSS_MINUTES:
            signal = StopSignal.CAUTION
            reasons.append(
                f"Letzter Trade war ein Verlust vor {since:.0f} Minuten. "
                f"{COOLDOWN_AFTER_LOSS_MINUTES} Minuten Abkuehlung, bevor der "
                f"naechste kommt -- der Trade direkt nach einem Verlust ist "
                f"statistisch der schlechteste des Tages."
            )

    if account.day_pnl_pct <= -DAILY_LOSS_LIMIT_PCT * 0.66:
        signal = StopSignal.CAUTION
        reasons.append(
            f"Bei {account.day_pnl_pct:.2f}% -- noch ein Verlust beendet den "
            f"Tag. Ab hier nur noch das beste Setup, nicht das naechste."
        )

    if day.trades_taken >= MAX_TRADES_PER_DAY - 1:
        signal = StopSignal.CAUTION
        reasons.append(
            f"{day.trades_taken} von {MAX_TRADES_PER_DAY} Trades verbraucht -- "
            f"noch einer."
        )

    if state.quality is Quality.MARGINAL:
        signal = StopSignal.CAUTION
        reasons.append("Sitzungsqualitaet nur maessig: "
                       + "; ".join(state.reasons))

    remaining = _minutes_of_good_session_left(moment)
    if remaining is not None and remaining < 30:
        signal = StopSignal.CAUTION
        reasons.append(
            f"Nur noch etwa {remaining} Minuten im guten Fenster. Ein Scalp "
            f"braucht bis zu 45 Minuten -- fuer einen neuen Einstieg ist es zu "
            f"spaet."
        )

    if not reasons:
        reasons.append(
            f"Bedingungen in Ordnung: {state.session.value} "
            f"({state.quality.value}), {day.trades_taken} von "
            f"{MAX_TRADES_PER_DAY} Trades, Tages-P/L "
            f"{account.day_pnl_pct:+.2f}%."
        )

    return SessionAdvice(signal, reasons, remaining)


def _minutes_of_good_session_left(moment: datetime) -> int | None:
    """Minutes until the prime window closes."""
    from .sessions import windows_for_day

    for w in windows_for_day(moment.date()):
        if w.name == "overlap" and w.contains(moment):
            return int((w.end_utc - moment).total_seconds() / 60)
    for w in windows_for_day(moment.date()):
        if w.name in ("london_killzone", "ny_killzone") and w.contains(moment):
            return int((w.end_utc - moment).total_seconds() / 60)
    return None
