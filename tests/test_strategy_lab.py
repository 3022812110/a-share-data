from __future__ import annotations

import math
from unittest import TestCase

import pandas as pd

from ashare_data.strategy_lab import evaluate_strategy_lab, evaluate_strategy_walk_forward, simulate_signals


def _frame_from_prices(open_prices, close_prices, *, volumes=None):
    index = pd.bdate_range("2024-01-02", periods=len(close_prices))
    volume_values = volumes or [1_000_000] * len(close_prices)
    return pd.DataFrame(
        {
            "open": open_prices,
            "high": [max(open_price, close_price) * 1.01 for open_price, close_price in zip(open_prices, close_prices)],
            "low": [min(open_price, close_price) * 0.99 for open_price, close_price in zip(open_prices, close_prices)],
            "close": close_prices,
            "volume": volume_values,
        },
        index=index,
    )


class StrategyExecutionModelTest(TestCase):
    def test_signal_is_executed_at_next_open_with_costs(self):
        frame = _frame_from_prices([10.0] * 12, [10.0] * 12)
        entries = pd.Series(False, index=frame.index)
        exits = pd.Series(False, index=frame.index)
        entries.iloc[2] = True
        exits.iloc[5] = True

        result = simulate_signals(
            frame,
            entries,
            exits,
            stock_code="600000",
            initial_cash=100000,
            max_position_pct=0.30,
            stop_loss_pct=50,
            take_profit_pct=50,
            max_holding_days=30,
        )

        self.assertEqual(result["closed_trades"], 1)
        trade = result["trades"][0]
        self.assertEqual(trade["entry_date"], frame.index[3].strftime("%Y-%m-%d"))
        self.assertEqual(trade["exit_date"], frame.index[6].strftime("%Y-%m-%d"))
        self.assertGreater(trade["entry_price"], 10.0)
        self.assertLess(trade["exit_price"], 10.0)
        self.assertGreater(result["fee_total"], 0)
        self.assertLess(result["strategy_return_pct"], 0)

    def test_limit_up_open_blocks_buy(self):
        opens = [10.0] * 10
        closes = [10.0] * 10
        opens[3] = 11.0
        closes[3] = 11.0
        frame = _frame_from_prices(opens, closes)
        entries = pd.Series(False, index=frame.index)
        exits = pd.Series(False, index=frame.index)
        entries.iloc[2] = True

        result = simulate_signals(
            frame,
            entries,
            exits,
            stock_code="600000",
            initial_cash=100000,
        )

        self.assertEqual(result["closed_trades"], 0)
        self.assertEqual(result["blocked_orders"], 1)
        self.assertEqual(result["exposure_pct"], 0)


class StrategyLabEvaluationTest(TestCase):
    def test_reports_three_strategies_with_chronological_holdout(self):
        count = 320
        closes = [10 + index * 0.025 + math.sin(index / 5) * 0.45 for index in range(count)]
        opens = [closes[0], *[closes[index - 1] * (1 + math.sin(index / 11) * 0.002) for index in range(1, count)]]
        volumes = [1_000_000 + (index % 17) * 80_000 for index in range(count)]
        frame = _frame_from_prices(opens, closes, volumes=volumes)

        result = evaluate_strategy_lab(
            frame,
            stock_code="600000",
            initial_cash=100000,
            max_position_pct=0.30,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["strategies"]), 3)
        self.assertEqual(result["training_bars"], 224)
        self.assertEqual(result["split_date"], frame.index[224].strftime("%Y-%m-%d"))
        self.assertIn("前70%", result["validation_method"])
        self.assertIn("下一交易日开盘", result["execution_model"])
        for strategy in result["strategies"]:
            self.assertIn("selected_params", strategy)
            self.assertIn("in_sample", strategy)
            self.assertIn("out_of_sample", strategy)
            self.assertIn(strategy["robustness"]["status"], {"stable", "observe", "reject", "insufficient"})

    def test_rejects_short_history(self):
        frame = _frame_from_prices([10.0] * 100, [10.0] * 100)

        result = evaluate_strategy_lab(frame, stock_code="600000")

        self.assertEqual(result["status"], "insufficient_data")
        self.assertEqual(result["required_bars"], 220)


class StrategyWalkForwardTest(TestCase):
    def test_uses_multiple_rolling_windows_and_keeps_latest_period(self):
        count = 340
        closes = [10 + index * 0.02 + math.sin(index / 6) * 0.55 for index in range(count)]
        opens = [closes[0], *[closes[index - 1] * (1 + math.sin(index / 9) * 0.002) for index in range(1, count)]]
        volumes = [900_000 + (index % 13) * 90_000 for index in range(count)]
        frame = _frame_from_prices(opens, closes, volumes=volumes)
        market_frame = pd.DataFrame(
            {"close": [3000 * (1.002 ** index) for index in range(count)]},
            index=frame.index,
        )

        result = evaluate_strategy_walk_forward(frame, stock_code="600000", market_frame=market_frame)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["window_count"], 3)
        self.assertEqual(result["strategies"][0]["aggregate"]["window_count"], 3)
        self.assertEqual(len(result["strategies"]), 3)
        for strategy in result["strategies"]:
            self.assertEqual(len(strategy["windows"]), 3)
            self.assertEqual(strategy["windows"][-1]["test_end_date"], frame.index[-1].strftime("%Y-%m-%d"))
            self.assertEqual(strategy["aggregate"]["best_market_regime"], "上涨")
            self.assertEqual(strategy["aggregate"]["by_market_regime"][0]["market_regime"], "上涨")
            self.assertIn(strategy["aggregate"]["robustness"]["status"], {"stable", "observe", "reject", "insufficient"})

    def test_requires_two_out_of_sample_windows(self):
        count = 259
        closes = [10 + index * 0.01 for index in range(count)]
        frame = _frame_from_prices(closes, closes)

        result = evaluate_strategy_walk_forward(frame, stock_code="600000")

        self.assertEqual(result["status"], "insufficient_data")
        self.assertEqual(result["required_bars"], 260)
        self.assertEqual(result["window_count"], 1)
