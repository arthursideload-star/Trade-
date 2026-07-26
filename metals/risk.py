"""Risk rules and position sizing for gold and silver.

Per CLAUDE.md, risk limits live in code, not configuration: changing one must
require a commit and a diff someone can read. The constants below are the
limits. They are deliberately not readable from a config file or an
environment variable.

The metal-specific rules (M1-M6) exist because gold and silver break the
assumptions behind ordinary forex risk rules: the daily range is several
percent, the wick past a level routinely exceeds a sensible forex stop, and
the spread multiplies during rollover and news.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .sessions import Quality, SessionState, classify
from .specs import get_spec

# --- Hard limits ------------------------------------------------------------

MAX_RISK_PER_TRADE_PCT = 1.0        # R1
DAILY_LOSS_LIMIT_PCT = 3.0          # R2
MIN_REWARD_RISK = 2.0               # R3
NEWS_BLACKOUT_MINUTES = 30          # R4
MAX_CONCURRENT_POSITIONS = 2        # R6b
MAX_CORRELATED_RISK_PCT = 1.5       # M4: gold + silver share one risk budget

# Metal-specific
MIN_STOP_ATR_MULTIPLE = 1.0         # M1: never stop tighter than 1.0x ATR(14)
STOP_BUFFER_ATR_MULTIPLE = 0.25     # M2: buffer past the structural level
MAX_SPREAD_ATR_FRACTION = 0.15      # M3: refuse if spread > 15% of ATR
WEEKEND_FLAT_HOUR_UTC = 19          # M5: flat by Friday 19:00 UTC
MAX_ROUND_NUMBER_PROXIMITY_PCT = 0.05  # M6: don't park a stop on a round number

# Sanity bounds on ATR expressed as a percentage of price. Gold's M5 ATR runs
# around 0.01% of price and silver's D1 ATR around 4%; nothing between M5 and
# D1 on either metal lands outside this band. A reading that does is almost
# always an ATR taken from the wrong instrument or a corrupt feed, not a
# regime shift -- and since position size is derived entirely from ATR, it has
# to be caught before the lot number is believed.
MIN_PLAUSIBLE_ATR_PCT = 0.003
MAX_PLAUSIBLE_ATR_PCT = 8.0


class RiskViolation(Exception):
    """Raised when a trade would break a hard limit."""


@dataclass
class AccountState:
    """Everything the sizing logic needs to know about the account."""

    equity: float
    currency: str = "USD"
    realised_pnl_today: float = 0.0
    open_positions: int = 0
    open_risk_pct: float = 0.0
    starting_equity_today: float | None = None

    def __post_init__(self) -> None:
        if self.equity <= 0:
            raise ValueError("equity must be positive")
        if self.starting_equity_today is None:
            self.starting_equity_today = self.equity - self.realised_pnl_today

    @property
    def day_pnl_pct(self) -> float:
        base = self.starting_equity_today or self.equity
        return self.realised_pnl_today / base * 100.0

    @property
    def daily_stop_hit(self) -> bool:
        return self.day_pnl_pct <= -DAILY_LOSS_LIMIT_PCT


@dataclass
class PositionPlan:
    """A fully specified, checkable trade proposal."""

    symbol: str
    direction: str            # "long" or "short"
    entry: float
    stop: float
    target: float
    lots: float
    risk_usd: float
    risk_pct: float
    reward_usd: float
    reward_risk: float
    stop_distance_usd_oz: float
    stop_atr_multiple: float
    spread_cost_usd: float
    warnings: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)

    @property
    def approved(self) -> bool:
        return not self.blocks

    def summary(self) -> str:
        state = "OK" if self.approved else "BLOCKED"
        return (
            f"[{state}] {self.direction.upper()} {self.symbol} "
            f"{self.lots:.2f} lots @ {self.entry} "
            f"SL {self.stop} TP {self.target} "
            f"R:R 1:{self.reward_risk:.2f} risk {self.risk_pct:.2f}%"
        )


def size_position(
    symbol: str,
    direction: str,
    entry: float,
    stop: float,
    target: float,
    account: AccountState,
    atr_value: float,
    *,
    risk_pct: float = MAX_RISK_PER_TRADE_PCT,
    spread_usd_oz: float | None = None,
    moment: datetime | None = None,
    session_state: SessionState | None = None,
    news_minutes_away: float | None = None,
    lot_step: float = 0.01,
    min_lot: float = 0.01,
) -> PositionPlan:
    """Size a position and check it against every hard rule.

    Returns a PositionPlan whose `blocks` list is empty only if the trade is
    permitted. Nothing here raises on a rule breach -- the caller needs to be
    able to show the user *why* a trade was refused, which a traceback does
    badly.

    `atr_value` is ATR(14) on the entry timeframe, in USD per ounce.
    """
    direction = direction.lower().strip()
    if direction not in ("long", "short"):
        raise ValueError("direction must be 'long' or 'short'")

    spec = get_spec(symbol)
    moment = moment or datetime.now(timezone.utc)
    session_state = session_state or classify(moment)
    spread = spread_usd_oz if spread_usd_oz is not None else spec.typical_spread_usd_oz

    warnings: list[str] = []
    blocks: list[str] = []

    # --- Geometry sanity ---------------------------------------------------
    if direction == "long" and not (stop < entry < target):
        blocks.append(
            f"geometry invalid for a long: need stop < entry < target, "
            f"got {stop} / {entry} / {target}"
        )
    if direction == "short" and not (target < entry < stop):
        blocks.append(
            f"geometry invalid for a short: need target < entry < stop, "
            f"got {target} / {entry} / {stop}"
        )

    stop_distance = abs(entry - stop)
    reward_distance = abs(target - entry)
    if stop_distance <= 0:
        blocks.append("stop distance is zero -- R7: every trade needs a "
                      "defined invalidation")
        return PositionPlan(symbol, direction, entry, stop, target, 0.0, 0.0,
                            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, warnings, blocks)

    # --- R2: daily loss limit ---------------------------------------------
    if account.daily_stop_hit:
        blocks.append(
            f"R2: daily loss limit reached ({account.day_pnl_pct:.2f}% vs "
            f"-{DAILY_LOSS_LIMIT_PCT}%) -- no new positions today"
        )

    # --- R1 / M4: risk budget ---------------------------------------------
    if risk_pct > MAX_RISK_PER_TRADE_PCT:
        warnings.append(
            f"R1: requested {risk_pct}% capped to {MAX_RISK_PER_TRADE_PCT}%"
        )
        risk_pct = MAX_RISK_PER_TRADE_PCT

    if account.open_risk_pct + risk_pct > MAX_CORRELATED_RISK_PCT:
        blocks.append(
            f"M4: gold and silver share one risk budget. Open risk "
            f"{account.open_risk_pct:.2f}% + {risk_pct:.2f}% would exceed the "
            f"{MAX_CORRELATED_RISK_PCT}% cap. Their correlation is high enough "
            f"that two positions is one position with extra steps."
        )

    if account.open_positions >= MAX_CONCURRENT_POSITIONS:
        blocks.append(
            f"R6b: already {account.open_positions} positions open "
            f"(max {MAX_CONCURRENT_POSITIONS})"
        )

    # --- R3: minimum reward/risk ------------------------------------------
    reward_risk = reward_distance / stop_distance
    if reward_risk < MIN_REWARD_RISK:
        blocks.append(
            f"R3: reward/risk is 1:{reward_risk:.2f}, below the 1:"
            f"{MIN_REWARD_RISK:.0f} minimum. Either the target is too close "
            f"or the stop is too wide -- do not fix this by tightening the stop."
        )

    # --- M1: stop must respect volatility ---------------------------------
    stop_atr_multiple = stop_distance / atr_value if atr_value > 0 else 0.0
    if atr_value > 0 and stop_atr_multiple < MIN_STOP_ATR_MULTIPLE:
        blocks.append(
            f"M1: stop is {stop_atr_multiple:.2f}x ATR ({stop_distance:.2f} vs "
            f"ATR {atr_value:.2f} USD/oz), below the {MIN_STOP_ATR_MULTIPLE}x "
            f"minimum. On metals a stop inside one ATR is noise, not risk -- "
            f"it will be taken out by a normal wick before the idea resolves."
        )
    if stop_atr_multiple > 4.0:
        warnings.append(
            f"stop is {stop_atr_multiple:.2f}x ATR, unusually wide. Check that "
            f"the structural level is the right one before accepting the "
            f"smaller position size that follows from it."
        )

    # --- ATR plausibility --------------------------------------------------
    if atr_value <= 0:
        blocks.append("ATR is zero or missing -- cannot size a position "
                      "without a volatility reading")
    elif entry > 0:
        atr_pct = atr_value / entry * 100.0
        if not (MIN_PLAUSIBLE_ATR_PCT <= atr_pct <= MAX_PLAUSIBLE_ATR_PCT):
            warnings.append(
                f"ATR {atr_value:.4f} USD/oz is {atr_pct:.3f}% of price, "
                f"outside the {MIN_PLAUSIBLE_ATR_PCT}-{MAX_PLAUSIBLE_ATR_PCT}% "
                f"band that covers every timeframe from M5 to D1 on both "
                f"metals. Regimes shift, but not by this much -- the usual "
                f"cause is an ATR read from the wrong instrument or a corrupt "
                f"feed. Every lot number below is derived from this value, so "
                f"check it against your MT5 chart before accepting the size."
            )

    # --- M3: spread relative to volatility ---------------------------------
    if atr_value > 0 and spread > atr_value * MAX_SPREAD_ATR_FRACTION:
        blocks.append(
            f"M3: spread {spread:.3f} USD/oz is "
            f"{spread / atr_value * 100:.0f}% of ATR, above the "
            f"{MAX_SPREAD_ATR_FRACTION * 100:.0f}% ceiling. The edge is being "
            f"paid to the broker."
        )

    # --- R4: news blackout --------------------------------------------------
    if news_minutes_away is not None and abs(news_minutes_away) < NEWS_BLACKOUT_MINUTES:
        blocks.append(
            f"R4: high-impact release {abs(news_minutes_away):.0f} minutes "
            f"away (blackout is {NEWS_BLACKOUT_MINUTES} minutes either side). "
            f"Gold routinely moves 80-200 USD/oz-equivalent on these prints "
            f"and the first direction is wrong often enough that it is not a "
            f"coin flip worth taking."
        )

    # --- R5 / session quality ----------------------------------------------
    if session_state.quality == Quality.AVOID:
        blocks.append(
            "R5: session quality is 'avoid' -- "
            + "; ".join(session_state.reasons)
        )
    elif session_state.quality == Quality.MARGINAL:
        warnings.append(
            "session quality is marginal -- "
            + "; ".join(session_state.reasons)
        )

    # --- M5: weekend gap risk ----------------------------------------------
    if moment.weekday() == 4 and moment.hour >= WEEKEND_FLAT_HOUR_UTC:
        blocks.append(
            f"M5: after Friday {WEEKEND_FLAT_HOUR_UTC}:00 UTC. Weekend gaps of "
            f"5 USD/oz or more occur in roughly a third of weeks on gold and a "
            f"stop does not protect against a gap."
        )

    # --- M6: stop parked on a round number ---------------------------------
    round_warning = _round_number_warning(symbol, stop)
    if round_warning:
        warnings.append(round_warning)

    # --- Sizing -------------------------------------------------------------
    risk_usd = account.equity * risk_pct / 100.0
    risk_per_lot = stop_distance * spec.contract_size_oz
    raw_lots = risk_usd / risk_per_lot if risk_per_lot > 0 else 0.0
    lots = _floor_to_step(raw_lots, lot_step)

    if lots < min_lot:
        blocks.append(
            f"position size rounds to {lots:.4f} lots, below the {min_lot} "
            f"minimum. At {account.equity:.2f} {account.currency} equity a "
            f"{stop_distance:.2f} USD/oz stop on {symbol} cannot be taken "
            f"within {risk_pct:.2f}% risk. This is an account-size constraint, "
            f"not a signal problem -- do not solve it by widening risk."
        )
        lots = 0.0

    actual_risk_usd = lots * risk_per_lot
    actual_risk_pct = actual_risk_usd / account.equity * 100.0
    reward_usd = lots * reward_distance * spec.contract_size_oz
    spread_cost = lots * spread * spec.contract_size_oz

    if actual_risk_usd > 0 and spread_cost > actual_risk_usd * 0.10:
        warnings.append(
            f"spread costs {spread_cost:.2f} USD, {spread_cost / actual_risk_usd * 100:.0f}% "
            f"of the amount at risk -- meaningful drag on a scalp"
        )

    if spec.broker_dependent:
        warnings.append(
            f"contract size for {spec.symbol} is taken as "
            f"{spec.contract_size_oz:.0f} oz per lot. Verify this in the MT5 "
            f"contract specification -- brokers differ, and on silver the "
            f"difference is 5x."
        )

    return PositionPlan(
        symbol=spec.symbol,
        direction=direction,
        entry=entry,
        stop=stop,
        target=target,
        lots=lots,
        risk_usd=actual_risk_usd,
        risk_pct=actual_risk_pct,
        reward_usd=reward_usd,
        reward_risk=reward_risk,
        stop_distance_usd_oz=stop_distance,
        stop_atr_multiple=stop_atr_multiple,
        spread_cost_usd=spread_cost,
        warnings=warnings,
        blocks=blocks,
    )


def structural_stop(
    symbol: str,
    direction: str,
    structural_level: float,
    atr_value: float,
    buffer_multiple: float = STOP_BUFFER_ATR_MULTIPLE,
) -> float:
    """Place a stop beyond a structural level with an ATR buffer.

    M2. Gold and silver routinely wick past a level to reach the stops sitting
    just behind it before the real move starts. A stop placed exactly at the
    swing low is not protecting the idea, it is funding someone else's entry.
    """
    spec = get_spec(symbol)
    buffer = atr_value * buffer_multiple
    raw = structural_level - buffer if direction == "long" else structural_level + buffer
    return spec.round_price(raw)


def _floor_to_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    return int(value / step) * step


def _round_number_warning(symbol: str, price: float) -> str | None:
    """M6: warn when a stop sits within a hair of a round number."""
    from .specs import round_levels

    for step in round_levels(symbol):
        nearest = round(price / step) * step
        if abs(price - nearest) / price * 100.0 < MAX_ROUND_NUMBER_PROXIMITY_PCT:
            return (
                f"M6: stop at {price} sits on the {nearest:g} round number. "
                f"Order flow clusters there and metals reach through it. Move "
                f"the stop past the level, not onto it."
            )
    return None


def check_daily_state(account: AccountState) -> list[str]:
    """Pre-session check the assistant runs before proposing anything."""
    notes: list[str] = []
    if account.daily_stop_hit:
        notes.append(
            f"R2 in force: {account.day_pnl_pct:.2f}% on the day. Trading is "
            f"finished until the next session. This rule exists because the "
            f"trade taken to recover a bad day is the one that turns a bad day "
            f"into a bad month."
        )
    elif account.day_pnl_pct <= -DAILY_LOSS_LIMIT_PCT * 0.66:
        notes.append(
            f"approaching the daily limit ({account.day_pnl_pct:.2f}% of "
            f"-{DAILY_LOSS_LIMIT_PCT}%) -- one more losing trade ends the day"
        )
    if account.open_risk_pct > 0:
        notes.append(
            f"{account.open_risk_pct:.2f}% already at risk in open positions; "
            f"{max(0.0, MAX_CORRELATED_RISK_PCT - account.open_risk_pct):.2f}% "
            f"of the shared metals budget remains"
        )
    return notes


# --- Documentation of the rule set, used by the CLI and the skill -----------

RULES: dict[str, str] = {
    "R1": "Risk per trade never exceeds 1% of account equity.",
    "R2": "At -3% on the day, trading stops until the next session.",
    "R3": "Minimum reward/risk 1:2, measured to the first target.",
    "R4": "No entry within 30 minutes either side of a high-impact release.",
    "R5": "No entry during rollover, deep Asian hours, or Friday late session.",
    "R6": "Position size never increases after a loss. No Martingale, no grid.",
    "R6b": "At most 2 positions open at once.",
    "R7": "Every trade has a defined invalidation before it is entered.",
    "R8": "The stop comes from structure; size follows from the stop. Never "
          "the other way round.",
    "M1": "Stop is never tighter than 1.0x ATR(14) on the entry timeframe.",
    "M2": "Stops sit beyond the structural level by 0.25x ATR, never on it.",
    "M3": "No entry when the spread exceeds 15% of ATR.",
    "M4": "Gold and silver share a single 1.5% risk budget -- they are one "
          "position expressed two ways.",
    "M5": "Flat by Friday 19:00 UTC. Stops do not protect against weekend gaps.",
    "M6": "Stops are not parked on round numbers.",
}
