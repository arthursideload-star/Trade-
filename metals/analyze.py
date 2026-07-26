"""Top-down orchestration: from raw data to a recommendation card.

The workflow mirrors how the analysis is actually done by hand:

    macro (days)  ->  H4 structure (day)  ->  H1 setup (hours)
                                          ->  M15 trigger (minutes)
                                          ->  veto layer  ->  sizing

The veto layer runs last and can only ever *reduce* confidence or block. That
ordering is deliberate: no amount of technical confluence should be able to
argue its way past a news blackout or a daily loss limit.

Every number in the output carries its provenance. A recommendation built on a
fallback price feed with no macro data and an unreachable news layer is a
different object from one built on the full stack, and the card says so
instead of looking identical.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import gsr, seasonality
from .candles import CandleSeries
from .indicators import adx, atr, atr_percent
from .levels import LevelMap, build_level_map
from .risk import (AccountState, PositionPlan, check_daily_state,
                   size_position, structural_stop)
from .sessions import Quality, SessionState, classify
from .setups import SetupSignal, detect_all
from .sources.calendar import news_blackout
from .sources.http import HttpClient
from .sources.macro import MacroContext, build_macro_context
from .sources.news import NewsContext, build_news_context
from .sources.prices import FetchResult, fetch_candles
from .specs import get_spec, get_vol_profile


@dataclass
class DataQuality:
    """What the analysis actually had to work with."""

    sources_used: dict[str, str] = field(default_factory=dict)
    degraded: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def penalty(self) -> float:
        """Confidence multiplier from data gaps. Never above 1.0."""
        factor = 1.0
        factor -= 0.10 * len(self.degraded)
        factor -= 0.15 * len(self.missing)
        return max(0.35, factor)

    def describe(self) -> list[str]:
        out = [f"{k}: {v}" for k, v in self.sources_used.items()]
        if self.degraded:
            out.append("degraded: " + ", ".join(self.degraded))
        if self.missing:
            out.append("unavailable: " + ", ".join(self.missing))
        return out


@dataclass
class Context:
    """Everything gathered before any setup is evaluated."""

    symbol: str
    moment: datetime
    price: float
    session: SessionState
    h4: CandleSeries | None = None
    h1: CandleSeries | None = None
    m15: CandleSeries | None = None
    d1: CandleSeries | None = None
    levels: LevelMap | None = None
    macro: MacroContext | None = None
    news: NewsContext | None = None
    ratio: gsr.RatioState | None = None
    seasonal: seasonality.SeasonalRead | None = None
    quality: DataQuality = field(default_factory=DataQuality)
    atr_h1: float = 0.0
    atr_m15: float = 0.0
    atr_pct_h1: float | None = None
    regime: str = "unknown"


@dataclass
class Recommendation:
    """The card the user reads before deciding whether to click."""

    symbol: str
    moment: datetime
    action: str                        # "long" | "short" | "no_trade"
    confidence: float
    setup: SetupSignal | None
    plan: PositionPlan | None
    context: Context
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)

    @property
    def actionable(self) -> bool:
        return (self.action != "no_trade"
                and self.plan is not None
                and self.plan.approved
                and self.confidence >= 0.55)

    def render(self) -> str:
        """Human-readable card, in the format the journal stores."""
        lines: list[str] = []
        spec = get_spec(self.symbol)
        lines.append("=" * 68)
        lines.append(f"  {spec.name} ({self.symbol})")
        lines.append(f"  {self.moment.strftime('%Y-%m-%d %H:%M UTC')}  "
                     f"| price {self.context.price:g}")
        lines.append("=" * 68)

        if self.action == "no_trade":
            lines.append("\n  RECOMMENDATION: no trade")
        else:
            lines.append(f"\n  RECOMMENDATION: {self.action.upper()}  "
                         f"(confidence {self.confidence:.0%})")

        if self.setup:
            lines.append(f"  Setup: {self.setup.setup_id} -- {self.setup.name}")

        if self.plan and self.plan.lots > 0:
            lines.append("")
            lines.append(f"  Entry   {self.plan.entry:g}")
            lines.append(f"  Stop    {self.plan.stop:g}   "
                         f"({self.plan.stop_distance_usd_oz:.2f} USD/oz = "
                         f"{self.plan.stop_atr_multiple:.2f}x ATR)")
            lines.append(f"  Target  {self.plan.target:g}")
            lines.append(f"  Size    {self.plan.lots:.2f} lots  "
                         f"(risk {self.plan.risk_usd:.2f} USD = "
                         f"{self.plan.risk_pct:.2f}%)")
            lines.append(f"  R:R     1:{self.plan.reward_risk:.2f}")

        if self.reasons:
            lines.append("\n  WHY")
            for r in self.reasons:
                lines.append(f"    - {r}")

        if self.warnings:
            lines.append("\n  WATCH")
            for w in self.warnings:
                lines.append(f"    ! {w}")

        if self.blocks:
            lines.append("\n  BLOCKED BY")
            for b in self.blocks:
                lines.append(f"    x {b}")

        if self.setup and self.setup.failure_mode:
            lines.append("\n  HOW THIS SETUP FAILS")
            lines.append(f"    {self.setup.failure_mode}")

        lines.append("\n  DATA")
        for d in self.context.quality.describe():
            lines.append(f"    {d}")

        lines.append("\n  Execution is manual. This is analysis, not advice, "
                     "and not a\n  prediction. The stop is the part that "
                     "matters.")
        lines.append("=" * 68)
        return "\n".join(lines)


# --- Context assembly -------------------------------------------------------

def gather_context(
    symbol: str,
    moment: datetime | None = None,
    client: HttpClient | None = None,
    *,
    with_macro: bool = True,
    with_news: bool = True,
    with_ratio: bool = True,
) -> Context:
    """Fetch and assemble everything needed for an analysis.

    Every layer is optional and degrades independently. A failure in the macro
    layer must not stop the technical read; it must show up as reduced
    confidence and a stated gap.
    """
    moment = moment or datetime.now(timezone.utc)
    client = client or HttpClient()
    canonical = get_spec(symbol).symbol
    quality = DataQuality()

    series: dict[str, CandleSeries | None] = {}
    for tf in ("4h", "1h", "15m", "1d"):
        try:
            result: FetchResult = fetch_candles(canonical, tf, 300, client)
            series[tf] = result.series.drop_forming_bar(moment)
            quality.sources_used[f"candles {tf}"] = result.provenance()
            if result.degraded:
                quality.degraded.append(f"candles {tf}")
        except Exception as exc:  # noqa: BLE001
            series[tf] = None
            quality.missing.append(f"candles {tf} ({exc})")

    h1 = series.get("1h")
    if h1 is None or len(h1) == 0:
        raise RuntimeError(
            "no H1 candles from any provider -- the analysis cannot proceed. "
            "Check network access and whether TWELVEDATA_API_KEY is set."
        )

    price = h1.last.close
    ctx = Context(
        symbol=canonical, moment=moment, price=price,
        session=classify(moment),
        h4=series.get("4h"), h1=h1, m15=series.get("15m"), d1=series.get("1d"),
        quality=quality,
    )

    ctx.atr_h1 = _last(atr(h1.highs, h1.lows, h1.closes, 14)) or 0.0
    if ctx.m15:
        ctx.atr_m15 = _last(
            atr(ctx.m15.highs, ctx.m15.lows, ctx.m15.closes, 14)
        ) or 0.0
    ctx.atr_pct_h1 = _last(atr_percent(h1.highs, h1.lows, h1.closes, 14))

    profile = get_vol_profile(canonical)
    if ctx.atr_h1 and not profile.is_plausible("h1", ctx.atr_h1):
        quality.degraded.append(
            f"H1 ATR {ctx.atr_h1:.3f} USD/oz sits outside the historical "
            f"envelope for {canonical} -- either the regime has shifted hard or "
            f"the feed is wrong. Verify against the MT5 chart before sizing."
        )

    ctx.levels = build_level_map(canonical, price, ctx.h4, ctx.m15 or h1, moment)
    ctx.regime = _classify_regime(ctx)
    ctx.seasonal = seasonality.read(canonical, moment.date())

    if with_macro:
        try:
            ctx.macro = build_macro_context(client)
            quality.sources_used["macro"] = "FRED"
            if ctx.macro.missing:
                quality.degraded.append("macro (partial)")
        except Exception as exc:  # noqa: BLE001
            quality.missing.append(f"macro ({exc})")

    if with_news:
        try:
            ctx.news = build_news_context(client)
            quality.sources_used["news"] = (
                f"{len(ctx.news.feeds_ok)} feed(s): "
                f"{', '.join(ctx.news.feeds_ok)}"
            )
            if ctx.news.feeds_failed:
                quality.degraded.append(
                    f"news ({len(ctx.news.feeds_failed)} feed(s) unreachable)"
                )
        except Exception as exc:  # noqa: BLE001
            quality.missing.append(f"news ({exc})")

    if with_ratio:
        # The ratio always needs both metals regardless of which one is being
        # analysed, so it is fetched by fixed symbol rather than relative to
        # the subject instrument.
        try:
            gold_tf = fetch_candles("XAUUSD", "1d", 200, client).series
            silver_tf = fetch_candles("XAGUSD", "1d", 200, client).series
            ctx.ratio = gsr.analyse(gold_tf, silver_tf)
            quality.sources_used["gold/silver ratio"] = "daily closes"
        except Exception as exc:  # noqa: BLE001
            quality.missing.append(f"gold/silver ratio ({exc})")

    return ctx


def analyse(
    symbol: str,
    account: AccountState,
    moment: datetime | None = None,
    client: HttpClient | None = None,
    context: Context | None = None,
    *,
    spread_usd_oz: float | None = None,
) -> Recommendation:
    """Full top-down analysis producing a sized, checked recommendation."""
    moment = moment or datetime.now(timezone.utc)
    ctx = context or gather_context(symbol, moment, client)

    reasons: list[str] = []
    warnings: list[str] = []
    blocks: list[str] = []

    # --- Layer 1: account state --------------------------------------------
    for note in check_daily_state(account):
        if "R2 in force" in note:
            blocks.append(note)
        else:
            warnings.append(note)

    # --- Layer 2: session --------------------------------------------------
    reasons.append(f"session: {ctx.session.session.value} "
                   f"({ctx.session.quality.value}) -- "
                   + "; ".join(ctx.session.reasons))
    if ctx.session.quality is Quality.AVOID:
        blocks.append("R5: " + "; ".join(ctx.session.reasons))

    # --- Layer 3: regime and volatility ------------------------------------
    reasons.append(_describe_regime(ctx))

    # --- Layer 4: macro ----------------------------------------------------
    macro_bias = "unknown"
    if ctx.macro:
        macro_bias = ctx.macro.bias
        reasons.extend(ctx.macro.explain())
    else:
        warnings.append(
            "no macro data. Gold's direction over days is set by real yields "
            "and the dollar; without them this is a purely technical read and "
            "should be weighted accordingly."
        )

    # --- Layer 5: ratio ----------------------------------------------------
    if ctx.ratio:
        reasons.extend(ctx.ratio.notes)
        note = gsr.pair_trade_note(ctx.ratio)
        if note:
            warnings.append(note)

    # --- Layer 6: setups ---------------------------------------------------
    signals = detect_all(ctx.symbol, ctx.h4, ctx.h1, ctx.m15,
                         ctx.levels or build_level_map(ctx.symbol, ctx.price),
                         moment, ctx.session)
    best = signals[0] if signals else None

    if best is None:
        reasons.append(
            "no setup from the catalogue is present. This is the normal state "
            "of the market most of the time -- the majority of bars are not "
            "an opportunity, and treating them as one is the most reliable way "
            "to lose money on metals."
        )
        return Recommendation(
            ctx.symbol, moment, "no_trade", 0.0, None, None, ctx,
            reasons, warnings, blocks,
        )

    reasons.append(f"setup {best.setup_id} ({best.name}): "
                   + "; ".join(best.evidence))
    warnings.extend(best.warnings)

    # --- Layer 7: alignment ------------------------------------------------
    confidence = best.confidence

    if macro_bias != "unknown":
        aligned = ((macro_bias == "bullish" and best.direction == "long")
                   or (macro_bias == "bearish" and best.direction == "short"))
        if aligned:
            confidence += 0.08
            reasons.append(f"macro backdrop ({macro_bias}) agrees with the setup")
        elif macro_bias != "neutral":
            confidence -= 0.12
            warnings.append(
                f"macro backdrop is {macro_bias} while the setup is "
                f"{best.direction}. Counter-macro trades on gold work, but they "
                f"need to be smaller and shorter-held than aligned ones."
            )

    if ctx.ratio:
        preferred, why = gsr.which_metal(ctx.ratio, best.direction)
        if preferred != ctx.symbol:
            confidence -= 0.05
            warnings.append(f"the ratio favours {preferred} for a "
                            f"{best.direction} here: {why}")
        else:
            reasons.append(f"ratio agrees with trading {ctx.symbol} here: {why}")

    if ctx.seasonal:
        seasonal_aligned = (
            (ctx.seasonal.score > 0 and best.direction == "long")
            or (ctx.seasonal.score < 0 and best.direction == "short")
        )
        confidence += ctx.seasonal.confidence_weight * (1 if seasonal_aligned else -1)
        reasons.append(ctx.seasonal.explain())

    # --- Layer 8: news veto -------------------------------------------------
    if ctx.news:
        vetoed, why = ctx.news.veto()
        if vetoed:
            blocks.append(f"R4 (news): {why}")
        lean, lean_note = ctx.news.directional_lean()
        reasons.append(lean_note)
        if lean != 0:
            aligned = (lean > 0 and best.direction == "long") or \
                      (lean < 0 and best.direction == "short")
            confidence += 0.05 if aligned else -0.08
        for item in ctx.news.top(3):
            reasons.append(f"headline: {item.title} ({item.source})")
    else:
        blocks.append(
            "R4: the news layer is unavailable, so it is not possible to "
            "confirm that no high-impact release is imminent. Refusing rather "
            "than assuming."
        )

    try:
        blackout, why = news_blackout(moment, client=client)
        if blackout:
            blocks.append(why)
        else:
            reasons.append(why)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"calendar check failed ({exc}); the news veto is "
                        f"resting on headlines alone")

    # --- Layer 9: data quality ---------------------------------------------
    confidence *= ctx.quality.penalty
    if ctx.quality.penalty < 1.0:
        warnings.append(
            f"confidence reduced by {(1 - ctx.quality.penalty):.0%} for data "
            f"gaps: {'; '.join(ctx.quality.degraded + ctx.quality.missing)}"
        )

    confidence = max(0.0, min(0.95, confidence))

    # --- Layer 10: sizing ---------------------------------------------------
    atr_for_stop = best.atr_value or ctx.atr_h1
    stop = structural_stop(ctx.symbol, best.direction, best.structural_level,
                           atr_for_stop)
    plan = size_position(
        ctx.symbol, best.direction, best.entry, stop, best.target,
        account, atr_for_stop,
        spread_usd_oz=spread_usd_oz,
        moment=moment, session_state=ctx.session,
    )
    warnings.extend(plan.warnings)
    blocks.extend(plan.blocks)

    action = best.direction if not blocks and confidence >= 0.55 else "no_trade"
    if blocks and confidence >= 0.55:
        reasons.append(
            "the setup itself is valid; it is the rule layer that is refusing "
            "it. That distinction matters for the journal -- this is not a "
            "failed read."
        )
    if not blocks and confidence < 0.55:
        warnings.append(
            f"confidence {confidence:.0%} is below the 55% threshold. Every "
            f"component is present but none is strong. A marginal setup taken "
            f"repeatedly is how an edge gets spent on commission."
        )

    return Recommendation(
        ctx.symbol, moment, action, confidence, best, plan, ctx,
        reasons, warnings, blocks,
    )


# --- helpers ----------------------------------------------------------------

def _last(values: list) -> float | None:
    for v in reversed(values):
        if v is not None:
            return v
    return None


def _classify_regime(ctx: Context) -> str:
    """trending / ranging / volatile / quiet, from ADX and ATR percentile."""
    if ctx.h4 is None or len(ctx.h4) < 40:
        return "unknown"
    a_series, _, _ = adx(ctx.h4.highs, ctx.h4.lows, ctx.h4.closes, 14)
    a_val = _last(a_series)
    if a_val is None:
        return "unknown"

    profile = get_vol_profile(ctx.symbol)
    low, typical, high = profile.band("h1")
    hot = ctx.atr_h1 > typical * 1.4
    cold = ctx.atr_h1 < typical * 0.6

    if a_val >= 25:
        return "trending_volatile" if hot else "trending"
    if a_val < 18:
        return "ranging_quiet" if cold else "ranging"
    return "transitional"


def _describe_regime(ctx: Context) -> str:
    guidance = {
        "trending": "trend setups (G3, G10) work; fade setups do not",
        "trending_volatile": "trend setups work but stops must be wider and "
                             "size correspondingly smaller",
        "ranging": "range and reversal setups (G4, G6, G7) work; breakouts "
                   "fail more often than they hold",
        "ranging_quiet": "thin conditions -- expect false breaks; the squeeze "
                         "setup G8 is the one to watch for the resolution",
        "transitional": "no clear regime; the highest-quality setups only",
        "unknown": "regime could not be classified from the available data",
    }
    pct = f"{ctx.atr_pct_h1:.2f}% of price" if ctx.atr_pct_h1 else "unknown"
    return (
        f"regime: {ctx.regime} -- H1 ATR {ctx.atr_h1:.3f} USD/oz ({pct}). "
        f"{guidance.get(ctx.regime, '')}"
    )
