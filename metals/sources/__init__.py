"""Data source connectors for the metals assistant.

Layout:

    http.py      shared HTTP client: timeouts, caching, retries, fallback
    registry.py  catalogue of every source with its tier, limits and caveats
    prices.py    spot and candle data, with an automatic provider fallback chain
    macro.py     real yields, the dollar, inflation expectations (FRED)
    cot.py       CFTC positioning
    news.py      RSS feeds and GDELT
    calendar.py  scheduled releases and the news blackout

Every module here is offline-testable: the HTTP layer is injectable, so the
parsing and interpretation logic is verified against recorded payloads rather
than against a live network.
"""

from __future__ import annotations

from .http import FetchError, HttpClient
from .registry import SOURCES, Auth, Category, coverage_report, keyless

__all__ = [
    "HttpClient",
    "FetchError",
    "SOURCES",
    "Category",
    "Auth",
    "keyless",
    "coverage_report",
]
