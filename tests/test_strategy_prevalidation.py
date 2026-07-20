from __future__ import annotations

from unittest import TestCase

from ashare_data.strategy_prevalidation import _build_validation_record


class StrategyPrevalidationTest(TestCase):
    def test_builds_cacheable_record_from_best_walk_forward_strategy(self):
        aggregate = {
            "robustness": {"status": "stable", "label": "跨窗口稳定"},
            "average_return_pct": 3.2,
        }
        evaluation = {
            "status": "ok",
            "bars": 320,
            "data_start_date": "2025-01-01",
            "data_end_date": "2026-07-17",
            "window_count": 3,
            "strategies": [
                {
                    "key": "trend_follow",
                    "name": "趋势跟随",
                    "aggregate": aggregate,
                }
            ],
        }

        record = _build_validation_record("600000", evaluation)

        self.assertEqual(record["validation_status"], "ok")
        self.assertEqual(record["best_strategy_key"], "trend_follow")
        self.assertEqual(record["robustness"]["status"], "stable")
        self.assertEqual(record["data_end_date"], "2026-07-17")

    def test_preserves_insufficient_data_as_watchable_cache_record(self):
        record = _build_validation_record(
            "000001",
            {
                "status": "insufficient_data",
                "bars": 120,
                "required_bars": 260,
            },
        )

        self.assertEqual(record["validation_status"], "insufficient_data")
        self.assertEqual(record["stock_code"], "000001")
        self.assertEqual(record["required_bars"], 260)
