"""The "in and out quickly, close it the moment it is green" strategy.

Described by the user, and implemented here exactly as described rather than
argued with, because the argument is settled by measurement and not by
opinion:

    Open one or more fixed-size positions, watch them, and close each one as
    soon as it shows a profit. Then open the next. No stop loss was mentioned.

This is a real pattern with a real name -- taking profit at a fixed small
distance while letting adverse positions run -- and the reason it is
convincing from the inside is that **it works most of the time**. That is not
an illusion: the win rate genuinely is very high. Nearly every trade closes
green, because a trade is only closed when it *is* green.

What that arrangement does is move the losses out of the win rate and into
two places where they are easy to miss:

*The tail.* A position that never comes back is never closed, so it is not a
"loss" in the statistics -- it is an open position. It stops being invisible
at the margin call, and by then it is the only trade that mattered.

*The margin.* Several 0.1-lot positions on a small account consume most of
the free margin, so the broker's stop-out arrives long before the trader's
own judgement does. This module models that explicitly, because it is the
mechanism that actually ends the account, and a backtest without it produces
a smooth rising curve that has nothing to do with the outcome.

Everything is parameterised so the strategy can be given its best shot: take
profit distance, an optional stop, how positions are sized, how direction is
chosen, and the spread. `optimise` sweeps them and reports what the best
configuration achieves -- which is the honest form of "training it".

    from metals.microscalp import MicroConfig, run, report
    print(report(run(MicroConfig())))
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass, field

from .candles import Candle, CandleSeries
from .specs import get_spec

# Broker mechanics. These are not strategy choices -- they are the terms the
# account is actually held under, and they are what the strategy runs into.
# EU retail leverage for gold is capped at 20:1 by the ESMA product
# intervention rules, which member states adopted. That is not a broker
# setting -- it is the law the account is opened under, and it decides
# whether a 0.1 lot position can be opened at all. Offshore brokers offer
# 1:500; that is a different regulatory regime, not a better deal.
EU_RETAIL_LEVERAGE_GOLD = 20.0
DEFAULT_LEVERAGE = EU_RETAIL_LEVERAGE_GOLD
# Below this ratio of equity to used margin the broker closes positions
# itself, worst one first. 50% is not a convention but the ESMA margin
# close-out rule, applied per account.
STOP_OUT_LEVEL = 0.50


@dataclass(frozen=True)
class MicroConfig:
    """One configuration of the strategy."""

    symbol: str = "XAUUSD"
    start_equity: float = 1_000.0
    lot: float = 0.10
    # "one or more 0.1 trades depending on how much is in the account"
    max_positions: int = 3
    equity_per_position: float = 300.0
    # Close as soon as it shows a profit. Expressed in USD per ounce *beyond*
    # the spread, since a position opens underwater by exactly the spread and
    # "in profit" has to mean net.
    take_profit_usd_oz: float = 0.10
    # None reproduces what was described: nothing closes a losing position.
    stop_loss_usd_oz: float | None = None
    spread_usd_oz: float = 0.30
    leverage: float = DEFAULT_LEVERAGE
    # long | short | follow (continue the last bar) | fade (against it) |
    # random
    direction: str = "follow"
    # Wait this many bars after a close before opening again. 0 is the purest
    # form of what was described: always in the market.
    cooldown_bars: int = 0


@dataclass
class Position:
    long: bool
    entry: float
    lots: float
    take_profit: float
    stop_loss: float | None
    opened_at: int

    def unrealised(self, price: float, oz_per_lot: float) -> float:
        move = (price - self.entry) if self.long else (self.entry - price)
        return move * self.lots * oz_per_lot


@dataclass
class RunResult:
    config: MicroConfig
    start_equity: float
    end_equity: float
    peak_equity: float
    trades: int
    wins: int
    losses: int
    realised: list[float] = field(default_factory=list)
    stopped_out: bool = False
    stop_out_bar: int | None = None
    bars: int = 0
    max_open: int = 0
    largest_loss: float = 0.0
    opening_price: float = 0.0

    @property
    def win_rate(self) -> float:
        return self.wins / self.trades if self.trades else 0.0

    @property
    def net(self) -> float:
        return self.end_equity - self.start_equity

    @property
    def return_pct(self) -> float:
        return self.net / self.start_equity * 100.0

    @property
    def max_drawdown_pct(self) -> float:
        return (self.peak_equity - self.end_equity) / self.peak_equity * 100.0 \
            if self.peak_equity > 0 else 0.0

    @property
    def mean_trade(self) -> float:
        return statistics.fmean(self.realised) if self.realised else 0.0


def _direction(cfg: MicroConfig, bars: list[Candle], i: int,
               rng: random.Random) -> bool:
    if cfg.direction == "long":
        return True
    if cfg.direction == "short":
        return False
    if cfg.direction == "random":
        return rng.random() < 0.5
    last = bars[i]
    up = last.close >= last.open
    return up if cfg.direction == "follow" else not up


def run(cfg: MicroConfig | None = None, series: CandleSeries | None = None,
        seed: int = 42, bars: int = 5_000) -> RunResult:
    """Trade one market, bar by bar.

    Two modelling choices, both deliberately unkind to the strategy, because
    the alternative is a backtest that agrees with the hope:

    *Adverse first.* When a bar's range covers both the take profit and the
    stop, the stop is taken. Which came first is unknowable from a bar, and
    assuming the good one flatters every result.

    *The broker closes before you do.* Equity is marked to market every bar
    against used margin, and at the stop-out level positions are closed from
    the worst down. This is the event the strategy is actually exposed to.
    """
    cfg = cfg or MicroConfig()
    from . import simulate
    if series is None:
        series = simulate.generate(bars=bars, timeframe="1m", seed=seed)
    candles = list(series.candles)
    spec = get_spec(cfg.symbol)
    oz = spec.contract_size_oz
    rng = random.Random(seed)

    equity = cfg.start_equity
    result = RunResult(config=cfg, start_equity=equity, end_equity=equity,
                       peak_equity=equity, trades=0, wins=0, losses=0,
                       bars=len(candles),
                       opening_price=candles[0].open if candles else 0.0)
    open_positions: list[Position] = []
    last_close_bar = -10_000

    def used_margin(price: float) -> float:
        return sum(p.lots * oz * price / cfg.leverage for p in open_positions)

    def close(pos: Position, price: float) -> None:
        nonlocal equity
        pnl = pos.unrealised(price, oz)
        equity += pnl
        result.realised.append(pnl)
        result.trades += 1
        if pnl > 0:
            result.wins += 1
        else:
            result.losses += 1
            result.largest_loss = min(result.largest_loss, pnl)

    for i, bar in enumerate(candles):
        # --- manage what is open -------------------------------------------
        still_open: list[Position] = []
        for pos in open_positions:
            hit_stop = pos.stop_loss is not None and (
                bar.low <= pos.stop_loss if pos.long else bar.high >= pos.stop_loss)
            hit_tp = (bar.high >= pos.take_profit if pos.long
                      else bar.low <= pos.take_profit)
            if hit_stop:
                close(pos, pos.stop_loss)          # adverse first, on purpose
            elif hit_tp:
                close(pos, pos.take_profit)
            else:
                still_open.append(pos)
        if len(still_open) != len(open_positions):
            last_close_bar = i
        open_positions = still_open

        # --- mark to market, and let the broker act ------------------------
        floating = sum(p.unrealised(bar.close, oz) for p in open_positions)
        margin = used_margin(bar.close)
        marked = equity + floating
        result.peak_equity = max(result.peak_equity, marked)

        if margin > 0 and marked / margin < STOP_OUT_LEVEL:
            # Stop-out: the broker closes, worst position first, until the
            # level is restored or nothing is left. Nothing about the
            # strategy's own logic gets a say here.
            for pos in sorted(open_positions,
                              key=lambda p: p.unrealised(bar.close, oz)):
                close(pos, bar.close)
                open_positions.remove(pos)
                margin = used_margin(bar.close)
                floating = sum(p.unrealised(bar.close, oz) for p in open_positions)
                if margin <= 0 or (equity + floating) / margin >= STOP_OUT_LEVEL:
                    break
            result.stopped_out = True
            if result.stop_out_bar is None:
                result.stop_out_bar = i
            if equity <= 0:
                equity = 0.0
                break

        # --- open the next one ---------------------------------------------
        if i < len(candles) - 1 and i - last_close_bar >= cfg.cooldown_bars:
            allowed = min(cfg.max_positions,
                          max(1, int(equity // cfg.equity_per_position)))
            while len(open_positions) < allowed:
                price = bar.close
                long = _direction(cfg, candles, i, rng)
                # Enter at the far side of the spread: a position opens
                # underwater by exactly that, which is why "in profit" has to
                # clear it before it means anything.
                entry = price + cfg.spread_usd_oz if long else price - cfg.spread_usd_oz
                tp = (entry + cfg.take_profit_usd_oz if long
                      else entry - cfg.take_profit_usd_oz)
                sl = None
                if cfg.stop_loss_usd_oz is not None:
                    sl = (entry - cfg.stop_loss_usd_oz if long
                          else entry + cfg.stop_loss_usd_oz)
                candidate = Position(long, entry, cfg.lot, tp, sl, i)
                projected = used_margin(price) + cfg.lot * oz * price / cfg.leverage
                if projected > equity + floating:
                    break                       # not enough free margin
                open_positions.append(candidate)
                result.max_open = max(result.max_open, len(open_positions))

    # Mark whatever is still open at the end -- an open loser is still a loss.
    final = candles[-1].close
    for pos in open_positions:
        close(pos, final)
    result.end_equity = max(0.0, equity)
    return result


@dataclass
class Sweep:
    """Many markets, one configuration."""

    config: MicroConfig
    runs: list[RunResult]

    @property
    def ruin_rate(self) -> float:
        return sum(1 for r in self.runs if r.end_equity <= r.start_equity * 0.5) \
            / len(self.runs)

    @property
    def stop_out_rate(self) -> float:
        return sum(1 for r in self.runs if r.stopped_out) / len(self.runs)

    @property
    def losing_rate(self) -> float:
        return sum(1 for r in self.runs if r.net < 0) / len(self.runs)

    @property
    def mean_return_pct(self) -> float:
        return statistics.fmean(r.return_pct for r in self.runs)

    @property
    def median_return_pct(self) -> float:
        return statistics.median(r.return_pct for r in self.runs)

    @property
    def mean_win_rate(self) -> float:
        rates = [r.win_rate for r in self.runs if r.trades]
        return statistics.fmean(rates) if rates else 0.0

    @property
    def mean_trades(self) -> float:
        return statistics.fmean(r.trades for r in self.runs)


def sweep(cfg: MicroConfig, markets: int = 100, bars: int = 5_000) -> Sweep:
    """Run one configuration across many independent markets.

    One run says nothing: this strategy's whole character is that most paths
    look excellent and a few end the account, so the distribution is the
    result and a single equity curve is an anecdote.
    """
    return Sweep(config=cfg,
                 runs=[run(cfg, seed=1000 + i, bars=bars) for i in range(markets)])


def optimise(base: MicroConfig | None = None, markets: int = 40,
             bars: int = 3_000) -> list[tuple[MicroConfig, Sweep]]:
    """Search the parameter space and rank by median outcome.

    Ranked on the median rather than the mean because the mean of a
    distribution with a fat left tail is dominated by whether the tail
    happened to be sampled. Returns every configuration tried, best first, so
    the shape of the search is visible and not just its winner.
    """
    base = base or MicroConfig()
    out: list[tuple[MicroConfig, Sweep]] = []
    for tp in (0.05, 0.10, 0.30, 1.00, 3.00):
        for sl in (None, 1.0, 3.0, 10.0):
            for direction in ("follow", "fade", "random"):
                for max_pos in (1, 3):
                    cfg = MicroConfig(
                        symbol=base.symbol, start_equity=base.start_equity,
                        lot=base.lot, max_positions=max_pos,
                        equity_per_position=base.equity_per_position,
                        take_profit_usd_oz=tp, stop_loss_usd_oz=sl,
                        spread_usd_oz=base.spread_usd_oz,
                        leverage=base.leverage, direction=direction,
                        cooldown_bars=base.cooldown_bars)
                    out.append((cfg, sweep(cfg, markets=markets, bars=bars)))
    out.sort(key=lambda pair: pair[1].median_return_pct, reverse=True)
    return out


def report(result: RunResult) -> str:
    r = result
    c = r.config
    lines = ["MICRO-SCALP — EIN MARKT", "=" * 68]
    lines.append(f"  {c.symbol} · {c.lot:g} Lot · bis zu {c.max_positions} "
                 f"Position(en) · Spread {c.spread_usd_oz:g} USD/oz")
    lines.append(f"  Gewinn mitnehmen bei {c.take_profit_usd_oz:g} USD/oz "
                 f"ueber dem Einstieg")
    lines.append(f"  Stop: {'keiner' if c.stop_loss_usd_oz is None else f'{c.stop_loss_usd_oz:g} USD/oz'}")
    lines.append("")
    if r.trades == 0 and r.max_open == 0:
        # Priced off the run's own first bar, not a hard-coded level: gold
        # moved from 4500 to about 4100 while this file was being written,
        # and a margin figure quoted from a stale price is wrong by that
        # ratio in the one message whose whole job is to state a number.
        margin = (c.lot * get_spec(c.symbol).contract_size_oz
                  * r.opening_price / c.leverage)
        lines.append("  KEIN EINZIGER TRADE MOEGLICH")
        lines.append(f"  Eine {c.lot:g}-Lot-Position auf Gold bindet bei Hebel "
                     f"1:{c.leverage:g} rund")
        lines.append(f"  {margin:,.0f} Margin. Das Konto hat {c.start_equity:,.0f}.")
        lines.append("  Das ist keine Strategiefrage, sondern eine Kontogroesse.")
        return "\n".join(lines)
    lines.append(f"  Trades              {r.trades}")
    lines.append(f"  Trefferquote        {r.win_rate * 100:.1f}%")
    lines.append(f"  Mittlerer Trade     {r.mean_trade:+.2f}")
    lines.append(f"  Groesster Verlust   {r.largest_loss:+.2f}")
    lines.append(f"  Start               {r.start_equity:,.2f}")
    lines.append(f"  Ende                {r.end_equity:,.2f}  "
                 f"({r.return_pct:+.1f}%)")
    if r.stopped_out:
        lines.append(f"  BROKER-STOP-OUT bei Bar {r.stop_out_bar} von {r.bars}")
    return "\n".join(lines)


def report_sweep(s: Sweep) -> str:
    c = s.config
    lines = [f"MICRO-SCALP — {len(s.runs)} UNABHAENGIGE MAERKTE", "=" * 68]
    lines.append(f"  Gewinnmitnahme {c.take_profit_usd_oz:g} · "
                 f"Stop {'keiner' if c.stop_loss_usd_oz is None else f'{c.stop_loss_usd_oz:g}'} · "
                 f"Richtung {c.direction} · max {c.max_positions} Position(en)")
    lines.append("")
    lines.append(f"  Trefferquote im Mittel   {s.mean_win_rate * 100:>6.1f}%")
    lines.append(f"  Trades pro Markt         {s.mean_trades:>6.0f}")
    lines.append(f"  Rendite im Median        {s.median_return_pct:>+6.1f}%")
    lines.append(f"  Rendite im Mittel        {s.mean_return_pct:>+6.1f}%")
    lines.append(f"  Maerkte mit Verlust      {s.losing_rate * 100:>6.0f}%")
    lines.append(f"  Broker-Stop-out          {s.stop_out_rate * 100:>6.0f}%")
    lines.append(f"  Konto halbiert o. schlimmer {s.ruin_rate * 100:>3.0f}%")
    return "\n".join(lines)
