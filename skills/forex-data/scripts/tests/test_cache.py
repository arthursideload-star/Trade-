"""Tests for the TTL file cache."""

import json
import time

import cache


def test_write_then_read_returns_the_payload(tmp_path):
    cache.write("k1", {"status": "ok"}, tmp_path)

    assert cache.read("k1", ttl_seconds=60, cache_dir=tmp_path) == {"status": "ok"}


def test_read_returns_none_for_missing_entry(tmp_path):
    assert cache.read("absent", ttl_seconds=60, cache_dir=tmp_path) is None


def test_read_returns_none_once_the_entry_is_stale(tmp_path):
    cache.write("k1", {"status": "ok"}, tmp_path)

    assert cache.read("k1", ttl_seconds=0, cache_dir=tmp_path) is None


def test_read_returns_none_for_corrupt_file(tmp_path):
    (tmp_path / "broken.json").write_text("not json", encoding="utf-8")

    assert cache.read("broken", ttl_seconds=60, cache_dir=tmp_path) is None


def test_read_returns_none_when_timestamp_is_missing(tmp_path):
    (tmp_path / "k1.json").write_text(json.dumps({"payload": {"a": 1}}), encoding="utf-8")

    assert cache.read("k1", ttl_seconds=60, cache_dir=tmp_path) is None


def test_write_creates_the_directory(tmp_path):
    target = tmp_path / "nested" / "deeper"

    cache.write("k1", {"status": "ok"}, target)

    assert cache.read("k1", ttl_seconds=60, cache_dir=target) == {"status": "ok"}


def test_write_leaves_no_temporary_file_behind(tmp_path):
    cache.write("k1", {"status": "ok"}, tmp_path)

    assert list(tmp_path.glob("*.tmp")) == []


def test_write_failure_does_not_raise(tmp_path):
    """A broken cache must never break a fetch."""
    blocker = tmp_path / "blocked"
    blocker.write_text("I am a file, not a directory", encoding="utf-8")

    cache.write("k1", {"status": "ok"}, blocker)


def test_entry_stays_fresh_within_its_ttl(tmp_path):
    cache.write("k1", {"status": "ok"}, tmp_path)
    time.sleep(0.05)

    assert cache.read("k1", ttl_seconds=60, cache_dir=tmp_path) is not None


def test_cache_key_is_stable_and_parameter_sensitive():
    assert cache.cache_key("a", "b") == cache.cache_key("a", "b")
    assert cache.cache_key("EUR/USD", "15min") != cache.cache_key("EUR/USD", "1h")


def test_ttl_scales_with_candle_length_within_bounds():
    five_minutes = cache.ttl_for_interval(300)
    four_hours = cache.ttl_for_interval(14400)

    assert five_minutes < four_hours
    assert cache.MIN_TTL_SECONDS <= five_minutes <= cache.MAX_TTL_SECONDS
    assert four_hours == cache.MAX_TTL_SECONDS


def test_ttl_never_drops_below_the_minimum():
    assert cache.ttl_for_interval(1) == cache.MIN_TTL_SECONDS


def test_default_cache_dir_honours_environment_override(monkeypatch, tmp_path):
    monkeypatch.setenv("FOREX_CACHE_DIR", str(tmp_path))

    assert cache.default_cache_dir() == tmp_path
