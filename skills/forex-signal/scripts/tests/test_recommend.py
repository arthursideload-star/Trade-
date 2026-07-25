"""Tests for the recommendation orchestrator."""

from datetime import datetime, timezone

import pytest

import recommend as rec


LIQUID = datetime(2026, 7, 22, 14, 0, tzinfo=timezone.utc)  # Wednesday overlap


def _block(interval, regime, allowed, rsi, hist, close, levels, atr=0.0010, patterns=None, fb=None):
    return {
        "interval": interval,
        "last_close": close,
        "last_datetime": "2026-07-22 14:00:00",
        "indicators": {"rsi_14": rsi, "macd_histogram": hist, "atr_14": atr},
        "regime": {"regime": regime, "allowed_direction": allowed, "reason": "test"},
        "levels": levels,
        "patterns_at_level": patterns or [],
        "failed_breakout": fb,
    }


def _bullish_analysis():
    levels = {
        "supports": [{"price": 1.0980, "kind": "support", "touches": 3}],
        "resistances": [{"price": 1.1050, "kind": "resistance", "touches": 3}],
        "distance_to_support_pips": 5,
        "distance_to_resistance_pips": 45,
    }
    return {
        "symbol": "EUR/USD",
        "timeframes": [
            _block("4h", "trend_up", "long_only", 62, 0.0005, 1.1000, levels),
            _block("1h", "trend_up", "long_only", 60, 0.0004, 1.1000, levels),
            _block(
                "15min",
                "trend_up",
                "long_only",
                63,
                0.0004,
                1.1000,
                levels,
                patterns=[{"name": "hammer", "direction": "bullish"}],
            ),
        ],
    }


# --- level derivation ------------------------------------------------------


def test_long_stop_sits_below_support_and_target_at_resistance():
    levels = {
        "supports": [{"price": 1.0980, "kind": "support", "touches": 3}],
        "resistances": [{"price": 1.1050, "kind": "resistance", "touches": 3}],
    }
    tl = rec.derive_trade_levels("long", 1.1000, levels, atr=0.0010, symbol="EUR/USD")
    assert tl.stop < 1.0980  # below the support, with buffer
    assert tl.target == 1.1050
    assert tl.reward_risk is not None


def test_short_stop_sits_above_resistance():
    levels = {
        "supports": [{"price": 1.0950, "kind": "support", "touches": 3}],
        "resistances": [{"price": 1.1020, "kind": "resistance", "touches": 3}],
    }
    tl = rec.derive_trade_levels("short", 1.1000, levels, atr=0.0010, symbol="EUR/USD")
    assert tl.stop > 1.1020
    assert tl.target == 1.0950


def test_fallback_stop_when_no_structural_level():
    levels = {"supports": [], "resistances": []}
    tl = rec.derive_trade_levels("long", 1.1000, levels, atr=0.0010, symbol="EUR/USD")
    assert tl.stop < 1.1000
    assert "fallback" in tl.stop_source
    assert tl.target is None


def test_reward_risk_is_measured_not_assumed():
    # Support 10 pips away (risk ~), resistance 50 pips away -> RR well above 1.
    levels = {
        "supports": [{"price": 1.0990, "kind": "support", "touches": 3}],
        "resistances": [{"price": 1.1050, "kind": "resistance", "touches": 3}],
    }
    tl = rec.derive_trade_levels("long", 1.1000, levels, atr=0.0005, symbol="EUR/USD")
    # Not hard-coded to 2.0
    assert tl.reward_risk != 2.0


# --- full card -------------------------------------------------------------


def test_bullish_setup_produces_a_long_card_with_sizing():
    card = rec.build_recommendation(_bullish_analysis(), account=10_000, now=LIQUID)

    assert card["direction"] == "long"
    assert card["trade"] is not None
    assert card["trade"]["sizing"]["units"] > 0
    assert card["trade"]["stop"] < card["trade"]["entry"]


def test_card_without_account_has_levels_but_no_size():
    card = rec.build_recommendation(_bullish_analysis(), account=None, now=LIQUID)

    assert card["direction"] == "long"
    assert card["trade"]["sizing"] is None
    assert card["trade"]["entry"] is not None


def test_card_runs_the_risk_gate():
    card = rec.build_recommendation(_bullish_analysis(), account=10_000, now=LIQUID)

    rule_ids = {r["rule"] for r in card["risk_gate"]["rules"]}
    assert {"R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"} <= rule_ids


def test_news_rule_stays_need_input_until_b5():
    card = rec.build_recommendation(_bullish_analysis(), account=10_000, now=LIQUID)
    r4 = next(r for r in card["risk_gate"]["rules"] if r["rule"] == "R4")
    assert r4["status"] == "need_input"


def test_thin_session_makes_the_card_not_tradeable():
    friday_night = datetime(2026, 7, 24, 21, 0, tzinfo=timezone.utc)
    card = rec.build_recommendation(_bullish_analysis(), account=10_000, now=friday_night)
    assert card["tradeable"] is False


def test_daily_loss_breach_blocks_the_card():
    card = rec.build_recommendation(
        _bullish_analysis(), account=10_000, now=LIQUID, daily_pnl_pct=-4.0
    )
    r2 = next(r for r in card["risk_gate"]["rules"] if r["rule"] == "R2")
    assert r2["status"] == "blocked"
    assert card["tradeable"] is False


def test_weak_signal_yields_a_wait_card():
    levels = {
        "supports": [{"price": 1.0980}],
        "resistances": [{"price": 1.1020}],
        "distance_to_support_pips": 20,
        "distance_to_resistance_pips": 20,
    }
    analysis = {
        "symbol": "EUR/USD",
        "timeframes": [
            _block("4h", "range", "both_cautious", 50, 0.0, 1.1000, levels),
            _block("1h", "range", "both_cautious", 50, 0.0, 1.1000, levels),
            _block("15min", "range", "both_cautious", 50, 0.0, 1.1000, levels),
        ],
    }
    card = rec.build_recommendation(analysis, account=10_000, now=LIQUID)
    assert card["direction"] == "wait"
    assert card["trade"] is None


# --- text rendering --------------------------------------------------------


def test_text_format_renders_a_card():
    card = rec.build_recommendation(_bullish_analysis(), account=10_000, now=LIQUID)
    text = rec.format_text(card)

    assert "EUR/USD" in text
    assert "LONG" in text
    assert "entry" in text
    assert "R:R" in text


def test_text_format_renders_a_wait_card():
    levels = {"supports": [], "resistances": [], "distance_to_support_pips": None,
              "distance_to_resistance_pips": None}
    analysis = {
        "symbol": "EUR/USD",
        "timeframes": [_block("15min", "range", "both_cautious", 50, 0.0, 1.1000, levels)],
    }
    card = rec.build_recommendation(analysis, account=None, now=LIQUID)
    text = rec.format_text(card)
    assert "WAIT" in text
