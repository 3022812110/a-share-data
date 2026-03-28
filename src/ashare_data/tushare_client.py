from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import requests

from .config import get_tushare_token

TUSHARE_API_URL = "https://api.tushare.pro"


def _normalize_tushare_code(stock_code: str) -> str:
    code = stock_code.strip().upper()
    if code.endswith((".SH", ".SZ", ".BJ")):
        return code
    if code.startswith(("60", "68", "51", "56", "58", "11")):
        return f"{code}.SH"
    if code.startswith(("00", "30", "12", "15")):
        return f"{code}.SZ"
    if code.startswith(("43", "83", "87", "88", "92")):
        return f"{code}.BJ"
    return code


def _to_compact_date(date_text: str | None) -> str | None:
    if date_text is None:
        return None
    return date_text.replace("-", "").strip()


def fetch_tushare_daily_bars(
    stock_code: str,
    start_date: str,
    end_date: str | None = None,
    *,
    timeout_seconds: int = 20,
) -> pd.DataFrame:
    token = get_tushare_token()
    if not token:
        return pd.DataFrame()

    ts_code = _normalize_tushare_code(stock_code)
    payload: dict[str, Any] = {
        "api_name": "daily",
        "token": token,
        "params": {
            "ts_code": ts_code,
            "start_date": _to_compact_date(start_date),
            "end_date": _to_compact_date(end_date),
        },
        "fields": "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount",
    }

    response = requests.post(TUSHARE_API_URL, json=payload, timeout=timeout_seconds)
    response.raise_for_status()
    body = response.json()

    if body.get("code") not in (0, None):
        return pd.DataFrame()

    data = body.get("data") or {}
    fields = data.get("fields") or []
    items = data.get("items") or []
    if not fields or not items:
        return pd.DataFrame()

    frame = pd.DataFrame(items, columns=fields)
    frame["stock_code"] = frame["ts_code"].astype(str).str.split(".").str[0]
    frame["trade_date"] = pd.to_datetime(frame["trade_date"].astype(str), format="%Y%m%d").dt.strftime("%Y-%m-%d")
    frame["trade_time"] = frame["trade_date"] + " 00:00:00"
    frame["change_pct"] = frame["pct_chg"]
    frame["turnover_ratio"] = None
    frame["fetched_at"] = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    frame["source"] = "tushare"

    ordered_columns = [
        "stock_code",
        "trade_time",
        "trade_date",
        "open",
        "close",
        "high",
        "low",
        "vol",
        "amount",
        "change_pct",
        "change",
        "turnover_ratio",
        "pre_close",
        "source",
        "fetched_at",
    ]
    frame = frame[ordered_columns].rename(columns={"vol": "volume"})
    return frame
