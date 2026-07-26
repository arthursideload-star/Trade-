"""Contract specifications for precious metals.

The canonical unit throughout this package is **USD per troy ounce**.

Reason: the word "pip" is ambiguous on metals. Some brokers and most
educational sites call 0.01 a pip on XAUUSD (0.01 x 100 oz = 1.00 USD per
standard lot), others call 0.10 a pip (0.10 x 100 oz = 10.00 USD per lot).
Mixing the two conventions is a documented way to size a position 10x too
large. This package therefore never sizes in pips: it sizes in dollars per
ounce and converts to lots exactly once, here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InstrumentSpec:
    """Contract specification for a tradable metal instrument."""

    symbol: str
    name: str
    # Troy ounces controlled by one standard lot (CFD) or one contract (futures).
    contract_size_oz: float
    # Smallest price increment the venue quotes, in USD per ounce.
    min_price_increment: float
    # Number of decimals normally quoted.
    price_decimals: int
    # Typical raw spread in USD per ounce during the London/NY overlap.
    typical_spread_usd_oz: float
    # Typical spread in USD per ounce during rollover / thin liquidity.
    thin_spread_usd_oz: float
    # Broker-dependent flag: warn the user to verify against their own platform.
    broker_dependent: bool = True
    notes: str = ""

    @property
    def value_per_dollar_move(self) -> float:
        """USD P/L for a 1.00 USD/oz move on one standard lot."""
        return self.contract_size_oz

    def value_of_move(self, move_usd_oz: float, lots: float) -> float:
        """USD P/L for a given price move and position size."""
        return move_usd_oz * self.contract_size_oz * lots

    def round_price(self, price: float) -> float:
        """Snap a price to the venue's quoted precision."""
        return round(price, self.price_decimals)


# --- Spot CFD instruments (what MT5 / PuPrime / IC Markets quote) -----------

XAUUSD = InstrumentSpec(
    symbol="XAUUSD",
    name="Gold Spot vs US Dollar",
    contract_size_oz=100.0,
    min_price_increment=0.01,
    price_decimals=2,
    typical_spread_usd_oz=0.20,
    thin_spread_usd_oz=1.00,
    notes=(
        "1 standard lot = 100 troy oz. A 1.00 USD/oz move = 100 USD per lot. "
        "PU Prime quotes roughly 0.30 USD/oz average on Standard accounts and "
        "0.08 USD/oz on Prime/ECN accounts; verify on your own platform."
    ),
)

XAGUSD = InstrumentSpec(
    symbol="XAGUSD",
    name="Silver Spot vs US Dollar",
    contract_size_oz=5000.0,
    min_price_increment=0.001,
    price_decimals=3,
    typical_spread_usd_oz=0.020,
    thin_spread_usd_oz=0.060,
    notes=(
        "1 standard lot = 5000 troy oz at most CFD brokers, but 1000 oz at "
        "some. This single number changes position size by 5x -- verify it in "
        "the MT5 contract specification before the first live trade."
    ),
)

# --- COMEX futures (reference: where the real price is discovered) ----------

GC = InstrumentSpec(
    symbol="GC",
    name="COMEX Gold Futures",
    contract_size_oz=100.0,
    min_price_increment=0.10,
    price_decimals=2,
    typical_spread_usd_oz=0.10,
    thin_spread_usd_oz=0.50,
    broker_dependent=False,
    notes="Tick 0.10 USD/oz = 10 USD per contract. Initial margin ~10k USD.",
)

MGC = InstrumentSpec(
    symbol="MGC",
    name="COMEX Micro Gold Futures",
    contract_size_oz=10.0,
    min_price_increment=0.10,
    price_decimals=2,
    typical_spread_usd_oz=0.10,
    thin_spread_usd_oz=0.50,
    broker_dependent=False,
    notes="Tick 0.10 USD/oz = 1 USD per contract.",
)

SI = InstrumentSpec(
    symbol="SI",
    name="COMEX Silver Futures",
    contract_size_oz=5000.0,
    min_price_increment=0.005,
    price_decimals=3,
    typical_spread_usd_oz=0.005,
    thin_spread_usd_oz=0.030,
    broker_dependent=False,
    notes="Tick 0.005 USD/oz = 25 USD per contract.",
)

SIL = InstrumentSpec(
    symbol="SIL",
    name="COMEX Micro Silver Futures",
    contract_size_oz=1000.0,
    min_price_increment=0.005,
    price_decimals=3,
    typical_spread_usd_oz=0.005,
    thin_spread_usd_oz=0.030,
    broker_dependent=False,
    notes="Tick 0.005 USD/oz = 5 USD per contract.",
)


SPECS: dict[str, InstrumentSpec] = {
    s.symbol: s for s in (XAUUSD, XAGUSD, GC, MGC, SI, SIL)
}

# Aliases seen in the wild across data providers and MT5 brokers.
ALIASES: dict[str, str] = {
    "XAU/USD": "XAUUSD",
    "XAUUSD.": "XAUUSD",
    "GOLD": "XAUUSD",
    "GOLD.": "XAUUSD",
    "XAU": "XAUUSD",
    "GC=F": "GC",
    "XAG/USD": "XAGUSD",
    "XAGUSD.": "XAGUSD",
    "SILVER": "XAGUSD",
    "SILVER.": "XAGUSD",
    "XAG": "XAGUSD",
    "SI=F": "SI",
}


def get_spec(symbol: str) -> InstrumentSpec:
    """Look up a spec, tolerating the symbol spellings providers use."""
    key = symbol.strip().upper()
    key = ALIASES.get(key, key)
    if key not in SPECS:
        raise KeyError(
            f"unknown instrument {symbol!r}; known: {sorted(SPECS)} "
            f"or aliases {sorted(ALIASES)}"
        )
    return SPECS[key]


# --- Volatility reference profiles -----------------------------------------
#
# Order-of-magnitude ATR values in USD per ounce, used as sanity bounds and as
# a fallback when live data is unavailable. These are regime-dependent and must
# be recomputed from live candles whenever candles exist -- see
# metals.indicators.atr. They exist so the code can flag "this ATR reading is
# implausible" rather than sizing a position off a corrupt feed.

@dataclass(frozen=True)
class VolatilityProfile:
    symbol: str
    # (low, typical, high) ATR in USD/oz per timeframe.
    atr_m5: tuple[float, float, float]
    atr_m15: tuple[float, float, float]
    atr_h1: tuple[float, float, float]
    atr_h4: tuple[float, float, float]
    atr_d1: tuple[float, float, float]
    # Typical full-day range in USD/oz: (quiet, normal, news day).
    daily_range: tuple[float, float, float]
    notes: str = ""

    def band(self, timeframe: str) -> tuple[float, float, float]:
        key = f"atr_{timeframe.lower()}"
        if not hasattr(self, key):
            raise KeyError(f"no ATR profile for timeframe {timeframe!r}")
        return getattr(self, key)

    def is_plausible(self, timeframe: str, atr_value: float) -> bool:
        """True if a measured ATR sits inside the historical envelope.

        A reading outside the band is not automatically wrong -- regimes do
        shift -- but it is a reason to refuse to size a position off it
        without a human looking at the chart first.
        """
        low, _, high = self.band(timeframe)
        # Generous envelope: regimes genuinely do double and halve.
        return low * 0.4 <= atr_value <= high * 2.5


# Values below are order-of-magnitude reference points consistent with gold
# trading in the low-to-mid four figures per ounce. Gold's H1 ATR is commonly
# quoted at 2-6 USD/oz and its daily range at 60-100 USD/oz in normal
# conditions, expanding to 150-300 USD/oz around high-impact releases.
GOLD_VOL = VolatilityProfile(
    symbol="XAUUSD",
    atr_m5=(0.5, 1.2, 3.0),
    atr_m15=(1.0, 2.2, 6.0),
    atr_h1=(2.0, 4.5, 12.0),
    atr_h4=(5.0, 11.0, 30.0),
    atr_d1=(12.0, 28.0, 80.0),
    daily_range=(35.0, 80.0, 300.0),
    notes=(
        "Gold's ranges scale with the price level. Treat these as ratios of "
        "price rather than absolutes when spot moves far from the level these "
        "were calibrated at; the percent-of-price view is the stable one."
    ),
)

SILVER_VOL = VolatilityProfile(
    symbol="XAGUSD",
    atr_m5=(0.010, 0.030, 0.090),
    atr_m15=(0.020, 0.055, 0.170),
    atr_h1=(0.045, 0.110, 0.350),
    atr_h4=(0.110, 0.270, 0.850),
    atr_d1=(0.250, 0.650, 2.200),
    daily_range=(0.60, 1.60, 6.00),
    notes=(
        "Silver's percentage moves typically run 1.5-2.5x gold's. In absolute "
        "USD/oz the numbers look small; in risk terms they are larger."
    ),
)

VOL_PROFILES: dict[str, VolatilityProfile] = {
    "XAUUSD": GOLD_VOL,
    "XAGUSD": SILVER_VOL,
    "GC": GOLD_VOL,
    "MGC": GOLD_VOL,
    "SI": SILVER_VOL,
    "SIL": SILVER_VOL,
}


def get_vol_profile(symbol: str) -> VolatilityProfile:
    spec = get_spec(symbol)
    return VOL_PROFILES[spec.symbol]


# --- Round-number grids -----------------------------------------------------
#
# Gold and silver respect round numbers unusually well because order flow
# clusters there. The grid spacing differs by an order of magnitude between
# the two metals, so it is defined per instrument rather than derived.

ROUND_LEVEL_STEPS: dict[str, list[float]] = {
    # major, intermediate, minor -- in USD per ounce
    "XAUUSD": [100.0, 50.0, 10.0],
    "XAGUSD": [5.0, 1.0, 0.50],
}


def round_levels(symbol: str) -> list[float]:
    spec = get_spec(symbol)
    base = "XAUUSD" if spec.symbol in ("XAUUSD", "GC", "MGC") else "XAGUSD"
    return ROUND_LEVEL_STEPS[base]
