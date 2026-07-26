"""Macro drivers: real yields, the dollar, inflation expectations.

This is the layer that explains gold rather than describes it. Gold does not
have earnings or a yield, so its price is largely the market's answer to
"what does it cost to hold something that pays nothing" -- which is the real
interest rate -- expressed in dollars, which is the second variable.

The relationship is strong but not mechanical. Rolling 60-day correlation of
gold against the dollar index has typically sat between -0.70 and -0.85, and
gold against 10-year real yields has averaged around -0.45 to -0.73 depending
on the period measured. Both correlations break down at times, and the
breakdown itself carries information -- see build_macro_context below.
"""

from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass, field
from datetime import date, timedelta

from .http import FetchError, HttpClient, try_sources

# FRED series that matter for metals, with why each one is here.
SERIES: dict[str, tuple[str, str]] = {
    "DFII10": ("10y TIPS real yield",
               "the direct opportunity cost of holding gold; the single "
               "strongest macro driver"),
    "DGS10": ("10y nominal Treasury yield",
              "nominal rates; the difference to DFII10 is the inflation "
              "expectation"),
    "T10YIE": ("10y breakeven inflation",
               "what the bond market expects inflation to be; gold's "
               "inflation-hedge case lives here"),
    "DTWEXBGS": ("broad trade-weighted dollar",
                 "a wider and more honest dollar measure than DXY, which is "
                 "57% euro"),
    "VIXCLS": ("VIX",
               "risk appetite; gold's safe-haven bid strengthens when this "
               "spikes"),
    "T10Y2Y": ("10y minus 2y spread",
               "curve shape; inversion has historically preceded the easing "
               "cycles gold likes"),
    "FEDFUNDS": ("effective fed funds rate",
                 "the policy rate itself"),
}


@dataclass(frozen=True)
class SeriesPoint:
    day: date
    value: float


@dataclass
class MacroSeries:
    series_id: str
    label: str
    points: list[SeriesPoint]
    source: str

    @property
    def latest(self) -> SeriesPoint | None:
        return self.points[-1] if self.points else None

    def change(self, days: int) -> float | None:
        """Absolute change over roughly `days` calendar days."""
        if len(self.points) < 2:
            return None
        target = self.points[-1].day - timedelta(days=days)
        earlier = [p for p in self.points if p.day <= target]
        if not earlier:
            return None
        return self.points[-1].value - earlier[-1].value

    def values(self) -> list[float]:
        return [p.value for p in self.points]


def fred_csv(client: HttpClient, series_id: str,
             start: date | None = None) -> MacroSeries:
    """FRED's public chart-download endpoint. No API key required."""
    start = start or (date.today() - timedelta(days=400))
    text = client.get_text(
        "https://fred.stlouisfed.org/graph/fredgraph.csv",
        params={"id": series_id, "cosd": start.isoformat()},
        cache_ttl=3600,
    )
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header or len(header) < 2:
        raise FetchError("fred_csv", f"unexpected CSV header {header!r}")
    points: list[SeriesPoint] = []
    for row in reader:
        if len(row) < 2 or row[1] in (".", "", "NA"):
            continue  # FRED marks holidays with a dot
        try:
            points.append(SeriesPoint(date.fromisoformat(row[0]), float(row[1])))
        except ValueError:
            continue
    if not points:
        raise FetchError("fred_csv", f"no usable observations for {series_id}")
    label = SERIES.get(series_id, (series_id, ""))[0]
    return MacroSeries(series_id, label, points, "fred_csv")


def fred_api(client: HttpClient, series_id: str, start: date | None = None,
             api_key: str | None = None) -> MacroSeries:
    key = api_key or os.environ.get("FRED_API_KEY")
    if not key:
        raise FetchError("fred", "FRED_API_KEY is not set")
    start = start or (date.today() - timedelta(days=400))
    data = client.get_json(
        "https://api.stlouisfed.org/fred/series/observations",
        params={"series_id": series_id, "api_key": key, "file_type": "json",
                "observation_start": start.isoformat()},
        cache_ttl=3600,
    )
    points = []
    for obs in data.get("observations", []):
        if obs.get("value") in (".", "", None):
            continue
        try:
            points.append(SeriesPoint(date.fromisoformat(obs["date"]),
                                      float(obs["value"])))
        except (ValueError, KeyError):
            continue
    if not points:
        raise FetchError("fred", f"no usable observations for {series_id}")
    label = SERIES.get(series_id, (series_id, ""))[0]
    return MacroSeries(series_id, label, points, "fred")


def fetch_series(series_id: str, client: HttpClient | None = None,
                 start: date | None = None) -> MacroSeries:
    client = client or HttpClient()
    result, _, _ = try_sources([
        ("fred", lambda: fred_api(client, series_id, start)),
        ("fred_csv", lambda: fred_csv(client, series_id, start)),
    ])
    return result


# --- Interpretation ---------------------------------------------------------

@dataclass
class MacroContext:
    """The macro backdrop, reduced to a bias the assistant can reason about."""

    real_yield: float | None = None
    real_yield_change_20d: float | None = None
    breakeven: float | None = None
    dollar: float | None = None
    dollar_change_20d: float | None = None
    vix: float | None = None
    curve: float | None = None
    available: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def bias(self) -> str:
        """'bullish' | 'bearish' | 'neutral' | 'unknown' for gold."""
        score = self.score
        if score is None:
            return "unknown"
        if score >= 1.0:
            return "bullish"
        if score <= -1.0:
            return "bearish"
        return "neutral"

    @property
    def score(self) -> float | None:
        """Net macro score for gold. Positive is supportive.

        Deliberately coarse. This decides whether to lean long or short over
        days, never where to enter. Each component contributes at most 1.0 so
        that no single reading can dominate.
        """
        parts: list[float] = []

        # Falling real yields lower the cost of holding a non-yielding asset.
        if self.real_yield_change_20d is not None:
            parts.append(max(-1.0, min(1.0, -self.real_yield_change_20d * 4.0)))

        # A weakening dollar mechanically lifts a dollar-denominated metal.
        if self.dollar_change_20d is not None:
            parts.append(max(-1.0, min(1.0, -self.dollar_change_20d * 0.5)))

        # A VIX spike brings a safe-haven bid, but only at genuinely elevated
        # levels -- routine VIX noise says nothing about gold.
        if self.vix is not None:
            if self.vix >= 28:
                parts.append(0.8)
            elif self.vix >= 20:
                parts.append(0.3)
            elif self.vix <= 13:
                parts.append(-0.2)

        # An absolute real yield below ~1% has historically been a tailwind.
        if self.real_yield is not None:
            if self.real_yield < 0.5:
                parts.append(0.7)
            elif self.real_yield < 1.5:
                parts.append(0.3)
            elif self.real_yield > 2.5:
                parts.append(-0.5)

        if not parts:
            return None
        return sum(parts) / len(parts) * 2.0

    def explain(self) -> list[str]:
        out: list[str] = []
        if self.real_yield is not None:
            direction = "unchanged"
            if self.real_yield_change_20d is not None:
                direction = ("falling" if self.real_yield_change_20d < -0.05
                             else "rising" if self.real_yield_change_20d > 0.05
                             else "flat")
            out.append(
                f"10y real yield {self.real_yield:.2f}% and {direction} over "
                f"20 days -- this is gold's opportunity cost, and it is the "
                f"variable to watch above all others"
            )
        if self.dollar is not None and self.dollar_change_20d is not None:
            out.append(
                f"broad dollar index {self.dollar:.1f}, "
                f"{self.dollar_change_20d:+.1f} over 20 days -- gold is priced "
                f"in dollars, so this is a mechanical headwind or tailwind "
                f"before any narrative"
            )
        if self.breakeven is not None:
            out.append(
                f"10y breakeven inflation {self.breakeven:.2f}% -- what the "
                f"bond market expects inflation to be"
            )
        if self.vix is not None:
            tone = ("elevated -- safe-haven bid is live" if self.vix >= 20
                    else "calm -- no safe-haven support")
            out.append(f"VIX {self.vix:.1f}, {tone}")
        out.extend(self.notes)
        if self.missing:
            out.append(
                f"unavailable: {', '.join(self.missing)}. The macro read is "
                f"partial, so weight it lower than usual."
            )
        return out


def build_macro_context(client: HttpClient | None = None) -> MacroContext:
    """Fetch the macro series and reduce them to a bias.

    Missing series degrade the result rather than failing it: a partial macro
    picture is still better than none, provided the caller is told what is
    missing.
    """
    client = client or HttpClient()
    ctx = MacroContext()

    wanted = ["DFII10", "DTWEXBGS", "T10YIE", "VIXCLS", "T10Y2Y"]
    fetched: dict[str, MacroSeries] = {}
    for sid in wanted:
        try:
            fetched[sid] = fetch_series(sid, client)
            ctx.available.append(sid)
        except Exception as exc:  # noqa: BLE001 - partial data is acceptable
            ctx.missing.append(f"{sid} ({exc})")

    if "DFII10" in fetched:
        s = fetched["DFII10"]
        ctx.real_yield = s.latest.value if s.latest else None
        ctx.real_yield_change_20d = s.change(28)
    if "DTWEXBGS" in fetched:
        s = fetched["DTWEXBGS"]
        ctx.dollar = s.latest.value if s.latest else None
        ctx.dollar_change_20d = s.change(28)
    if "T10YIE" in fetched:
        ctx.breakeven = fetched["T10YIE"].latest.value if fetched["T10YIE"].latest else None
    if "VIXCLS" in fetched:
        ctx.vix = fetched["VIXCLS"].latest.value if fetched["VIXCLS"].latest else None
    if "T10Y2Y" in fetched:
        ctx.curve = fetched["T10Y2Y"].latest.value if fetched["T10Y2Y"].latest else None

    # The most useful macro observation is often that the usual relationship
    # has stopped working.
    if (ctx.real_yield_change_20d is not None
            and ctx.dollar_change_20d is not None
            and ctx.real_yield_change_20d > 0.10
            and ctx.dollar_change_20d > 1.0):
        ctx.notes.append(
            "both real yields and the dollar are rising -- the textbook "
            "combination against gold. If gold is holding up anyway, something "
            "outside this model is bidding it (central bank buying and "
            "geopolitical demand are the usual candidates), and the macro "
            "short case is weaker than the numbers suggest."
        )

    return ctx


def correlation_check(gold_closes: list[float], other_closes: list[float],
                      name: str, expected_sign: str = "negative",
                      period: int = 20) -> str | None:
    """Flag when gold's usual relationship with a driver has inverted.

    A gold/dollar correlation that flips positive is not noise -- it usually
    means a third factor (a crisis bid, a central-bank programme) is dominating
    both, and models built on the normal relationship will be wrong.
    """
    from ..indicators import rolling_correlation

    if len(gold_closes) < period + 5 or len(other_closes) < period + 5:
        return None
    n = min(len(gold_closes), len(other_closes))
    corr = rolling_correlation(gold_closes[-n:], other_closes[-n:], period)
    latest = next((c for c in reversed(corr) if c is not None), None)
    if latest is None:
        return None

    if expected_sign == "negative" and latest > 0.2:
        return (
            f"gold/{name} {period}-period correlation is {latest:+.2f}, "
            f"positive where it is normally strongly negative. The usual "
            f"driver has stopped explaining price -- treat macro-based "
            f"direction with reduced confidence until it re-couples."
        )
    if expected_sign == "positive" and latest < -0.2:
        return (
            f"gold/{name} correlation is {latest:+.2f}, inverted from its "
            f"normal positive relationship."
        )
    return None
