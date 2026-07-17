from __future__ import annotations

import sqlite3
from unittest import TestCase

from ashare_data.recommendation_performance import _calibration_summary, calculate_forward_metrics, register_recommendation_items


class RecommendationPerformanceTest(TestCase):
    def test_calculates_forward_return_and_price_excursions(self):
        bars = [
            {"trade_date": "2026-07-20", "close": 11, "high": 11.5, "low": 9.5},
            {"trade_date": "2026-07-21", "close": 10.5, "high": 11.2, "low": 10},
            {"trade_date": "2026-07-22", "close": 12, "high": 12.5, "low": 10.2},
        ]

        metrics = calculate_forward_metrics(10, bars)

        self.assertEqual(metrics["1"]["return_pct"], 10)
        self.assertEqual(metrics["1"]["max_adverse_pct"], -5)
        self.assertEqual(metrics["3"]["return_pct"], 20)
        self.assertEqual(metrics["3"]["max_favorable_pct"], 25)

    def test_only_returns_horizons_with_enough_trading_days(self):
        bars = [{"trade_date": "2026-07-20", "close": 10.2, "high": 10.3, "low": 9.9}]

        metrics = calculate_forward_metrics(10, bars)

        self.assertIn("1", metrics)
        self.assertNotIn("3", metrics)

    def test_calibration_waits_for_twenty_five_day_samples(self):
        result = _calibration_summary({"sample_count": 19, "win_rate_pct": 80, "avg_return_pct": 10})

        self.assertEqual(result["status"], "collecting")

    def test_calibration_distinguishes_stable_and_tighten(self):
        stable = _calibration_summary({"sample_count": 20, "win_rate_pct": 60, "avg_return_pct": 2})
        tighten = _calibration_summary({"sample_count": 20, "win_rate_pct": 40, "avg_return_pct": -1})

        self.assertEqual(stable["status"], "stable")
        self.assertEqual(tighten["status"], "tighten")

    def test_registers_each_recommendation_as_a_trackable_item(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.execute(
            """
            CREATE TABLE ai_recommendation_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                account_id TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                recommendation_date TEXT NOT NULL,
                base_price REAL NOT NULL,
                score REAL,
                market_regime TEXT,
                policy_version TEXT NOT NULL,
                metrics_json TEXT NOT NULL DEFAULT '{}',
                evaluated_trade_days INTEGER NOT NULL DEFAULT 0,
                latest_evaluated_date TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(run_id, stock_code)
            )
            """
        )

        count = register_recommendation_items(
            connection,
            run_id=1,
            account_id="default",
            policy_version="test.v1",
            market_context={"latest_trade_time": "2026-07-17 15:00:00", "regime": "震荡"},
            recommendations=[{"stock_code": "000001", "stock_name": "示例", "price": 10, "score": 88}],
            created_at="2026-07-17T07:00:00Z",
        )
        row = connection.execute("SELECT * FROM ai_recommendation_items").fetchone()
        connection.close()

        self.assertEqual(count, 1)
        self.assertEqual(row["recommendation_date"], "2026-07-17")
        self.assertEqual(row["base_price"], 10)
