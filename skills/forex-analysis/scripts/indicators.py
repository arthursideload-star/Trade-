#!/usr/bin/env python3
"""Deterministic technical indicators, standard library only.

These are the "hard numbers" the plan (BOT-PLAN.md section 2) wants computed
rather than guessed, so they must be reproducible and testable. TA-Lib is
avoided on purpose: it needs a compiled C library that would not be present in
the interactive Claude session where this actually runs.

Every function takes a list of floats oldest-first (the order the forex-data
skill guarantees) and returns a list of the same length. Positions without
enough history to be defined are None, never a fabricated 0.0 — a downstream
reader must be able to tell "no value yet" from "the value is zero".

Smoothing follows Wilder where Wilder defined it (RSI, ATR, ADX), because that
is what charting platforms show; using a plain EMA there would disagree with
the numbers a trader sees on MT5.
"""

from __future__ import annotations

from typing import Optional

Series = list[Optional[float]]


def _check_length(values: list[float], period: int) -> None:
    if period < 1:
        raise ValueError(f"period must be >= 1, got {period}")
    if not values:
        raise ValueError("values must not be empty")


def sma(values: list[float], period: int) -> Series:
    """Simple moving average."""
    _check_length(values, period)
    out: Series = [None] * len(values)
    running = 0.0
    for i, value in enumerate(values):
        running += value
        if i >= period:
            running -= values[i - period]
        if i >= period - 1:
            out[i] = running / period
    return out


def ema(values: list[float], period: int) -> Series:
    """Exponential moving average, seeded with the SMA of the first `period`.

    Seeding with an SMA rather than the first value removes the long startup
    bias a raw-seed EMA carries, and matches the convention charting tools use.
    """
    _check_length(values, period)
    out: Series = [None] * len(values)
    if len(values) < period:
        return out

    multiplier = 2.0 / (period + 1)
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(values)):
        prev = (values[i] - prev) * multiplier + prev
        out[i] = prev
    return out


def wilder_rma(values: list[float], period: int) -> Series:
    """Wilder's running moving average (a.k.a. RMA/SMMA)."""
    _check_length(values, period)
    out: Series = [None] * len(values)
    if len(values) < period:
        return out

    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(values)):
        prev = (prev * (period - 1) + values[i]) / period
        out[i] = prev
    return out


def rsi(closes: list[float], period: int = 14) -> Series:
    """Relative Strength Index with Wilder smoothing."""
    _check_length(closes, period)
    out: Series = [None] * len(closes)
    if len(closes) <= period:
        return out

    gains = [0.0] * len(closes)
    losses = [0.0] * len(closes)
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains[i] = max(change, 0.0)
        losses[i] = max(-change, 0.0)

    # First average is a simple mean over the first `period` changes, which sit
    # at indices 1..period, so the first RSI value lands at index `period`.
    avg_gain = sum(gains[1 : period + 1]) / period
    avg_loss = sum(losses[1 : period + 1]) / period
    out[period] = _rsi_from_averages(avg_gain, avg_loss)

    for i in range(period + 1, len(closes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out[i] = _rsi_from_averages(avg_gain, avg_loss)
    return out


def _rsi_from_averages(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def true_range(highs: list[float], lows: list[float], closes: list[float]) -> list[float]:
    """True range per bar. The first bar uses high-low (no prior close)."""
    _same_length(highs, lows, closes)
    tr = [highs[0] - lows[0]]
    for i in range(1, len(highs)):
        prev_close = closes[i - 1]
        tr.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - prev_close),
                abs(lows[i] - prev_close),
            )
        )
    return tr


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> Series:
    """Average True Range with Wilder smoothing."""
    tr = true_range(highs, lows, closes)
    return wilder_rma(tr, period)


def macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, Series]:
    """MACD line, signal line and histogram."""
    if fast >= slow:
        raise ValueError("fast period must be smaller than slow period")

    fast_ema = ema(closes, fast)
    slow_ema = ema(closes, slow)

    macd_line: Series = [
        (f - s) if (f is not None and s is not None) else None
        for f, s in zip(fast_ema, slow_ema)
    ]

    # The signal EMA runs only over the defined stretch of the MACD line.
    defined = [v for v in macd_line if v is not None]
    signal_defined = ema(defined, signal) if len(defined) >= signal else []

    signal_line: Series = [None] * len(closes)
    histogram: Series = [None] * len(closes)
    if signal_defined:
        offset = next(i for i, v in enumerate(macd_line) if v is not None)
        for j, value in enumerate(signal_defined):
            idx = offset + j
            signal_line[idx] = value
            if value is not None and macd_line[idx] is not None:
                histogram[idx] = macd_line[idx] - value

    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def bollinger_bands(
    closes: list[float],
    period: int = 20,
    num_std: float = 2.0,
) -> dict[str, Series]:
    """Bollinger Bands using the population standard deviation."""
    _check_length(closes, period)
    middle = sma(closes, period)
    upper: Series = [None] * len(closes)
    lower: Series = [None] * len(closes)

    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1 : i + 1]
        mean = middle[i]
        variance = sum((x - mean) ** 2 for x in window) / period
        deviation = variance ** 0.5
        upper[i] = mean + num_std * deviation
        lower[i] = mean - num_std * deviation

    return {"middle": middle, "upper": upper, "lower": lower}


def stochastic(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    k_period: int = 14,
    d_period: int = 3,
) -> dict[str, Series]:
    """Stochastic oscillator %K and %D."""
    _same_length(highs, lows, closes)
    percent_k: Series = [None] * len(closes)

    for i in range(k_period - 1, len(closes)):
        window_high = max(highs[i - k_period + 1 : i + 1])
        window_low = min(lows[i - k_period + 1 : i + 1])
        span = window_high - window_low
        # A flat window has no range; %K is undefined rather than 50 by fiat.
        percent_k[i] = 100.0 * (closes[i] - window_low) / span if span else None

    defined = [(i, v) for i, v in enumerate(percent_k) if v is not None]
    percent_d: Series = [None] * len(closes)
    values_only = [v for _, v in defined]
    d_defined = sma(values_only, d_period) if len(values_only) >= d_period else []
    for (orig_i, _), d_val in zip(defined[d_period - 1 :], [v for v in d_defined if v is not None]):
        percent_d[orig_i] = d_val

    return {"k": percent_k, "d": percent_d}


def adx(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> dict[str, Series]:
    """ADX with +DI and -DI, Wilder smoothing.

    ADX measures trend strength without direction; +DI/-DI give the direction.
    The regime classifier in regime.py leans on all three.
    """
    _same_length(highs, lows, closes)
    n = len(highs)
    out_adx: Series = [None] * n
    out_plus: Series = [None] * n
    out_minus: Series = [None] * n
    if n <= period:
        return {"adx": out_adx, "plus_di": out_plus, "minus_di": out_minus}

    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    tr = true_range(highs, lows, closes)
    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dm[i] = up_move if (up_move > down_move and up_move > 0) else 0.0
        minus_dm[i] = down_move if (down_move > up_move and down_move > 0) else 0.0

    smoothed_tr = wilder_rma(tr, period)
    smoothed_plus = wilder_rma(plus_dm, period)
    smoothed_minus = wilder_rma(minus_dm, period)

    dx = [None] * n
    for i in range(period, n):
        st = smoothed_tr[i]
        if not st:
            continue
        plus_di = 100.0 * smoothed_plus[i] / st
        minus_di = 100.0 * smoothed_minus[i] / st
        out_plus[i] = plus_di
        out_minus[i] = minus_di
        di_sum = plus_di + minus_di
        dx[i] = 100.0 * abs(plus_di - minus_di) / di_sum if di_sum else 0.0

    # ADX is Wilder's smoothing of DX, starting once `period` DX values exist.
    first_dx = period
    dx_defined = [v for v in dx[first_dx:] if v is not None]
    if len(dx_defined) >= period:
        adx_seed = sum(dx_defined[:period]) / period
        adx_start = first_dx + period - 1
        out_adx[adx_start] = adx_seed
        prev = adx_seed
        for i in range(adx_start + 1, n):
            if dx[i] is None:
                continue
            prev = (prev * (period - 1) + dx[i]) / period
            out_adx[i] = prev

    return {"adx": out_adx, "plus_di": out_plus, "minus_di": out_minus}


def _same_length(*series: list[float]) -> None:
    lengths = {len(s) for s in series}
    if len(lengths) != 1:
        raise ValueError(f"series must have equal length, got {sorted(lengths)}")
    if lengths == {0}:
        raise ValueError("series must not be empty")


def last_defined(series: Series) -> Optional[float]:
    """Return the most recent non-None value, or None if there is none."""
    for value in reversed(series):
        if value is not None:
            return value
    return None
