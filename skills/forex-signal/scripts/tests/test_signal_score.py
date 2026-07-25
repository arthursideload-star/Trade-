"""Tests for the weighted signal score."""

import pytest

import signal_score as ss


# --- individual factors ----------------------------------------------------


def test_trend_alignment_full_bull_when_all_timeframes_up():
    f = ss.factor_trend_alignment({"4h": "trend_up", "1h": "trend_up", "15min": "trend_up"})
    assert f.contribution == pytest.approx(1.0)


def test_trend_alignment_full_bear_when_all_down():
    f = ss.factor_trend_alignment({"4h": "trend_down", "1h": "trend_down", "15min": "trend_down"})
    assert f.contribution == pytest.approx(-1.0)


def test_trend_alignment_neutral_on_disagreement():
    f = ss.factor_trend_alignment({"4h": "trend_up", "1h": "trend_down", "15min": "range"})
    assert f.contribution == pytest.approx(0.0)


def test_trend_alignment_none_without_data():
    assert ss.factor_trend_alignment({}).contribution is None


def test_momentum_bullish_high_rsi_positive_hist():
    f = ss.factor_momentum(rsi=70, macd_hist=0.0005)
    assert f.contribution > 0


def test_momentum_bearish_low_rsi_negative_hist():
    f = ss.factor_momentum(rsi=30, macd_hist=-0.0005)
    assert f.contribution < 0


def test_momentum_none_without_data():
    assert ss.factor_momentum(None, None).contribution is None


def test_pattern_bullish_vote():
    f = ss.factor_pattern_at_level(
        [{"name": "hammer", "direction": "bullish"}], None
    )
    assert f.contribution == pytest.approx(1.0)


def test_pattern_failed_breakout_counts():
    f = ss.factor_pattern_at_level([], {"direction": "bearish"})
    assert f.contribution == pytest.approx(-1.0)


def test_pattern_zero_without_any():
    assert ss.factor_pattern_at_level([], None).contribution == 0.0


def test_sr_near_support_leans_long():
    f = ss.factor_sr_proximity(dist_support_pips=2, dist_resistance_pips=40)
    assert f.contribution > 0


def test_sr_near_resistance_leans_short():
    f = ss.factor_sr_proximity(dist_support_pips=40, dist_resistance_pips=2)
    assert f.contribution < 0


def test_volume_is_always_unavailable_for_forex():
    assert ss.factor_volume().contribution is None


# --- redistribution of missing weight --------------------------------------


def test_missing_volume_weight_is_redistributed_not_treated_as_zero():
    # All available factors fully bullish -> net must be +1 despite volume being
    # absent. A fake zero for volume would drag this below 1.
    factors = [
        ss.Factor("trend_alignment", 1.0, ""),
        ss.Factor("momentum", 1.0, ""),
        ss.Factor("pattern_at_level", 1.0, ""),
        ss.factor_volume(),  # None
        ss.Factor("sr_proximity", 1.0, ""),
    ]
    result = ss.combine(factors)
    assert result.net == pytest.approx(1.0)
    assert result.direction == "long"


def test_all_factors_missing_yields_wait():
    factors = [
        ss.Factor("trend_alignment", None, ""),
        ss.Factor("momentum", None, ""),
        ss.Factor("pattern_at_level", None, ""),
        ss.factor_volume(),
        ss.Factor("sr_proximity", None, ""),
    ]
    result = ss.combine(factors)
    assert result.direction == "wait"
    assert result.confidence == 0.0


# --- direction and confidence threshold ------------------------------------


def test_weak_lean_becomes_wait():
    factors = [
        ss.Factor("trend_alignment", 0.1, ""),
        ss.Factor("momentum", 0.0, ""),
        ss.Factor("pattern_at_level", 0.0, ""),
        ss.factor_volume(),
        ss.Factor("sr_proximity", 0.0, ""),
    ]
    result = ss.combine(factors)
    assert result.direction == "wait"


def test_strong_bearish_lean_is_short():
    factors = [
        ss.Factor("trend_alignment", -1.0, ""),
        ss.Factor("momentum", -1.0, ""),
        ss.Factor("pattern_at_level", -0.5, ""),
        ss.factor_volume(),
        ss.Factor("sr_proximity", -1.0, ""),
    ]
    result = ss.combine(factors)
    assert result.direction == "short"
    assert result.confidence > ss.MIN_CONFIDENCE_TO_TRADE


# --- from a full analysis payload ------------------------------------------


def _analysis(regime="trend_up", rsi=65, hist=0.0004, ds=3, dr=40, patterns=None, fb=None):
    return {
        "symbol": "EUR/USD",
        "timeframes": [
            {
                "interval": tf,
                "regime": {"regime": regime},
                "indicators": {"rsi_14": rsi, "macd_histogram": hist},
                "levels": {
                    "distance_to_support_pips": ds,
                    "distance_to_resistance_pips": dr,
                },
                "patterns_at_level": patterns or [],
                "failed_breakout": fb,
            }
            for tf in ("4h", "1h", "15min")
        ],
    }


def test_score_from_analysis_bullish_setup_is_long():
    result = ss.score_from_analysis(
        _analysis(patterns=[{"name": "hammer", "direction": "bullish"}])
    )
    assert result.direction == "long"
    assert result.confidence > ss.MIN_CONFIDENCE_TO_TRADE


def test_score_from_analysis_bearish_setup_is_short():
    result = ss.score_from_analysis(
        _analysis(
            regime="trend_down",
            rsi=32,
            hist=-0.0004,
            ds=40,
            dr=3,
            patterns=[{"name": "shooting_star", "direction": "bearish"}],
        )
    )
    assert result.direction == "short"


def test_score_from_analysis_serializes_weights_and_factors():
    payload = ss.score_from_analysis(_analysis()).to_dict()
    names = {f["name"] for f in payload["factors"]}
    assert names == set(ss.WEIGHTS)
    # Volume present in the breakdown but marked unavailable.
    volume = next(f for f in payload["factors"] if f["name"] == "volume")
    assert volume["contribution"] is None


def test_score_from_analysis_requires_timeframes():
    with pytest.raises(ValueError, match="no timeframes"):
        ss.score_from_analysis({"symbol": "EUR/USD", "timeframes": []})
