"""Rebuilding the journal from a broker export.

MetaTrader's own VPS never sends the EA's journal file back, so once the bot
moves to hosting the only record that reaches the PC is the broker's deal
history. This reader turns that into the journal schema.

The thing worth guarding hardest is what it refuses to do. A deal export
records what a trade MADE, never what it RISKED, and every expectancy figure
in this project is denominated in R -- money made over money risked. An
importer that invented a denominator would produce numbers that look exactly
like the real ones and mean nothing.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from metals.journal import COLUMNS, load
from metals.sources.mt5report import ReportError, convert, render, write

HTML_HEADER = """<html><body><table>
<tr><th>Time</th><th>Deal</th><th>Symbol</th><th>Type</th><th>Direction</th>
<th>Volume</th><th>Price</th><th>Order</th><th>Commission</th><th>Swap</th>
<th>Profit</th><th>Balance</th><th>Comment</th></tr>
"""


def _deal(time, kind, direction, price, profit="", comment="",
          symbol="XAUUSD", volume="0.10", order="55"):
    return (f"<tr><td>{time}</td><td>1</td><td>{symbol}</td><td>{kind}</td>"
            f"<td>{direction}</td><td>{volume}</td><td>{price}</td>"
            f"<td>{order}</td><td>0.00</td><td>0.00</td><td>{profit}</td>"
            f"<td>10000.00</td><td>{comment}</td></tr>\n")


class ReaderBase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def _write(self, body: str, name: str = "report.html") -> str:
        path = os.path.join(self.dir.name, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        return path


class ItReadsWhatMetaTraderWrites(ReaderBase):

    def test_a_round_trip_becomes_one_closed_trade(self):
        path = self._write(
            HTML_HEADER
            + _deal("2026.08.05 14:03:11", "buy", "in", "4100.50",
                    comment="HS sl=4098.00")
            + _deal("2026.08.05 14:09:40", "sell", "out", "4102.75",
                    profit="22.50")
            + "</table></body></html>")
        result = convert(path)
        self.assertEqual(result.trades, 1)
        row = result.rows[0]
        self.assertEqual(row["direction"], "long")
        self.assertEqual(row["kind"], "close")
        self.assertEqual(row["minutes_held"], "6")
        self.assertAlmostEqual(float(row["pnl"]), 22.50)

    def test_the_direction_comes_from_the_opening_leg(self):
        """The closing deal is always the opposite type, so reading the
        direction off it reports every trade backwards."""
        path = self._write(
            HTML_HEADER
            + _deal("2026.08.05 15:00:00", "sell", "in", "4103.10")
            + _deal("2026.08.05 15:07:00", "buy", "out", "4101.00",
                    profit="21.00")
            + "</table></body></html>")
        (row,) = convert(path).rows
        self.assertEqual(row["direction"], "short")

    def test_german_headers_are_understood(self):
        body = ("<html><body><table>"
                "<tr><th>Zeit</th><th>Symbol</th><th>Typ</th>"
                "<th>Richtung</th><th>Volumen</th><th>Preis</th>"
                "<th>Gewinn</th><th>Kommentar</th></tr>"
                "<tr><td>2026.08.05 14:03:11</td><td>XAUUSD</td><td>buy</td>"
                "<td>in</td><td>0,10</td><td>4100,50</td><td></td>"
                "<td>HS sl=4098,00</td></tr>"
                "<tr><td>2026.08.05 14:09:40</td><td>XAUUSD</td><td>sell</td>"
                "<td>out</td><td>0,10</td><td>4102,75</td><td>22,50</td>"
                "<td></td></tr>"
                "</table></body></html>")
        result = convert(self._write(body))
        self.assertEqual(result.trades, 1)
        self.assertAlmostEqual(float(result.rows[0]["pnl"]), 22.50)

    def test_a_tab_separated_export_also_works(self):
        body = ("Time\tSymbol\tType\tDirection\tVolume\tPrice\tProfit\tComment\n"
                "2026.08.05 14:03:11\tXAUUSD\tbuy\tin\t0.10\t4100.50\t\t"
                "HS sl=4098.00\n"
                "2026.08.05 14:09:40\tXAUUSD\tsell\tout\t0.10\t4102.75\t22.50\t\n")
        result = convert(self._write(body, "report.csv"))
        self.assertEqual(result.trades, 1)

    def test_summary_lines_above_the_table_do_not_confuse_it(self):
        """MetaTrader puts a variable number of header lines above the deals.

        Counting them is how an importer breaks on the next terminal build,
        so the table is found by its column names instead.
        """
        body = ("<html><body>"
                "<table><tr><td>Account:</td><td>Demo</td></tr>"
                "<tr><td>Company:</td><td>Some Broker</td></tr></table>"
                + HTML_HEADER
                + _deal("2026.08.05 14:03:11", "buy", "in", "4100.50",
                        comment="HS sl=4098.00")
                + _deal("2026.08.05 14:09:40", "sell", "out", "4102.75",
                        profit="22.50")
                + "</table></body></html>")
        self.assertEqual(convert(self._write(body)).trades, 1)


class ItRefusesToInventTheDenominator(ReaderBase):
    """The guard that matters more than any parsing detail."""

    def test_a_trade_without_a_recorded_stop_gets_no_r_multiple(self):
        path = self._write(
            HTML_HEADER
            + _deal("2026.08.05 14:03:11", "buy", "in", "4100.50")
            + _deal("2026.08.05 14:09:40", "sell", "out", "4102.75",
                    profit="22.50")
            + "</table></body></html>")
        result = convert(path)
        self.assertEqual(result.rows[0]["r_multiple"], "")
        self.assertEqual(result.without_r, 1)

    def test_the_stop_in_the_comment_produces_an_r_multiple(self):
        path = self._write(
            HTML_HEADER
            + _deal("2026.08.05 14:03:11", "buy", "in", "4100.00",
                    comment="HS sl=4098.00")
            + _deal("2026.08.05 14:09:40", "sell", "out", "4101.00",
                    profit="20.00")
            + "</table></body></html>")
        (row,) = convert(path).rows
        # 2.00 USD/oz stop, 0.10 lots = 10 oz, so 20 USD at risk. A 20 USD
        # profit is therefore exactly 1 R.
        self.assertAlmostEqual(float(row["r_multiple"]), 1.0, places=3)
        self.assertAlmostEqual(float(row["risk_per_unit"]), 2.0)

    def test_the_report_says_how_many_lack_an_r(self):
        """Silence about a missing denominator would be the whole failure."""
        path = self._write(
            HTML_HEADER
            + _deal("2026.08.05 14:03:11", "buy", "in", "4100.50")
            + _deal("2026.08.05 14:09:40", "sell", "out", "4102.75",
                    profit="22.50")
            + "</table></body></html>")
        text = render(convert(path), "out.csv")
        self.assertIn("ohne R-Multiple", text)
        self.assertIn("geraten", text)


class ItSaysWhenItCannotRead(ReaderBase):

    def test_a_missing_file_is_named(self):
        with self.assertRaises(ReportError):
            convert(os.path.join(self.dir.name, "nope.html"))

    def test_an_empty_file_is_refused(self):
        with self.assertRaises(ReportError):
            convert(self._write(""))

    def test_a_file_without_a_deals_table_explains_where_to_get_one(self):
        with self.assertRaises(ReportError) as caught:
            convert(self._write("<html><body><p>nothing here</p></body></html>"))
        self.assertIn("Kontohistorie", str(caught.exception))

    def test_a_position_still_open_is_counted_not_dropped_silently(self):
        path = self._write(
            HTML_HEADER
            + _deal("2026.08.05 14:03:11", "buy", "in", "4100.50")
            + "</table></body></html>")
        result = convert(path)
        self.assertEqual(result.trades, 0)
        self.assertEqual(result.unpaired, 1)


class TheOutputIsAJournal(ReaderBase):
    """The whole point: metals journal must read the result unchanged."""

    def test_the_written_file_loads_as_a_journal(self):
        path = self._write(
            HTML_HEADER
            + _deal("2026.08.05 14:03:11", "buy", "in", "4100.00",
                    comment="HS sl=4098.00")
            + _deal("2026.08.05 14:09:40", "sell", "out", "4101.00",
                    profit="20.00")
            + "</table></body></html>")
        out = os.path.join(self.dir.name, "converted.csv")
        write(convert(path), out)
        entries = load(out)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].kind, "close")
        self.assertAlmostEqual(entries[0].r_multiple, 1.0, places=3)

    def test_the_header_is_the_project_schema(self):
        out = os.path.join(self.dir.name, "converted.csv")
        write(convert(self._write(
            HTML_HEADER
            + _deal("2026.08.05 14:03:11", "buy", "in", "4100.00")
            + _deal("2026.08.05 14:09:40", "sell", "out", "4101.00",
                    profit="20.00")
            + "</table></body></html>")), out)
        with open(out, encoding="utf-8") as fh:
            header = fh.readline().strip()
        self.assertEqual(tuple(header.split(",")), COLUMNS)

    def test_a_symbol_filter_keeps_other_instruments_out(self):
        path = self._write(
            HTML_HEADER
            + _deal("2026.08.05 14:03:11", "buy", "in", "1.10",
                    symbol="EURUSD")
            + _deal("2026.08.05 14:09:40", "sell", "out", "1.11",
                    symbol="EURUSD", profit="9.00")
            + _deal("2026.08.05 15:03:11", "buy", "in", "4100.00")
            + _deal("2026.08.05 15:09:40", "sell", "out", "4101.00",
                    profit="20.00")
            + "</table></body></html>")
        result = convert(path, symbol_filter="XAUUSD")
        self.assertEqual(result.trades, 1)
        self.assertEqual(result.symbols, {"XAUUSD"})


if __name__ == "__main__":
    unittest.main()
