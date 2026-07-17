from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date
from unittest import TestCase
from unittest.mock import patch

from ashare_data.market_refresh_service import sync_tracked_snapshot_daily_bars


class SnapshotDailyBarAmountTest(TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE stock_market_snapshot (
                stock_code TEXT PRIMARY KEY,
                trade_time TEXT,
                open REAL,
                price REAL,
                high REAL,
                low REAL,
                volume REAL,
                amount REAL,
                change_pct REAL,
                change_amount REAL,
                turnover_ratio REAL,
                pre_close REAL,
                source TEXT,
                fetched_at TEXT
            );
            CREATE TABLE daily_bars (
                stock_code TEXT NOT NULL,
                trade_time TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                open REAL,
                close REAL,
                high REAL,
                low REAL,
                volume REAL,
                amount REAL,
                change_pct REAL,
                change REAL,
                turnover_ratio REAL,
                pre_close REAL,
                source TEXT NOT NULL,
                adjust_type INTEGER NOT NULL,
                k_type INTEGER NOT NULL,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (stock_code, trade_date, adjust_type, k_type)
            );
            """
        )
        self.connection.execute(
            """
            INSERT INTO stock_market_snapshot VALUES (
                '000988', '2026-07-17 15:00:00', 10, 11, 12, 9,
                1000, 768311, 1.2, 0.13, 2.5, 10.87, 'tencent', '2026-07-17T07:00:00Z'
            )
            """
        )

    def tearDown(self):
        self.connection.close()

    def test_tencent_amount_in_wan_is_stored_as_yuan_in_daily_bars(self):
        @contextmanager
        def connection_context():
            with self.connection:
                yield self.connection

        with (
            patch("ashare_data.market_refresh_service.get_connection", side_effect=connection_context),
            patch("ashare_data.market_refresh_service.expected_latest_trade_date", return_value=date(2026, 7, 17)),
        ):
            count = sync_tracked_snapshot_daily_bars(["000988"])

        row = self.connection.execute(
            "SELECT amount, source FROM daily_bars WHERE stock_code = '000988'"
        ).fetchone()
        self.assertEqual(count, 1)
        self.assertEqual(row["amount"], 7_683_110_000)
        self.assertEqual(row["source"], "market_snapshot_amount_wan_to_yuan")
