"""Predict a move from the day's range, then bank half of it.

The strategy as the user specified it:

    The bot looks at the chart -- the day's high and low, and the candles --
    and decides buy or sell. It predicts how far the move goes. When half of
    that prediction is reached, it closes and opens the next one. If the
    trade goes the wrong way, a stop closes it.

The prediction is the part that makes this different from `microscalp`, and
it is the part that makes it testable. A fixed tiny take-profit has no
opinion about the market; a predicted target does, and an opinion can be
wrong in a way that shows up in the numbers.

**Why taking half is not a detail.** Closing at half the predicted move
sounds merely cautious. It is actually the whole risk profile: the bot is
right about direction more often than it is right about distance, and half a
target is reached far more often than a full one. That buys a higher win rate
at a lower reward per trade -- which is a real trade, not a free lunch, and
`optimise` measures where the exchange rate is best.

**The stop is expressed in the same currency as the target**, as a fraction
of the predicted move. Predict +30, take profit at +15, stop at -15, and the
trade is a coin flip that needs to be right more than half the time. Set the
stop tighter and the win rate falls while the loser costs less. That single
ratio is the strategy's main dial and it is swept, not guessed.

    from metals.dayrange import DayRangeConfig, sweep, report_sweep
    print(report_sweep(sweep(DayRangeConfig())))
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta

from .candles import Candle, CandleSeries
from .microscalp import EU_RETAIL_LEVERAGE_GOLD, STOP_OUT_LEVEL
from .risk import (DAILY_LOSS_LIMIT_PCT, MAX_RISK_PER_TRADE_PCT,
                   NEWS_BLACKOUT_MINUTES, RULES, WEEKEND_FLAT_HOUR_UTC)
from .specs import get_spec

# A day's range on gold is a real reference level -- the high and low that
# actual participants traded against -- which is why it is the anchor here
# rather than a moving average. Before this many bars have printed, "today's
# range" is a couple of candles and means nothing.
MIN_BARS_FOR_A_RANGE = 60

# Broker rollover in UTC. Most XAUUSD brokers keep server time at GMT+2/+3,
# so their 00:00 falls here -- the same assumption the backtest already makes
# with --tz broker_gmt3.
ROLLOVER_HOUR_UTC = 21

# Weekday whose rollover is charged three times, covering the weekend that
# settles but does not trade. Monday=0, so this is Wednesday.
TRIPLE_SWAP_WEEKDAY = 2


@dataclass(frozen=True)
class DayRangeConfig:
    symbol: str = "XAUUSD"
    start_equity: float = 20_000.0
    lot: float = 0.10
    max_positions: int = 1
    leverage: float = EU_RETAIL_LEVERAGE_GOLD
    spread_usd_oz: float = 0.30

    # Slippage, as a fraction of the spread, charged on entry alongside it.
    # The same convention and the same default as metals/backtest.py, which
    # is the point: two engines in this project that charged different costs
    # for the same trade would make their results incomparable, and the
    # project rule is that backtest, paper and live share the code.
    #
    # This module charged spread only until the divergence was noticed, so
    # every figure produced before that was measured at two thirds of the
    # cost the backtest would have applied. See docs/REPO-AUDIT.md, A8.
    slippage_fraction: float = 0.5

    # Risk per trade in percent of equity. When set, the lot size is derived
    # from the stop distance instead of `lot` being used as a constant, and
    # it is clamped to the hard limit in metals/risk.py -- this dial can only
    # ever make a position smaller than the rule allows, never larger.
    #
    # A fixed lot is what most published gold EAs use and it is the reason
    # they destroy small accounts: 0.10 lot is a sensible size at 20,000 and
    # a bet-the-account size at 400. See metals/claims.py, finding A1.
    risk_pct: float | None = None
    lot_step: float = 0.01
    min_lot: float = 0.01

    # Ceiling on what a single signal may risk, as a share of equity, when
    # the position cannot be made any smaller. Where `risk_pct` scales the
    # position down to fit the stop, this instead **declines the trade** when
    # even the minimum lot would risk too much.
    #
    # It exists because on a small gold account those are different things.
    # Scaling down is impossible below 0.01 lot, so the only remaining
    # control is which setups to accept -- and the setups differ enormously:
    # one session's stops ranged from 8.59 to 84.51 USD, a factor of ten.
    # Taking only the narrow ones is the third option between "trade nothing"
    # and "let the market decide how much to bet".
    max_risk_pct: float | None = None

    # --- the exit scheme the MQL5 expert actually runs -------------------
    # Off by default, so every number measured so far keeps its meaning.
    # When on, the exit matches SECTION 10 of the EA: close a share of the
    # position at a near target, move the stop to break-even, and trail the
    # remainder with ATR up to a far target.
    #
    # It exists because audit finding A11 could only *estimate* the cost of
    # the difference, by blending two rows of a target sweep. An estimate of
    # what the thing that will actually trade does is not good enough when
    # the alternative is to measure it.
    ea_exit: bool = False
    first_target_r: float = 0.5        # InpFirstTargetR
    first_target_fraction: float = 0.60  # InpFirstTargetPct / 100
    runner_target_r: float = 2.5       # InpRunnerTargetR
    trail_atr_mult: float = 1.2        # InpTrailAtrMult

    # High-impact releases to stand aside for, as UTC (hour, minute) pairs.
    # Rule R4 bans an entry within NEWS_BLACKOUT_MINUTES either side of one.
    #
    # This exists because the strategy was bypassing R4 the same way it was
    # bypassing R1 before the audit: the rule lived in metals/risk.py, was
    # enforced by size_position, and the code that actually trades never
    # called it. See docs/REPO-AUDIT.md, finding A7.
    #
    # Times rather than dates, because the simulator's days are synthetic.
    # Against real history, feed the actual release times from
    # metals.sources.calendar -- which is where the live rule lives, and this
    # field deliberately does not duplicate its schedule.
    news_times_utc: tuple[tuple[int, int], ...] = ()

    # Rule M5: flat by Friday WEEKEND_FLAT_HOUR_UTC. On by default, because
    # M5 is one of the hard metal rules and not a preference -- a stop does
    # not protect against a weekend gap, it just becomes the price you get
    # after the gap.
    #
    # Found the same way as A1 and A7: the rule lived in metals/risk.py,
    # size_position enforced it, and dayrange.py contained no occurrence of
    # "weekend" at all. Three rules now, all with the same shape -- the code
    # that actually trades was the last place the rules reached.
    weekend_flat: bool = True

    # Rule R2: at -DAILY_LOSS_LIMIT_PCT on the day, no new entries until the
    # next session. On by default, same reasoning as M5 -- it is a hard rule.
    #
    # Found by the coverage table below rather than by reading, which was the
    # point of building it: R1, R4 and M5 each took a manual discovery, and
    # this one did not.
    daily_loss_limit: bool = True

    # --- the prediction ---
    # How close to an end of the day's range price must sit before the bot
    # will trade against it. 0.30 means the lower or upper third.
    edge_fraction: float = 0.30
    # How many recent candles must agree with the direction. The user's "und
    # die Kerzen": price being low is not a signal, price being low and
    # turning is.
    confirm_bars: int = 3
    # A range narrower than this many ATRs is noise, not structure.
    min_range_atr: float = 2.0

    # --- what "a day" and "enough of it" mean in bars ---
    # Both defaults describe M1, which is what the strategy was built on.
    # They are configuration rather than constants only so the same rules can
    # be run on M5 or M15 without silently meaning "five days of range".
    bars_per_day: int = 1_440
    min_bars_for_range: int = MIN_BARS_FOR_A_RANGE

    # Overnight financing, in USD per standard lot per night, signed from the
    # trader's point of view. Long gold is charged, short gold is credited,
    # and the asymmetry is large -- it is the cost of carrying metal.
    #
    # These are one broker's published numbers and vary widely between
    # brokers; they are here so the cost exists in the model at all, which
    # matters far more than the third decimal. Set both to 0.0 to measure
    # without it.
    swap_long_usd_per_lot: float = -73.6
    swap_short_usd_per_lot: float = 30.0

    # UTC hours in which an entry may be opened. Empty means all of them,
    # which is the default: a session filter is a claim to be measured, not a
    # setting to be assumed. See metals/claims.py, claim C3.
    trade_hours_utc: tuple[int, ...] = ()

    # --- what to do with it ---
    # Close at this fraction of the predicted move. The user's "die Hälfte".
    take_fraction: float = 0.50
    # Stop at this fraction of the predicted move, on the other side.
    stop_fraction: float = 0.50
    # Give up if the target was not reached within this many bars.
    time_stop_bars: int = 240


@dataclass(frozen=True)
class Prediction:
    direction: str          # "long" | "short" | "none"
    entry: float = 0.0
    target: float = 0.0     # where the bot thinks price is going
    reason: str = ""

    @property
    def move(self) -> float:
        return abs(self.target - self.entry)


def in_news_blackout(ts: datetime,
                     news_times_utc: tuple[tuple[int, int], ...]) -> bool:
    """Rule R4: no entry within the blackout window of a release.

    The window comes from metals.risk so there is one number, not two. This
    is not a filter chosen because a backtest liked it -- the simulator
    cannot evaluate it at all, since its jumps are random rather than tied to
    a clock. It is here because the documented behaviour of gold around CPI,
    NFP and FOMC (spreads from 1-2 points to 15-20, plus slippage) makes an
    entry in that window a different trade from the one the rules priced.
    """
    if not news_times_utc:
        return False
    minutes_now = ts.hour * 60 + ts.minute
    return any(abs(minutes_now - (h * 60 + m)) <= NEWS_BLACKOUT_MINUTES
               for h, m in news_times_utc)


# --------------------------------------------------------------------------
# Which hard rules this engine implements, and which it does not
# --------------------------------------------------------------------------
# Three rules were found missing here one at a time, by reading: R1 (A1),
# R4 (A7), M5 (A15). Each time the fix was to carry the rule across by hand,
# and each time the *next* gap stayed invisible until somebody happened to
# look. That is the actual defect, and it is what this table fixes.
#
# Every rule in metals.risk.RULES must appear below with a status. A test
# fails when one does not, so a rule added to the risk layer cannot quietly
# fail to reach the code that trades.
#
# "n/a" is a legitimate answer and requires a reason. A rule that does not
# apply is different from a rule nobody thought about, and the difference has
# to be written down or it is lost.
RULE_COVERAGE: dict[str, tuple[str, str]] = {
    "R1": ("implemented", "lots_for caps risk_pct at MAX_RISK_PER_TRADE_PCT"),
    "R2": ("implemented", "daily loss limit stops new entries for the day"),
    "R3": ("n/a", "reward/risk follows from take_fraction and stop_fraction, "
                  "which are swept rather than fixed at 1:2. A hard 1:2 floor "
                  "would delete the strategy's main dial."),
    "R4": ("implemented", "in_news_blackout refuses entries around releases"),
    "R5": ("implemented", "rollover is handled; the Friday late session is "
                          "covered by M5 below"),
    "R6": ("n/a", "size never increases after a loss by construction: it is "
                  "either a constant lot or derived from equity, which falls. "
                  "There is no path that scales up on a loser."),
    "R6b": ("implemented", "max_positions, default 1"),
    "R7": ("implemented", "every trade carries stop_loss from the moment it "
                          "is opened; there is no unprotected path"),
    "R8": ("implemented", "lots_for takes the stop distance as input, so size "
                          "follows the stop and never the reverse"),
    "M1": ("implemented", "min_range_atr refuses ranges narrower than the ATR "
                          "multiple"),
    "M2": ("n/a", "the stop is a fraction of the predicted move, not a level "
                  "with a buffer. There is no structural level here to sit "
                  "beyond."),
    "M3": ("implemented", "spread_usd_oz is charged with slippage on entry"),
    "M4": ("n/a", "this engine trades one symbol. The shared gold/silver "
                  "budget belongs to the layer that runs both, not here."),
    "M5": ("implemented", "past_weekend_flat closes and blocks from Friday"),
    "M6": ("n/a", "stops are derived from the predicted move, so they land "
                  "where the arithmetic puts them rather than on a chosen "
                  "level that could be a round number."),
}


def uncovered_rules() -> list[str]:
    """Rules in the risk layer with no entry above. Should always be empty."""
    return [key for key in RULES if key not in RULE_COVERAGE]


def past_weekend_flat(ts: datetime) -> bool:
    """Rule M5: Friday from WEEKEND_FLAT_HOUR_UTC onward, be flat.

    Like the news blackout, this is not a filter a backtest chose. The
    simulator cannot argue for or against it: it skips the closed hours
    entirely, so a position carried across a weekend simply resumes at the
    next bar with no gap at all. Real gold gaps at the Sunday open, and a
    stop does not protect against a gap -- it becomes the price you get
    *after* it.

    So the measurement here will say "no difference", and that is the
    expected answer rather than evidence the rule is pointless. What the
    test checks is that the rule is obeyed, not that it pays.
    """
    return ts.weekday() == 4 and ts.hour >= WEEKEND_FLAT_HOUR_UTC


def lots_for(cfg: DayRangeConfig, equity: float, stop_distance_usd: float,
             oz_per_lot: float) -> float:
    """How large the position may be.

    Returns 0.0 when the account cannot carry even the minimum lot at this
    stop distance -- which is a real answer, not an error. A 400-euro account
    meeting a 20-dollar stop is being told the truth: this trade does not fit
    inside a 1% risk limit, so it is not taken. Rounding it up to the broker
    minimum instead is exactly how small accounts die.
    """
    if cfg.risk_pct is None:
        return cfg.lot
    if stop_distance_usd <= 0 or equity <= 0:
        return 0.0
    pct = min(cfg.risk_pct, MAX_RISK_PER_TRADE_PCT)   # R1, and it is a cap
    money = equity * pct / 100.0
    raw = money / (stop_distance_usd * oz_per_lot)
    lots = int(raw / cfg.lot_step) * cfg.lot_step     # floor, never round up
    return round(lots, 8) if lots >= cfg.min_lot else 0.0


def _atr(bars: list[Candle], i: int, period: int = 14) -> float:
    lo = max(1, i - period + 1)
    trs = [max(b.high - b.low,
               abs(b.high - bars[j - 1].close),
               abs(b.low - bars[j - 1].close))
           for j, b in enumerate(bars[lo:i + 1], start=lo)]
    return statistics.fmean(trs) if trs else 0.0


def predict(bars: list[Candle], i: int, cfg: DayRangeConfig) -> Prediction:
    """Read the day's range and the last few candles, and form an opinion.

    Deliberately simple and fully inspectable: price near one end of the
    day's range, with the recent candles turning away from that end, is a
    move back towards the other end. That is the rule the user described, and
    writing it down this plainly is what makes it possible to find out
    whether it is true.
    """
    if i < cfg.min_bars_for_range:
        return Prediction("none", reason="not enough of the day yet")

    if cfg.trade_hours_utc and bars[i].ts.hour not in cfg.trade_hours_utc:
        return Prediction("none", reason="outside the chosen session")

    if in_news_blackout(bars[i].ts, cfg.news_times_utc):
        return Prediction("none", reason="R4: high-impact release nearby")

    day = bars[max(0, i - cfg.bars_per_day):i + 1]   # the last 24h of bars
    high = max(b.high for b in day)
    low = min(b.low for b in day)
    span = high - low
    price = bars[i].close

    atr = _atr(bars, i)
    if atr <= 0 or span < atr * cfg.min_range_atr:
        return Prediction("none", reason="the day's range is too narrow to lean on")

    position = (price - low) / span              # 0 at the low, 1 at the high

    recent = bars[i - cfg.confirm_bars + 1:i + 1]
    rising = all(b.close >= b.open for b in recent)
    falling = all(b.close <= b.open for b in recent)

    if position <= cfg.edge_fraction and rising:
        return Prediction("long", price, high,
                          f"lower third of the day's range and {cfg.confirm_bars} "
                          f"candles turning up")
    if position >= 1 - cfg.edge_fraction and falling:
        return Prediction("short", price, low,
                          f"upper third of the day's range and {cfg.confirm_bars} "
                          f"candles turning down")
    return Prediction("none", reason="price is mid-range or not turning")


@dataclass
class Trade:
    long: bool
    entry: float
    lots: float
    take_profit: float
    stop_loss: float
    predicted: float
    opened_at: int
    # Set only under the EA exit scheme, which closes part of the position
    # at a near target and lets the rest run. The original stop distance is
    # kept because R has to stay measured against the risk the trade was
    # opened with -- moving the stop to break-even must not silently
    # redefine what one R is.
    original_lots: float = 0.0
    original_risk_per_unit: float = 0.0
    partial_taken: bool = False
    banked_pnl: float = 0.0
    closing_in_full: bool = False

    def __post_init__(self) -> None:
        if not self.original_lots:
            self.original_lots = self.lots
        if not self.original_risk_per_unit:
            self.original_risk_per_unit = abs(self.entry - self.stop_loss)


@dataclass
class Result:
    config: DayRangeConfig
    start_equity: float
    end_equity: float
    trades: int = 0
    wins: int = 0
    losses: int = 0
    signals: int = 0
    r_multiples: list[float] = field(default_factory=list)
    exits: dict[str, int] = field(default_factory=dict)
    stopped_out: bool = False
    # Signals the account was too small to act on. Counted rather than
    # silently dropped, because "the strategy made 4% " means something
    # different when it also refused nine trades out of ten.
    skipped_too_small: int = 0
    skipped_no_margin: int = 0
    skipped_stop_too_wide: int = 0
    partials_taken: int = 0
    # Bars on which R2 held new entries back. Counted rather than
    # silent, because 'the strategy made 4%' means something
    # different when it also spent a third of the run switched off.
    days_stopped_out_of_risk: int = 0
    # Trades where the position could not be split and the EA
    # therefore closed in full at the first target. On a
    # minimum-lot account this is every trade.
    unsplittable_closes: int = 0
    # Positive means financing cost the account money over the run. Tracked
    # separately from trade P&L because it is not a trading result -- it is
    # rent, and it accrues whether the position is right or wrong.
    swap_paid_usd: float = 0.0
    nights_held: int = 0
    # Equity marked to market every bar, not just at the close. The floating
    # value was already being computed for the stop-out check and thrown
    # away, so a run reported only what the account looked like once the
    # positions had resolved -- which is not what living through it felt
    # like, and not what a margin call responds to.
    peak_equity: float = 0.0
    trough_equity: float = 0.0
    max_drawdown_pct: float = 0.0
    # How far away the target sat, in dollars per ounce. Recorded because a
    # cost is only meaningful next to the move it is charged against: the
    # same 0.40 spread is a rounding error against a 20-dollar target and
    # fatal against a 10-cent one.
    target_distances: list[float] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        return self.wins / self.trades if self.trades else 0.0

    @property
    def return_pct(self) -> float:
        return (self.end_equity - self.start_equity) / self.start_equity * 100.0

    @property
    def expectancy_r(self) -> float:
        return statistics.fmean(self.r_multiples) if self.r_multiples else 0.0

    @property
    def mean_target_usd(self) -> float:
        return (statistics.fmean(self.target_distances)
                if self.target_distances else 0.0)

    @property
    def signals_acted_on(self) -> float:
        """Share of signals that became a trade. The account-size question."""
        return self.trades / self.signals if self.signals else 0.0


def run(cfg: DayRangeConfig | None = None, series: CandleSeries | None = None,
        seed: int = 42, bars: int = 20_000) -> Result:
    cfg = cfg or DayRangeConfig()
    from . import simulate
    if series is None:
        series = simulate.generate(bars=bars, timeframe="1m", seed=seed)
    candles = list(series.candles)
    oz = get_spec(cfg.symbol).contract_size_oz

    equity = cfg.start_equity
    res = Result(config=cfg, start_equity=equity, end_equity=equity,
                 peak_equity=equity, trough_equity=equity)
    open_trades: list[Trade] = []
    last_rollover: date | None = None
    # R2 bookkeeping. The trading day is bounded by the broker rollover, not
    # by midnight UTC -- otherwise the limit would reset in the middle of the
    # New York session, which is where the losses that trigger it happen.
    day_start_equity = equity
    current_day: date | None = None

    for i, bar in enumerate(candles):
        trading_day = (bar.ts.date() if bar.ts.hour < ROLLOVER_HOUR_UTC
                       else bar.ts.date() + timedelta(days=1))
        if current_day is None or trading_day != current_day:
            current_day = trading_day
            day_start_equity = equity

        # Overnight financing, charged before anything else this bar. A
        # position that is still open when the broker rolls the day pays for
        # the privilege, and for long gold that is not a rounding error.
        if bar.ts.hour >= ROLLOVER_HOUR_UTC and bar.ts.date() != last_rollover:
            if last_rollover is not None and open_trades:
                nights = 3 if bar.ts.weekday() == TRIPLE_SWAP_WEEKDAY else 1
                for t in open_trades:
                    rate = (cfg.swap_long_usd_per_lot if t.long
                            else cfg.swap_short_usd_per_lot)
                    charge = rate * t.lots * nights
                    equity += charge
                    res.swap_paid_usd -= charge
                    res.nights_held += nights
            last_rollover = bar.ts.date()

        still: list[Trade] = []
        for t in open_trades:
            if cfg.ea_exit and not t.partial_taken:
                # First target: bank part of the position and move the stop
                # to break-even, which is what makes the remainder a free
                # option. Checked before the stop test only when the bar did
                # not also reach the stop -- adverse-first still governs.
                r_unit = t.original_risk_per_unit
                first = (t.entry + r_unit * cfg.first_target_r if t.long
                         else t.entry - r_unit * cfg.first_target_r)
                reached = (bar.high >= first if t.long else bar.low <= first)
                stopped = (bar.low <= t.stop_loss if t.long
                           else bar.high >= t.stop_loss)
                if reached and not stopped:
                    part = round(t.lots * cfg.first_target_fraction, 8)
                    part = int(part / cfg.lot_step) * cfg.lot_step
                    if part >= cfg.min_lot and t.lots - part >= cfg.min_lot:
                        gain = (first - t.entry) if t.long else (t.entry - first)
                        t.banked_pnl += gain * part * oz
                        equity += gain * part * oz
                        t.lots = round(t.lots - part, 8)
                        t.stop_loss = t.entry          # break-even
                        t.take_profit = (
                            t.entry + r_unit * cfg.runner_target_r if t.long
                            else t.entry - r_unit * cfg.runner_target_r)
                        res.partials_taken += 1
                    else:
                        # Neither side of the split reaches the broker
                        # minimum, so the EA closes the position in full at
                        # the first target instead. This is not an edge
                        # case on a small account -- it is the *only* case:
                        # at 0.01 lot nothing can be split, so every trade
                        # caps at first_target_r and no runner ever exists.
                        t.take_profit = first
                        t.closing_in_full = True
                        res.unsplittable_closes += 1
                    t.partial_taken = True

            # No trail on a position the EA is closing outright. Letting it
            # run here would sometimes exit at a *better* trailed stop than
            # the first target, which flatters a path the expert does not
            # take.
            if (cfg.ea_exit and t.partial_taken and t.lots > 0
                    and not t.closing_in_full):
                # ATR trail on the remainder, never loosening.
                atr_now = _atr(candles, i)
                if atr_now > 0:
                    dist = atr_now * cfg.trail_atr_mult
                    candidate = (bar.close - dist if t.long
                                 else bar.close + dist)
                    if t.long and candidate > t.stop_loss:
                        t.stop_loss = candidate
                    elif not t.long and candidate < t.stop_loss:
                        t.stop_loss = candidate

            # Adverse first: when a bar spans both levels the stop is taken,
            # because which came first cannot be known from a bar.
            hit_stop = bar.low <= t.stop_loss if t.long else bar.high >= t.stop_loss
            hit_tp = bar.high >= t.take_profit if t.long else bar.low <= t.take_profit
            timed_out = i - t.opened_at >= cfg.time_stop_bars
            weekend = cfg.weekend_flat and past_weekend_flat(bar.ts)

            exit_price, why = None, ""
            if hit_stop:
                exit_price, why = t.stop_loss, "stop"
            elif hit_tp:
                exit_price, why = t.take_profit, "target"
            elif weekend:
                # Ahead of the time stop: a position that would otherwise be
                # held into Friday's close is exactly what M5 forbids.
                exit_price, why = bar.close, "weekend_flat"
            elif timed_out:
                exit_price, why = bar.close, "time_stop"

            if exit_price is None:
                still.append(t)
                continue

            pnl = ((exit_price - t.entry) if t.long else (t.entry - exit_price)) \
                * t.lots * oz
            # R is measured against the risk the trade was OPENED with, on
            # the size it was opened with. Using the current stop would make
            # every break-even exit an infinite R, and using the reduced
            # size would credit the runner with the whole trade's risk.
            risk = t.original_risk_per_unit * t.original_lots * oz
            pnl += t.banked_pnl
            equity += ((exit_price - t.entry) if t.long
                       else (t.entry - exit_price)) * t.lots * oz
            res.trades += 1
            res.exits[why] = res.exits.get(why, 0) + 1
            res.r_multiples.append(pnl / risk if risk > 0 else 0.0)
            if pnl > 0:
                res.wins += 1
            else:
                res.losses += 1
        open_trades = still

        used = sum(t.lots * oz * bar.close / cfg.leverage for t in open_trades)
        floating = sum(((bar.close - t.entry) if t.long else (t.entry - bar.close))
                       * t.lots * oz for t in open_trades)

        marked = equity + floating
        if marked > res.peak_equity:
            res.peak_equity = marked
        if res.trough_equity == 0.0 or marked < res.trough_equity:
            res.trough_equity = marked
        if res.peak_equity > 0:
            drop = (res.peak_equity - marked) / res.peak_equity * 100.0
            if drop > res.max_drawdown_pct:
                res.max_drawdown_pct = drop
        if used > 0 and (equity + floating) / used < STOP_OUT_LEVEL:
            for t in open_trades:
                pnl = ((bar.close - t.entry) if t.long else (t.entry - bar.close)) \
                    * t.lots * oz
                equity += pnl
                res.trades += 1
                res.losses += 1
                res.exits["broker_stop_out"] = res.exits.get("broker_stop_out", 0) + 1
            open_trades = []
            res.stopped_out = True
            if equity <= 0:
                equity = 0.0
                break

        day_loss_pct = ((day_start_equity - equity) / day_start_equity * 100.0
                        if day_start_equity > 0 else 0.0)
        daily_stop = (cfg.daily_loss_limit
                      and day_loss_pct >= DAILY_LOSS_LIMIT_PCT)
        if daily_stop:
            res.days_stopped_out_of_risk += 1

        if (len(open_trades) < cfg.max_positions and i < len(candles) - 1
                and not daily_stop
                and not (cfg.weekend_flat and past_weekend_flat(bar.ts))):
            p = predict(candles, i, cfg)
            if p.direction != "none":
                res.signals += 1
                long = p.direction == "long"
                cost = cfg.spread_usd_oz * (1 + cfg.slippage_fraction)
                entry = p.entry + cost if long else p.entry - cost
                move = p.move
                tp = entry + move * cfg.take_fraction if long \
                    else entry - move * cfg.take_fraction
                sl = entry - move * cfg.stop_fraction if long \
                    else entry + move * cfg.stop_fraction

                lots = lots_for(cfg, equity, abs(entry - sl), oz)
                if lots <= 0:
                    res.skipped_too_small += 1
                    continue

                if cfg.max_risk_pct is not None and equity > 0:
                    would_risk = abs(entry - sl) * lots * oz / equity * 100.0
                    if would_risk > cfg.max_risk_pct:
                        res.skipped_stop_too_wide += 1
                        continue

                need = lots * oz * bar.close / cfg.leverage
                if used + need <= equity + floating:
                    open_trades.append(Trade(long, entry, lots, tp, sl,
                                             p.target, i))
                    res.target_distances.append(abs(tp - entry))
                else:
                    res.skipped_no_margin += 1

    last = candles[-1].close
    for t in open_trades:
        remainder = ((last - t.entry) if t.long else (t.entry - last)) \
            * t.lots * oz
        pnl = remainder + t.banked_pnl
        # These used to be counted as trades and as wins or losses while
        # being left out of r_multiples, so expectancy was a mean over a
        # subset reported as if it covered everything. Every other exit path
        # records its R here; this one has to as well.
        risk = t.original_risk_per_unit * t.original_lots * oz
        equity += remainder
        res.trades += 1
        res.exits["still_open"] = res.exits.get("still_open", 0) + 1
        res.r_multiples.append(pnl / risk if risk > 0 else 0.0)
        if pnl > 0:
            res.wins += 1
        else:
            res.losses += 1
    res.end_equity = max(0.0, equity)
    return res


@dataclass
class Sweep:
    config: DayRangeConfig
    runs: list[Result]

    @property
    def median_return_pct(self) -> float:
        return statistics.median(r.return_pct for r in self.runs)

    @property
    def mean_expectancy_r(self) -> float:
        vals = [r.expectancy_r for r in self.runs if r.trades]
        return statistics.fmean(vals) if vals else 0.0

    @property
    def mean_win_rate(self) -> float:
        vals = [r.win_rate for r in self.runs if r.trades]
        return statistics.fmean(vals) if vals else 0.0

    @property
    def mean_trades(self) -> float:
        return statistics.fmean(r.trades for r in self.runs)

    @property
    def losing_rate(self) -> float:
        return sum(1 for r in self.runs if r.return_pct < 0) / len(self.runs)

    @property
    def stop_out_rate(self) -> float:
        return sum(1 for r in self.runs if r.stopped_out) / len(self.runs)

    @property
    def mean_target_usd(self) -> float:
        vals = [r.mean_target_usd for r in self.runs if r.target_distances]
        return statistics.fmean(vals) if vals else 0.0

    @property
    def mean_signals(self) -> float:
        return statistics.fmean(r.signals for r in self.runs)

    @property
    def share_of_signals_taken(self) -> float:
        return statistics.fmean(r.signals_acted_on for r in self.runs)

    @property
    def mean_skipped_too_small(self) -> float:
        return statistics.fmean(r.skipped_too_small for r in self.runs)

    @property
    def worst_return_pct(self) -> float:
        return min(r.return_pct for r in self.runs)


def sweep(cfg: DayRangeConfig | None = None, markets: int = 40,
          bars: int = 20_000, seed_base: int = 1_000) -> Sweep:
    cfg = cfg or DayRangeConfig()
    return Sweep(cfg, [run(cfg, seed=seed_base + i, bars=bars)
                       for i in range(markets)])


def optimise(base: DayRangeConfig | None = None, markets: int = 20,
             bars: int = 15_000, seed_base: int = 1_000
             ) -> list[tuple[DayRangeConfig, Sweep]]:
    """Sweep the dials that matter, ranked by expectancy per trade.

    Ranked on expectancy rather than total return because return depends on
    how many signals a particular market happened to offer, which says more
    about the market than about the rules.
    """
    base = base or DayRangeConfig()
    out: list[tuple[DayRangeConfig, Sweep]] = []
    for take in (0.30, 0.50, 0.75, 1.00):
        for stop in (0.25, 0.50, 1.00):
            for edge in (0.20, 0.30, 0.40):
                for confirm in (2, 3):
                    cfg = replace(base, edge_fraction=edge,
                                  confirm_bars=confirm, take_fraction=take,
                                  stop_fraction=stop)
                    out.append((cfg, sweep(cfg, markets=markets, bars=bars,
                                           seed_base=seed_base)))
    out.sort(key=lambda pair: pair[1].mean_expectancy_r, reverse=True)
    return out


def report_run(r: Result, source: str = "simulated") -> str:
    """One run over one series -- the shape a real-history test produces.

    Separate from `report_sweep` because the two answer different questions
    and must not be confused. A sweep says what the rules do across many
    markets; this says what they did on the one history that actually
    happened, which is a single sample and is reported as one.
    """
    c = r.config
    lines = [f"TAGESSPANNE-STRATEGIE — EIN LAUF", "=" * 68]
    lines.append(f"  Daten: {source}")
    lines.append(f"  Mitnahme {c.take_fraction:.0%} · Stop {c.stop_fraction:.0%} "
                 f"· Zone {c.edge_fraction:.0%} · {c.confirm_bars} Kerzen")
    lines.append(f"  Kosten: Spread {c.spread_usd_oz:.2f} $ "
                 f"+ {c.slippage_fraction:.0%} Slippage")
    lines.append("")
    lines.append(f"  Signale            {r.signals:>8}")
    lines.append(f"  Trades             {r.trades:>8}")
    if r.skipped_too_small:
        lines.append(f"  abgelehnt (zu gross){r.skipped_too_small:>7}")
    if not r.trades:
        lines.append("")
        lines.append("  KEIN TRADE. Ohne Trades gibt es nichts auszuwerten —")
        lines.append("  das ist ein Ergebnis, kein Fehler.")
        return "\n".join(lines)

    lines.append(f"  Trefferquote       {r.win_rate * 100:>7.1f}%")
    lines.append(f"  Erwartungswert     {r.expectancy_r:>+7.3f}R")
    lines.append(f"  Rendite            {r.return_pct:>+7.2f}%")
    lines.append(f"  Ziel im Schnitt    {r.mean_target_usd:>7.2f} $/oz")
    if r.swap_paid_usd:
        lines.append(f"  Swap gezahlt       {r.swap_paid_usd:>+7.2f} $ "
                     f"({r.nights_held} Naechte)")
    lines.append("  Ausstiege: " + ", ".join(f"{k} {v}"
                                             for k, v in sorted(r.exits.items())))
    lines.append("")

    from .journal import mean_interval, trades_needed
    lo, hi = mean_interval(r.r_multiples)
    lines.append(f"  95%-Band auf den Erwartungswert: {lo:+.3f} bis {hi:+.3f} R")
    if lo <= 0 <= hi:
        lines.append("  -> Das Band schliesst die Null ein. Kein Vorteil belegt.")
    elif lo > 0:
        lines.append("  -> Das Band liegt ueber der Null.")
    else:
        lines.append("  -> Das Band liegt unter der Null.")
    sd = statistics.pstdev(r.r_multiples) if len(r.r_multiples) > 1 else 0.0
    need = trades_needed(0.1, sd) if sd > 0 else None
    if need:
        lines.append(f"  Fuer einen Vorteil von +0.10R braeuchte es rund "
                     f"{need:,} Trades.")
    if r.stopped_out:
        lines.append("  BROKER-STOP-OUT in diesem Lauf.")
    return "\n".join(lines)


def report_sweep(s: Sweep) -> str:
    c = s.config
    lines = [f"TAGESSPANNE-STRATEGIE — {len(s.runs)} MAERKTE", "=" * 68]
    lines.append(f"  Ziel: Vorhersage bis zum anderen Ende der Tagesspanne")
    lines.append(f"  Mitnahme bei {c.take_fraction:.0%} der Vorhersage · "
                 f"Stop bei {c.stop_fraction:.0%} · "
                 f"Einstiegszone aeusseres {c.edge_fraction:.0%} · "
                 f"{c.confirm_bars} Bestaetigungskerzen")
    lines.append("")
    lines.append(f"  Signale pro Markt     {s.mean_signals:>7.0f}")
    lines.append(f"  Trades pro Markt      {s.mean_trades:>7.0f}")
    # Printed before the win rate on purpose. A tiny account produces a
    # magnificent-looking hit rate on the two trades it could afford, and
    # reading that number without this one is how a 400-euro account gets
    # talked into starting.
    if s.mean_skipped_too_small >= 1:
        lines.append(f"  davon abgelehnt       {s.mean_skipped_too_small:>7.0f}"
                     f"   (Konto zu klein fuer 1% Risiko)")
        lines.append(f"  Signale genutzt       {s.share_of_signals_taken * 100:>6.1f}%")
    lines.append(f"  Trefferquote          {s.mean_win_rate * 100:>6.1f}%")
    lines.append(f"  Erwartungswert        {s.mean_expectancy_r:>+7.3f}R")
    lines.append(f"  Rendite im Median     {s.median_return_pct:>+6.1f}%")
    lines.append(f"  Maerkte mit Verlust   {s.losing_rate * 100:>6.0f}%")
    lines.append(f"  Broker-Stop-out       {s.stop_out_rate * 100:>6.0f}%")
    return "\n".join(lines)
