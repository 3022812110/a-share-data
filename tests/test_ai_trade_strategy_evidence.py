from __future__ import annotations

from unittest import TestCase

from ashare_data.ai_trade import _build_candidate_strategy_evidence, _build_recommendation_item


def _stability_result(*, status="stable", strategy_key="trend_follow", regime="上涨", avg_return=4.0, avg_excess=1.5):
    return {
        "status": "ok",
        "run_id": 7,
        "ranking": [
            {
                "stock_code": "600000",
                "best_strategy_key": strategy_key,
                "best_strategy_name": "趋势跟随" if strategy_key == "trend_follow" else "超跌修复",
                "robustness": {"status": status, "label": "跨窗口稳定" if status == "stable" else "跨窗口观察"},
                "aggregate": {
                    "average_return_pct": avg_return,
                    "average_excess_return_pct": avg_excess,
                    "positive_window_pct": 66.67,
                    "worst_drawdown_pct": -6.0,
                    "by_market_regime": [
                        {
                            "market_regime": regime,
                            "total_trades": 4,
                            "average_return_pct": avg_return,
                            "average_excess_return_pct": avg_excess,
                        }
                    ],
                },
            }
        ],
    }


class StrategyEvidenceGateTest(TestCase):
    def test_stable_strategy_matching_current_regime_supports_candidate(self):
        evidence = _build_candidate_strategy_evidence(
            "600000",
            stability_result=_stability_result(),
            current_market_regime="偏强",
        )

        self.assertEqual(evidence["action"], "support")
        self.assertGreater(evidence["score_adjustment"], 0)
        self.assertTrue(evidence["market_regime_match"])

    def test_market_regime_mismatch_blocks_otherwise_stable_strategy(self):
        evidence = _build_candidate_strategy_evidence(
            "600000",
            stability_result=_stability_result(),
            current_market_regime="震荡",
        )

        self.assertEqual(evidence["action"], "block")
        self.assertFalse(evidence["market_regime_match"])

    def test_observe_strategy_is_penalized(self):
        evidence = _build_candidate_strategy_evidence(
            "600000",
            stability_result=_stability_result(status="observe"),
            current_market_regime="偏强",
        )

        self.assertEqual(evidence["action"], "caution")
        self.assertLess(evidence["score_adjustment"], 0)
        self.assertLess(evidence["position_multiplier"], 1)

    def test_rejected_strategy_is_blocked(self):
        evidence = _build_candidate_strategy_evidence(
            "600000",
            stability_result=_stability_result(status="reject"),
            current_market_regime="偏强",
        )

        self.assertEqual(evidence["action"], "block")
        self.assertEqual(evidence["position_multiplier"], 0)

    def test_uncovered_candidate_cannot_claim_strategy_support(self):
        evidence = _build_candidate_strategy_evidence(
            "000001",
            stability_result=_stability_result(),
            current_market_regime="偏强",
        )

        self.assertEqual(evidence["action"], "untested")
        self.assertEqual(evidence["label"], "策略未验证")

    def test_insufficient_prevalidation_stays_watchable_instead_of_claiming_mismatch(self):
        evidence = _build_candidate_strategy_evidence(
            "000001",
            stability_result={
                "status": "ok",
                "ranking": [
                    {
                        "stock_code": "000001",
                        "validation_id": 11,
                        "validation_status": "insufficient_data",
                        "robustness": {"status": "insufficient", "label": "样本不足"},
                        "aggregate": {},
                    }
                ],
            },
            current_market_regime="震荡",
        )

        self.assertEqual(evidence["action"], "caution")
        self.assertIsNone(evidence["market_regime_match"])

    def test_unverified_candidate_is_watch_only(self):
        item = _build_recommendation_item(
            {
                "stock_code": "000001",
                "market": "SZ",
                "stock_name": "示例",
                "price": 10,
                "change_pct": 3,
                "turnover_ratio": 5,
                "volume_ratio": 1.5,
                "amount": 200000,
                "score": 80,
                "theme_tags": ["活跃股"],
                "strategy_evidence": {"action": "untested", "reason": "尚未验证"},
            },
            quantity=100,
            market_context={"regime": "震荡", "rising_ratio": 50},
            topic_context={},
            total_assets=100000,
        )

        self.assertEqual(item["action"], "watch")
        self.assertEqual(item["recommended_quantity"], 0)
        self.assertEqual(item["estimated_cash"], 0)
        self.assertEqual(item["confidence"], "低")

    def test_supported_candidate_keeps_buy_plan(self):
        item = _build_recommendation_item(
            {
                "stock_code": "600000",
                "market": "SH",
                "stock_name": "示例",
                "price": 10,
                "change_pct": 3,
                "turnover_ratio": 5,
                "volume_ratio": 1.5,
                "amount": 200000,
                "score": 100,
                "theme_tags": ["活跃股"],
                "strategy_evidence": {"action": "support", "reason": "证据通过"},
            },
            quantity=300,
            market_context={"regime": "偏强", "rising_ratio": 70},
            topic_context={},
            total_assets=100000,
        )

        self.assertEqual(item["action"], "buy")
        self.assertEqual(item["recommended_quantity"], 300)
        self.assertEqual(item["estimated_cash"], 3000)
