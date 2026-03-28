from __future__ import annotations

from datetime import datetime, timedelta

import backtrader as bt
import pandas as pd

from .db import get_connection
from .sync import sync_daily_bars_for_codes
from .watchlist import normalize_stock_code


class SmaCrossStrategy(bt.Strategy):
    params = (("fast", 5), ("slow", 20))

    def __init__(self) -> None:
        fast_sma = bt.indicators.SimpleMovingAverage(self.data.close, period=self.params.fast)
        slow_sma = bt.indicators.SimpleMovingAverage(self.data.close, period=self.params.slow)
        self.crossover = bt.indicators.CrossOver(fast_sma, slow_sma)

    def next(self) -> None:
        if not self.position and self.crossover > 0:
            self.buy()
        elif self.position and self.crossover < 0:
            self.close()


def _load_daily_bar_frame(stock_code: str, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
    normalized_code = normalize_stock_code(stock_code)
    conditions = ["stock_code = ?", "k_type = 1"]
    params: list[object] = [normalized_code]
    if start_date:
        conditions.append("trade_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("trade_date <= ?")
        params.append(end_date)

    with get_connection() as connection:
        frame = pd.read_sql_query(
            f"""
            SELECT trade_date, open, high, low, close, volume
            FROM daily_bars
            WHERE {' AND '.join(conditions)}
            ORDER BY trade_date ASC
            """,
            connection,
            params=params,
        )
    if frame.empty:
        return frame

    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["open", "high", "low", "close"])
    frame = frame.set_index("trade_date")
    return frame


def ensure_daily_bars_for_backtest(stock_code: str, *, lookback_days: int = 400) -> pd.DataFrame:
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    frame = _load_daily_bar_frame(stock_code, start_date=start_date, end_date=end_date)
    latest_date = frame.index.max().date().isoformat() if not frame.empty else None

    if frame.empty or latest_date < (datetime.now().date() - timedelta(days=7)).isoformat():
        sync_daily_bars_for_codes(
            stock_codes=[stock_code],
            start_date=start_date,
            end_date=end_date,
        )
        frame = _load_daily_bar_frame(stock_code, start_date=start_date, end_date=end_date)
    return frame


def run_backtest(
    stock_code: str,
    *,
    fast_period: int = 5,
    slow_period: int = 20,
    initial_cash: float = 100000.0,
) -> dict[str, object]:
    if fast_period <= 0 or slow_period <= 0 or fast_period >= slow_period:
        raise ValueError("fast_period must be > 0 and smaller than slow_period")

    frame = ensure_daily_bars_for_backtest(stock_code)
    if len(frame) < slow_period + 10:
        return {
            "stock_code": normalize_stock_code(stock_code),
            "strategy": f"SMA {fast_period}/{slow_period}",
            "bars": len(frame),
            "status": "insufficient_data",
        }

    benchmark_return_pct = float(((frame["close"].iloc[-1] / frame["close"].iloc[0]) - 1.0) * 100)

    data = bt.feeds.PandasData(dataname=frame)
    cerebro = bt.Cerebro(stdstats=False)
    cerebro.addstrategy(SmaCrossStrategy, fast=fast_period, slow=slow_period)
    cerebro.adddata(data)
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")

    strategy = cerebro.run()[0]
    final_value = cerebro.broker.getvalue()
    trade_stats = strategy.analyzers.trades.get_analysis()
    drawdown_stats = strategy.analyzers.drawdown.get_analysis()

    closed_trades = int(getattr(getattr(trade_stats, "total", {}), "closed", 0) or trade_stats.get("total", {}).get("closed", 0) or 0)
    won_trades = int(getattr(getattr(trade_stats, "won", {}), "total", 0) or trade_stats.get("won", {}).get("total", 0) or 0)

    return {
        "stock_code": normalize_stock_code(stock_code),
        "strategy": f"SMA {fast_period}/{slow_period}",
        "bars": int(len(frame)),
        "data_start_date": frame.index.min().strftime("%Y-%m-%d"),
        "data_end_date": frame.index.max().strftime("%Y-%m-%d"),
        "initial_cash": round(initial_cash, 2),
        "final_value": float(round(final_value, 2)),
        "strategy_return_pct": float(round(((final_value / initial_cash) - 1.0) * 100, 2)),
        "benchmark_return_pct": round(benchmark_return_pct, 2),
        "max_drawdown_pct": round(float(drawdown_stats.get("max", {}).get("drawdown", 0) or 0), 2),
        "closed_trades": closed_trades,
        "won_trades": won_trades,
        "win_rate_pct": round((won_trades / closed_trades) * 100, 2) if closed_trades else 0.0,
        "status": "ok",
    }
