"""HTTP layer shared by every data source.

Standard library only, so the package installs nowhere and runs anywhere.

Three things matter here and are easy to get wrong:

* **Timeouts.** A hanging request during the London open is worse than no
  data, because the assistant sits waiting instead of saying "no data".
* **Caching.** Free API tiers are metered in requests per day. A 60-second
  cache turns "analyse gold, then analyse silver, then re-check gold" from
  three requests into one.
* **Testability.** The fetcher is injectable, so every source can be tested
  offline against recorded payloads. Nothing in this package requires a live
  network to verify its logic.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

DEFAULT_TIMEOUT = 12.0
DEFAULT_USER_AGENT = "trade-metals-assistant/1.0 (+https://github.com/)"


class FetchError(RuntimeError):
    """Any failure to obtain a usable response from a source."""

    def __init__(self, url: str, reason: str, status: int | None = None):
        self.url = url
        self.reason = reason
        self.status = status
        super().__init__(f"{url}: {reason}" + (f" (HTTP {status})" if status else ""))


class Fetcher(Protocol):
    def __call__(self, url: str, *, headers: dict[str, str] | None = ...,
                 timeout: float = ...) -> bytes: ...


def urllib_fetch(url: str, *, headers: dict[str, str] | None = None,
                 timeout: float = DEFAULT_TIMEOUT) -> bytes:
    """The real network call. Replaced wholesale in tests."""
    req = urllib.request.Request(url, headers={
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "*/*",
        **(headers or {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise FetchError(url, exc.reason or "http error", exc.code) from exc
    except urllib.error.URLError as exc:
        raise FetchError(url, f"network error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise FetchError(url, f"timed out after {timeout}s") from exc


@dataclass
class _CacheEntry:
    value: bytes
    expires_at: float


@dataclass
class HttpClient:
    """Fetcher with TTL caching and bounded retries."""

    fetcher: Fetcher = urllib_fetch
    timeout: float = DEFAULT_TIMEOUT
    cache_ttl: float = 60.0
    retries: int = 2
    backoff: float = 0.6
    _cache: dict[str, _CacheEntry] = field(default_factory=dict, repr=False)
    _request_log: list[tuple[float, str]] = field(default_factory=list, repr=False)

    def get(self, url: str, params: dict[str, Any] | None = None,
            headers: dict[str, str] | None = None,
            cache_ttl: float | None = None) -> bytes:
        full = _with_params(url, params)
        ttl = self.cache_ttl if cache_ttl is None else cache_ttl
        now = time.monotonic()

        entry = self._cache.get(full)
        if entry and entry.expires_at > now:
            return entry.value

        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                data = self.fetcher(full, headers=headers, timeout=self.timeout)
                self._request_log.append((time.time(), full))
                if ttl > 0:
                    self._cache[full] = _CacheEntry(data, now + ttl)
                return data
            except FetchError as exc:
                last = exc
                # 4xx other than 429 will not fix themselves on retry.
                if exc.status and exc.status != 429 and 400 <= exc.status < 500:
                    raise
                if attempt < self.retries:
                    time.sleep(self.backoff * (2 ** attempt))
        raise last if last else FetchError(full, "unknown failure")

    def get_json(self, url: str, params: dict[str, Any] | None = None,
                 headers: dict[str, str] | None = None,
                 cache_ttl: float | None = None) -> Any:
        raw = self.get(url, params, headers, cache_ttl)
        try:
            return json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            snippet = raw[:200].decode("utf-8", errors="replace")
            raise FetchError(url, f"response is not JSON: {snippet!r}") from exc

    def get_text(self, url: str, params: dict[str, Any] | None = None,
                 headers: dict[str, str] | None = None,
                 cache_ttl: float | None = None) -> str:
        return self.get(url, params, headers, cache_ttl).decode(
            "utf-8", errors="replace"
        )

    @property
    def request_count(self) -> int:
        """How many real requests were made -- for staying inside free tiers."""
        return len(self._request_log)

    def requests_since(self, seconds: float) -> int:
        cutoff = time.time() - seconds
        return sum(1 for ts, _ in self._request_log if ts >= cutoff)

    def clear_cache(self) -> None:
        self._cache.clear()


def _with_params(url: str, params: dict[str, Any] | None) -> str:
    if not params:
        return url
    clean = {k: v for k, v in params.items() if v is not None}
    if not clean:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{urllib.parse.urlencode(clean)}"


def try_sources(
    attempts: list[tuple[str, Callable[[], Any]]],
    on_error: Callable[[str, Exception], None] | None = None,
) -> tuple[Any, str, list[tuple[str, str]]]:
    """Run provider callables in order until one succeeds.

    Returns (value, winning_source_name, failures). Fallback chains are the
    whole point of having many sources: a free tier that is out of credits at
    14:00 UTC should not stop the assistant from answering.
    """
    failures: list[tuple[str, str]] = []
    for name, fn in attempts:
        try:
            value = fn()
            if value is not None:
                return value, name, failures
            failures.append((name, "returned no data"))
        except Exception as exc:  # noqa: BLE001 - fallback must survive anything
            failures.append((name, str(exc)))
            if on_error:
                on_error(name, exc)
    raise FetchError(
        "|".join(n for n, _ in attempts),
        "all sources failed: " + "; ".join(f"{n}: {e}" for n, e in failures),
    )
