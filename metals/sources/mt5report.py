"""Turn a MetaTrader history export into the journal schema.

Why this exists
---------------
MetaTrader's own VPS runs a copy of the terminal that never sends files back.
The `GoldHalfScalp.csv` the EA writes lives on the VPS and cannot be reached
from the PC, so the moment the bot moves to hosting, the analysis in
`metals journal` loses its input.

The trades themselves are not lost, though: they sit on the broker's server
and the local terminal shows them under Kontohistorie. Exporting that and
converting it here restores the one thing that matters most -- what was
traded and what it made.

What is recovered and what is not
---------------------------------
**Recovered:** every closed trade, its direction, entry, exit, volume, the
money it made, how long it was held, and an R multiple wherever the stop
distance can be established.

**Not recovered:** the signals that were *seen and refused*. Those exist only
in the EA's own file, because a refusal never becomes a deal. If you want to
know which gate is doing the work, the VPS Journal tab is the only source and
you have to read it yourself.

**Also not recovered: R multiples, unless a stop is known.** R is money over
money risked, and a deal export records the money made but not what was at
risk. Where the EA wrote its stop into the order comment, this reads it back;
otherwise `r_multiple` stays empty rather than being invented. An R computed
against a guessed denominator is worse than no R at all -- every expectancy
in this project is denominated in it.

    python -m metals journal --file <converted.csv>
"""

from __future__ import annotations

import csv
import html
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..journal import COLUMNS

# Header names as MetaTrader writes them, English and German. Matched
# case-insensitively against the first row that looks like a table header.
_HEADERS: dict[str, tuple[str, ...]] = {
    "time": ("time", "zeit", "open time", "close time", "schliesszeit"),
    "deal": ("deal", "geschäft", "geschaeft", "ticket"),
    "symbol": ("symbol",),
    "type": ("type", "typ"),
    "direction": ("direction", "richtung"),
    "volume": ("volume", "volumen", "lots", "size"),
    "price": ("price", "preis", "kurs"),
    "order": ("order", "auftrag"),
    "commission": ("commission", "kommission", "provision"),
    "fee": ("fee", "gebühr", "gebuehr"),
    "swap": ("swap",),
    "profit": ("profit", "gewinn", "p/l"),
    "comment": ("comment", "kommentar"),
}

# Direction words for the leg that closes a position.
_OUT_WORDS = {"out", "aus", "raus", "out by"}
_IN_WORDS = {"in", "ein", "rein"}


class ReportError(Exception):
    """The file could not be read as a MetaTrader history export."""


@dataclass
class Deal:
    time: datetime
    symbol: str
    type: str
    direction: str
    volume: float | None
    price: float | None
    order: str
    profit: float
    comment: str


@dataclass
class Conversion:
    rows: list[dict] = field(default_factory=list)
    deals_seen: int = 0
    unpaired: int = 0
    without_r: int = 0
    source: str = ""
    symbols: set[str] = field(default_factory=set)

    @property
    def trades(self) -> int:
        return len(self.rows)


def _strip_tags(cell: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", cell)).replace("\xa0", " ").strip()


def _rows_from_html(text: str) -> list[list[str]]:
    out: list[list[str]] = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S | re.I):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S | re.I)
        if cells:
            out.append([_strip_tags(c) for c in cells])
    return out


def _rows_from_delimited(text: str) -> list[list[str]]:
    sample = "\n".join(text.splitlines()[:20])
    delimiter = "\t" if sample.count("\t") > sample.count(";") \
        and sample.count("\t") > sample.count(",") else \
        (";" if sample.count(";") > sample.count(",") else ",")
    return [row for row in csv.reader(text.splitlines(), delimiter=delimiter)
            if any(cell.strip() for cell in row)]


def _find_header(rows: list[list[str]]) -> tuple[int, dict[str, int]]:
    """The header row is the first one that carries a time and a profit column.

    Matched by content rather than by position: MetaTrader's report puts a
    variable number of summary lines above the table, and counting them is
    how an importer breaks on the next terminal build.
    """
    for index, row in enumerate(rows):
        lowered = [c.strip().lower() for c in row]
        mapping: dict[str, int] = {}
        for field_name, names in _HEADERS.items():
            for position, cell in enumerate(lowered):
                if cell in names:
                    mapping.setdefault(field_name, position)
        if "time" in mapping and "profit" in mapping and "symbol" in mapping:
            return index, mapping
    raise ReportError(
        "no deals table found. Expected a row with Time/Zeit, Symbol and "
        "Profit/Gewinn columns.\n"
        "In MetaTrader: tab Kontohistorie -> right click -> Bericht, or "
        "'Als Datei speichern'. Send the file if this keeps failing -- the "
        "export format differs between terminal builds.")


def _as_float(raw: str) -> float | None:
    raw = (raw or "").strip().replace(" ", "").replace(" ", "")
    if not raw:
        return None
    # MetaTrader writes thousands separators and, in some locales, a comma
    # decimal point. Both spellings have to survive.
    if "," in raw and "." in raw:
        raw = raw.replace(",", "") if raw.rfind(".") > raw.rfind(",") \
            else raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _as_time(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    for fmt in ("%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


# The EA writes its stop into the order comment where the broker allows it.
# Read back rather than guessed: see the module docstring on why a guessed
# denominator is worse than an empty column.
_STOP_IN_COMMENT = re.compile(r"sl[= ]\s*([\d.,]+)", re.I)


def convert(path: str, symbol_filter: str | None = None) -> Conversion:
    """Read a MetaTrader export and return rows in the journal schema."""
    if not os.path.exists(path):
        raise ReportError(f"{path} does not exist")
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    if not text.strip():
        raise ReportError(f"{path} is empty")

    rows = _rows_from_html(text) if "<tr" in text.lower() \
        else _rows_from_delimited(text)
    if not rows:
        raise ReportError(f"{path} has no rows this reader can see")

    header_at, columns = _find_header(rows)
    result = Conversion(source=os.path.basename(path))

    def cell(row: list[str], name: str) -> str:
        position = columns.get(name)
        if position is None or position >= len(row):
            return ""
        return row[position].strip()

    deals: list[Deal] = []
    for row in rows[header_at + 1:]:
        when = _as_time(cell(row, "time"))
        if when is None:
            continue                       # summary lines, blank rows
        sym = cell(row, "symbol")
        if not sym:
            continue
        if symbol_filter and symbol_filter.upper() not in sym.upper():
            continue
        profit = sum(v for v in (_as_float(cell(row, "profit")),
                                 _as_float(cell(row, "swap")),
                                 _as_float(cell(row, "commission")),
                                 _as_float(cell(row, "fee"))) if v is not None)
        deals.append(Deal(
            time=when, symbol=sym, type=cell(row, "type").lower(),
            direction=cell(row, "direction").lower(),
            volume=_as_float(cell(row, "volume")),
            price=_as_float(cell(row, "price")),
            order=cell(row, "order"), profit=profit,
            comment=cell(row, "comment"),
        ))
        result.deals_seen += 1
        result.symbols.add(sym)

    # Pair each closing deal with the opening one before it. Direction is used
    # where the export carries it; otherwise the deals alternate, which is
    # what a one-position-at-a-time EA produces.
    open_deal: Deal | None = None
    for deal in sorted(deals, key=lambda d: d.time):
        closes = (deal.direction in _OUT_WORDS if deal.direction
                  else open_deal is not None)
        opens = (deal.direction in _IN_WORDS if deal.direction
                 else open_deal is None)

        if opens and not closes:
            open_deal = deal
            continue
        if not closes:
            continue
        if open_deal is None:
            result.unpaired += 1
            continue

        stop = _STOP_IN_COMMENT.search(open_deal.comment or "")
        risk_per_unit = _as_float(stop.group(1)) if stop else None
        if risk_per_unit is not None and open_deal.price is not None:
            risk_per_unit = abs(open_deal.price - risk_per_unit)

        # `type` on the opening deal is buy/sell; the closing deal is the
        # opposite, so the direction is taken from the opening leg.
        is_long = "buy" in open_deal.type or "kauf" in open_deal.type
        minutes = (deal.time - open_deal.time).total_seconds() / 60.0

        r_multiple = ""
        if risk_per_unit and open_deal.volume:
            # Money risked = stop distance x ounces. 100 oz per lot on gold;
            # stated rather than assumed silently, and only used when the
            # stop was actually recorded.
            risk_money = risk_per_unit * open_deal.volume * 100.0
            if risk_money > 0:
                r_multiple = f"{deal.profit / risk_money:.3f}"
        if not r_multiple:
            result.without_r += 1

        result.rows.append({
            "timestamp": deal.time.strftime("%Y-%m-%d %H:%M:%S"),
            "kind": "close",
            "symbol": open_deal.symbol,
            "setup": "",
            "direction": "long" if is_long else "short",
            "session": "",
            "mode": "auto",
            "entry": "" if open_deal.price is None else f"{open_deal.price:g}",
            "stop": "",
            "target1": "",
            "target2": "",
            "atr": "",
            "spread": "",
            "risk_per_unit": "" if risk_per_unit is None
                             else f"{risk_per_unit:g}",
            "lots": "" if open_deal.volume is None else f"{open_deal.volume:g}",
            "taken": "",
            "skip_reason": "",
            "exit_reason": "",
            "r_multiple": r_multiple,
            "pnl": f"{deal.profit:.2f}",
            "minutes_held": f"{minutes:.0f}",
            "confidence": "",
        })
        open_deal = None

    if open_deal is not None:
        result.unpaired += 1
    return result


def write(conversion: Conversion, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(COLUMNS))
        writer.writeheader()
        for row in conversion.rows:
            writer.writerow(row)


def render(conversion: Conversion, out_path: str) -> str:
    lines = [
        f"{conversion.deals_seen} Deals gelesen aus {conversion.source}.",
        f"{conversion.trades} abgeschlossene Trades nach {out_path} "
        f"geschrieben.",
    ]
    if conversion.symbols:
        lines.append(f"Symbole: {', '.join(sorted(conversion.symbols))}")
    if conversion.unpaired:
        lines.append(
            f"{conversion.unpaired} Deal(s) ohne Gegenstueck — meist eine "
            f"Position, die beim Export noch offen war.")
    if conversion.without_r:
        lines.append(
            f"{conversion.without_r} Trade(s) ohne R-Multiple. Ein Deal-Export "
            f"speichert, was ein Trade eingebracht hat, nicht was er "
            f"riskiert hat.\n"
            f"Ohne bekannten Stop bleibt die Spalte leer statt geraten — jede "
            f"Erwartungswert-Zahl dieses Projekts haengt an ihr.")
    if not conversion.trades:
        lines.append(
            "Keine abgeschlossenen Trades gefunden. Entweder hat der Bot noch "
            "keinen geschlossen, oder das Exportformat weicht ab — dann "
            "schick die Datei.")
    lines.append("")
    lines.append(f"Auswerten mit: python -m metals journal --file {out_path}")
    return "\n".join(lines)
