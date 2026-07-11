from __future__ import annotations

from datetime import datetime
from unittest import TestCase
from unittest.mock import patch
from zoneinfo import ZoneInfo

from ashare_data.data_health import expected_latest_trade_date


CHINA_TZ = ZoneInfo("Asia/Shanghai")


class ExpectedLatestTradeDateTest(TestCase):
    def test_weekend_uses_previous_calendar_trade_day(self):
        current = datetime(2026, 7, 11, 10, 0, tzinfo=CHINA_TZ)
        rows = [{"trade_date": "2026-07-10"}, {"trade_date": "2026-07-09"}]
        connection = _Connection(rows)
        with patch("ashare_data.data_health.get_connection", return_value=_Context(connection)):
            self.assertEqual(expected_latest_trade_date(current).isoformat(), "2026-07-10")

    def test_before_open_uses_previous_trade_day(self):
        current = datetime(2026, 7, 10, 8, 0, tzinfo=CHINA_TZ)
        rows = [{"trade_date": "2026-07-10"}, {"trade_date": "2026-07-09"}]
        connection = _Connection(rows)
        with patch("ashare_data.data_health.get_connection", return_value=_Context(connection)):
            self.assertEqual(expected_latest_trade_date(current).isoformat(), "2026-07-09")


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class _Connection:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, *_args, **_kwargs):
        return _Cursor(self.rows)


class _Context:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, *_args):
        return False
