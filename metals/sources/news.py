"""News ingestion for the metals assistant.

Two distinct jobs, deliberately kept separate:

1. **Veto.** Is something happening right now that makes any technical setup
   unreliable? This is a safety function and it fails closed: when the news
   layer cannot be reached, the assistant says so and reduces confidence
   rather than assuming the coast is clear.

2. **Context.** What is the market's story today? A ceasefire, a central bank
   surprise, a mine strike. This shifts the directional lean, and it is the
   part that genuinely needs judgement rather than a rule.

RSS is used in preference to news APIs wherever possible: no key, no quota,
no vendor, and the primary sources (the Fed, the ECB) publish it themselves.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree

from .http import FetchError, HttpClient

# Feeds worth listening to for metals, in rough order of signal quality.
FEEDS: dict[str, tuple[str, str]] = {
    "fed_press": ("https://www.federalreserve.gov/feeds/press_all.xml",
                  "Federal Reserve press releases -- the primary source for "
                  "the variable that prices gold"),
    "fed_speeches": ("https://www.federalreserve.gov/feeds/speeches.xml",
                     "Fed speeches; a hawkish or dovish shift often shows up "
                     "here before it shows up in policy"),
    "kitco": ("https://www.kitco.com/news/category/mining/rss",
              "Kitco -- metals-specific newsroom"),
    "goldseek": ("https://news.goldseek.com/newsRSS.xml",
                 "GoldSeek -- physical-market commentary, structurally bullish"),
    "mining_com": ("https://www.mining.com/feed/",
                   "Mining.com -- supply-side news; matters more for silver"),
    "ecb_press": ("https://www.ecb.europa.eu/rss/press.html",
                  "ECB press releases -- reaches gold through EUR/USD"),
}

# Terms that change the metals picture, weighted by how much they usually move it.
HIGH_IMPACT_TERMS: dict[str, float] = {
    "fomc": 1.0, "federal reserve": 0.9, "rate decision": 1.0,
    "interest rate": 0.8, "cpi": 0.95, "inflation": 0.6,
    "non-farm": 0.95, "nonfarm": 0.95, "payroll": 0.9,
    "jobs report": 0.85, "unemployment": 0.7, "pce": 0.8, "ppi": 0.7,
    "powell": 0.85, "central bank": 0.7, "quantitative": 0.7,
    "war": 0.8, "ceasefire": 0.8, "sanctions": 0.7, "invasion": 0.9,
    "strike": 0.5, "tariff": 0.7, "default": 0.9, "debt ceiling": 0.8,
    "gold reserve": 0.7, "bullion": 0.5, "lease rate": 0.7,
    "backwardation": 0.8, "squeeze": 0.7, "shortage": 0.6,
    "etf outflow": 0.6, "etf inflow": 0.6,
}

# Rough directional lean of a term for gold. Genuinely rough -- context beats
# keywords, which is why this feeds a hint rather than a decision.
DIRECTIONAL_TERMS: dict[str, int] = {
    "ceasefire": -1, "peace deal": -1, "de-escalation": -1,
    "risk-on": -1, "rally in stocks": -1, "hawkish": -1,
    "rate hike": -1, "stronger dollar": -1, "yields rise": -1,
    "war": +1, "invasion": +1, "escalation": +1, "attack": +1,
    "sanctions": +1, "risk-off": +1, "dovish": +1, "rate cut": +1,
    "weaker dollar": +1, "yields fall": +1, "safe haven": +1,
    "central bank buying": +1, "shortage": +1, "backwardation": +1,
}


@dataclass(frozen=True)
class NewsItem:
    title: str
    link: str
    published: datetime | None
    source: str
    summary: str = ""

    @property
    def text(self) -> str:
        return f"{self.title} {self.summary}".lower()

    def impact_score(self) -> float:
        """0.0-1.0 estimate of how much this headline matters to metals."""
        text = self.text
        hits = [w for term, w in HIGH_IMPACT_TERMS.items() if term in text]
        if not hits:
            return 0.0
        # Strongest term dominates; additional terms add a little.
        top = max(hits)
        return min(1.0, top + 0.05 * (len(hits) - 1))

    def direction_hint(self) -> int:
        """+1 supportive for gold, -1 negative, 0 unclear."""
        text = self.text
        score = sum(v for term, v in DIRECTIONAL_TERMS.items() if term in text)
        return (score > 0) - (score < 0)

    def age_minutes(self, now: datetime | None = None) -> float | None:
        if self.published is None:
            return None
        now = now or datetime.now(timezone.utc)
        return (now - self.published).total_seconds() / 60.0


def fetch_feed(client: HttpClient, feed_key: str) -> list[NewsItem]:
    """Fetch and parse one RSS or Atom feed."""
    if feed_key not in FEEDS:
        raise FetchError(feed_key, "unknown feed")
    url, _ = FEEDS[feed_key]
    raw = client.get(url, cache_ttl=300)
    return parse_feed(raw, feed_key)


def parse_feed(raw: bytes, source: str) -> list[NewsItem]:
    """Parse RSS 2.0 or Atom into NewsItems.

    Written against the bytes rather than a requests object so it can be
    tested against recorded payloads with no network.
    """
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise FetchError(source, f"malformed feed XML: {exc}") from exc

    items: list[NewsItem] = []
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    for node in root.iter():
        tag = node.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        title = _text(node, "title", ns)
        if not title:
            continue
        link = _text(node, "link", ns)
        if not link:
            link_node = node.find("atom:link", ns)
            if link_node is not None:
                link = link_node.get("href", "")
        published = _parse_date(
            _text(node, "pubDate", ns)
            or _text(node, "published", ns)
            or _text(node, "updated", ns)
            or _text(node, "date", ns)
        )
        summary = (_text(node, "description", ns)
                   or _text(node, "summary", ns) or "")
        items.append(NewsItem(
            title=_clean(title), link=link or "",
            published=published, source=source, summary=_clean(summary)[:400],
        ))
    return items


def gdelt_search(client: HttpClient, query: str = "gold OR silver OR bullion",
                 hours: int = 24, max_records: int = 50) -> list[NewsItem]:
    """Query GDELT for worldwide coverage of a topic.

    This is the source that answers "has something happened in the world",
    across languages and outside the financial press. It measures coverage,
    not market impact -- a spike is a reason to look at the chart, not a
    reason to take a trade.
    """
    data = client.get_json(
        "https://api.gdeltproject.org/api/v2/doc/doc",
        params={"query": query, "mode": "artlist", "format": "json",
                "maxrecords": max_records, "timespan": f"{hours}h",
                "sort": "datedesc"},
        cache_ttl=600,
    )
    out: list[NewsItem] = []
    for art in (data.get("articles") or []):
        out.append(NewsItem(
            title=_clean(art.get("title", "")),
            link=art.get("url", ""),
            published=_parse_gdelt_date(art.get("seendate")),
            source=f"gdelt:{art.get('domain', 'unknown')}",
        ))
    return out


@dataclass
class NewsContext:
    """The news layer's verdict, ready to fold into a recommendation."""

    items: list[NewsItem] = field(default_factory=list)
    feeds_ok: list[str] = field(default_factory=list)
    feeds_failed: list[tuple[str, str]] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def reachable(self) -> bool:
        """True only when at least one *curated* feed answered.

        GDELT alone does not count. It measures worldwide coverage volume, not
        headlines from the sources that carry policy and metals news -- so a
        run where only GDELT answered has no visibility of an FOMC statement,
        which is precisely what the veto exists to catch. Treating GDELT as
        sufficient would let a trade through 20 minutes after a rate decision.
        """
        return any(f in FEEDS for f in self.feeds_ok)

    @property
    def world_coverage_ok(self) -> bool:
        """Whether the broad geopolitical layer (GDELT) answered."""
        return "gdelt" in self.feeds_ok

    def recent(self, minutes: int = 120) -> list[NewsItem]:
        cutoff = self.fetched_at - timedelta(minutes=minutes)
        return [i for i in self.items
                if i.published is None or i.published >= cutoff]

    def top(self, n: int = 5, min_impact: float = 0.4) -> list[NewsItem]:
        scored = [(i.impact_score(), i) for i in self.items]
        scored = [(s, i) for s, i in scored if s >= min_impact]
        scored.sort(key=lambda x: (x[0], x[1].published or datetime.min.replace(
            tzinfo=timezone.utc)), reverse=True)
        return [i for _, i in scored[:n]]

    @property
    def max_impact(self) -> float:
        return max((i.impact_score() for i in self.recent(180)), default=0.0)

    def directional_lean(self) -> tuple[int, str]:
        """Net directional hint from recent high-impact headlines."""
        recent = [i for i in self.recent(360) if i.impact_score() >= 0.5]
        if not recent:
            return 0, "no high-impact metals headlines in the last six hours"
        votes = [i.direction_hint() for i in recent]
        net = sum(votes)
        pos, neg = votes.count(1), votes.count(-1)
        if net > 0:
            return 1, (f"{pos} of {len(votes)} high-impact headlines lean "
                       f"supportive for metals")
        if net < 0:
            return -1, (f"{neg} of {len(votes)} high-impact headlines lean "
                        f"negative for metals")
        return 0, "high-impact headlines are directionally mixed"

    def veto(self, threshold: float = 0.85,
             window_minutes: int = 45) -> tuple[bool, str]:
        """Should the assistant refuse to propose a trade right now?

        Fails closed: an unreachable news layer produces a warning and a
        confidence penalty rather than silent permission.
        """
        if not self.reachable:
            extra = ""
            if self.world_coverage_ok:
                extra = (" GDELT answered, but it reports coverage volume "
                         "rather than the policy and metals headlines the veto "
                         "needs, so it does not substitute for them.")
            return True, (
                "no curated news feed could be reached, so it is not possible "
                "to tell whether a high-impact release just landed. This is a "
                "refusal by design: on gold, trading blind through a CPI print "
                "is how an account gets halved in one candle." + extra + " "
                + "; ".join(f"{n}: {e}" for n, e in self.feeds_failed[:3])
            )
        hot = [i for i in self.recent(window_minutes) if i.impact_score() >= threshold]
        if hot:
            head = hot[0]
            return True, (
                f"high-impact headline within the last {window_minutes} "
                f"minutes: {head.title!r} ({head.source}). Spreads widen "
                f"severalfold and the first move reverses often enough that "
                f"entering here is a coin flip with a worse payoff."
            )
        return False, "no high-impact metals headline in the immediate window"


def build_news_context(client: HttpClient | None = None,
                       feeds: list[str] | None = None,
                       include_gdelt: bool = True) -> NewsContext:
    """Gather headlines from every reachable feed.

    Individual feed failures are recorded and tolerated; only a total failure
    triggers the veto.
    """
    client = client or HttpClient()
    ctx = NewsContext()
    for key in (feeds or list(FEEDS)):
        try:
            ctx.items.extend(fetch_feed(client, key))
            ctx.feeds_ok.append(key)
        except Exception as exc:  # noqa: BLE001 - one bad feed must not stop the rest
            ctx.feeds_failed.append((key, str(exc)))

    if include_gdelt:
        try:
            ctx.items.extend(gdelt_search(client))
            ctx.feeds_ok.append("gdelt")
        except Exception as exc:  # noqa: BLE001
            ctx.feeds_failed.append(("gdelt", str(exc)))

    ctx.items = _deduplicate(ctx.items)
    ctx.items.sort(
        key=lambda i: i.published or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return ctx


def _deduplicate(items: list[NewsItem]) -> list[NewsItem]:
    """Collapse the same story arriving through several feeds.

    Wire copy is syndicated: one Reuters story on a rate decision reaches
    Kitco, GoldSeek and GDELT within minutes. Counting it three times inflates
    the directional lean and wastes the slots in `top()` on a single event.
    Matching is on a normalised title, which catches syndication without
    merging genuinely distinct stories on the same topic.
    """
    seen: dict[str, NewsItem] = {}
    for item in items:
        key = re.sub(r"[^a-z0-9 ]", "", item.title.lower()).strip()
        key = re.sub(r"\s+", " ", key)
        if not key:
            continue
        existing = seen.get(key)
        # Keep the earliest timestamp -- that is when the story actually broke,
        # which is what the veto window is measured against.
        if existing is None:
            seen[key] = item
        elif (item.published and existing.published
              and item.published < existing.published):
            seen[key] = item
    return list(seen.values())


# --- parsing helpers --------------------------------------------------------

def _text(node, tag: str, ns: dict[str, str]) -> str:
    for candidate in (tag, f"atom:{tag}"):
        found = node.find(candidate, ns)
        if found is not None and found.text:
            return found.text
    return ""


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


_RSS_FORMATS = (
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S %Z",
    "%a, %d %b %Y %H:%M %z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S",
)


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    for fmt in _RSS_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_gdelt_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return _parse_date(value)
