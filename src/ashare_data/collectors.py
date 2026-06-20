from __future__ import annotations

from datetime import datetime
import time

import adata
import pandas as pd

from .akshare_client import fetch_akshare_daily_bars
from .baostock_client import fetch_baostock_daily_bars
from .tushare_client import fetch_tushare_daily_bars


def _utc_now_str() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def fetch_trade_calendar(year: int | None = None) -> pd.DataFrame:
    frame = adata.stock.info.trade_calendar(year=year).copy()
    frame["trade_date"] = frame["trade_date"].astype(str)
    frame["trade_status"] = frame["trade_status"].astype(int)
    frame["day_week"] = frame["day_week"].astype(int)
    frame["fetched_at"] = _utc_now_str()
    return frame[["trade_date", "trade_status", "day_week", "fetched_at"]]


def fetch_daily_bars(
    stock_code: str,
    start_date: str,
    end_date: str | None = None,
    *,
    k_type: int = 1,
    adjust_type: int = 1,
) -> pd.DataFrame:
    if k_type == 1:
        try:
            frame = fetch_akshare_daily_bars(
                stock_code=stock_code,
                start_date=start_date,
                end_date=end_date,
                adjust_type=adjust_type,
            )
        except Exception:
            frame = pd.DataFrame()
        if not frame.empty:
            frame["adjust_type"] = adjust_type
            frame["k_type"] = k_type
            frame["fetched_at"] = _utc_now_str()
            ordered_columns = [
                "stock_code",
                "trade_time",
                "trade_date",
                "open",
                "close",
                "high",
                "low",
                "volume",
                "amount",
                "change_pct",
                "change",
                "turnover_ratio",
                "pre_close",
                "source",
                "adjust_type",
                "k_type",
                "fetched_at",
            ]
            return frame[ordered_columns]

        try:
            frame = fetch_baostock_daily_bars(
                stock_code=stock_code,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception:
            frame = pd.DataFrame()
        if not frame.empty:
            frame["adjust_type"] = adjust_type
            frame["k_type"] = k_type
            frame["fetched_at"] = _utc_now_str()
            ordered_columns = [
                "stock_code",
                "trade_time",
                "trade_date",
                "open",
                "close",
                "high",
                "low",
                "volume",
                "amount",
                "change_pct",
                "change",
                "turnover_ratio",
                "pre_close",
                "source",
                "adjust_type",
                "k_type",
                "fetched_at",
            ]
            return frame[ordered_columns]

    fetchers = [
        adata.stock.market.get_market,
        adata.stock.market.east_market.get_market,
        adata.stock.market.qq_market.get_market,
        adata.stock.market.sina_market.get_market,
    ]

    frame = pd.DataFrame()
    source = "adata"
    for fetcher in fetchers:
        for _ in range(2):
            try:
                result = fetcher(
                    stock_code=stock_code,
                    start_date=start_date,
                    end_date=end_date,
                    k_type=k_type,
                    adjust_type=adjust_type,
                )
            except Exception:
                result = None
            frame = result.copy() if result is not None else pd.DataFrame()
            if not frame.empty:
                break
            time.sleep(0.8)
        if not frame.empty:
            break

    if frame.empty:
        try:
            frame = fetch_tushare_daily_bars(
                stock_code=stock_code,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception:
            frame = pd.DataFrame()
        source = "tushare"

    if frame.empty:
        return frame

    frame["stock_code"] = frame["stock_code"].astype(str)
    frame["trade_time"] = frame["trade_time"].astype(str)
    frame["trade_date"] = frame["trade_date"].astype(str)
    if "source" not in frame.columns:
        frame["source"] = source
    frame["adjust_type"] = adjust_type
    frame["k_type"] = k_type
    frame["fetched_at"] = _utc_now_str()

    ordered_columns = [
        "stock_code",
        "trade_time",
        "trade_date",
        "open",
        "close",
        "high",
        "low",
        "volume",
        "amount",
        "change_pct",
        "change",
        "turnover_ratio",
        "pre_close",
        "source",
        "adjust_type",
        "k_type",
        "fetched_at",
    ]
    return frame[ordered_columns]
