from __future__ import annotations

from datetime import datetime, timedelta
import math
from typing import Iterable

import baostock as bs
import requests

from .akshare_client import (
    fetch_market_exchange_overview,
    fetch_market_index_snapshot,
    upsert_market_index_snapshot,
    upsert_market_overview_cache,
)
from .db import get_connection, init_db
from .watchlist import normalize_stock_code


TENCENT_QUOTE_URL = "http://qt.gtimg.cn/q="


def _utc_now_str() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _local_trade_time_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _normalize_trade_time(value: str | None, fallback: str) -> str:
    raw = (value or "").strip()
    if len(raw) == 14 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]} {raw[8:10]}:{raw[10:12]}:{raw[12:14]}"
    if len(raw) == 6 and raw.isdigit():
        return f"{fallback[:10]} {raw[:2]}:{raw[2:4]}:{raw[4:6]}"
    return fallback


def _safe_float(value: str | float | int | None) -> float | None:
    if value in (None, "", "--"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _market_from_code(stock_code: str) -> str:
    code = normalize_stock_code(stock_code)
    if code.startswith(("600", "601", "603", "605", "688", "689")):
        return "SH"
    if code.startswith(("000", "001", "002", "003", "300", "301")):
        return "SZ"
    if code.startswith(("430", "440", "830", "831", "832", "833", "834", "835", "836", "837", "838", "839", "870", "871", "872", "873", "874", "875", "876", "877", "878", "879", "880", "920")):
        return "BJ"
    return ""


def _is_a_share_code(stock_code: str, market: str | None = None) -> bool:
    code = normalize_stock_code(stock_code)
    selected_market = (market or _market_from_code(code)).upper()
    if selected_market == "SH":
        return code.startswith(("600", "601", "603", "605", "688", "689"))
    if selected_market == "SZ":
        return code.startswith(("000", "001", "002", "003", "300", "301"))
    if selected_market == "BJ":
        return code.startswith(
            (
                "430",
                "440",
                "830",
                "831",
                "832",
                "833",
                "834",
                "835",
                "836",
                "837",
                "838",
                "839",
                "870",
                "871",
                "872",
                "873",
                "874",
                "875",
                "876",
                "877",
                "878",
                "879",
                "880",
                "920",
            )
        )
    return False


def _tencent_symbol(stock_code: str, market: str | None = None) -> str:
    code = normalize_stock_code(stock_code)
    selected_market = (market or _market_from_code(code)).lower()
    return f"{selected_market}{code}" if selected_market else code


def _query_all_stock_rows(trade_date: str | None = None) -> list[dict[str, str]]:
    login_result = bs.login()
    try:
        if login_result.error_code != "0":
            raise RuntimeError(login_result.error_msg)
        query_result = bs.query_all_stock(day=trade_date or "")
        if query_result.error_code != "0":
            raise RuntimeError(query_result.error_msg)

        rows: list[dict[str, str]] = []
        while query_result.next():
            raw = dict(zip(query_result.fields, query_result.get_row_data()))
            code_with_market = str(raw.get("code", "")).strip()
            if "." not in code_with_market:
                continue
            market, stock_code = code_with_market.split(".", 1)
            stock_code = normalize_stock_code(stock_code)
            if not _is_a_share_code(stock_code, market.upper()):
                continue
            rows.append(
                {
                    "stock_code": stock_code,
                    "stock_name": str(raw.get("code_name", stock_code)).strip() or stock_code,
                    "market": market.upper(),
                    "source": "baostock",
                    "updated_at": _utc_now_str(),
                }
            )
        return rows
    finally:
        bs.logout()


def _load_catalog_from_db() -> list[dict[str, str]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT stock_code, stock_name, market, source, updated_at
            FROM stock_catalog
            WHERE market IN ('SH', 'SZ', 'BJ')
            ORDER BY stock_code
            """
        ).fetchall()

    return [
        {
            "stock_code": row["stock_code"],
            "stock_name": row["stock_name"] or row["stock_code"],
            "market": row["market"] or _market_from_code(row["stock_code"]),
            "source": row["source"] or "stock_catalog",
            "updated_at": row["updated_at"] or _utc_now_str(),
        }
        for row in rows
        if row["stock_code"]
    ]


def _resolve_full_market_catalog(trade_date: str | None = None) -> tuple[list[dict[str, str]], str | None]:
    if trade_date:
        try:
            rows = _query_all_stock_rows(trade_date=trade_date)
        except Exception:
            rows = []
        if rows:
            return rows, trade_date

    baostock_available = True
    try:
        rows = _query_all_stock_rows()
    except Exception:
        rows = []
        baostock_available = False
    if rows:
        return rows, trade_date

    # BaoStock occasionally accepts the TCP connection but fails during login
    # with "network receive error". Retrying another 14 logins only blocks the
    # refresh endpoint for minutes, so use the persisted catalog immediately.
    if baostock_available:
        today = datetime.now().date()
        for offset in range(1, 15):
            candidate = (today - timedelta(days=offset)).isoformat()
            try:
                rows = _query_all_stock_rows(trade_date=candidate)
            except Exception:
                break
            if rows:
                return rows, candidate

    rows = _load_catalog_from_db()
    if rows:
        return rows, "stock_catalog"

    return [], None


def _chunked(items: list[dict[str, str]], size: int) -> Iterable[list[dict[str, str]]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def fetch_market_snapshot(stock_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    if not stock_rows:
        return []

    fetched_at = _utc_now_str()
    trade_time = _local_trade_time_str()
    results: list[dict[str, object]] = []

    for chunk in _chunked(stock_rows, 60):
        symbol_map = {
            _tencent_symbol(row["stock_code"], row.get("market")): row
            for row in chunk
        }
        query_symbols = ",".join(symbol_map.keys())
        response = requests.get(
            f"{TENCENT_QUOTE_URL}{query_symbols}",
            timeout=10,
            headers={"Referer": "https://gu.qq.com/"},
        )
        response.raise_for_status()

        for item in response.text.split(";"):
            fields = item.split("~")
            if len(fields) <= 49:
                continue
            symbol_token = fields[0].split("v_", 1)[-1].split("=", 1)[0].strip()
            base_row = symbol_map.get(symbol_token)
            if not base_row:
                continue
            stock_code = normalize_stock_code(fields[2] or base_row["stock_code"])
            results.append(
                {
                    "stock_code": stock_code,
                    "market": base_row.get("market") or _market_from_code(stock_code),
                    "stock_name": (fields[1] or base_row["stock_name"]).strip(),
                    "price": _safe_float(fields[3]),
                    "change_amount": _safe_float(fields[31]),
                    "change_pct": _safe_float(fields[32]),
                    "turnover_ratio": _safe_float(fields[38]),
                    "volume_ratio": _safe_float(fields[49]),
                    "pe_ratio": _safe_float(fields[39]),
                    "pb_ratio": _safe_float(fields[46]),
                    "amplitude": _safe_float(fields[43]),
                    "open": _safe_float(fields[5]),
                    "high": _safe_float(fields[33]),
                    "low": _safe_float(fields[34]),
                    "pre_close": _safe_float(fields[4]),
                    "volume": _safe_float(fields[36]),
                    "amount": _safe_float(fields[37]),
                    "circulating_market_value": _safe_float(fields[44]),
                    "total_market_value": _safe_float(fields[45]),
                    "source": "tencent",
                    "trade_time": _normalize_trade_time(fields[30], trade_time),
                    "fetched_at": fetched_at,
                }
            )

    return results


def upsert_stock_catalog(rows: list[dict[str, str]]) -> None:
    if not rows:
        return

    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO stock_catalog (stock_code, stock_name, source, market, group_name, updated_at)
            VALUES (:stock_code, :stock_name, :source, :market, NULL, :updated_at)
            ON CONFLICT(stock_code) DO UPDATE SET
                stock_name = excluded.stock_name,
                source = excluded.source,
                market = excluded.market,
                updated_at = excluded.updated_at
            """,
            rows,
        )


def upsert_market_snapshot(rows: list[dict[str, object]]) -> None:
    if not rows:
        return

    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO stock_market_snapshot (
                stock_code, market, stock_name, price, change_amount, change_pct,
                turnover_ratio, volume_ratio, pe_ratio, pb_ratio, amplitude,
                open, high, low, pre_close, volume, amount,
                circulating_market_value, total_market_value, source,
                trade_time, fetched_at
            )
            VALUES (
                :stock_code, :market, :stock_name, :price, :change_amount, :change_pct,
                :turnover_ratio, :volume_ratio, :pe_ratio, :pb_ratio, :amplitude,
                :open, :high, :low, :pre_close, :volume, :amount,
                :circulating_market_value, :total_market_value, :source,
                :trade_time, :fetched_at
            )
            ON CONFLICT(stock_code) DO UPDATE SET
                market = excluded.market,
                stock_name = excluded.stock_name,
                price = excluded.price,
                change_amount = excluded.change_amount,
                change_pct = excluded.change_pct,
                turnover_ratio = excluded.turnover_ratio,
                volume_ratio = excluded.volume_ratio,
                pe_ratio = excluded.pe_ratio,
                pb_ratio = excluded.pb_ratio,
                amplitude = excluded.amplitude,
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                pre_close = excluded.pre_close,
                volume = excluded.volume,
                amount = excluded.amount,
                circulating_market_value = excluded.circulating_market_value,
                total_market_value = excluded.total_market_value,
                source = excluded.source,
                trade_time = excluded.trade_time,
                fetched_at = excluded.fetched_at
            """,
            rows,
        )


def _load_catalog_for_codes(stock_codes: list[str]) -> list[dict[str, str]]:
    normalized_codes = [normalize_stock_code(code) for code in stock_codes if normalize_stock_code(code)]
    if not normalized_codes:
        return []

    placeholders = ", ".join("?" for _ in normalized_codes)
    with get_connection() as connection:
        found_rows = connection.execute(
            f"""
            SELECT stock_code, stock_name, market
            FROM stock_catalog
            WHERE stock_code IN ({placeholders})
            """,
            normalized_codes,
        ).fetchall()

    found_map = {
        row["stock_code"]: {
            "stock_code": row["stock_code"],
            "stock_name": row["stock_name"] or row["stock_code"],
            "market": row["market"] or _market_from_code(row["stock_code"]),
            "source": "stock_catalog",
            "updated_at": _utc_now_str(),
        }
        for row in found_rows
    }
    rows: list[dict[str, str]] = []
    for code in normalized_codes:
        rows.append(
            found_map.get(
                code,
                {
                    "stock_code": code,
                    "stock_name": code,
                    "market": _market_from_code(code),
                    "source": "derived",
                    "updated_at": _utc_now_str(),
                },
            )
        )
    return [row for row in rows if row["market"]]


def sync_stock_market_snapshot(
    *,
    trade_date: str | None = None,
    stock_codes: list[str] | None = None,
) -> dict[str, object]:
    init_db()

    if stock_codes:
        catalog_rows = _load_catalog_for_codes(stock_codes)
        resolved_trade_date = trade_date
    else:
        catalog_rows, resolved_trade_date = _resolve_full_market_catalog(trade_date=trade_date)

    upsert_stock_catalog(catalog_rows)
    if not stock_codes and catalog_rows:
        valid_codes = [row["stock_code"] for row in catalog_rows]
        placeholders = ", ".join("?" for _ in valid_codes)
        with get_connection() as connection:
            connection.execute(
                f"DELETE FROM stock_market_snapshot WHERE stock_code NOT IN ({placeholders})",
                valid_codes,
            )
    snapshot_rows = fetch_market_snapshot(catalog_rows)
    upsert_market_snapshot(snapshot_rows)
    try:
        index_rows = fetch_market_index_snapshot()
        upsert_market_index_snapshot(index_rows)
    except Exception:
        index_rows = []

    try:
        market_overview = fetch_market_exchange_overview()
        upsert_market_overview_cache(market_overview)
    except Exception:
        market_overview = {}

    return {
        "catalog_count": len(catalog_rows),
        "snapshot_count": len(snapshot_rows),
        "index_count": len(index_rows),
        "market_overview_ready": bool(market_overview),
        "resolved_trade_date": resolved_trade_date,
        "fetched_at": _utc_now_str(),
    }
