"""Loading real downloaded history files.

The tests here are mostly about the ways these files are wrong: the wrong
timezone, duplicate bars, impossible OHLC, weekend rows, gaps. A loader that
only handles clean input is not useful, because none of these downloads are
clean.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from metals.sources.history import (HistoryError, KNOWN_OFFSETS, detect_format,
                                    load, parse_timestamp, resample, to_csv)

UTC = timezone.utc


def _write(text: str, suffix: str = ".csv") -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _bars(n: int, start: datetime, fmt: str, price: float = 2050.0,
          step_min: int = 5, sep: str = ",") -> str:
    """Generate n plausible M5 rows in a given timestamp format."""
    rows = []
    ts = start
    for i in range(n):
        # Skip weekends so the validator does not flag them.
        while ts.weekday() == 5 or (ts.weekday() == 6 and ts.hour < 22):
            ts += timedelta(hours=1)
        o = price + i * 0.05
        h = o + 0.6
        lo = o - 0.6
        c = o + 0.1
        rows.append(sep.join([ts.strftime(fmt), f"{o:.2f}", f"{h:.2f}",
                              f"{lo:.2f}", f"{c:.2f}", "120"]))
        ts += timedelta(minutes=step_min)
    return "\n".join(rows)


class TestTimestampParsing(unittest.TestCase):
    def test_the_formats_these_downloads_actually_use(self):
        cases = {
            "2024-01-02 07:15:00": datetime(2024, 1, 2, 7, 15),
            "2024-01-02 07:15": datetime(2024, 1, 2, 7, 15),
            "2024.01.02 07:15": datetime(2024, 1, 2, 7, 15),      # MetaTrader
            "20240102 071500": datetime(2024, 1, 2, 7, 15),        # HistData
            "2024-01-02T07:15:00": datetime(2024, 1, 2, 7, 15),
        }
        for text, expected in cases.items():
            self.assertEqual(parse_timestamp(text), expected, text)

    def test_epoch_seconds_and_milliseconds(self):
        expected = datetime(2024, 1, 2, 6, 55)   # 1704178500 as UTC
        self.assertEqual(parse_timestamp("1704178500"), expected)
        self.assertEqual(parse_timestamp("1704178500000"), expected)

    def test_unparseable_raises(self):
        with self.assertRaises(ValueError):
            parse_timestamp("not a date")


class TestFormatDetection(unittest.TestCase):
    def test_metatrader(self):
        self.assertEqual(
            detect_format(["Date", "Open", "High", "Low", "Close", "Volume"],
                          ["2024.01.02 07:15", "2050", "2051", "2049", "2050"]),
            "metatrader")

    def test_histdata(self):
        self.assertEqual(
            detect_format([], ["20240102 071500", "2050", "2051", "2049"]),
            "histdata")

    def test_dukascopy(self):
        self.assertEqual(
            detect_format(["timestamp", "open", "high", "low", "close", "volume"],
                          ["2024-01-02 07:15:00", "2050", "2051", "2049", "2050"]),
            "dukascopy")


class TestLoading(unittest.TestCase):
    def test_dukascopy_style_utc(self):
        text = ("timestamp,open,high,low,close,volume\n"
                + _bars(600, datetime(2024, 1, 2, 8, 0), "%Y-%m-%d %H:%M:%S"))
        path = _write(text)
        try:
            series, report = load(path, "utc")
            self.assertEqual(report.detected_format, "dukascopy")
            self.assertGreater(report.rows_used, 500)
            self.assertEqual(series[0].ts.tzinfo, UTC)
            self.assertEqual(series[0].ts.hour, 8)
        finally:
            os.unlink(path)

    def test_metatrader_broker_time_is_shifted_to_utc(self):
        """The whole point of the module: a broker-time file must move.

        A bar stamped 10:00 on a GMT+3 server is 07:00 UTC. Without this the
        London-open setups would fire three hours early.
        """
        text = ("Date,Open,High,Low,Close,Volume\n"
                + _bars(600, datetime(2024, 1, 2, 10, 0), "%Y.%m.%d %H:%M"))
        path = _write(text)
        try:
            series, report = load(path, "broker_gmt3")
            self.assertEqual(report.detected_format, "metatrader")
            self.assertEqual(series[0].ts.hour, 7)
            self.assertEqual(series[0].ts.tzinfo, UTC)
        finally:
            os.unlink(path)

    def test_histdata_semicolons_and_eastern_time(self):
        text = _bars(600, datetime(2024, 1, 2, 3, 0), "%Y%m%d %H%M%S", sep=";")
        path = _write(text)
        try:
            series, report = load(path, "us_eastern_no_dst")
            # 03:00 EST is 08:00 UTC.
            self.assertEqual(series[0].ts.hour, 8)
            self.assertTrue(any("no header" in w for w in report.warnings))
        finally:
            os.unlink(path)

    def test_timezone_must_be_stated(self):
        path = _write("timestamp,open,high,low,close\n2024-01-02 08:00:00,1,2,0.5,1.5\n")
        try:
            with self.assertRaises(HistoryError) as ctx:
                load(path, "central_european_summer_maybe")
            self.assertIn("no default on purpose", str(ctx.exception))
        finally:
            os.unlink(path)

    def test_signed_offset_is_accepted(self):
        text = ("timestamp,open,high,low,close,volume\n"
                + _bars(300, datetime(2024, 1, 2, 10, 0), "%Y-%m-%d %H:%M:%S"))
        path = _write(text)
        try:
            series, _ = load(path, "+2")
            self.assertEqual(series[0].ts.hour, 8)
        finally:
            os.unlink(path)

    def test_duplicates_are_dropped(self):
        row = "2024-01-02 08:00:00,2050,2051,2049,2050,100\n"
        text = "timestamp,open,high,low,close,volume\n" + row * 3
        path = _write(text)
        try:
            series, report = load(path, "utc")
            self.assertEqual(len(series), 1)
            self.assertEqual(report.duplicates_dropped, 2)
        finally:
            os.unlink(path)

    def test_impossible_ohlc_is_rejected(self):
        """A single bad row propagates into a false ATR and a wrong lot size."""
        text = ("timestamp,open,high,low,close,volume\n"
                "2024-01-02 08:00:00,2050,2051,2049,2050,100\n"
                "2024-01-02 08:05:00,2050,2040,2060,2050,100\n"   # high < low
                "2024-01-02 08:10:00,2050,2051,2049,2999,100\n")  # close outside
        path = _write(text)
        try:
            series, report = load(path, "utc")
            self.assertEqual(len(series), 1)
            self.assertEqual(report.invalid_dropped, 2)
        finally:
            os.unlink(path)

    def test_missing_ohlc_column_raises_with_the_header(self):
        path = _write("timestamp,open,high,volume\n2024-01-02 08:00:00,1,2,5\n")
        try:
            with self.assertRaises(HistoryError) as ctx:
                load(path, "utc")
            self.assertIn("'low'", str(ctx.exception))
        finally:
            os.unlink(path)

    def test_empty_file_raises(self):
        path = _write("")
        try:
            with self.assertRaises(HistoryError):
                load(path, "utc")
        finally:
            os.unlink(path)

    def test_missing_file_raises(self):
        with self.assertRaises(HistoryError):
            load("/nonexistent/xauusd.csv", "utc")

    def test_date_range_filter(self):
        text = ("timestamp,open,high,low,close,volume\n"
                + _bars(2000, datetime(2024, 1, 2, 8, 0), "%Y-%m-%d %H:%M:%S"))
        path = _write(text)
        try:
            series, _ = load(path, "utc",
                             start=datetime(2024, 1, 3, tzinfo=UTC),
                             end=datetime(2024, 1, 5, tzinfo=UTC))
            for c in series:
                self.assertGreaterEqual(c.ts, datetime(2024, 1, 3, tzinfo=UTC))
                self.assertLessEqual(c.ts, datetime(2024, 1, 5, tzinfo=UTC))
        finally:
            os.unlink(path)


class TestValidation(unittest.TestCase):
    def test_wrong_timezone_is_flagged_by_the_volatility_profile(self):
        """The check that catches the error nothing else can see.

        Gold's most volatile hours are the London/NY overlap. Build a file
        whose ranges peak at 12:00-16:00 in its own local time, then load it
        claiming a 10-hour offset -- the peak lands at 02:00 UTC, which is
        impossible for gold, and the loader must say so.
        """
        rows = ["timestamp,open,high,low,close,volume"]
        ts = datetime(2024, 1, 2, 0, 0)
        for _ in range(3000):
            if ts.weekday() == 5:
                ts += timedelta(hours=1)
                continue
            wide = 12 <= ts.hour <= 16
            rng = 4.0 if wide else 0.3
            o = 2050.0
            rows.append(f"{ts:%Y-%m-%d %H:%M:%S},{o:.2f},{o + rng:.2f},"
                        f"{o - rng:.2f},{o:.2f},100")
            ts += timedelta(minutes=5)
        path = _write("\n".join(rows))
        try:
            _, good = load(path, "utc")
            self.assertFalse(any("timezone" in w for w in good.warnings),
                             good.warnings)

            _, bad = load(path, "+10")
            self.assertTrue(any("looks wrong" in w for w in bad.warnings),
                            bad.warnings)
        finally:
            os.unlink(path)

    def test_weekend_bars_are_flagged(self):
        rows = ["timestamp,open,high,low,close,volume"]
        # A Saturday in 2024.
        ts = datetime(2024, 1, 6, 0, 0)
        for _ in range(400):
            rows.append(f"{ts:%Y-%m-%d %H:%M:%S},2050,2051,2049,2050,100")
            ts += timedelta(minutes=5)
        path = _write("\n".join(rows))
        try:
            _, report = load(path, "utc")
            self.assertTrue(any("Saturday" in w for w in report.warnings),
                            report.warnings)
        finally:
            os.unlink(path)

    def test_absurd_jumps_are_flagged(self):
        rows = ["timestamp,open,high,low,close,volume"]
        ts = datetime(2024, 1, 2, 8, 0)
        for i in range(300):
            price = 2050.0 if i != 150 else 20500.0   # decimal error
            rows.append(f"{ts:%Y-%m-%d %H:%M:%S},{price},{price + 1},"
                        f"{price - 1},{price},100")
            ts += timedelta(minutes=5)
        path = _write("\n".join(rows))
        try:
            _, report = load(path, "utc")
            self.assertTrue(any("bad tick or a decimal error" in w
                                for w in report.warnings), report.warnings)
        finally:
            os.unlink(path)

    def test_report_renders(self):
        text = ("timestamp,open,high,low,close,volume\n"
                + _bars(400, datetime(2024, 1, 2, 8, 0), "%Y-%m-%d %H:%M:%S"))
        path = _write(text)
        try:
            _, report = load(path, "utc")
            out = report.render()
            self.assertIn("HISTORY LOAD REPORT", out)
            self.assertIn("source timezone", out)
            self.assertTrue(report.usable)
        finally:
            os.unlink(path)


class TestResampleAndExport(unittest.TestCase):
    def test_m1_to_m5(self):
        text = ("timestamp,open,high,low,close,volume\n"
                + _bars(600, datetime(2024, 1, 2, 8, 0), "%Y-%m-%d %H:%M:%S",
                        step_min=1))
        path = _write(text)
        try:
            m1, _ = load(path, "utc", timeframe="1m")
            m5 = resample(m1, "5m")
            self.assertEqual(m5.timeframe, "5m")
            self.assertLess(len(m5), len(m1))
            self.assertGreater(len(m5), len(m1) / 6)
        finally:
            os.unlink(path)

    def test_round_trip_through_csv(self):
        text = ("timestamp,open,high,low,close,volume\n"
                + _bars(300, datetime(2024, 1, 2, 8, 0), "%Y-%m-%d %H:%M:%S"))
        path = _write(text)
        out = path.replace(".csv", "_norm.csv")
        try:
            original, _ = load(path, "utc")
            to_csv(original, out)
            reloaded, _ = load(out, "utc")
            self.assertEqual(len(original), len(reloaded))
            self.assertEqual(original[0].ts, reloaded[0].ts)
            self.assertAlmostEqual(original.last.close, reloaded.last.close, 3)
        finally:
            os.unlink(path)
            if os.path.exists(out):
                os.unlink(out)


class TestBacktestOnLoadedData(unittest.TestCase):
    def test_a_loaded_file_runs_through_the_backtest(self):
        """End to end: file on disk -> loader -> backtest engine."""
        from metals.backtest import BacktestConfig, run

        text = ("timestamp,open,high,low,close,volume\n"
                + _bars(3000, datetime(2024, 1, 2, 0, 0), "%Y-%m-%d %H:%M:%S"))
        path = _write(text)
        try:
            series, _ = load(path, "utc")
            result = run(series, BacktestConfig(), data_source="test file")
            self.assertGreater(result.bars_tested, 0)
            self.assertIsInstance(result.trades, list)
        finally:
            os.unlink(path)


class TestOffsetTable(unittest.TestCase):
    def test_documented_offsets(self):
        self.assertEqual(KNOWN_OFFSETS["utc"], 0.0)
        self.assertEqual(KNOWN_OFFSETS["us_eastern_no_dst"], -5.0)
        self.assertEqual(KNOWN_OFFSETS["broker_gmt3"], 3.0)


if __name__ == "__main__":
    unittest.main()
