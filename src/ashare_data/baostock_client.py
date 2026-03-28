from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

import baostock as bs
import pandas as pd


def _normalize_baostock_code(stock_code: str) -> str:
    code = stock_code.strip()
    if "." in code:
        prefix, suffix = code.split(".", 1)
        if prefix in {"sh", "sz", "bj"}:
            return f"{prefix}.{suffix}"
        if suffix.lower() in {"sh", "sz", "bj"}:
            return f"{suffix.lower()}.{prefix}"

    if code.startswith(("60", "68", "51", "56", "58", "11")):
        return f"sh.{code}"
    if code.startswith(("00", "30", "12", "15")):
        return f"sz.{code}"
    if code.startswith(("43", "83", "87", "88", "92")):
        return f"bj.{code}"
    return code


@contextmanager
def _baostock_session():
    login_result = bs.login()
    try:
        if login_result.error_code != "0":
            raise RuntimeError(login_result.error_msg)
        yield
    finally:
        bs.logout()


def fetch_baostock_daily_bars(
    stock_code: str,
    start_date: str,
    end_date: str | None = None,
    *,
    adjustflag: str = "2",
) -> pd.DataFrame:
    normalized_code = _normalize_baostock_code(stock_code)
    if not any(normalized_code.startswith(prefix) for prefix in ("sh.", "sz.", "bj.")):
        return pd.DataFrame()

    with _baostock_session():
        query_result = bs.query_history_k_data_plus(
            normalized_code,
            "date,open,high,low,close,preclose,volume,amount,pctChg",
            start_date=start_date,
            end_date=end_date or "",
            frequency="d",
            adjustflag=adjustflag,
        )

        if query_result.error_code != "0":
            return pd.DataFrame()

        rows: list[list[str]] = []
        while query_result.next():
            rows.append(query_result.get_row_data())

    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows, columns=query_result.fields)
    for column in ["open", "high", "low", "close", "preclose", "volume", "amount", "pctChg"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame["stock_code"] = normalized_code.split(".", 1)[1]
    frame["trade_date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
    frame["trade_time"] = frame["trade_date"] + " 00:00:00"
    frame["change_pct"] = frame["pctChg"]
    frame["change"] = frame["close"] - frame["preclose"]
    frame["turnover_ratio"] = None
    frame["pre_close"] = frame["preclose"]
    frame["fetched_at"] = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    frame["source"] = "baostock"

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
        "fetched_at",
    ]
    return frame[ordered_columns]
