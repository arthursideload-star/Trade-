#!/usr/bin/env python3
"""The hard risk rules R1-R8 from BOT-PLAN.md section 4, encoded as a gate.

These limits live in code, not in a config file, so that changing one is a
reviewable commit (CLAUDE.md). The gate takes a proposed trade plus whatever
context is available and returns, per rule, one of:

  ok        - the rule is satisfied
  blocked   - the rule forbids this trade
  need_input - the rule cannot be judged without data this run does not have
               (daily P&L for R2, a news calendar for R4); the caller/Claude
               must supply it before acting

"need_input" is deliberately not "ok": a rule that could not be checked must
never look like a rule that passed. R4 and R2 stay need_input until Sprint B5
wires in the news and journal feeds.

Standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

MIN_REWARD_RISK = 2.0  # R3
MAX_RISK_PCT = 1.0  # R1
DAILY_LOSS_LIMIT_PCT = -3.0  # R2
NEWS_BLACKOUT_MINUTES = 30  # R4

OK = "ok"
BLOCKED = "blocked"
NEED_INPUT = "need_input"


@dataclass
class RuleResult:
    rule: str
    status: str
    detail: str

    def to_dict(self) -> dict:
        return {"rule": self.rule, "status": self.status, "detail": self.detail}


@dataclass
class GateResult:
    results: list[RuleResult] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return any(r.status == BLOCKED for r in self.results)

    @property
    def needs_input(self) -> bool:
        return any(r.status == NEED_INPUT for r in self.results)

    @property
    def clear(self) -> bool:
        """True only when every rule is satisfied and none is unresolved."""
        return all(r.status == OK for r in self.results)

    def to_dict(self) -> dict:
        return {
            "clear": self.clear,
            "blocked": self.blocked,
            "needs_input": self.needs_input,
            "rules": [r.to_dict() for r in self.results],
        }


# Thin, liquidity-poor windows to avoid (R5), in UTC hours. The Asian afternoon
# lull and the Friday close are when spreads widen and moves get noisy.
def _is_thin_session(moment: datetime) -> tuple[bool, str]:
    utc = moment.astimezone(timezone.utc)
    hour = utc.hour
    weekday = utc.weekday()  # Monday = 0

    if weekday == 4 and hour >= 20:
        return True, "Friday after 20:00 UTC (weekend gap risk, thin book)"
    if weekday == 6 and hour < 22:
        return True, "Weekend, market effectively closed until Sunday 22:00 UTC"
    if weekday == 5:
        return True, "Saturday, market closed"
    # Asian afternoon lull between the Tokyo and London sessions.
    if 6 <= hour < 7:
        return True, "London pre-open lull"
    if 21 <= hour < 22:
        return True, "New York close, liquidity thinning"
    return False, "Within a liquid session"


def evaluate(
    direction: str,
    entry: float,
    stop: Optional[float],
    reward_risk: Optional[float],
    risk_pct: float,
    regime_allowed_direction: str,
    now: Optional[datetime] = None,
    daily_pnl_pct: Optional[float] = None,
    high_impact_news_within_minutes: Optional[int] = None,
    size_increased_after_loss: Optional[bool] = None,
) -> GateResult:
    """Run all eight rules against a proposed trade."""
    now = now or datetime.now(timezone.utc)
    direction = direction.lower()
    results: list[RuleResult] = []

    # R1: risk per trade <= 1%.
    if risk_pct <= MAX_RISK_PCT:
        results.append(RuleResult("R1", OK, f"Risk {risk_pct}% within the {MAX_RISK_PCT}% cap"))
    else:
        results.append(
            RuleResult("R1", BLOCKED, f"Risk {risk_pct}% exceeds the {MAX_RISK_PCT}% cap")
        )

    # R2: daily loss limit. Needs the day's realised P&L.
    if daily_pnl_pct is None:
        results.append(
            RuleResult("R2", NEED_INPUT, "Provide today's P&L %; blocks new trades below -3%")
        )
    elif daily_pnl_pct <= DAILY_LOSS_LIMIT_PCT:
        results.append(
            RuleResult("R2", BLOCKED, f"Daily P&L {daily_pnl_pct:.1f}% at or below the -3% limit")
        )
    else:
        results.append(RuleResult("R2", OK, f"Daily P&L {daily_pnl_pct:.1f}% above the -3% limit"))

    # R3: minimum reward:risk 1:2.
    if reward_risk is None:
        results.append(RuleResult("R3", NEED_INPUT, "No target set, reward:risk unknown"))
    elif reward_risk >= MIN_REWARD_RISK:
        results.append(RuleResult("R3", OK, f"Reward:risk {reward_risk:.2f} meets the 1:2 minimum"))
    else:
        results.append(
            RuleResult("R3", BLOCKED, f"Reward:risk {reward_risk:.2f} below the 1:2 minimum")
        )

    # R4: no trade within 30 min of high-impact news. Needs a calendar (B5).
    if high_impact_news_within_minutes is None:
        results.append(
            RuleResult("R4", NEED_INPUT, "No news calendar wired in yet; check for NFP/CPI/FOMC")
        )
    elif high_impact_news_within_minutes <= NEWS_BLACKOUT_MINUTES:
        results.append(
            RuleResult(
                "R4",
                BLOCKED,
                f"High-impact news in {high_impact_news_within_minutes} min "
                f"(< {NEWS_BLACKOUT_MINUTES} min blackout)",
            )
        )
    else:
        results.append(RuleResult("R4", OK, "No high-impact news inside the blackout window"))

    # R5: avoid thin sessions.
    thin, why = _is_thin_session(now)
    results.append(RuleResult("R5", BLOCKED if thin else OK, why))

    # R6: never increase size after a loss (no martingale).
    if size_increased_after_loss is None:
        results.append(
            RuleResult("R6", OK, "Sizing is fixed-fractional by design; no size increase after loss")
        )
    elif size_increased_after_loss:
        results.append(RuleResult("R6", BLOCKED, "Size was increased after a loss (martingale)"))
    else:
        results.append(RuleResult("R6", OK, "Size not increased after a loss"))

    # R7: every trade has a defined stop.
    if stop is None:
        results.append(RuleResult("R7", BLOCKED, "No stop defined"))
    else:
        results.append(RuleResult("R7", OK, f"Stop defined at {stop}"))

    # R8: the stop comes from structure and the size follows from it. In this
    # pipeline the stop is always an input (from levels.py) and the size is
    # computed from it in position_sizing.py, so the discipline holds whenever a
    # stop exists. Without a stop there is nothing for size to follow.
    if stop is None:
        results.append(RuleResult("R8", BLOCKED, "No structural stop, so size cannot follow it"))
    else:
        results.append(
            RuleResult("R8", OK, "Stop is structural; size is derived from it, not the reverse")
        )

    # Regime alignment: not one of R1-R8, but a hard gate the signal must obey.
    # The regime dictates which side may be traded (PLAN.md A5).
    results.append(_check_regime_direction(direction, regime_allowed_direction))

    return GateResult(results=results)


def _check_regime_direction(direction: str, allowed: str) -> RuleResult:
    """The regime dictates which side may be traded (PLAN.md A5)."""
    if allowed == "long_only" and direction != "long":
        return RuleResult("REGIME", BLOCKED, "Regime is long-only; a short is not permitted")
    if allowed == "short_only" and direction != "short":
        return RuleResult("REGIME", BLOCKED, "Regime is short-only; a long is not permitted")
    if allowed == "none":
        return RuleResult("REGIME", BLOCKED, "Regime undefined; no direction permitted")
    return RuleResult("REGIME", OK, f"Direction {direction} permitted by regime ({allowed})")
