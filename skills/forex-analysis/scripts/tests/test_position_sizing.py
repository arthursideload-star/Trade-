"""Tests for forex position sizing."""

import pytest

import position_sizing as ps


# --- pip size and quote currency -------------------------------------------


def test_quote_currency_extracted_from_pair():
    assert ps.quote_currency("EUR/USD") == "USD"
    assert ps.quote_currency("USD/JPY") == "JPY"


def test_pip_size_depends_on_jpy():
    assert ps.pip_size("EUR/USD") == 0.0001
    assert ps.pip_size("USD/JPY") == 0.01


# --- core sizing math ------------------------------------------------------


def test_units_make_the_structural_stop_cost_exactly_the_risk_budget():
    # 10,000 account, 1% = 100 risk. Stop 20 pips = 0.0020. units = 100/0.0020 = 50,000.
    result = ps.calculate_position(
        symbol="EUR/USD",
        direction="long",
        entry=1.1000,
        stop=1.0980,
        account_balance=10_000,
        risk_pct=1.0,
    )
    assert result.risk_amount == pytest.approx(100.0)
    assert result.units == pytest.approx(50_000, rel=1e-6)
    assert result.stop_distance_pips == pytest.approx(20.0)


def test_lots_are_units_over_a_standard_lot():
    result = ps.calculate_position("EUR/USD", "long", 1.10, 1.098, 10_000)
    assert result.lots == pytest.approx(result.units / 100_000)


def test_jpy_pair_uses_the_larger_pip():
    # Stop 20 pips on a JPY pair = 0.20 price.
    result = ps.calculate_position("USD/JPY", "long", 150.00, 149.80, 10_000)
    assert result.stop_distance_pips == pytest.approx(20.0)


def test_wider_stop_gives_a_smaller_position():
    tight = ps.calculate_position("EUR/USD", "long", 1.1000, 1.0990, 10_000)
    wide = ps.calculate_position("EUR/USD", "long", 1.1000, 1.0950, 10_000)
    assert wide.units < tight.units


# --- R1: risk cap ----------------------------------------------------------


def test_risk_above_one_percent_is_clamped_to_one_percent():
    result = ps.calculate_position("EUR/USD", "long", 1.10, 1.098, 10_000, risk_pct=5.0)
    assert result.risk_pct == ps.MAX_RISK_PCT_PER_TRADE
    assert any("exceeds the R1 limit" in w for w in result.warnings)


# --- R3: reward:risk -------------------------------------------------------


def test_reward_risk_is_computed_from_the_target():
    # entry 1.10, stop 1.098 (risk 0.002), target 1.104 (reward 0.004) -> 2.0
    result = ps.calculate_position("EUR/USD", "long", 1.100, 1.098, 10_000, target=1.104)
    assert result.reward_risk == pytest.approx(2.0)
    assert result.meets_min_rr is True


def test_reward_risk_below_two_is_flagged():
    result = ps.calculate_position("EUR/USD", "long", 1.100, 1.098, 10_000, target=1.103)
    assert result.meets_min_rr is False
    assert any("below the R3 minimum" in w for w in result.warnings)


# --- R8 / R7: stop side ----------------------------------------------------


def test_long_stop_must_be_below_entry():
    with pytest.raises(ValueError, match="stop must be below entry"):
        ps.calculate_position("EUR/USD", "long", 1.100, 1.102, 10_000)


def test_short_stop_must_be_above_entry():
    with pytest.raises(ValueError, match="stop must be above entry"):
        ps.calculate_position("EUR/USD", "short", 1.100, 1.098, 10_000)


def test_short_position_sizes_correctly():
    result = ps.calculate_position("EUR/USD", "short", 1.1000, 1.1020, 10_000, target=1.0960)
    assert result.units == pytest.approx(50_000, rel=1e-6)
    assert result.reward_risk == pytest.approx(2.0)


# --- currency mismatch honesty ---------------------------------------------


def test_matching_account_currency_has_no_conversion_warning():
    result = ps.calculate_position(
        "EUR/USD", "long", 1.10, 1.098, 10_000, account_currency="USD"
    )
    assert result.account_currency_matches_quote is True
    assert not any("conversion" in w for w in result.warnings)


def test_mismatched_account_currency_is_flagged_not_hidden():
    result = ps.calculate_position(
        "EUR/GBP", "long", 0.8500, 0.8480, 10_000, account_currency="USD"
    )
    assert result.account_currency_matches_quote is False
    assert any("conversion" in w for w in result.warnings)


# --- validation ------------------------------------------------------------


def test_zero_balance_rejected():
    with pytest.raises(ValueError, match="account_balance must be positive"):
        ps.calculate_position("EUR/USD", "long", 1.10, 1.098, 0)


def test_equal_entry_and_stop_rejected():
    with pytest.raises(ValueError, match="must differ"):
        ps.calculate_position("EUR/USD", "long", 1.10, 1.10, 10_000)


def test_bad_direction_rejected():
    with pytest.raises(ValueError, match="direction must be"):
        ps.calculate_position("EUR/USD", "sideways", 1.10, 1.098, 10_000)


def test_to_dict_is_json_friendly():
    payload = ps.calculate_position("EUR/USD", "long", 1.10, 1.098, 10_000, target=1.104).to_dict()
    assert payload["units"] > 0
    assert payload["reward_risk"] == 2.0
