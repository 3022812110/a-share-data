from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime
from typing import Any, Mapping, Sequence

import pandas as pd

from .backtesting import ensure_daily_bars_for_backtest
from .db import get_connection, init_db
from .market_regime import classify_market_regime, ensure_market_index_history
from .watchlist import normalize_stock_code


COMMISSION_RATE = 0.0003
COMMISSION_MIN = 5.0
STAMP_DUTY_RATE = 0.0005
TRANSFER_FEE_RATE = 0.00001
SLIPPAGE_RATE = 0.0005
MIN_LAB_BARS = 220
DEFAULT_LOOKBACK_DAYS = 1600
WALK_FORWARD_TRAIN_BARS = 180
WALK_FORWARD_TEST_BARS = 40
WALK_FORWARD_MAX_WINDOWS = 3
MIN_WALK_FORWARD_BARS = WALK_FORWARD_TRAIN_BARS + WALK_FORWARD_TEST_BARS * 2
DEFAULT_STABILITY_STOCK_LIMIT = 8


STRATEGY_FAMILIES: tuple[dict[str, Any], ...] = (
    {
        "key": "trend_follow",
        "name": "趋势跟随",
        "description": "均线方向与中期动量同时确认后参与，趋势破坏时退出。",
        "variants": (
            {"fast": 10, "slow": 30, "momentum": 20, "stop_loss_pct": 8, "take_profit_pct": 25, "max_holding_days": 45},
            {"fast": 20, "slow": 60, "momentum": 20, "stop_loss_pct": 10, "take_profit_pct": 30, "max_holding_days": 60},
            {"fast": 20, "slow": 90, "momentum": 40, "stop_loss_pct": 10, "take_profit_pct": 35, "max_holding_days": 80},
        ),
    },
    {
        "key": "breakout",
        "name": "放量突破",
        "description": "突破前期高点且量能确认后参与，跌回趋势线时退出。",
        "variants": (
            {"lookback": 20, "volume_window": 20, "volume_ratio": 1.2, "exit_ma": 10, "stop_loss_pct": 7, "take_profit_pct": 22, "max_holding_days": 30},
            {"lookback": 40, "volume_window": 20, "volume_ratio": 1.1, "exit_ma": 20, "stop_loss_pct": 8, "take_profit_pct": 28, "max_holding_days": 45},
            {"lookback": 60, "volume_window": 30, "volume_ratio": 1.0, "exit_ma": 20, "stop_loss_pct": 10, "take_profit_pct": 35, "max_holding_days": 60},
        ),
    },
    {
        "key": "mean_reversion",
        "name": "超跌修复",
        "description": "只在中期趋势未完全破坏时参与短期超跌，恢复到均线后退出。",
        "variants": (
            {"rsi_period": 6, "entry_rsi": 22, "exit_rsi": 55, "trend_ma": 60, "trend_floor": 0.92, "stop_loss_pct": 6, "take_profit_pct": 12, "max_holding_days": 12},
            {"rsi_period": 9, "entry_rsi": 28, "exit_rsi": 58, "trend_ma": 60, "trend_floor": 0.90, "stop_loss_pct": 7, "take_profit_pct": 15, "max_holding_days": 15},
            {"rsi_period": 14, "entry_rsi": 32, "exit_rsi": 60, "trend_ma": 120, "trend_floor": 0.88, "stop_loss_pct": 8, "take_profit_pct": 18, "max_holding_days": 20},
        ),
    },
)


def _utc_now_str() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    prepared = frame.copy()
    if not isinstance(prepared.index, pd.DatetimeIndex):
        if "trade_date" not in prepared.columns:
            raise ValueError("strategy frame requires a DatetimeIndex or trade_date column")
        prepared["trade_date"] = pd.to_datetime(prepared["trade_date"])
        prepared = prepared.set_index("trade_date")
    prepared = prepared.sort_index()
    for column in ("open", "high", "low", "close", "volume"):
        if column not in prepared.columns:
            raise ValueError(f"strategy frame missing required column: {column}")
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    prepared = prepared.dropna(subset=["open", "high", "low", "close"])
    prepared = prepared[~prepared.index.duplicated(keep="last")]
    return prepared


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).rolling(period, min_periods=period).mean()
    relative_strength = gain / loss.replace(0, float("nan"))
    result = 100 - (100 / (1 + relative_strength))
    result = result.where(loss > 0, 100.0)
    return result.fillna(50.0)


def build_strategy_signals(
    frame: pd.DataFrame,
    strategy_key: str,
    params: Mapping[str, Any],
) -> tuple[pd.Series, pd.Series]:
    prepared = _prepare_frame(frame)
    close = prepared["close"]
    volume = prepared["volume"].fillna(0)

    if strategy_key == "trend_follow":
        fast = close.rolling(int(params["fast"]), min_periods=int(params["fast"])).mean()
        slow = close.rolling(int(params["slow"]), min_periods=int(params["slow"])).mean()
        momentum = close.pct_change(int(params["momentum"]))
        entry = (fast > slow) & (close > fast) & (momentum > 0)
        exit_signal = (close < fast) | (fast < slow)
    elif strategy_key == "breakout":
        lookback = int(params["lookback"])
        volume_window = int(params["volume_window"])
        previous_high = close.rolling(lookback, min_periods=lookback).max().shift(1)
        average_volume = volume.rolling(volume_window, min_periods=volume_window).mean().shift(1)
        exit_average = close.rolling(int(params["exit_ma"]), min_periods=int(params["exit_ma"])).mean()
        entry = (close > previous_high) & (volume >= average_volume * float(params["volume_ratio"]))
        exit_signal = close < exit_average
    elif strategy_key == "mean_reversion":
        rsi = _rsi(close, int(params["rsi_period"]))
        trend_average = close.rolling(int(params["trend_ma"]), min_periods=int(params["trend_ma"])).mean()
        entry = (rsi <= float(params["entry_rsi"])) & (close >= trend_average * float(params["trend_floor"]))
        exit_signal = (rsi >= float(params["exit_rsi"])) | (close >= trend_average)
    else:
        raise ValueError(f"unsupported strategy: {strategy_key}")

    return entry.fillna(False).astype(bool), exit_signal.fillna(False).astype(bool)


def _limit_ratio(stock_code: str) -> float:
    code = normalize_stock_code(stock_code)
    if code.startswith(("300", "301", "688")):
        return 0.20
    if code.startswith(("4", "8", "9")):
        return 0.30
    return 0.10


def _buy_fees(gross_amount: float) -> float:
    return max(COMMISSION_MIN, gross_amount * COMMISSION_RATE) + gross_amount * TRANSFER_FEE_RATE


def _sell_fees(gross_amount: float) -> float:
    return (
        max(COMMISSION_MIN, gross_amount * COMMISSION_RATE)
        + gross_amount * STAMP_DUTY_RATE
        + gross_amount * TRANSFER_FEE_RATE
    )


def _drawdown_pct(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    series = pd.Series(values, dtype=float)
    peaks = series.cummax().replace(0, float("nan"))
    drawdowns = (series / peaks - 1) * 100
    return round(float(drawdowns.min() or 0), 2)


def _performance_metrics(
    *,
    initial_cash: float,
    equity_values: Sequence[float],
    trades: Sequence[Mapping[str, Any]],
    fee_total: float,
    exposure_bars: int,
    total_bars: int,
    blocked_orders: int,
) -> dict[str, Any]:
    final_value = float(equity_values[-1]) if equity_values else float(initial_cash)
    strategy_return_pct = ((final_value / initial_cash) - 1) * 100 if initial_cash else 0.0
    periods = max(1, len(equity_values) - 1)
    annualized_return_pct = ((final_value / initial_cash) ** (252 / periods) - 1) * 100 if initial_cash > 0 and final_value > 0 else 0.0
    returns = pd.Series(equity_values, dtype=float).pct_change().dropna()
    volatility = float(returns.std(ddof=0) * math.sqrt(252) * 100) if len(returns) > 1 else 0.0
    sharpe = float((returns.mean() / returns.std(ddof=0)) * math.sqrt(252)) if len(returns) > 1 and returns.std(ddof=0) > 0 else 0.0
    wins = [float(item["pnl"]) for item in trades if float(item["pnl"]) > 0]
    losses = [float(item["pnl"]) for item in trades if float(item["pnl"]) < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "initial_cash": round(float(initial_cash), 2),
        "final_value": round(final_value, 2),
        "strategy_return_pct": round(strategy_return_pct, 2),
        "annualized_return_pct": round(annualized_return_pct, 2),
        "max_drawdown_pct": _drawdown_pct(equity_values),
        "annualized_volatility_pct": round(volatility, 2),
        "sharpe_ratio": round(sharpe, 2),
        "closed_trades": len(trades),
        "won_trades": len(wins),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 2) if trades else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else None,
        "fee_total": round(float(fee_total), 2),
        "exposure_pct": round(exposure_bars / max(1, total_bars) * 100, 2),
        "blocked_orders": int(blocked_orders),
        "trades": list(trades)[-12:],
    }


def simulate_signals(
    frame: pd.DataFrame,
    entry_signal: pd.Series,
    exit_signal: pd.Series,
    *,
    stock_code: str,
    initial_cash: float = 100000.0,
    max_position_pct: float = 0.30,
    stop_loss_pct: float = 8.0,
    take_profit_pct: float = 25.0,
    max_holding_days: int = 45,
    evaluation_start: int = 1,
) -> dict[str, Any]:
    prepared = _prepare_frame(frame)
    if len(prepared) < 2:
        return _performance_metrics(
            initial_cash=initial_cash,
            equity_values=[initial_cash],
            trades=[],
            fee_total=0,
            exposure_bars=0,
            total_bars=len(prepared),
            blocked_orders=0,
        )
    if initial_cash <= 0:
        raise ValueError("initial_cash must be greater than 0")
    if not 0 < max_position_pct <= 1:
        raise ValueError("max_position_pct must be in (0, 1]")

    entry = entry_signal.reindex(prepared.index, fill_value=False).astype(bool)
    exit_rule = exit_signal.reindex(prepared.index, fill_value=False).astype(bool)
    start = max(1, min(int(evaluation_start), len(prepared) - 1))
    cash = float(initial_cash)
    quantity = 0
    entry_price = 0.0
    entry_cost = 0.0
    entry_index: int | None = None
    entry_date: str | None = None
    pending_action = "buy" if bool(entry.iloc[start - 1]) else None
    pending_reason = "strategy_entry" if pending_action else None
    fee_total = 0.0
    blocked_orders = 0
    exposure_bars = 0
    trades: list[dict[str, Any]] = []
    equity_values: list[float] = []
    limit_ratio = _limit_ratio(stock_code)

    for index in range(start, len(prepared)):
        row = prepared.iloc[index]
        previous_row = prepared.iloc[index - 1]
        open_price = float(row["open"])
        close_price = float(row["close"])
        previous_close = float(previous_row["close"])

        if pending_action == "buy" and quantity == 0:
            pending_action = None
            pending_reason = None
            if open_price >= previous_close * (1 + limit_ratio - 0.001):
                blocked_orders += 1
            else:
                execution_price = open_price * (1 + SLIPPAGE_RATE)
                budget = cash * max_position_pct
                quantity_to_buy = int(budget // (execution_price * 100)) * 100
                while quantity_to_buy > 0:
                    gross_amount = execution_price * quantity_to_buy
                    fees = _buy_fees(gross_amount)
                    if gross_amount + fees <= cash:
                        break
                    quantity_to_buy -= 100
                if quantity_to_buy > 0:
                    gross_amount = execution_price * quantity_to_buy
                    fees = _buy_fees(gross_amount)
                    cash -= gross_amount + fees
                    fee_total += fees
                    quantity = quantity_to_buy
                    entry_price = execution_price
                    entry_cost = gross_amount + fees
                    entry_index = index
                    entry_date = prepared.index[index].strftime("%Y-%m-%d")
        elif pending_action == "sell" and quantity > 0:
            if open_price <= previous_close * (1 - limit_ratio + 0.001):
                blocked_orders += 1
            else:
                execution_price = open_price * (1 - SLIPPAGE_RATE)
                gross_amount = execution_price * quantity
                fees = _sell_fees(gross_amount)
                proceeds = gross_amount - fees
                pnl = proceeds - entry_cost
                fee_total += fees
                cash += proceeds
                trades.append(
                    {
                        "entry_date": entry_date,
                        "exit_date": prepared.index[index].strftime("%Y-%m-%d"),
                        "entry_price": round(entry_price, 3),
                        "exit_price": round(execution_price, 3),
                        "quantity": quantity,
                        "holding_days": index - int(entry_index or index),
                        "pnl": round(pnl, 2),
                        "return_pct": round((proceeds / entry_cost - 1) * 100, 2) if entry_cost else 0.0,
                        "exit_reason": pending_reason or "strategy_exit",
                    }
                )
                quantity = 0
                entry_price = 0.0
                entry_cost = 0.0
                entry_index = None
                entry_date = None
                pending_action = None
                pending_reason = None

        if quantity > 0:
            exposure_bars += 1
        equity_values.append(cash + quantity * close_price)

        if quantity > 0 and pending_action != "sell":
            holding_days = index - int(entry_index or index)
            if close_price <= entry_price * (1 - stop_loss_pct / 100):
                pending_action = "sell"
                pending_reason = "stop_loss"
            elif close_price >= entry_price * (1 + take_profit_pct / 100):
                pending_action = "sell"
                pending_reason = "take_profit"
            elif bool(exit_rule.iloc[index]):
                pending_action = "sell"
                pending_reason = "strategy_exit"
            elif holding_days >= int(max_holding_days):
                pending_action = "sell"
                pending_reason = "max_holding_days"
        elif quantity == 0 and pending_action is None and bool(entry.iloc[index]):
            pending_action = "buy"
            pending_reason = "strategy_entry"

    if quantity > 0:
        final_close = float(prepared.iloc[-1]["close"])
        execution_price = final_close * (1 - SLIPPAGE_RATE)
        gross_amount = execution_price * quantity
        fees = _sell_fees(gross_amount)
        proceeds = gross_amount - fees
        pnl = proceeds - entry_cost
        fee_total += fees
        cash += proceeds
        trades.append(
            {
                "entry_date": entry_date,
                "exit_date": prepared.index[-1].strftime("%Y-%m-%d"),
                "entry_price": round(entry_price, 3),
                "exit_price": round(execution_price, 3),
                "quantity": quantity,
                "holding_days": len(prepared) - 1 - int(entry_index or len(prepared) - 1),
                "pnl": round(pnl, 2),
                "return_pct": round((proceeds / entry_cost - 1) * 100, 2) if entry_cost else 0.0,
                "exit_reason": "end_of_test",
            }
        )
        equity_values[-1] = cash

    return _performance_metrics(
        initial_cash=initial_cash,
        equity_values=equity_values,
        trades=trades,
        fee_total=fee_total,
        exposure_bars=exposure_bars,
        total_bars=len(equity_values),
        blocked_orders=blocked_orders,
    )


def _benchmark_metrics(
    frame: pd.DataFrame,
    *,
    initial_cash: float,
    max_position_pct: float,
    evaluation_start: int,
) -> dict[str, Any]:
    prepared = _prepare_frame(frame)
    start = max(0, min(int(evaluation_start), len(prepared) - 1))
    start_price = float(prepared.iloc[start]["open"]) * (1 + SLIPPAGE_RATE)
    end_price = float(prepared.iloc[-1]["close"]) * (1 - SLIPPAGE_RATE)
    budget = initial_cash * max_position_pct
    quantity = int(budget // (start_price * 100)) * 100
    if quantity <= 0:
        return {"return_pct": 0.0, "max_drawdown_pct": 0.0}
    buy_cost = start_price * quantity + _buy_fees(start_price * quantity)
    cash = initial_cash - buy_cost
    equity_values = [cash + quantity * float(item) for item in prepared["close"].iloc[start:]]
    sell_proceeds = end_price * quantity - _sell_fees(end_price * quantity)
    final_value = cash + sell_proceeds
    equity_values[-1] = final_value
    return {
        "return_pct": round((final_value / initial_cash - 1) * 100, 2),
        "max_drawdown_pct": _drawdown_pct(equity_values),
    }


def _evaluate_variant(
    frame: pd.DataFrame,
    *,
    stock_code: str,
    strategy_key: str,
    params: Mapping[str, Any],
    initial_cash: float,
    max_position_pct: float,
    evaluation_start: int,
) -> dict[str, Any]:
    entry, exit_signal = build_strategy_signals(frame, strategy_key, params)
    metrics = simulate_signals(
        frame,
        entry,
        exit_signal,
        stock_code=stock_code,
        initial_cash=initial_cash,
        max_position_pct=max_position_pct,
        stop_loss_pct=float(params["stop_loss_pct"]),
        take_profit_pct=float(params["take_profit_pct"]),
        max_holding_days=int(params["max_holding_days"]),
        evaluation_start=evaluation_start,
    )
    benchmark = _benchmark_metrics(
        frame,
        initial_cash=initial_cash,
        max_position_pct=max_position_pct,
        evaluation_start=evaluation_start,
    )
    metrics["benchmark_return_pct"] = benchmark["return_pct"]
    metrics["excess_return_pct"] = round(metrics["strategy_return_pct"] - benchmark["return_pct"], 2)
    metrics["score"] = round(
        metrics["strategy_return_pct"]
        + metrics["excess_return_pct"] * 0.5
        + max(-3.0, min(3.0, metrics["sharpe_ratio"])) * 1.5
        + metrics["max_drawdown_pct"] * 0.5,
        2,
    )
    return metrics


def evaluate_strategy_lab(
    frame: pd.DataFrame,
    *,
    stock_code: str,
    initial_cash: float = 100000.0,
    max_position_pct: float = 0.30,
) -> dict[str, Any]:
    prepared = _prepare_frame(frame)
    normalized_code = normalize_stock_code(stock_code)
    if len(prepared) < MIN_LAB_BARS:
        return {
            "status": "insufficient_data",
            "stock_code": normalized_code,
            "bars": len(prepared),
            "required_bars": MIN_LAB_BARS,
            "summary": f"当前只有 {len(prepared)} 根有效日线，至少需要 {MIN_LAB_BARS} 根才能做样本外比较。",
        }
    if initial_cash <= 0:
        raise ValueError("initial_cash must be greater than 0")
    if not 0 < max_position_pct <= 1:
        raise ValueError("max_position_pct must be in (0, 1]")

    split_index = max(120, min(int(len(prepared) * 0.70), len(prepared) - 60))
    training = prepared.iloc[:split_index]
    strategy_results: list[dict[str, Any]] = []
    for family in STRATEGY_FAMILIES:
        training_variants = []
        for params in family["variants"]:
            metrics = _evaluate_variant(
                training,
                stock_code=normalized_code,
                strategy_key=family["key"],
                params=params,
                initial_cash=initial_cash,
                max_position_pct=max_position_pct,
                evaluation_start=1,
            )
            training_variants.append({"params": dict(params), "metrics": metrics})
        selected = max(training_variants, key=lambda item: (item["metrics"]["score"], item["metrics"]["closed_trades"]))
        out_of_sample = _evaluate_variant(
            prepared,
            stock_code=normalized_code,
            strategy_key=family["key"],
            params=selected["params"],
            initial_cash=initial_cash,
            max_position_pct=max_position_pct,
            evaluation_start=split_index,
        )
        in_sample = selected["metrics"]
        overfit_gap = round(in_sample["strategy_return_pct"] - out_of_sample["strategy_return_pct"], 2)
        if out_of_sample["closed_trades"] < 2:
            robustness = {
                "status": "insufficient",
                "label": "样本不足",
                "reason": "样本外完整交易少于 2 次，暂不能判断策略稳定性。",
            }
        elif (
            out_of_sample["strategy_return_pct"] > 0
            and out_of_sample["excess_return_pct"] >= 0
            and out_of_sample["max_drawdown_pct"] >= -12
            and overfit_gap <= 20
        ):
            robustness = {
                "status": "stable",
                "label": "样本外可用",
                "reason": "样本外收益为正、跑赢同期基准且回撤在约束内。",
            }
        elif out_of_sample["strategy_return_pct"] > 0 and out_of_sample["max_drawdown_pct"] >= -15:
            robustness = {
                "status": "observe",
                "label": "继续观察",
                "reason": "样本外收益为正，但尚未同时满足超额收益和稳健性要求。",
            }
        else:
            robustness = {
                "status": "reject",
                "label": "暂不采用",
                "reason": "样本外收益或回撤不达标，不应据此生成买入依据。",
            }
        strategy_results.append(
            {
                "key": family["key"],
                "name": family["name"],
                "description": family["description"],
                "selected_params": selected["params"],
                "in_sample": in_sample,
                "out_of_sample": out_of_sample,
                "overfit_gap_pct": overfit_gap,
                "robustness": robustness,
            }
        )

    eligible = [
        item
        for item in strategy_results
        if item["robustness"]["status"] in {"stable", "observe"}
        and item["out_of_sample"]["closed_trades"] >= 2
    ]
    eligible.sort(key=lambda item: item["out_of_sample"]["score"], reverse=True)
    recommended = eligible[0] if eligible else None
    if recommended and recommended["robustness"]["status"] == "stable":
        conclusion = {
            "status": "evidence_available",
            "label": f"可参考：{recommended['name']}",
            "summary": "该策略通过当前时间顺序样本外门槛，可作为研究证据，但仍需结合市场风控和组合仓位。",
            "recommended_strategy_key": recommended["key"],
        }
    elif recommended:
        conclusion = {
            "status": "observe_only",
            "label": f"仅观察：{recommended['name']}",
            "summary": "目前只有初步正向结果，尚不足以单独支持买入。",
            "recommended_strategy_key": recommended["key"],
        }
    else:
        conclusion = {
            "status": "no_valid_strategy",
            "label": "暂无可靠策略",
            "summary": "三类策略均未通过样本外门槛，当前不应引用回测结果支持买入。",
            "recommended_strategy_key": None,
        }

    return {
        "status": "ok",
        "stock_code": normalized_code,
        "bars": len(prepared),
        "data_start_date": prepared.index.min().strftime("%Y-%m-%d"),
        "data_end_date": prepared.index.max().strftime("%Y-%m-%d"),
        "split_date": prepared.index[split_index].strftime("%Y-%m-%d"),
        "training_bars": split_index,
        "out_of_sample_bars": len(prepared) - split_index,
        "initial_cash": round(float(initial_cash), 2),
        "max_position_pct": round(float(max_position_pct) * 100, 2),
        "validation_method": "按时间顺序前70%选参数、后30%只做样本外验证",
        "execution_model": "收盘产生信号、下一交易日开盘成交；含100股整手、T+1、手续费、印花税、过户费、滑点和涨跌停阻断",
        "conclusion": conclusion,
        "strategies": strategy_results,
        "limitations": [
            "当前是单股票时间序列验证，不能替代全市场截面检验。",
            "历史日线无法完整还原盘中排队、停牌和真实冲击成本。",
            "样本外通过只表示该历史区间较稳健，不代表未来收益。",
        ],
    }


def _walk_forward_windows(
    total_bars: int,
    *,
    train_bars: int = WALK_FORWARD_TRAIN_BARS,
    test_bars: int = WALK_FORWARD_TEST_BARS,
    max_windows: int = WALK_FORWARD_MAX_WINDOWS,
) -> list[dict[str, int]]:
    windows: list[dict[str, int]] = []
    test_end = int(total_bars)
    while len(windows) < max(1, int(max_windows)):
        test_start = test_end - int(test_bars)
        train_start = test_start - int(train_bars)
        if train_start < 0:
            break
        windows.append(
            {
                "train_start": train_start,
                "train_end": test_start,
                "test_start": test_start,
                "test_end": test_end,
            }
        )
        test_end = test_start
    return list(reversed(windows))


def _compact_metrics(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metrics.items() if key != "trades"}


def _aggregate_walk_forward_windows(windows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out_metrics = [item["out_of_sample"] for item in windows]
    window_count = len(out_metrics)
    total_trades = sum(int(item.get("closed_trades") or 0) for item in out_metrics)
    won_trades = sum(int(item.get("won_trades") or 0) for item in out_metrics)
    positive_windows = sum(float(item.get("strategy_return_pct") or 0) > 0 for item in out_metrics)
    benchmark_wins = sum(float(item.get("excess_return_pct") or 0) > 0 for item in out_metrics)
    average_return = sum(float(item.get("strategy_return_pct") or 0) for item in out_metrics) / max(1, window_count)
    average_excess = sum(float(item.get("excess_return_pct") or 0) for item in out_metrics) / max(1, window_count)
    worst_drawdown = min((float(item.get("max_drawdown_pct") or 0) for item in out_metrics), default=0.0)
    parameter_counts = Counter(
        json.dumps(item["selected_params"], ensure_ascii=False, sort_keys=True)
        for item in windows
    )
    parameter_stability_pct = (
        max(parameter_counts.values()) / window_count * 100
        if parameter_counts and window_count
        else 0.0
    )
    positive_window_pct = positive_windows / max(1, window_count) * 100
    beat_benchmark_pct = benchmark_wins / max(1, window_count) * 100

    if total_trades < 3:
        robustness = {
            "status": "insufficient",
            "label": "跨窗口样本不足",
            "reason": "滚动样本外完整交易少于 3 次，暂不能形成稳定性证据。",
        }
    elif (
        average_return > 0
        and average_excess >= 0
        and positive_window_pct >= 60
        and beat_benchmark_pct >= 50
        and worst_drawdown >= -12
    ):
        robustness = {
            "status": "stable",
            "label": "跨窗口稳定",
            "reason": "多数滚动窗口收益为正、平均跑赢基准且最差回撤受控。",
        }
    elif average_return > 0 and positive_window_pct >= 50 and worst_drawdown >= -15:
        robustness = {
            "status": "observe",
            "label": "跨窗口观察",
            "reason": "滚动结果初步为正，但超额收益或窗口一致性尚未全部达标。",
        }
    else:
        robustness = {
            "status": "reject",
            "label": "跨窗口失效",
            "reason": "滚动样本外收益、超额收益或回撤未达到采用门槛。",
        }

    score = (
        average_excess * 1.2
        + average_return * 0.5
        + positive_window_pct * 0.03
        + beat_benchmark_pct * 0.02
        + worst_drawdown * 0.2
        + min(total_trades, 12) * 0.2
    )
    return {
        "window_count": window_count,
        "total_trades": total_trades,
        "won_trades": won_trades,
        "win_rate_pct": round(won_trades / total_trades * 100, 2) if total_trades else 0.0,
        "average_return_pct": round(average_return, 2),
        "average_excess_return_pct": round(average_excess, 2),
        "positive_window_pct": round(positive_window_pct, 2),
        "beat_benchmark_pct": round(beat_benchmark_pct, 2),
        "worst_drawdown_pct": round(worst_drawdown, 2),
        "parameter_stability_pct": round(parameter_stability_pct, 2),
        "score": round(score, 2),
        "robustness": robustness,
    }


def _summarize_windows_by_market_regime(windows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    regimes = sorted({str(item.get("market_regime", {}).get("regime") or "未知") for item in windows})
    summaries = []
    for regime in regimes:
        regime_windows = [
            item
            for item in windows
            if str(item.get("market_regime", {}).get("regime") or "未知") == regime
        ]
        aggregate = _aggregate_walk_forward_windows(regime_windows)
        summaries.append(
            {
                "market_regime": regime,
                **aggregate,
            }
        )
    return summaries


def evaluate_strategy_walk_forward(
    frame: pd.DataFrame,
    *,
    stock_code: str,
    market_frame: pd.DataFrame | None = None,
    initial_cash: float = 100000.0,
    max_position_pct: float = 0.30,
    train_bars: int = WALK_FORWARD_TRAIN_BARS,
    test_bars: int = WALK_FORWARD_TEST_BARS,
    max_windows: int = WALK_FORWARD_MAX_WINDOWS,
) -> dict[str, Any]:
    prepared = _prepare_frame(frame)
    normalized_code = normalize_stock_code(stock_code)
    windows = _walk_forward_windows(
        len(prepared),
        train_bars=train_bars,
        test_bars=test_bars,
        max_windows=max_windows,
    )
    if len(windows) < 2:
        required_bars = int(train_bars) + int(test_bars) * 2
        return {
            "status": "insufficient_data",
            "stock_code": normalized_code,
            "bars": len(prepared),
            "required_bars": required_bars,
            "window_count": len(windows),
            "summary": f"当前只有 {len(prepared)} 根有效日线，至少需要 {required_bars} 根才能完成两次滚动样本外验证。",
        }
    if initial_cash <= 0:
        raise ValueError("initial_cash must be greater than 0")
    if not 0 < max_position_pct <= 1:
        raise ValueError("max_position_pct must be in (0, 1]")

    strategy_results: list[dict[str, Any]] = []
    for family in STRATEGY_FAMILIES:
        family_windows: list[dict[str, Any]] = []
        for window_index, window in enumerate(windows, start=1):
            training = prepared.iloc[window["train_start"]:window["train_end"]]
            evaluation = prepared.iloc[window["train_start"]:window["test_end"]]
            training_variants = []
            for params in family["variants"]:
                metrics = _evaluate_variant(
                    training,
                    stock_code=normalized_code,
                    strategy_key=family["key"],
                    params=params,
                    initial_cash=initial_cash,
                    max_position_pct=max_position_pct,
                    evaluation_start=1,
                )
                training_variants.append({"params": dict(params), "metrics": metrics})
            selected = max(
                training_variants,
                key=lambda item: (item["metrics"]["score"], item["metrics"]["closed_trades"]),
            )
            out_of_sample = _evaluate_variant(
                evaluation,
                stock_code=normalized_code,
                strategy_key=family["key"],
                params=selected["params"],
                initial_cash=initial_cash,
                max_position_pct=max_position_pct,
                evaluation_start=len(training),
            )
            market_regime = classify_market_regime(
                market_frame,
                as_of_date=evaluation.index[len(training)],
            )
            family_windows.append(
                {
                    "window": window_index,
                    "training_start_date": training.index.min().strftime("%Y-%m-%d"),
                    "training_end_date": training.index.max().strftime("%Y-%m-%d"),
                    "test_start_date": evaluation.index[len(training)].strftime("%Y-%m-%d"),
                    "test_end_date": evaluation.index.max().strftime("%Y-%m-%d"),
                    "market_regime": market_regime,
                    "selected_params": selected["params"],
                    "in_sample": _compact_metrics(selected["metrics"]),
                    "out_of_sample": _compact_metrics(out_of_sample),
                }
            )
        aggregate = _aggregate_walk_forward_windows(family_windows)
        aggregate["by_market_regime"] = _summarize_windows_by_market_regime(family_windows)
        known_regimes = [
            item
            for item in aggregate["by_market_regime"]
            if item["market_regime"] != "未知"
        ]
        aggregate["best_market_regime"] = (
            max(
                known_regimes,
                key=lambda item: (
                    item["average_excess_return_pct"],
                    item["average_return_pct"],
                ),
            )["market_regime"]
            if known_regimes
            else "未知"
        )
        strategy_results.append(
            {
                "key": family["key"],
                "name": family["name"],
                "description": family["description"],
                "aggregate": aggregate,
                "windows": family_windows,
            }
        )

    robustness_priority = {"stable": 3, "observe": 2, "reject": 1, "insufficient": 0}
    strategy_results.sort(
        key=lambda item: (
            robustness_priority[item["aggregate"]["robustness"]["status"]],
            item["aggregate"]["score"],
        ),
        reverse=True,
    )
    best_strategy = strategy_results[0]
    return {
        "status": "ok",
        "stock_code": normalized_code,
        "bars": len(prepared),
        "data_start_date": prepared.index.min().strftime("%Y-%m-%d"),
        "data_end_date": prepared.index.max().strftime("%Y-%m-%d"),
        "train_bars": int(train_bars),
        "test_bars": int(test_bars),
        "window_count": len(windows),
        "validation_method": f"最近 {int(train_bars)} 根选参、随后 {int(test_bars)} 根样本外验证，向前滚动 {len(windows)} 次",
        "best_strategy_key": best_strategy["key"],
        "best_strategy_name": best_strategy["name"],
        "conclusion": best_strategy["aggregate"]["robustness"],
        "strategies": strategy_results,
    }


def _lookup_stock_name(connection, stock_code: str) -> str:
    row = connection.execute(
        """
        SELECT COALESCE(
            (SELECT NULLIF(display_name, '') FROM watchlist WHERE stock_code = ? LIMIT 1),
            (SELECT stock_name FROM paper_positions WHERE stock_code = ? ORDER BY updated_at DESC LIMIT 1),
            (SELECT stock_name FROM stock_market_snapshot WHERE stock_code = ? LIMIT 1),
            (SELECT stock_name FROM stock_catalog WHERE stock_code = ? LIMIT 1),
            ?
        ) AS stock_name
        """,
        (stock_code, stock_code, stock_code, stock_code, stock_code),
    ).fetchone()
    return str(row["stock_name"] if row else stock_code)


def _load_strategy_universe(
    stock_codes: Sequence[str] | None,
    *,
    max_stocks: int,
) -> list[dict[str, str]]:
    limit = max(1, min(int(max_stocks), 12))
    requested = []
    for value in stock_codes or []:
        normalized = normalize_stock_code(str(value))
        if normalized not in requested:
            requested.append(normalized)
    with get_connection() as connection:
        if requested:
            return [
                {
                    "stock_code": code,
                    "stock_name": _lookup_stock_name(connection, code),
                    "source": "指定股票",
                }
                for code in requested[:limit]
            ]

        universe: list[dict[str, str]] = []
        seen: set[str] = set()

        def append_rows(rows, source: str, *, max_add: int | None = None) -> int:
            added = 0
            for row in rows:
                if max_add is not None and added >= max(0, int(max_add)):
                    break
                code = normalize_stock_code(str(row["stock_code"]))
                if code in seen or len(universe) >= limit:
                    continue
                seen.add(code)
                universe.append(
                    {
                        "stock_code": code,
                        "stock_name": str(row["stock_name"] or _lookup_stock_name(connection, code)),
                        "source": source,
                    }
                )
                added += 1
            return added

        append_rows(
            connection.execute(
                """
                SELECT stock_code, MAX(stock_name) AS stock_name
                FROM paper_positions
                WHERE quantity > 0
                GROUP BY stock_code
                ORDER BY MAX(updated_at) DESC
                """
            ).fetchall(),
            "当前持仓",
            max_add=max(0, limit - 2),
        )
        watchlist_slots = max(0, min(3, limit - len(universe) - 2))
        append_rows(
            connection.execute(
                """
                SELECT w.stock_code,
                       COALESCE(NULLIF(w.display_name, ''), s.stock_name, c.stock_name, w.stock_code) AS stock_name
                FROM watchlist w
                LEFT JOIN stock_market_snapshot s ON s.stock_code = w.stock_code
                LEFT JOIN stock_catalog c ON c.stock_code = w.stock_code
                WHERE w.is_active = 1
                ORDER BY w.updated_at DESC
                """
            ).fetchall(),
            "我的自选",
            max_add=watchlist_slots,
        )
        append_rows(
            connection.execute(
                """
                SELECT stock_code, MAX(stock_name) AS stock_name, MAX(created_at) AS latest_created_at
                FROM ai_recommendation_items
                GROUP BY stock_code
                ORDER BY latest_created_at DESC
                LIMIT 24
                """
            ).fetchall(),
            "最近推荐",
            max_add=min(2, limit - len(universe)),
        )
        if len(universe) < limit:
            append_rows(
                connection.execute(
                    """
                    SELECT stock_code, stock_name
                    FROM stock_market_snapshot
                    WHERE market IN ('SH', 'SZ')
                      AND stock_name NOT LIKE '%ST%'
                      AND price > 0
                    ORDER BY amount DESC
                    LIMIT 24
                    """
                ).fetchall(),
                "高流动性补充",
            )
    return universe[:limit]


def run_strategy_stability_lab(
    stock_codes: Sequence[str] | None = None,
    *,
    max_stocks: int = DEFAULT_STABILITY_STOCK_LIMIT,
    initial_cash: float = 100000.0,
    max_position_pct: float = 0.30,
) -> dict[str, Any]:
    init_db()
    universe = _load_strategy_universe(stock_codes, max_stocks=max_stocks)
    market_history_error = None
    try:
        market_frame = ensure_market_index_history(min_bars=MIN_WALK_FORWARD_BARS)
    except Exception as error:
        market_frame = pd.DataFrame()
        market_history_error = str(error)
    ranking: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    robustness_priority = {"stable": 3, "observe": 2, "reject": 1, "insufficient": 0}

    for stock in universe:
        try:
            frame = ensure_daily_bars_for_backtest(
                stock["stock_code"],
                lookback_days=DEFAULT_LOOKBACK_DAYS,
                min_bars=MIN_WALK_FORWARD_BARS,
            )
            evaluation = evaluate_strategy_walk_forward(
                frame,
                stock_code=stock["stock_code"],
                market_frame=market_frame,
                initial_cash=initial_cash,
                max_position_pct=max_position_pct,
            )
        except Exception as error:
            unavailable.append({**stock, "reason": str(error)})
            continue
        if evaluation["status"] != "ok":
            unavailable.append({**stock, **evaluation})
            continue
        best_strategy = evaluation["strategies"][0]
        aggregate = best_strategy["aggregate"]
        ranking.append(
            {
                **stock,
                "bars": evaluation["bars"],
                "data_start_date": evaluation["data_start_date"],
                "data_end_date": evaluation["data_end_date"],
                "window_count": evaluation["window_count"],
                "best_strategy_key": best_strategy["key"],
                "best_strategy_name": best_strategy["name"],
                "robustness": aggregate["robustness"],
                "aggregate": aggregate,
                "strategies": evaluation["strategies"],
            }
        )

    ranking.sort(
        key=lambda item: (
            robustness_priority[item["robustness"]["status"]],
            item["aggregate"]["score"],
        ),
        reverse=True,
    )
    stable_count = sum(item["robustness"]["status"] == "stable" for item in ranking)
    observe_count = sum(item["robustness"]["status"] == "observe" for item in ranking)
    reject_count = sum(item["robustness"]["status"] == "reject" for item in ranking)
    insufficient_count = sum(item["robustness"]["status"] == "insufficient" for item in ranking) + len(unavailable)
    if stable_count:
        conclusion = {
            "status": "evidence_available",
            "label": f"发现 {stable_count} 只跨窗口稳定标的",
            "summary": "这些结果可作为研究证据，但仍需服从市场风控、组合仓位和行情新鲜度约束。",
        }
    elif observe_count:
        conclusion = {
            "status": "observe_only",
            "label": "暂无跨窗口稳定标的",
            "summary": f"有 {observe_count} 只仅达到观察门槛，当前不应仅凭策略结果新增仓位。",
        }
    else:
        conclusion = {
            "status": "no_valid_strategy",
            "label": "本轮未发现可靠策略证据",
            "summary": "当前股票池没有通过滚动样本外门槛的标的，策略层面不支持新增买入。",
        }

    result = {
        "status": "ok" if universe else "empty_universe",
        "universe_size": len(universe),
        "evaluated_count": len(ranking),
        "stable_count": stable_count,
        "observe_count": observe_count,
        "reject_count": reject_count,
        "insufficient_count": insufficient_count,
        "window_config": {
            "train_bars": WALK_FORWARD_TRAIN_BARS,
            "test_bars": WALK_FORWARD_TEST_BARS,
            "max_windows": WALK_FORWARD_MAX_WINDOWS,
        },
        "market_regime_model": {
            "index_code": "SH000001",
            "method": "每个样本外窗口开始前，使用上证指数过去20/60日收益与均线分类上涨、震荡或下跌",
            "uses_future_data": False,
            "history_bars": len(market_frame),
            "error": market_history_error,
        },
        "universe": universe,
        "conclusion": conclusion,
        "ranking": ranking,
        "unavailable": unavailable,
        "limitations": [
            "排行榜只比较当前持仓、自选、最近推荐和必要的高流动性补充股票，不代表全市场扫描。",
            "滚动日线验证仍无法还原停牌、排队成交和真实冲击成本。",
            "跨窗口稳定只表示历史证据更一致，不代表未来收益。",
        ],
    }
    created_at = _utc_now_str()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO strategy_stability_runs (universe_json, result_json, created_at)
            VALUES (?, ?, ?)
            """,
            (
                json.dumps(universe, ensure_ascii=False),
                json.dumps(result, ensure_ascii=False),
                created_at,
            ),
        )
        run_id = int(cursor.lastrowid)
    return {"run_id": run_id, "created_at": created_at, **result}


def load_latest_strategy_stability() -> dict[str, Any]:
    init_db()
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, result_json, created_at
            FROM strategy_stability_runs
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
    if not row:
        return {
            "status": "not_run",
            "summary": "还没有策略稳定性记录，请先运行多股票滚动验证。",
        }
    return {
        "run_id": int(row["id"]),
        "created_at": row["created_at"],
        **json.loads(row["result_json"]),
    }


def run_strategy_lab(
    stock_code: str,
    *,
    initial_cash: float = 100000.0,
    max_position_pct: float = 0.30,
) -> dict[str, Any]:
    normalized_code = normalize_stock_code(stock_code)
    init_db()
    frame = ensure_daily_bars_for_backtest(
        normalized_code,
        lookback_days=DEFAULT_LOOKBACK_DAYS,
        min_bars=MIN_LAB_BARS,
    )
    result = evaluate_strategy_lab(
        frame,
        stock_code=normalized_code,
        initial_cash=initial_cash,
        max_position_pct=max_position_pct,
    )
    if result.get("status") != "ok":
        return result

    created_at = _utc_now_str()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO strategy_experiment_runs (
                stock_code, data_start_date, data_end_date, split_date,
                result_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_code,
                result["data_start_date"],
                result["data_end_date"],
                result["split_date"],
                json.dumps(result, ensure_ascii=False),
                created_at,
            ),
        )
        run_id = int(cursor.lastrowid)
    return {"run_id": run_id, "created_at": created_at, **result}
