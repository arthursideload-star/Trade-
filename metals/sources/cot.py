"""CFTC Commitments of Traders positioning for gold and silver.

What this is good for and what it is not:

* **Good for:** spotting positioning extremes that precede multi-week turns.
  When managed money is maximally long and commercials maximally short, the
  marginal buyer has already bought.
* **Not good for:** anything intraday. The report lands Friday 15:30 ET and
  describes the *previous Tuesday*. It is three days stale on arrival and a
  week stale by the following Thursday.

The thresholds below are the levels commonly cited as extremes. They are
regime-dependent: open interest has grown over the decades, so a raw contract
count that was extreme in 2010 is ordinary now. `percentile_extreme` therefore
scores against the instrument's own recent history as well as against the
absolute levels, and the assistant should prefer the percentile reading.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from .http import FetchError, HttpClient

# CFTC market codes for the COMEX metals contracts.
MARKET_CODES: dict[str, str] = {
    "XAUUSD": "088691",   # GOLD - COMMODITY EXCHANGE INC.
    "XAGUSD": "084691",   # SILVER - COMMODITY EXCHANGE INC.
}

# Absolute contract-count levels commonly described as extremes. Treated as
# secondary evidence behind the percentile reading, for the reason above.
ABSOLUTE_EXTREMES: dict[str, dict[str, float]] = {
    "XAUUSD": {"commercial_short_extreme": -250_000,
               "managed_long_extreme": 200_000},
    "XAGUSD": {"commercial_short_extreme": -60_000,
               "managed_long_extreme": 40_000},
}


@dataclass(frozen=True)
class CotReport:
    symbol: str
    report_date: date
    commercial_long: int
    commercial_short: int
    managed_long: int
    managed_short: int
    open_interest: int
    source: str = "cftc_cot"

    @property
    def commercial_net(self) -> int:
        return self.commercial_long - self.commercial_short

    @property
    def managed_net(self) -> int:
        return self.managed_long - self.managed_short

    @property
    def age_days(self) -> int:
        return (datetime.now(timezone.utc).date() - self.report_date).days

    @property
    def managed_net_pct_oi(self) -> float | None:
        """Managed-money net as a share of open interest.

        This normalises across the decades of open-interest growth that make
        raw contract counts incomparable over time.
        """
        if self.open_interest <= 0:
            return None
        return self.managed_net / self.open_interest * 100.0


def fetch_cot(symbol: str, client: HttpClient | None = None,
              weeks: int = 104) -> list[CotReport]:
    """Fetch the recent COT history for a metal from the CFTC's open-data API."""
    client = client or HttpClient()
    from ..specs import get_spec

    canonical = get_spec(symbol).symbol
    code = MARKET_CODES.get(canonical)
    if code is None:
        raise FetchError("cftc_cot", f"no COT market code for {canonical}")

    since = (date.today() - timedelta(weeks=weeks)).isoformat()
    rows = client.get_json(
        "https://publicreporting.cftc.gov/resource/6dca-aqww.json",
        params={
            "cftc_contract_market_code": code,
            "$where": f"report_date_as_yyyy_mm_dd > '{since}'",
            "$order": "report_date_as_yyyy_mm_dd ASC",
            "$limit": weeks + 10,
        },
        cache_ttl=6 * 3600,
    )
    if not isinstance(rows, list) or not rows:
        raise FetchError("cftc_cot", "no rows returned")

    out: list[CotReport] = []
    for r in rows:
        try:
            out.append(CotReport(
                symbol=canonical,
                report_date=datetime.fromisoformat(
                    r["report_date_as_yyyy_mm_dd"].replace("Z", "+00:00")
                ).date(),
                commercial_long=_int(r, "prod_merc_positions_long_all",
                                     "comm_positions_long_all"),
                commercial_short=_int(r, "prod_merc_positions_short_all",
                                      "comm_positions_short_all"),
                managed_long=_int(r, "m_money_positions_long_all"),
                managed_short=_int(r, "m_money_positions_short_all"),
                open_interest=_int(r, "open_interest_all"),
            ))
        except (KeyError, ValueError):
            continue
    if not out:
        raise FetchError("cftc_cot", "rows returned but none were parseable")
    return out


@dataclass
class CotSignal:
    symbol: str
    latest: CotReport
    managed_percentile: float | None
    commercial_percentile: float | None
    reading: str            # "crowded_long" | "crowded_short" | "neutral"
    strength: float         # 0.0 - 1.0
    notes: list[str]

    @property
    def contrarian_bias(self) -> str:
        """Which way the positioning extreme leans, if any."""
        if self.reading == "crowded_long":
            return "bearish"
        if self.reading == "crowded_short":
            return "bullish"
        return "neutral"


def analyse_cot(reports: list[CotReport]) -> CotSignal:
    """Turn a COT history into a positioning read.

    The percentile of the current managed-money net position within its own
    two-year range is the primary measure, because it survives the growth in
    contract sizes that makes absolute thresholds drift.
    """
    if not reports:
        raise ValueError("no reports")
    latest = reports[-1]
    notes: list[str] = []

    managed_history = [r.managed_net for r in reports]
    commercial_history = [r.commercial_net for r in reports]
    m_pct = _percentile(managed_history, latest.managed_net)
    c_pct = _percentile(commercial_history, latest.commercial_net)

    reading, strength = "neutral", 0.0
    if m_pct is not None:
        if m_pct >= 90:
            reading, strength = "crowded_long", min(1.0, (m_pct - 90) / 10 * 0.5 + 0.5)
            notes.append(
                f"managed money net long sits in the {m_pct:.0f}th percentile of "
                f"its two-year range. Everyone who was going to buy has bought; "
                f"the marginal buyer is gone and downside surprises get "
                f"amplified by liquidation."
            )
        elif m_pct <= 10:
            reading, strength = "crowded_short", min(1.0, (10 - m_pct) / 10 * 0.5 + 0.5)
            notes.append(
                f"managed money net position sits in the {m_pct:.0f}th "
                f"percentile -- speculative positioning is washed out, which "
                f"historically precedes upside more often than not."
            )

    absolute = ABSOLUTE_EXTREMES.get(latest.symbol, {})
    if absolute:
        if latest.commercial_net <= absolute["commercial_short_extreme"]:
            notes.append(
                f"commercial net short {latest.commercial_net:,} contracts, past "
                f"the {absolute['commercial_short_extreme']:,.0f} level often "
                f"described as an extreme. Commercials hedge production, so "
                f"their short is not a directional bet -- but the size of it "
                f"tracks how much speculative length is on the other side."
            )
        if latest.managed_net >= absolute["managed_long_extreme"]:
            notes.append(
                f"managed money net long {latest.managed_net:,} contracts, past "
                f"the commonly cited {absolute['managed_long_extreme']:,.0f} "
                f"extreme."
            )

    notes.append(
        f"report is for {latest.report_date.isoformat()}, {latest.age_days} days "
        f"old. COT signals take 4-8 weeks to resolve -- this sets a lean, never "
        f"an entry."
    )
    if latest.age_days > 12:
        notes.append(
            "this report is unusually stale; the weekly release may have been "
            "missed or delayed."
        )

    return CotSignal(latest.symbol, latest, m_pct, c_pct, reading, strength, notes)


def gold_silver_positioning_divergence(
    gold: CotSignal, silver: CotSignal
) -> str | None:
    """Flag when speculators are positioned oppositely in the two metals.

    Gold and silver usually move together. When positioning diverges sharply,
    one of the two is being driven by something metal-specific -- industrial
    demand or a supply squeeze in silver's case -- and the usual "trade them as
    one" assumption stops holding.
    """
    if gold.managed_percentile is None or silver.managed_percentile is None:
        return None
    gap = abs(gold.managed_percentile - silver.managed_percentile)
    if gap < 40:
        return None
    leader = "gold" if gold.managed_percentile > silver.managed_percentile else "silver"
    return (
        f"speculative positioning has diverged sharply: gold at the "
        f"{gold.managed_percentile:.0f}th percentile, silver at the "
        f"{silver.managed_percentile:.0f}th. {leader.capitalize()} is the "
        f"crowded side. The two metals normally share a driver, so a gap this "
        f"wide means something metal-specific is at work -- do not size them "
        f"as one position, and check the gold/silver ratio for the same story."
    )


# --- helpers ----------------------------------------------------------------

def _int(row: dict, *keys: str) -> int:
    """Read the first present key. The CFTC has renamed these columns before."""
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return int(float(row[k]))
    raise KeyError(f"none of {keys} present")


def _percentile(history: list[int], value: int) -> float | None:
    if len(history) < 20:
        return None
    below = sum(1 for h in history if h < value)
    return below / len(history) * 100.0
