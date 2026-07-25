#!/usr/bin/env python3
"""Position sizing for forex, structure-first.

Encodes the sizing-related risk rules from BOT-PLAN.md section 4. The order of
operations is not negotiable and is the whole point of rule R8: the stop comes
from the chart structure, and the size is whatever makes that stop cost exactly
the risk budget. Size is never chosen first and the stop bent to fit.

  risk_amount (quote ccy) = balance * risk_pct
  stop_distance (price)   = |entry - stop|
  units (base ccy)        = risk_amount / stop_distance

Assumes the account is denominated in the pair's quote currency (true for a
USD account trading EUR/USD, GBP/USD, AUD/USD). For pairs whose quote is not
the account currency the unit count is exact in the quote currency but needs a
conversion to the account currency; the result flags this instead of hiding it.

Standard library only. Decimal is used so the money math carries no binary float
noise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal, localcontext
from typing import Optional

# --- risk limits, in code on purpose (CLAUDE.md) ---------------------------
MAX_RISK_PCT_PER_TRADE = 1.0  # R1: never risk more than 1% of the account
MIN_REWARD_RISK = 2.0  # R3: reject anything below 1:2
STANDARD_LOT = 100_000  # units of base currency
MINI_LOT = 10_000
MICRO_LOT = 1_000

PIP_SIZE_JPY = 0.01
PIP_SIZE_DEFAULT = 0.0001


def pip_size(symbol: str) -> float:
    return PIP_SIZE_JPY if symbol.upper().endswith("JPY") else PIP_SIZE_DEFAULT


def quote_currency(symbol: str) -> str:
    return symbol.upper().split("/")[-1] if "/" in symbol else symbol.upper()[3:]


@dataclass
class SizingResult:
    symbol: str
    direction: str
    entry: float
    stop: float
    target: Optional[float]
    account_balance: float
    risk_pct: float
    risk_amount: float
    stop_distance_pips: float
    units: float
    lots: float
    reward_risk: Optional[float]
    meets_min_rr: Optional[bool]
    quote_currency: str
    account_currency_matches_quote: bool
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "entry": self.entry,
            "stop": self.stop,
            "target": self.target,
            "account_balance": self.account_balance,
            "risk_pct": self.risk_pct,
            "risk_amount": round(self.risk_amount, 2),
            "stop_distance_pips": round(self.stop_distance_pips, 1),
            "units": round(self.units, 2),
            "lots": round(self.lots, 3),
            "reward_risk": None if self.reward_risk is None else round(self.reward_risk, 2),
            "meets_min_rr": self.meets_min_rr,
            "quote_currency": self.quote_currency,
            "account_currency_matches_quote": self.account_currency_matches_quote,
            "warnings": self.warnings,
        }


def reward_risk_ratio(entry: float, stop: float, target: float) -> float:
    """Reward-to-risk from the three prices. Direction is inferred from entry/stop."""
    risk = abs(entry - stop)
    if risk == 0:
        raise ValueError("entry and stop must differ")
    reward = abs(target - entry)
    return reward / risk


def calculate_position(
    symbol: str,
    direction: str,
    entry: float,
    stop: float,
    account_balance: float,
    target: Optional[float] = None,
    risk_pct: float = MAX_RISK_PCT_PER_TRADE,
    account_currency: Optional[str] = None,
) -> SizingResult:
    """Size a position so the structural stop costs exactly the risk budget."""
    direction = direction.lower()
    if direction not in ("long", "short"):
        raise ValueError(f"direction must be long or short, got {direction!r}")
    if account_balance <= 0:
        raise ValueError("account_balance must be positive")
    if entry <= 0 or stop <= 0:
        raise ValueError("entry and stop must be positive prices")
    if entry == stop:
        raise ValueError("entry and stop must differ")

    warnings: list[str] = []

    # R1: the risk budget is capped regardless of what the caller passes.
    if risk_pct > MAX_RISK_PCT_PER_TRADE:
        warnings.append(
            f"risk_pct {risk_pct} exceeds the R1 limit of {MAX_RISK_PCT_PER_TRADE}%, "
            f"clamped to {MAX_RISK_PCT_PER_TRADE}%"
        )
        risk_pct = MAX_RISK_PCT_PER_TRADE
    if risk_pct <= 0:
        raise ValueError("risk_pct must be positive")

    # R8 / R7: the stop must sit on the correct side of entry for the direction,
    # otherwise the "stop" is not an invalidation level at all.
    if direction == "long" and stop >= entry:
        raise ValueError("for a long, stop must be below entry")
    if direction == "short" and stop <= entry:
        raise ValueError("for a short, stop must be above entry")

    pip = pip_size(symbol)
    stop_distance_price = abs(entry - stop)
    stop_distance_pips = stop_distance_price / pip

    with localcontext() as ctx:
        ctx.prec = 28
        risk_amount = Decimal(str(account_balance)) * Decimal(str(risk_pct)) / Decimal(100)
        units_dec = risk_amount / Decimal(str(stop_distance_price))
        units = float(units_dec.quantize(Decimal("0.01"), rounding=ROUND_DOWN))

    reward_risk = None
    meets_min_rr = None
    if target is not None:
        if direction == "long" and target <= entry:
            warnings.append("target is not above entry for a long")
        if direction == "short" and target >= entry:
            warnings.append("target is not below entry for a short")
        reward_risk = reward_risk_ratio(entry, stop, target)
        # R3: below 1:2 is a no-trade, surfaced here for the caller to enforce.
        meets_min_rr = reward_risk >= MIN_REWARD_RISK
        if not meets_min_rr:
            warnings.append(
                f"reward:risk {reward_risk:.2f} is below the R3 minimum of {MIN_REWARD_RISK:.1f} "
                "-> no trade"
            )

    quote = quote_currency(symbol)
    matches = account_currency is None or account_currency.upper() == quote
    if not matches:
        warnings.append(
            f"account currency {account_currency} differs from quote currency {quote}; "
            "unit count is exact in the quote currency but needs conversion to the account currency"
        )

    return SizingResult(
        symbol=symbol,
        direction=direction,
        entry=entry,
        stop=stop,
        target=target,
        account_balance=account_balance,
        risk_pct=risk_pct,
        risk_amount=float(risk_amount),
        stop_distance_pips=stop_distance_pips,
        units=units,
        lots=units / STANDARD_LOT,
        reward_risk=reward_risk,
        meets_min_rr=meets_min_rr,
        quote_currency=quote,
        account_currency_matches_quote=matches,
        warnings=warnings,
    )
