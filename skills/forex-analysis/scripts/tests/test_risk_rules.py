"""Tests for the R1-R8 risk gate."""

from datetime import datetime, timezone

import risk_rules as rr


def _status(gate, rule):
    return next(r.status for r in gate.results if r.rule == rule)


# A Wednesday 14:00 UTC moment sits inside the liquid London/NY overlap.
LIQUID = datetime(2026, 7, 22, 14, 0, tzinfo=timezone.utc)


def _clean_gate(**overrides):
    params = dict(
        direction="long",
        entry=1.10,
        stop=1.098,
        reward_risk=2.5,
        risk_pct=1.0,
        regime_allowed_direction="long_only",
        now=LIQUID,
        daily_pnl_pct=-1.0,
        high_impact_news_within_minutes=120,
        size_increased_after_loss=False,
    )
    params.update(overrides)
    return rr.evaluate(**params)


# --- happy path ------------------------------------------------------------


def test_a_clean_trade_clears_every_rule():
    gate = _clean_gate()
    assert gate.clear is True
    assert gate.blocked is False
    assert gate.needs_input is False


# --- R1 --------------------------------------------------------------------


def test_r1_blocks_risk_above_one_percent():
    gate = _clean_gate(risk_pct=2.0)
    assert _status(gate, "R1") == rr.BLOCKED
    assert gate.blocked


# --- R2 --------------------------------------------------------------------


def test_r2_needs_input_without_daily_pnl():
    gate = _clean_gate(daily_pnl_pct=None)
    assert _status(gate, "R2") == rr.NEED_INPUT
    assert gate.clear is False  # unresolved is not clear


def test_r2_blocks_below_the_daily_loss_limit():
    gate = _clean_gate(daily_pnl_pct=-3.5)
    assert _status(gate, "R2") == rr.BLOCKED


def test_r2_ok_above_the_limit():
    assert _status(_clean_gate(daily_pnl_pct=-2.0), "R2") == rr.OK


# --- R3 --------------------------------------------------------------------


def test_r3_blocks_below_two_to_one():
    assert _status(_clean_gate(reward_risk=1.5), "R3") == rr.BLOCKED


def test_r3_ok_at_two_to_one():
    assert _status(_clean_gate(reward_risk=2.0), "R3") == rr.OK


def test_r3_needs_input_without_a_target():
    assert _status(_clean_gate(reward_risk=None), "R3") == rr.NEED_INPUT


# --- R4 --------------------------------------------------------------------


def test_r4_needs_input_without_a_news_feed():
    assert _status(_clean_gate(high_impact_news_within_minutes=None), "R4") == rr.NEED_INPUT


def test_r4_blocks_inside_the_news_blackout():
    assert _status(_clean_gate(high_impact_news_within_minutes=15), "R4") == rr.BLOCKED


def test_r4_ok_outside_the_blackout():
    assert _status(_clean_gate(high_impact_news_within_minutes=45), "R4") == rr.OK


# --- R5 --------------------------------------------------------------------


def test_r5_blocks_friday_evening():
    friday_night = datetime(2026, 7, 24, 21, 0, tzinfo=timezone.utc)  # Friday
    assert _status(_clean_gate(now=friday_night), "R5") == rr.BLOCKED


def test_r5_blocks_the_weekend():
    saturday = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)  # Saturday
    assert _status(_clean_gate(now=saturday), "R5") == rr.BLOCKED


def test_r5_ok_in_the_london_ny_overlap():
    assert _status(_clean_gate(now=LIQUID), "R5") == rr.OK


# --- R6 --------------------------------------------------------------------


def test_r6_blocks_size_increase_after_a_loss():
    assert _status(_clean_gate(size_increased_after_loss=True), "R6") == rr.BLOCKED


def test_r6_ok_by_default():
    assert _status(_clean_gate(size_increased_after_loss=None), "R6") == rr.OK


# --- R7 --------------------------------------------------------------------


def test_r7_blocks_a_missing_stop():
    assert _status(_clean_gate(stop=None), "R7") == rr.BLOCKED


# --- R8 --------------------------------------------------------------------


def test_r8_ok_when_a_structural_stop_exists():
    assert _status(_clean_gate(), "R8") == rr.OK


def test_r8_blocks_without_a_stop():
    assert _status(_clean_gate(stop=None), "R8") == rr.BLOCKED


# --- regime alignment (separate gate) --------------------------------------


def test_regime_blocks_a_short_in_a_long_only_regime():
    gate = _clean_gate(direction="short", regime_allowed_direction="long_only")
    assert _status(gate, "REGIME") == rr.BLOCKED


def test_regime_blocks_everything_when_undefined():
    gate = _clean_gate(regime_allowed_direction="none")
    assert _status(gate, "REGIME") == rr.BLOCKED


def test_regime_allows_the_permitted_direction():
    assert _status(_clean_gate(regime_allowed_direction="both_cautious"), "REGIME") == rr.OK


# --- aggregate flags -------------------------------------------------------


def test_needs_input_surfaces_at_the_gate_level():
    gate = _clean_gate(daily_pnl_pct=None, high_impact_news_within_minutes=None)
    assert gate.needs_input is True
    assert gate.blocked is False


def test_to_dict_lists_every_rule():
    payload = _clean_gate().to_dict()
    rule_ids = {r["rule"] for r in payload["rules"]}
    assert {"R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "REGIME"} <= rule_ids
