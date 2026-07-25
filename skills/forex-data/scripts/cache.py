#!/usr/bin/env python3
"""TTL file cache for Twelve Data responses.

The free tier allows 800 credits per day and 8 requests per minute. A top-down
analysis reads four timeframes per pair, so repeated analyses of the same pair
would burn credits for data that has not changed yet. This cache stores raw API
payloads on disk and serves them until they go stale.
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

# A forming candle keeps changing, so the TTL is a fraction of the candle
# length rather than the full length: fresh enough to trade on, cheap enough
# to re-run an analysis a few times.
TTL_DIVISOR = 5
MIN_TTL_SECONDS = 30
MAX_TTL_SECONDS = 900


def default_cache_dir() -> Path:
    """Return the cache directory, overridable via FOREX_CACHE_DIR."""
    override = os.environ.get("FOREX_CACHE_DIR")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "trade-forex-data"


def ttl_for_interval(interval_seconds: int) -> int:
    """Derive a cache TTL from the candle length."""
    ttl = interval_seconds // TTL_DIVISOR
    return max(MIN_TTL_SECONDS, min(ttl, MAX_TTL_SECONDS))


def cache_key(*parts: Any) -> str:
    """Build a stable filename-safe key from the request parameters."""
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def read(key: str, ttl_seconds: int, cache_dir: Optional[Path] = None) -> Optional[dict]:
    """Return the cached payload for *key*, or None if missing or stale."""
    path = (cache_dir or default_cache_dir()) / f"{key}.json"
    try:
        with path.open("r", encoding="utf-8") as handle:
            entry = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None

    stored_at = entry.get("stored_at")
    if not isinstance(stored_at, (int, float)):
        return None
    if time.time() - stored_at > ttl_seconds:
        return None

    payload = entry.get("payload")
    return payload if isinstance(payload, dict) else None


def write(key: str, payload: dict, cache_dir: Optional[Path] = None) -> None:
    """Store *payload* under *key*. Cache failures must never break a fetch."""
    directory = cache_dir or default_cache_dir()
    path = directory / f"{key}.json"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        # Write via a temporary file so a crash cannot leave a truncated entry.
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump({"stored_at": time.time(), "payload": payload}, handle)
        tmp.replace(path)
    except OSError:
        return
