"""Synthetic gold market with realistic statistical properties.

**Read this before believing any number produced from it.**

This generator exists because the build environment has no network access to
historical price data. It reproduces the statistical *properties* of gold that
are documented and measurable:

* volatility clustering (a GARCH-like process -- quiet periods follow quiet
  periods, violent ones follow violent ones)
* fat tails (occasional jumps far outside a normal distribution)
* a session volatility profile (Asia thin, London/NY overlap violent)
* round-number magnetism and rejection
* liquidity sweeps: the market reaching through an obvious level and coming
  back

What it does **not** reproduce, and cannot:

* the actual sequence of real gold prices
* the reflexive relationship between news and price
* the way real order flow reacts to the very levels a strategy uses
* regime changes driven by policy

**Consequence, stated plainly:** results measured on this data test whether
the machinery works -- whether setups fire, whether R multiples are computed
correctly, whether costs are applied, whether the exit logic behaves. They are
**not** a measured hit rate for real gold, and must never be used to size a
real position or to decide that a strategy is profitable.

To get real numbers, run the same backtest against real candles:

    python -m metals backtest --source live --bars 5000

which requires network access and, ideally, a Twelve Data key.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .candles import Candle, CandleSeries


@dataclass
class MarketParams:
    """Parameters of the generated market, in the metal's own units."""

    start_price: float = 4500.0
    # Baseline per-bar volatility as a fraction of price.
    base_vol: float = 0.00035
    # GARCH-like persistence: how much of last bar's shock carries forward.
    vol_persistence: float = 0.92
    vol_reaction: float = 0.07
    # Probability per bar of a jump, and its size in units of base vol.
    jump_probability: float = 0.004
    jump_size: float = 8.0
    # Strength of pull toward round numbers, and of rejection at them.
    round_magnet: float = 0.10
    round_step: float = 10.0
    # Probability per bar of a liquidity sweep at a recent extreme.
    sweep_probability: float = 0.010
    sweep_depth_atr: float = 0.7
    # Slow drift, expressed per bar. Deliberately near zero: a generator with
    # a strong drift makes every long strategy look good.
    drift: float = 0.0
    # Mean reversion toward a slow anchor, which prevents random walk blowups.
    reversion: float = 0.002


# Session volatility multipliers by UTC hour. Shaped from the documented
# pattern: Asia thin, London open lively, the overlap the most violent, and
# the rollover hour dead.
_HOUR_VOL = {
    0: 0.55, 1: 0.50, 2: 0.45, 3: 0.45, 4: 0.50, 5: 0.60,
    6: 0.95, 7: 1.30, 8: 1.35, 9: 1.15, 10: 1.00, 11: 0.95,
    12: 1.25, 13: 1.70, 14: 1.60, 15: 1.45, 16: 1.30, 17: 1.05,
    18: 0.85, 19: 0.70, 20: 0.60, 21: 0.35, 22: 0.30, 23: 0.40,
}


class _Rng:
    """Deterministic PRNG so a seed always reproduces the same market.

    Uses an explicit LCG plus Box-Muller rather than `random`, so results do
    not depend on global interpreter state or Python version.
    """

    def __init__(self, seed: int):
        self.state = (seed * 2654435761) % (2 ** 32) or 1
        self._spare: float | None = None

    def uniform(self) -> float:
        self.state = (1664525 * self.state + 1013904223) % (2 ** 32)
        return self.state / 2 ** 32

    def normal(self) -> float:
        if self._spare is not None:
            v, self._spare = self._spare, None
            return v
        while True:
            u = self.uniform() * 2 - 1
            v = self.uniform() * 2 - 1
            s = u * u + v * v
            if 0 < s < 1:
                break
        factor = math.sqrt(-2.0 * math.log(s) / s)
        self._spare = v * factor
        return u * factor


def generate(
    bars: int = 5000,
    timeframe: str = "5m",
    seed: int = 42,
    params: MarketParams | None = None,
    start: datetime | None = None,
    symbol: str = "XAUUSD",
) -> CandleSeries:
    """Generate a synthetic candle series.

    Bars falling in the market's closed hours (weekend, rollover) are skipped
    rather than generated flat, so session-aware strategies see the same gaps
    they would see live.
    """
    p = params or MarketParams()
    rng = _Rng(seed)
    step_minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}[timeframe]
    ts = start or datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)

    price = p.start_price
    anchor = p.start_price
    vol = p.base_vol
    recent_highs: list[float] = []
    recent_lows: list[float] = []

    candles: list[Candle] = []
    generated = 0
    guard = 0

    while generated < bars and guard < bars * 4:
        guard += 1
        ts += timedelta(minutes=step_minutes)

        if not _market_open(ts):
            continue

        hour_mult = _HOUR_VOL[ts.hour]

        # GARCH-like volatility update.
        shock = rng.normal()
        vol = math.sqrt(
            p.base_vol ** 2 * (1 - p.vol_persistence - p.vol_reaction)
            + p.vol_persistence * vol ** 2
            + p.vol_reaction * (vol * shock) ** 2
        )
        effective_vol = vol * hour_mult

        # Jump component -- this is what produces the fat tails.
        jump = 0.0
        if rng.uniform() < p.jump_probability * hour_mult:
            jump = rng.normal() * effective_vol * p.jump_size

        # Round-number magnetism: a weak pull toward the nearest handle.
        nearest = round(price / p.round_step) * p.round_step
        magnet = (nearest - price) / price * p.round_magnet

        # Slow mean reversion so the walk does not drift to absurdity.
        anchor += (price - anchor) * 0.001
        pull = (anchor - price) / price * p.reversion

        ret = p.drift + rng.normal() * effective_vol + jump + magnet + pull
        close = price * (1 + ret)

        body_high = max(price, close)
        body_low = min(price, close)
        wick = effective_vol * price * (0.4 + abs(rng.normal()) * 0.6)
        high = body_high + abs(rng.normal()) * wick
        low = body_low - abs(rng.normal()) * wick

        # Liquidity sweep: reach through a recent extreme and come back.
        if recent_highs and rng.uniform() < p.sweep_probability * hour_mult:
            target_high = max(recent_highs[-20:])
            target_low = min(recent_lows[-20:])
            depth = effective_vol * price * p.sweep_depth_atr
            if rng.uniform() < 0.5 and high < target_high < high + depth * 3:
                high = target_high + depth
            elif low > target_low > low - depth * 3:
                low = target_low - depth

        high = max(high, body_high)
        low = min(low, body_low)

        candles.append(Candle(
            ts=ts, open=round(price, 2), high=round(high, 2),
            low=round(low, 2), close=round(close, 2),
            volume=round(1000 * hour_mult * (0.5 + abs(rng.normal())), 0),
        ))
        recent_highs.append(high)
        recent_lows.append(low)
        if len(recent_highs) > 60:
            recent_highs.pop(0)
            recent_lows.pop(0)

        price = close
        generated += 1

    return CandleSeries(symbol, timeframe, candles, source="simulated")


def _market_open(ts: datetime) -> bool:
    wd = ts.weekday()
    if wd == 5:
        return False
    if wd == 6:
        return ts.hour >= 22
    if wd == 4 and ts.hour >= 21:
        return False
    if ts.hour == 22:          # daily break
        return False
    return True


def describe(series: CandleSeries) -> dict[str, float]:
    """Statistical summary, for checking the generator produces gold-like data."""
    from .indicators import atr, atr_percent

    closes = series.closes
    rets = [(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    sd = math.sqrt(var)
    kurt = (sum((r - mean) ** 4 for r in rets) / len(rets) / var ** 2
            if var > 0 else 0.0)

    a_pct = [v for v in atr_percent(series.highs, series.lows, closes, 14)
             if v is not None]
    a_abs = [v for v in atr(series.highs, series.lows, closes, 14)
             if v is not None]

    # Volatility clustering: correlation of |return| with the previous |return|.
    abs_rets = [abs(r) for r in rets]
    n = len(abs_rets) - 1
    m1 = sum(abs_rets[:-1]) / n
    m2 = sum(abs_rets[1:]) / n
    cov = sum((abs_rets[i] - m1) * (abs_rets[i + 1] - m2) for i in range(n)) / n
    v1 = sum((x - m1) ** 2 for x in abs_rets[:-1]) / n
    v2 = sum((x - m2) ** 2 for x in abs_rets[1:]) / n
    clustering = cov / math.sqrt(v1 * v2) if v1 > 0 and v2 > 0 else 0.0

    return {
        "bars": float(len(series)),
        "start_price": series[0].open,
        "end_price": series.last.close,
        "total_move_pct": (series.last.close / series[0].open - 1) * 100,
        "mean_atr_pct": sum(a_pct) / len(a_pct) if a_pct else 0.0,
        "mean_atr_usd": sum(a_abs) / len(a_abs) if a_abs else 0.0,
        "return_sd_pct": sd * 100,
        "excess_kurtosis": kurt - 3.0,
        "vol_clustering": clustering,
    }
