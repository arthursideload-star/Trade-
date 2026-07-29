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

from .candles import Candle, CandleSeries
from .microscalp import EU_RETAIL_LEVERAGE_GOLD, STOP_OUT_LEVEL
from .risk import MAX_RISK_PER_TRADE_PCT
from .specs import get_spec

# A day's range on gold is a real reference level -- the high and low that
# actual participants traded against -- which is why it is the anchor here
# rather than a moving average. Before this many bars have printed, "today's
# range" is a couple of candles and means nothing.
MIN_BARS_FOR_A_RANGE = 60


@dataclass(frozen=True)
class DayRangeConfig:
    symbol: str = "XAUUSD"
    start_equity: float = 20_000.0
    lot: float = 0.10
    max_positions: int = 1
    leverage: float = EU_RETAIL_LEVERAGE_GOLD
    spread_usd_oz: float = 0.30

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
    res = Result(config=cfg, start_equity=equity, end_equity=equity)
    open_trades: list[Trade] = []

    for i, bar in enumerate(candles):
        still: list[Trade] = []
        for t in open_trades:
            # Adverse first: when a bar spans both levels the stop is taken,
            # because which came first cannot be known from a bar.
            hit_stop = bar.low <= t.stop_loss if t.long else bar.high >= t.stop_loss
            hit_tp = bar.high >= t.take_profit if t.long else bar.low <= t.take_profit
            timed_out = i - t.opened_at >= cfg.time_stop_bars

            exit_price, why = None, ""
            if hit_stop:
                exit_price, why = t.stop_loss, "stop"
            elif hit_tp:
                exit_price, why = t.take_profit, "target"
            elif timed_out:
                exit_price, why = bar.close, "time_stop"

            if exit_price is None:
                still.append(t)
                continue

            pnl = ((exit_price - t.entry) if t.long else (t.entry - exit_price)) \
                * t.lots * oz
            risk = abs(t.entry - t.stop_loss) * t.lots * oz
            equity += pnl
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

        if len(open_trades) < cfg.max_positions and i < len(candles) - 1:
            p = predict(candles, i, cfg)
            if p.direction != "none":
                res.signals += 1
                long = p.direction == "long"
                entry = p.entry + cfg.spread_usd_oz if long \
                    else p.entry - cfg.spread_usd_oz
                move = p.move
                tp = entry + move * cfg.take_fraction if long \
                    else entry - move * cfg.take_fraction
                sl = entry - move * cfg.stop_fraction if long \
                    else entry + move * cfg.stop_fraction

                lots = lots_for(cfg, equity, abs(entry - sl), oz)
                if lots <= 0:
                    res.skipped_too_small += 1
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
        pnl = ((last - t.entry) if t.long else (t.entry - last)) * t.lots * oz
        equity += pnl
        res.trades += 1
        res.exits["still_open"] = res.exits.get("still_open", 0) + 1
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
