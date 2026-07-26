"""Gold and silver trading assistant.

A deterministic analysis toolkit for XAU/USD and XAG/USD, built to be driven
by Claude in an interactive session: the calculators here produce the numbers,
Claude reads them alongside news and macro context and writes the
recommendation.

Everything is standard-library Python. There is nothing to install.

Entry points:

    from metals.analyze import analyse, gather_context
    from metals.risk import AccountState

    account = AccountState(equity=10_000)
    rec = analyse("XAUUSD", account)
    print(rec.render())

Or from the shell:

    python -m metals analyse XAUUSD --equity 10000
    python -m metals sources
    python -m metals rules
"""

from __future__ import annotations

__version__ = "1.0.0"

from .risk import RULES, AccountState
from .specs import XAGUSD, XAUUSD, get_spec

__all__ = [
    "AccountState",
    "RULES",
    "XAUUSD",
    "XAGUSD",
    "get_spec",
    "__version__",
]
