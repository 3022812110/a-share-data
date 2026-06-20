from __future__ import annotations

from datetime import date, datetime, timedelta
import json
from typing import Any

import pandas as pd

from .db import get_connection
from .watchlist import normalize_stock_code

try:
    import akshare as ak
except ImportError:  # pragma: no cover - optional dependency at runtime
    ak = None


MAJOR_INDEX_CODES = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000300": "沪深300",
}


def _require_akshare() -> None:
    if ak is None:
        raise RuntimeError("akshare is not installed")


def _utc_now_str() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _today_trade_date() -> date:
    current = datetime.now()
    candidate = current.date()
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    if current.hour < 9 and candidate == current.date():
        candidate -= timedelta(days=1)
        while candidate.weekday() >= 5:
            candidate -= timedelta(days=1)
    return candidate


def _trade_time_for_snapshot() -> str:
    current = datetime.now()
    trade_date = _today_trade_date()
    if trade_date == current.date() and 9 <= current.hour < 15:
        return current.strftime("%Y-%m-%d %H:%M:%S")
    return f"{trade_date.isoformat()} 15:00:00"


def _safe_float(value: Any) -> float | None:
    if value in (None, "", "--"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _adjust_value(adjust_type: int) -> str:
    return {
        0: "",
        1: "qfq",
        2: "hfq",
    }.get(adjust_type, "")


def fetch_akshare_daily_bars(
    stock_code: str,
    start_date: str,
    end_date: str | None = None,
    *,
    adjust_type: int = 1,
) -> pd.DataFrame:
    _require_akshare()
    normalized_code = normalize_stock_code(stock_code)
    frame = ak.stock_zh_a_hist(
        symbol=normalized_code,
        period="daily",
        start_date=start_date.replace("-", ""),
        end_date=(end_date or _today_trade_date().isoformat()).replace("-", ""),
        adjust=_adjust_value(adjust_type),
    )
    if frame is None or frame.empty:
        return pd.DataFrame()

    result = frame.copy()
    result["trade_date"] = pd.to_datetime(result["日期"]).dt.strftime("%Y-%m-%d")
    result["trade_time"] = result["trade_date"] + " 15:00:00"
    result["stock_code"] = result["股票代码"].astype(str).map(normalize_stock_code)
    result["open"] = pd.to_numeric(result["开盘"], errors="coerce")
    result["close"] = pd.to_numeric(result["收盘"], errors="coerce")
    result["high"] = pd.to_numeric(result["最高"], errors="coerce")
    result["low"] = pd.to_numeric(result["最低"], errors="coerce")
    result["volume"] = pd.to_numeric(result["成交量"], errors="coerce")
    result["amount"] = pd.to_numeric(result["成交额"], errors="coerce")
    result["change_pct"] = pd.to_numeric(result["涨跌幅"], errors="coerce")
    result["change"] = pd.to_numeric(result["涨跌额"], errors="coerce")
    result["turnover_ratio"] = pd.to_numeric(result["换手率"], errors="coerce")
    result["pre_close"] = result["close"].shift(1)
    result["source"] = "akshare"
    return result[
        [
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
        ]
    ]


def fetch_akshare_stock_profile(stock_code: str) -> dict[str, Any]:
    _require_akshare()
    normalized_code = normalize_stock_code(stock_code)
    frame = ak.stock_individual_info_em(symbol=normalized_code)
    if frame is None or frame.empty:
        return {}

    raw = {
        str(row["item"]): row["value"]
        for row in frame.to_dict(orient="records")
        if row.get("item")
    }
    return {
        "stock_code": normalized_code,
        "stock_name": raw.get("股票简称"),
        "latest_price": _safe_float(raw.get("最新")),
        "industry": raw.get("行业"),
        "listing_date": str(raw.get("上市时间")) if raw.get("上市时间") else None,
        "total_share_capital": _safe_float(raw.get("总股本")),
        "circulating_share_capital": _safe_float(raw.get("流通股")),
        "total_market_value": _safe_float(raw.get("总市值")),
        "circulating_market_value": _safe_float(raw.get("流通市值")),
        "raw_items": raw,
    }


def get_stock_profile(stock_code: str, *, max_age_hours: int = 24) -> dict[str, Any]:
    normalized_code = normalize_stock_code(stock_code)
    with get_connection() as connection:
        cached = connection.execute(
            """
            SELECT payload_json, updated_at
            FROM stock_profile_cache
            WHERE stock_code = ?
            """,
            (normalized_code,),
        ).fetchone()

    if cached:
        updated_at = datetime.fromisoformat(cached["updated_at"].replace("Z", "+00:00"))
        if datetime.utcnow() - updated_at.replace(tzinfo=None) <= timedelta(hours=max_age_hours):
            return json.loads(cached["payload_json"])

    try:
        profile = fetch_akshare_stock_profile(normalized_code)
    except Exception:
        return json.loads(cached["payload_json"]) if cached else {}
    if profile:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO stock_profile_cache (stock_code, payload_json, source, updated_at)
                VALUES (?, ?, 'akshare', ?)
                ON CONFLICT(stock_code) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                (normalized_code, json.dumps(profile, ensure_ascii=False), _utc_now_str()),
            )
    return profile


def fetch_market_index_snapshot() -> list[dict[str, Any]]:
    _require_akshare()
    frame = ak.stock_zh_index_spot_sina()
    if frame is None or frame.empty:
        return []

    trade_time = _trade_time_for_snapshot()
    fetched_at = _utc_now_str()
    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        index_code = str(record.get("代码", "")).strip()
        if index_code not in MAJOR_INDEX_CODES:
            continue
        rows.append(
            {
                "index_code": index_code,
                "index_name": MAJOR_INDEX_CODES[index_code],
                "price": _safe_float(record.get("最新价")),
                "change_amount": _safe_float(record.get("涨跌额")),
                "change_pct": _safe_float(record.get("涨跌幅")),
                "pre_close": _safe_float(record.get("昨收")),
                "open": _safe_float(record.get("今开")),
                "high": _safe_float(record.get("最高")),
                "low": _safe_float(record.get("最低")),
                "volume": _safe_float(record.get("成交量")),
                "amount": _safe_float(record.get("成交额")),
                "source": "akshare",
                "trade_time": trade_time,
                "fetched_at": fetched_at,
            }
        )
    return rows


def fetch_market_exchange_overview() -> dict[str, Any]:
    _require_akshare()
    report_date = _today_trade_date().strftime("%Y%m%d")
    sse_frame = ak.stock_sse_summary()
    szse_frame = ak.stock_szse_summary(date=report_date)

    sse_map = {
        str(row["项目"]): row["股票"]
        for row in sse_frame.to_dict(orient="records")
        if row.get("项目")
    }
    sz_stock_row = next(
        (row for row in szse_frame.to_dict(orient="records") if row.get("证券类别") == "股票"),
        {},
    )

    overview = {
        "report_date": str(sse_map.get("报告时间") or report_date),
        "sse": {
            "listed_companies": int(float(sse_map.get("上市公司", 0) or 0)),
            "listed_stocks": int(float(sse_map.get("上市股票", 0) or 0)),
            "total_market_value": _safe_float(sse_map.get("总市值")),
            "circulating_market_value": _safe_float(sse_map.get("流通市值")),
            "average_pe": _safe_float(sse_map.get("平均市盈率")),
        },
        "szse": {
            "stock_count": int(float(sz_stock_row.get("数量", 0) or 0)),
            "trading_amount": (_safe_float(sz_stock_row.get("成交金额")) or 0) / 100000000,
            "total_market_value": (_safe_float(sz_stock_row.get("总市值")) or 0) / 100000000,
            "circulating_market_value": (_safe_float(sz_stock_row.get("流通市值")) or 0) / 100000000,
        },
    }
    return overview


def upsert_market_index_snapshot(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO market_index_snapshot (
                index_code, index_name, price, change_amount, change_pct,
                open, high, low, pre_close, volume, amount, source, trade_time, fetched_at
            )
            VALUES (
                :index_code, :index_name, :price, :change_amount, :change_pct,
                :open, :high, :low, :pre_close, :volume, :amount, :source, :trade_time, :fetched_at
            )
            ON CONFLICT(index_code) DO UPDATE SET
                index_name = excluded.index_name,
                price = excluded.price,
                change_amount = excluded.change_amount,
                change_pct = excluded.change_pct,
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                pre_close = excluded.pre_close,
                volume = excluded.volume,
                amount = excluded.amount,
                source = excluded.source,
                trade_time = excluded.trade_time,
                fetched_at = excluded.fetched_at
            """,
            rows,
        )


def upsert_market_overview_cache(payload: dict[str, Any]) -> None:
    if not payload:
        return
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO market_overview_cache (cache_key, payload_json, source, fetched_at)
            VALUES ('latest', ?, 'akshare', ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                payload_json = excluded.payload_json,
                source = excluded.source,
                fetched_at = excluded.fetched_at
            """,
            (json.dumps(payload, ensure_ascii=False), _utc_now_str()),
        )
