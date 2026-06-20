from __future__ import annotations

from datetime import datetime
from unittest import TestCase
from unittest.mock import patch
from zoneinfo import ZoneInfo

from ashare_data.market_clock import get_a_share_market_status


CHINA_TZ = ZoneInfo("Asia/Shanghai")


class MarketClockTest(TestCase):
    def status_at(self, value: str, *, trading_day: bool = True):
        current = datetime.fromisoformat(value).replace(tzinfo=CHINA_TZ)
        row = {"trade_status": 1 if trading_day else 0}
        with (
            patch("ashare_data.market_clock._calendar_has_date", return_value=True),
            patch("ashare_data.market_clock._calendar_row", return_value=row),
            patch("ashare_data.market_clock._find_next_open", return_value="2026-06-22 09:30:00"),
        ):
            return get_a_share_market_status(current)

    def test_morning_session_is_open(self):
        status = self.status_at("2026-06-18T10:00:00")
        self.assertTrue(status["is_open"])
        self.assertEqual(status["session"], "morning")

    def test_lunch_break_is_closed(self):
        status = self.status_at("2026-06-18T12:00:00")
        self.assertFalse(status["is_open"])
        self.assertEqual(status["session"], "lunch_break")

    def test_exchange_holiday_is_closed(self):
        status = self.status_at("2026-06-19T10:00:00", trading_day=False)
        self.assertFalse(status["is_open"])
        self.assertIn("休市日", status["reason"])

    def test_after_close_is_closed(self):
        status = self.status_at("2026-06-18T15:01:00")
        self.assertFalse(status["is_open"])
        self.assertEqual(status["session"], "closed")
