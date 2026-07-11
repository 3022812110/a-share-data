from __future__ import annotations

from unittest import TestCase
from unittest.mock import Mock, patch

from ashare_data.eastmoney_kline import fetch_tencent_stock_kline


class TencentKlineFallbackTest(TestCase):
    def test_parses_adjusted_daily_bars_and_calculates_change(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "code": 0,
            "msg": "",
            "data": {
                "sz300065": {
                    "qfqday": [
                        ["2026-07-09", "23.00", "23.99", "24.20", "22.80", "1000"],
                        ["2026-07-10", "23.57", "28.79", "28.79", "23.32", "1200"],
                    ]
                }
            },
        }

        with patch("ashare_data.eastmoney_kline._SESSION.get", return_value=response):
            result = fetch_tencent_stock_kline("300065", limit=50)

        self.assertEqual(result["source"], "tencent")
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["latest"]["time"], "2026-07-10")
        self.assertAlmostEqual(result["latest"]["change_pct"], 20.0083, places=3)
