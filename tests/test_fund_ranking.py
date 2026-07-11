from __future__ import annotations

from unittest import TestCase
from unittest.mock import Mock, patch

from ashare_data.market_feeds import _FUND_RANKING_CACHE, fetch_fund_ranking


class FundRankingTest(TestCase):
    def setUp(self):
        _FUND_RANKING_CACHE.clear()

    def test_maps_three_day_funds_and_opening_change(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "data": {
                "diff": [
                    {
                        "f12": "002185",
                        "f14": "华天科技",
                        "f2": 25.31,
                        "f3": 6.66,
                        "f8": 14.89,
                        "f17": 26.10,
                        "f18": 23.73,
                        "f267": 2871478960,
                        "f268": 7.54,
                    }
                ]
            }
        }

        with patch("ashare_data.market_feeds._SESSION.get", return_value=response):
            result = fetch_fund_ranking(period="3d", limit=20)

        self.assertEqual(result["source_days"], 3)
        self.assertEqual(result["items"][0]["stock_code"], "002185")
        self.assertAlmostEqual(result["items"][0]["net_inflow_yi"], 28.7147896)
        self.assertAlmostEqual(result["items"][0]["opening_pct"], 9.9873, places=3)

    def test_marks_thirteen_day_window_as_public_proxy(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"data": {"diff": []}}
        with patch("ashare_data.market_feeds._SESSION.get", return_value=response):
            result = fetch_fund_ranking(period="13d", limit=20)
        self.assertTrue(result["is_proxy"])
        self.assertEqual(result["source_days"], 10)
