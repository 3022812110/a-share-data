from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from .db import get_connection, init_db
from .eastmoney_kline import fetch_stock_kline


DEFAULT_MARKET_INDEX_CODE = "SH000001"
DEFAULT_MARKET_INDEX_LIMIT = 800
MIN_MARKET_REGIME_BARS = 61


def _utc_now_str() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _prepare_market_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    prepared = frame.copy()
    if not isinstance(prepared.index, pd.DatetimeIndex):
        if "trade_date" not in prepared.columns:
            return pd.DataFrame()
        prepared["trade_date"] = pd.to_datetime(prepared["trade_date"], errors="coerce")
        prepared = prepared.set_index("trade_date")
    prepared.index = pd.to_datetime(prepared.index, errors="coerce")
    prepared = prepared[~prepared.index.isna()].sort_index()
    prepared["close"] = pd.to_numeric(prepared.get("close"), errors="coerce")
    return prepared.dropna(subset=["close"])


def load_market_index_history(index_code: str = DEFAULT_MARKET_INDEX_CODE) -> pd.DataFrame:
    init_db()
    with get_connection() as connection:
        frame = pd.read_sql_query(
            """
            SELECT trade_date, open, close, high, low, volume, amount
            FROM market_index_daily_bars
            WHERE index_code = ?
            ORDER BY trade_date ASC
            """,
            connection,
            params=(index_code.upper(),),
        )
    return _prepare_market_frame(frame)


def ensure_market_index_history(
    index_code: str = DEFAULT_MARKET_INDEX_CODE,
    *,
    min_bars: int = 260,
    limit: int = DEFAULT_MARKET_INDEX_LIMIT,
) -> pd.DataFrame:
    normalized_code = index_code.upper()
    frame = load_market_index_history(normalized_code)
    latest_date = frame.index.max().date() if not frame.empty else None
    stale_before = datetime.now().date() - timedelta(days=7)
    if len(frame) >= int(min_bars) and latest_date and latest_date >= stale_before:
        return frame

    payload = fetch_stock_kline(
        normalized_code,
        interval="day",
        adjust="none",
        limit=max(int(limit), int(min_bars)),
    )
    fetched_at = _utc_now_str()
    rows = []
    for item in payload.get("items") or []:
        trade_date = str(item.get("time") or "")[:10]
        if not trade_date:
            continue
        rows.append(
            (
                normalized_code,
                trade_date,
                item.get("open"),
                item.get("close"),
                item.get("high"),
                item.get("low"),
                item.get("volume"),
                item.get("amount"),
                str(payload.get("source") or "eastmoney"),
                fetched_at,
            )
        )
    if rows:
        with get_connection() as connection:
            connection.executemany(
                """
                INSERT INTO market_index_daily_bars (
                    index_code, trade_date, open, close, high, low,
                    volume, amount, source, fetched_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(index_code, trade_date) DO UPDATE SET
                    open = excluded.open,
                    close = excluded.close,
                    high = excluded.high,
                    low = excluded.low,
                    volume = excluded.volume,
                    amount = excluded.amount,
                    source = excluded.source,
                    fetched_at = excluded.fetched_at
                """,
                rows,
            )
    return load_market_index_history(normalized_code)


def classify_market_regime(
    frame: pd.DataFrame | None,
    *,
    as_of_date: str | pd.Timestamp,
) -> dict[str, Any]:
    prepared = _prepare_market_frame(frame)
    cutoff = pd.Timestamp(as_of_date)
    history = prepared.loc[prepared.index < cutoff]
    if len(history) < MIN_MARKET_REGIME_BARS:
        return {
            "regime": "未知",
            "signal_date": None,
            "bars": len(history),
            "reason": f"窗口开始前只有 {len(history)} 根指数日线，无法分类。",
        }

    close = history["close"]
    latest_close = float(close.iloc[-1])
    ma20 = float(close.iloc[-20:].mean())
    ma60 = float(close.iloc[-60:].mean())
    return_20 = (latest_close / float(close.iloc[-21]) - 1) * 100
    return_60 = (latest_close / float(close.iloc[-61]) - 1) * 100
    volatility_20 = float(close.pct_change().iloc[-20:].std(ddof=0) * (252 ** 0.5) * 100)

    if latest_close > ma60 * 1.01 and ma20 > ma60 * 1.005 and return_20 >= 2 and return_60 >= 4:
        regime = "上涨"
        reason = "指数位于中期均线上方，短中期收益和均线方向同时向上。"
    elif latest_close < ma60 * 0.99 and ma20 < ma60 * 0.995 and return_20 <= -2 and return_60 <= -4:
        regime = "下跌"
        reason = "指数位于中期均线下方，短中期收益和均线方向同时向下。"
    else:
        regime = "震荡"
        reason = "趋势、均线和阶段收益没有形成一致的上涨或下跌状态。"

    return {
        "regime": regime,
        "signal_date": history.index[-1].strftime("%Y-%m-%d"),
        "bars": len(history),
        "close": round(latest_close, 2),
        "ma20": round(ma20, 2),
        "ma60": round(ma60, 2),
        "return_20d_pct": round(return_20, 2),
        "return_60d_pct": round(return_60, 2),
        "annualized_volatility_20d_pct": round(volatility_20, 2),
        "reason": reason,
    }


def map_current_market_regime(regime: str | None) -> str:
    mapping = {
        "偏强": "上涨",
        "震荡": "震荡",
        "偏弱": "下跌",
        "极弱": "下跌",
    }
    return mapping.get(str(regime or ""), "未知")
