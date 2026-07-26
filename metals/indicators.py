"""Deterministic indicator calculations.

Pure Python, no dependencies. Every function returns a list aligned to the
input length, with None for the warm-up period, so an index into the result
always refers to the same bar as the same index into the input.

Settings default to the values that hold up on metals rather than the
textbook forex defaults -- see docs/GOLD-SILBER.md Teil XII for why RSI
bands are widened on gold and silver.
"""

from __future__ import annotations

from math import sqrt
from typing import Sequence

Num = float | None


def _clean(values: Sequence[float]) -> list[float]:
    return [float(v) for v in values]


# --- Moving averages --------------------------------------------------------

def sma(values: Sequence[float], period: int) -> list[Num]:
    if period <= 0:
        raise ValueError("period must be positive")
    vals = _clean(values)
    out: list[Num] = [None] * len(vals)
    if len(vals) < period:
        return out
    running = sum(vals[:period])
    out[period - 1] = running / period
    for i in range(period, len(vals)):
        running += vals[i] - vals[i - period]
        out[i] = running / period
    return out


def ema(values: Sequence[float], period: int) -> list[Num]:
    """Exponential MA seeded with an SMA, which is what charting packages do."""
    if period <= 0:
        raise ValueError("period must be positive")
    vals = _clean(values)
    out: list[Num] = [None] * len(vals)
    if len(vals) < period:
        return out
    k = 2.0 / (period + 1.0)
    prev = sum(vals[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(vals)):
        prev = vals[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def wilder_ma(values: Sequence[float], period: int) -> list[Num]:
    """Wilder's smoothing -- the one ATR, RSI and ADX are actually defined on."""
    vals = _clean(values)
    out: list[Num] = [None] * len(vals)
    if len(vals) < period:
        return out
    prev = sum(vals[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(vals)):
        prev = (prev * (period - 1) + vals[i]) / period
        out[i] = prev
    return out


# --- Volatility -------------------------------------------------------------

def true_range(highs: Sequence[float], lows: Sequence[float],
               closes: Sequence[float]) -> list[Num]:
    h, l, c = _clean(highs), _clean(lows), _clean(closes)
    out: list[Num] = [None] * len(h)
    if not h:
        return out
    out[0] = h[0] - l[0]
    for i in range(1, len(h)):
        out[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    return out


def atr(highs: Sequence[float], lows: Sequence[float],
        closes: Sequence[float], period: int = 14) -> list[Num]:
    """Average True Range in the instrument's price units (USD/oz for metals)."""
    tr = [v for v in true_range(highs, lows, closes)]
    values = [v if v is not None else 0.0 for v in tr]
    return wilder_ma(values, period)


def atr_percent(highs: Sequence[float], lows: Sequence[float],
                closes: Sequence[float], period: int = 14) -> list[Num]:
    """ATR as a percentage of price -- the comparable figure across metals.

    Gold at 4 USD/oz ATR and silver at 0.11 USD/oz ATR look nothing alike in
    absolute terms and very similar in percentage terms. Regime logic uses
    this one.
    """
    a = atr(highs, lows, closes, period)
    c = _clean(closes)
    return [
        (v / c[i] * 100.0) if (v is not None and c[i]) else None
        for i, v in enumerate(a)
    ]


def stdev(values: Sequence[float], period: int) -> list[Num]:
    vals = _clean(values)
    out: list[Num] = [None] * len(vals)
    for i in range(period - 1, len(vals)):
        window = vals[i - period + 1: i + 1]
        mean = sum(window) / period
        var = sum((x - mean) ** 2 for x in window) / period
        out[i] = sqrt(var)
    return out


def bollinger(values: Sequence[float], period: int = 20,
              mult: float = 2.0) -> tuple[list[Num], list[Num], list[Num]]:
    mid = sma(values, period)
    sd = stdev(values, period)
    upper = [m + mult * s if (m is not None and s is not None) else None
             for m, s in zip(mid, sd)]
    lower = [m - mult * s if (m is not None and s is not None) else None
             for m, s in zip(mid, sd)]
    return upper, mid, lower


def bollinger_bandwidth(values: Sequence[float], period: int = 20,
                        mult: float = 2.0) -> list[Num]:
    """(upper-lower)/mid. Low readings mark the squeeze that precedes expansion."""
    up, mid, lo = bollinger(values, period, mult)
    return [
        ((u - l) / m * 100.0) if (u is not None and l is not None and m) else None
        for u, m, l in zip(up, mid, lo)
    ]


def keltner(highs: Sequence[float], lows: Sequence[float],
            closes: Sequence[float], period: int = 20,
            mult: float = 1.5) -> tuple[list[Num], list[Num], list[Num]]:
    mid = ema(closes, period)
    a = atr(highs, lows, closes, period)
    upper = [m + mult * v if (m is not None and v is not None) else None
             for m, v in zip(mid, a)]
    lower = [m - mult * v if (m is not None and v is not None) else None
             for m, v in zip(mid, a)]
    return upper, mid, lower


def squeeze_on(highs: Sequence[float], lows: Sequence[float],
               closes: Sequence[float], period: int = 20) -> list[bool | None]:
    """True where Bollinger Bands sit entirely inside the Keltner Channel.

    On metals this fires less often than on forex but resolves harder when it
    does, because a metals range break usually coincides with a macro catalyst.
    """
    bb_u, _, bb_l = bollinger(closes, period, 2.0)
    kc_u, _, kc_l = keltner(highs, lows, closes, period, 1.5)
    out: list[bool | None] = []
    for u, l, ku, kl in zip(bb_u, bb_l, kc_u, kc_l):
        if None in (u, l, ku, kl):
            out.append(None)
        else:
            out.append(u < ku and l > kl)  # type: ignore[operator]
    return out


# --- Momentum ---------------------------------------------------------------

def rsi(values: Sequence[float], period: int = 14) -> list[Num]:
    vals = _clean(values)
    out: list[Num] = [None] * len(vals)
    if len(vals) <= period:
        return out
    gains, losses = [], []
    for i in range(1, len(vals)):
        change = vals[i] - vals[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    out[period] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1 + avg_gain / avg_loss)
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        idx = i + 1
        out[idx] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1 + avg_gain / avg_loss)
    return out


def macd(values: Sequence[float], fast: int = 12, slow: int = 26,
         signal: int = 9) -> tuple[list[Num], list[Num], list[Num]]:
    ef, es = ema(values, fast), ema(values, slow)
    line: list[Num] = [
        (f - s) if (f is not None and s is not None) else None
        for f, s in zip(ef, es)
    ]
    defined = [v for v in line if v is not None]
    sig_tail = ema(defined, signal)
    offset = len(line) - len(defined)
    sig: list[Num] = [None] * offset + list(sig_tail)
    hist: list[Num] = [
        (m - s) if (m is not None and s is not None) else None
        for m, s in zip(line, sig)
    ]
    return line, sig, hist


def stochastic(highs: Sequence[float], lows: Sequence[float],
               closes: Sequence[float], k_period: int = 14,
               k_smooth: int = 3, d_period: int = 3) -> tuple[list[Num], list[Num]]:
    h, l, c = _clean(highs), _clean(lows), _clean(closes)
    raw: list[Num] = [None] * len(c)
    for i in range(k_period - 1, len(c)):
        hh = max(h[i - k_period + 1: i + 1])
        ll = min(l[i - k_period + 1: i + 1])
        raw[i] = 50.0 if hh == ll else (c[i] - ll) / (hh - ll) * 100.0
    defined = [v for v in raw if v is not None]
    k_tail = sma(defined, k_smooth)
    offset = len(raw) - len(defined)
    k: list[Num] = [None] * offset + list(k_tail)
    k_defined = [v for v in k if v is not None]
    d_tail = sma(k_defined, d_period)
    d: list[Num] = [None] * (len(k) - len(k_defined)) + list(d_tail)
    return k, d


def momentum(values: Sequence[float], period: int = 10) -> list[Num]:
    vals = _clean(values)
    return [
        (vals[i] - vals[i - period]) if i >= period else None
        for i in range(len(vals))
    ]


def roc(values: Sequence[float], period: int = 10) -> list[Num]:
    vals = _clean(values)
    return [
        ((vals[i] / vals[i - period] - 1.0) * 100.0)
        if (i >= period and vals[i - period]) else None
        for i in range(len(vals))
    ]


# --- Trend strength ---------------------------------------------------------

def adx(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float],
        period: int = 14) -> tuple[list[Num], list[Num], list[Num]]:
    """Returns (adx, plus_di, minus_di)."""
    h, l, c = _clean(highs), _clean(lows), _clean(closes)
    n = len(h)
    if n < period * 2:
        empty: list[Num] = [None] * n
        return empty, list(empty), list(empty)

    plus_dm, minus_dm, tr = [0.0], [0.0], [h[0] - l[0]]
    for i in range(1, n):
        up = h[i] - h[i - 1]
        down = l[i - 1] - l[i]
        plus_dm.append(up if (up > down and up > 0) else 0.0)
        minus_dm.append(down if (down > up and down > 0) else 0.0)
        tr.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))

    tr_s = wilder_ma(tr, period)
    p_s = wilder_ma(plus_dm, period)
    m_s = wilder_ma(minus_dm, period)

    p_di: list[Num] = [
        (p / t * 100.0) if (p is not None and t) else None
        for p, t in zip(p_s, tr_s)
    ]
    m_di: list[Num] = [
        (m / t * 100.0) if (m is not None and t) else None
        for m, t in zip(m_s, tr_s)
    ]
    dx: list[Num] = []
    for p, m in zip(p_di, m_di):
        if p is None or m is None or (p + m) == 0:
            dx.append(None)
        else:
            dx.append(abs(p - m) / (p + m) * 100.0)
    defined = [v for v in dx if v is not None]
    a_tail = wilder_ma(defined, period)
    a: list[Num] = [None] * (len(dx) - len(defined)) + list(a_tail)
    return a, p_di, m_di


# --- Volume-aware ------------------------------------------------------------

def vwap_session(highs: Sequence[float], lows: Sequence[float],
                 closes: Sequence[float], volumes: Sequence[float | None],
                 session_starts: Sequence[bool]) -> list[Num]:
    """VWAP that resets at each flagged session start.

    Metals CFD feeds carry tick volume, not real traded volume. Tick volume
    correlates well enough with real volume to be usable for VWAP, but the
    number itself is not comparable across brokers -- so this is a relative
    tool only. Where volume is absent, the result is None rather than a
    silently wrong unweighted average.
    """
    h, l, c = _clean(highs), _clean(lows), _clean(closes)
    out: list[Num] = []
    cum_pv = cum_v = 0.0
    for i in range(len(c)):
        if session_starts[i]:
            cum_pv = cum_v = 0.0
        v = volumes[i]
        if v is None or v <= 0:
            out.append(None if cum_v == 0 else cum_pv / cum_v)
            continue
        typical = (h[i] + l[i] + c[i]) / 3.0
        cum_pv += typical * v
        cum_v += v
        out.append(cum_pv / cum_v)
    return out


def volume_ratio(volumes: Sequence[float | None], period: int = 20) -> list[Num]:
    """Current volume divided by its rolling average. >1.5 is a genuine surge."""
    vals = [v if v is not None else 0.0 for v in volumes]
    avg = sma(vals, period)
    return [
        (vals[i] / avg[i]) if (avg[i] not in (None, 0)) else None
        for i in range(len(vals))
    ]


# --- Correlation ------------------------------------------------------------

def rolling_correlation(a: Sequence[float], b: Sequence[float],
                        period: int = 20) -> list[Num]:
    """Pearson correlation of two aligned series over a rolling window.

    Used for gold vs DXY and gold vs real yields. A correlation that breaks
    its usual sign is itself a signal -- see docs/GOLD-SILBER.md Teil X.
    """
    x, y = _clean(a), _clean(b)
    n = min(len(x), len(y))
    out: list[Num] = [None] * n
    for i in range(period - 1, n):
        xs = x[i - period + 1: i + 1]
        ys = y[i - period + 1: i + 1]
        mx = sum(xs) / period
        my = sum(ys) / period
        cov = sum((xs[k] - mx) * (ys[k] - my) for k in range(period))
        vx = sum((v - mx) ** 2 for v in xs)
        vy = sum((v - my) ** 2 for v in ys)
        out[i] = cov / sqrt(vx * vy) if vx > 0 and vy > 0 else None
    return out


def zscore(values: Sequence[float], period: int = 100) -> list[Num]:
    """How many standard deviations the latest value sits from its own mean.

    The gold-silver ratio is traded on exactly this, so it gets its own helper.
    """
    vals = _clean(values)
    out: list[Num] = [None] * len(vals)
    for i in range(period - 1, len(vals)):
        window = vals[i - period + 1: i + 1]
        mean = sum(window) / period
        var = sum((v - mean) ** 2 for v in window) / period
        sd = sqrt(var)
        out[i] = (vals[i] - mean) / sd if sd > 0 else None
    return out


# --- Swing structure --------------------------------------------------------

def swing_points(highs: Sequence[float], lows: Sequence[float],
                 left: int = 2, right: int = 2
                 ) -> tuple[list[int], list[int]]:
    """Fractal swing highs and lows.

    Returns (swing_high_indices, swing_low_indices). `right` bars must have
    printed after the pivot, so the most recent `right` bars can never contain
    a confirmed swing -- this is deliberate and matches how the levels can
    actually be traded.
    """
    h, l = _clean(highs), _clean(lows)
    sh, sl = [], []
    for i in range(left, len(h) - right):
        window_h = h[i - left: i + right + 1]
        if h[i] == max(window_h) and window_h.count(h[i]) == 1:
            sh.append(i)
        window_l = l[i - left: i + right + 1]
        if l[i] == min(window_l) and window_l.count(l[i]) == 1:
            sl.append(i)
    return sh, sl
