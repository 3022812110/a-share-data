from __future__ import annotations

from unittest import TestCase

from ashare_data.trade_risk import build_market_risk_context, build_portfolio_risk_diagnosis, evaluate_buy_order_risk


def _market_row(**overrides):
    row = {
        "stock_count": 5200,
        "rising_count": 2800,
        "falling_count": 2200,
        "limit_up_count": 45,
        "limit_down_count": 8,
        "turnover_yi": 13000,
        "latest_trade_time": "2026-07-17 15:00:00",
        "latest_fetch": "2026-07-17T07:01:00Z",
    }
    row.update(overrides)
    return row


class MarketRiskContextTest(TestCase):
    def test_extreme_market_blocks_new_positions(self):
        context = build_market_risk_context(
            _market_row(
                rising_count=405,
                falling_count=4757,
                limit_up_count=12,
                limit_down_count=635,
            ),
            expected_trade_date="2026-07-17",
        )

        self.assertEqual(context["regime"], "极弱")
        self.assertFalse(context["trade_gate"]["allow_new_positions"])
        self.assertEqual(context["trade_gate"]["max_total_position_pct"], 0)

    def test_stale_snapshot_blocks_new_positions(self):
        context = build_market_risk_context(
            _market_row(latest_trade_time="2026-07-16 15:00:00"),
            expected_trade_date="2026-07-17",
        )

        self.assertEqual(context["regime"], "数据异常")
        self.assertFalse(context["trade_gate"]["allow_new_positions"])
        self.assertIn("行情日期", context["trade_gate"]["reasons"][0])

    def test_weak_market_limits_total_and_single_position(self):
        context = build_market_risk_context(
            _market_row(
                rising_count=1900,
                falling_count=3100,
                limit_up_count=18,
                limit_down_count=25,
            ),
            expected_trade_date="2026-07-17",
        )

        self.assertEqual(context["regime"], "偏弱")
        self.assertTrue(context["trade_gate"]["allow_new_positions"])
        self.assertEqual(context["trade_gate"]["max_total_position_pct"], 10)
        self.assertEqual(context["trade_gate"]["max_single_position_pct"], 5)


class BuyOrderRiskTest(TestCase):
    def test_rejects_order_above_total_position_limit(self):
        market_context = build_market_risk_context(
            _market_row(),
            expected_trade_date="2026-07-17",
        )
        result = evaluate_buy_order_risk(
            market_context=market_context,
            total_assets=20000,
            current_market_value=6500,
            current_stock_value=0,
            order_cash=1000,
        )

        self.assertFalse(result["allowed"])
        self.assertTrue(any("总仓位" in reason for reason in result["reasons"]))

    def test_rejects_order_when_daily_loss_circuit_breaker_trips(self):
        market_context = build_market_risk_context(
            _market_row(rising_count=3600, falling_count=1400, limit_up_count=80, limit_down_count=5),
            expected_trade_date="2026-07-17",
        )
        result = evaluate_buy_order_risk(
            market_context=market_context,
            total_assets=20000,
            current_market_value=0,
            current_stock_value=0,
            order_cash=1000,
            daily_pnl=-450,
        )

        self.assertFalse(result["allowed"])
        self.assertTrue(any("单日亏损熔断" in reason for reason in result["reasons"]))


class PortfolioRiskDiagnosisTest(TestCase):
    def test_extreme_market_with_positions_returns_only_reduce_conclusion(self):
        market_context = build_market_risk_context(
            _market_row(rising_count=405, falling_count=4757, limit_up_count=12, limit_down_count=635),
            expected_trade_date="2026-07-17",
        )
        result = build_portfolio_risk_diagnosis(
            account={"total_assets": 20000, "market_value": 10000, "daily_return_pct": -0.5, "drawdown_pct": -1},
            positions=[{"stock_code": "000001", "stock_name": "示例", "market_value": 10000, "current_price": 10}],
            market_context=market_context,
        )

        self.assertEqual(result["label"], "只减不加")
        self.assertTrue(result["needs_action"])

    def test_stop_loss_breach_is_listed_as_urgent_position_action(self):
        market_context = build_market_risk_context(
            _market_row(rising_count=3600, falling_count=1400, limit_up_count=80, limit_down_count=5),
            expected_trade_date="2026-07-17",
        )
        result = build_portfolio_risk_diagnosis(
            account={"total_assets": 20000, "market_value": 2000, "daily_return_pct": -0.2, "drawdown_pct": -1},
            positions=[{
                "stock_code": "000001",
                "stock_name": "示例",
                "market_value": 2000,
                "current_price": 9.5,
                "stop_loss_price": 10,
            }],
            market_context=market_context,
        )

        self.assertEqual(result["level"], "high")
        self.assertEqual(result["position_actions"][0]["action"], "review_reduce")
