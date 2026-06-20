from __future__ import annotations

from datetime import date, datetime, timedelta
import json
import math
import re
from typing import Any

import requests

from .db import get_connection, init_db
from .watchlist import normalize_stock_code


EASTMONEY_STOCK_CHANGES_URL = "https://push2ex.eastmoney.com/getAllStockChanges"

BULLISH_CHANGE_TYPES = {
    8201,
    8202,
    8193,
    4,
    32,
    64,
    8207,
    8209,
    8211,
    8213,
    8215,
    16,
}
BEARISH_CHANGE_TYPES = {
    8204,
    8203,
    8194,
    8,
    128,
    8208,
    8210,
    8212,
    8214,
    8216,
}
ALL_CHANGE_TYPES = [
    8201,
    8202,
    8193,
    4,
    32,
    64,
    8207,
    8209,
    8211,
    8213,
    8215,
    16,
    8204,
    8203,
    8194,
    8,
    128,
    8208,
    8210,
    8212,
    8214,
    8216,
]
CHANGE_TYPE_NAMES = {
    8201: "火箭发射",
    8202: "快速反弹",
    8193: "大笔买入",
    4: "封涨停板",
    32: "打开跌停板",
    64: "有大买盘",
    8207: "竞价上涨",
    8209: "高开5日线",
    8211: "向上缺口",
    8213: "60日新高",
    8215: "60日大幅上涨",
    16: "打开涨停板",
    8204: "加速下跌",
    8203: "高台跳水",
    8194: "大笔卖出",
    8: "封跌停板",
    128: "有大卖盘",
    8208: "竞价下跌",
    8210: "低开5日线",
    8212: "向下缺口",
    8214: "60日新低",
    8216: "60日大幅下跌",
}

_SESSION = requests.Session()


def load_stock_change_types() -> dict[str, Any]:
    return {
        "all": [
            {
                "value": change_type,
                "label": CHANGE_TYPE_NAMES.get(change_type, f"类型{change_type}"),
                "direction": _direction_for_type(change_type),
            }
            for change_type in ALL_CHANGE_TYPES
        ],
        "bullish": [
            {"value": change_type, "label": CHANGE_TYPE_NAMES[change_type], "direction": "bullish"}
            for change_type in ALL_CHANGE_TYPES
            if change_type in BULLISH_CHANGE_TYPES
        ],
        "bearish": [
            {"value": change_type, "label": CHANGE_TYPE_NAMES[change_type], "direction": "bearish"}
            for change_type in ALL_CHANGE_TYPES
            if change_type in BEARISH_CHANGE_TYPES
        ],
    }


def sync_stock_changes(
    *,
    change_types: str | list[int] | None = None,
    page: int = 1,
    page_size: int = 80,
    persist: bool = True,
) -> dict[str, Any]:
    init_db()
    normalized_types = _parse_change_types(change_types)
    payload = fetch_stock_changes(
        change_types=normalized_types,
        page=page,
        page_size=page_size,
    )
    saved_count = save_stock_change_events(payload["items"]) if persist else 0
    payload["saved_count"] = saved_count
    payload["persisted"] = persist
    payload["change_types"] = normalized_types
    return payload


def fetch_stock_changes(
    *,
    change_types: list[int] | None = None,
    page: int = 1,
    page_size: int = 80,
) -> dict[str, Any]:
    selected_types = change_types or ALL_CHANGE_TYPES
    page = max(1, int(page or 1))
    page_size = max(10, min(int(page_size or 80), 500))
    now = datetime.now()
    fetched_at = _utc_now_str()
    trade_date = _resolve_event_trade_date(now)

    response = _SESSION.get(
        EASTMONEY_STOCK_CHANGES_URL,
        params={
            "type": ",".join(str(item) for item in selected_types),
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "pageindex": page - 1,
            "pagesize": page_size,
            "dpt": "wzchanges",
            "_": int(now.timestamp() * 1000),
        },
        headers={
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://quote.eastmoney.com/changes/",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
        },
        timeout=12,
    )
    response.raise_for_status()
    data = _loads_json_or_jsonp(response.text)
    payload = data.get("data") if isinstance(data, dict) else {}
    rows = payload.get("allstock") if isinstance(payload, dict) else []
    total = int(payload.get("tc") or 0) if isinstance(payload, dict) else 0

    items = [
        _normalize_change_row(row, trade_date=trade_date, fetched_at=fetched_at)
        for row in rows or []
        if isinstance(row, dict)
    ]
    items = [item for item in items if item["stock_code"]]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "fetched_at": fetched_at,
        "trade_date": trade_date,
    }


def save_stock_change_events(items: list[dict[str, Any]]) -> int:
    if not items:
        return 0

    now = _utc_now_str()
    rows = [
        {
            "event_key": item["event_key"],
            "trade_date": item["trade_date"],
            "event_time": item["event_time"],
            "stock_code": item["stock_code"],
            "stock_name": item["stock_name"],
            "market_code": item["market_code"],
            "change_type": item["change_type"],
            "type_name": item["type_name"],
            "direction": item["direction"],
            "price": item["price"],
            "change_pct": item["change_pct"],
            "volume": item["volume"],
            "amount": item["amount"],
            "raw_info": item["raw_info"],
            "source": "eastmoney",
            "fetched_at": item["fetched_at"],
            "created_at": now,
        }
        for item in items
    ]
    with get_connection() as connection:
        before_changes = connection.total_changes
        connection.executemany(
            """
            INSERT OR IGNORE INTO stock_change_events (
                event_key, trade_date, event_time, stock_code, stock_name, market_code,
                change_type, type_name, direction, price, change_pct, volume, amount,
                raw_info, source, fetched_at, created_at
            )
            VALUES (
                :event_key, :trade_date, :event_time, :stock_code, :stock_name, :market_code,
                :change_type, :type_name, :direction, :price, :change_pct, :volume, :amount,
                :raw_info, :source, :fetched_at, :created_at
            )
            """,
            rows,
        )
        return connection.total_changes - before_changes


def load_stock_change_history(
    *,
    page: int = 1,
    page_size: int = 80,
    keyword: str = "",
    start_date: str | None = None,
    end_date: str | None = None,
    direction: str = "all",
    change_types: str | list[int] | None = None,
) -> dict[str, Any]:
    init_db()
    page = max(1, int(page or 1))
    page_size = max(10, min(int(page_size or 80), 200))
    offset = (page - 1) * page_size
    conditions: list[str] = []
    params: list[Any] = []

    normalized_keyword = keyword.strip()
    if normalized_keyword:
        search = f"%{normalized_keyword}%"
        conditions.append("(stock_code LIKE ? OR stock_name LIKE ? OR type_name LIKE ?)")
        params.extend([search, search, search])

    normalized_start = _normalize_date_text(start_date)
    normalized_end = _normalize_date_text(end_date)
    if normalized_start:
        conditions.append("trade_date >= ?")
        params.append(normalized_start)
    if normalized_end:
        conditions.append("trade_date <= ?")
        params.append(normalized_end)

    if direction in {"bullish", "bearish", "neutral"}:
        conditions.append("direction = ?")
        params.append(direction)

    normalized_types = _parse_change_types(change_types, allow_empty=True)
    if normalized_types:
        placeholders = ", ".join("?" for _ in normalized_types)
        conditions.append(f"change_type IN ({placeholders})")
        params.extend(normalized_types)

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    with get_connection() as connection:
        total_row = connection.execute(
            f"SELECT COUNT(*) AS total FROM stock_change_events {where_sql}",
            params,
        ).fetchone()
        rows = connection.execute(
            f"""
            SELECT
                id, trade_date, event_time, stock_code, stock_name, market_code,
                change_type, type_name, direction, price, change_pct, volume,
                amount, fetched_at, created_at
            FROM stock_change_events
            {where_sql}
            ORDER BY trade_date DESC, event_time DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()
        summary_rows = connection.execute(
            f"""
            SELECT direction, COUNT(*) AS count
            FROM stock_change_events
            {where_sql}
            GROUP BY direction
            """,
            params,
        ).fetchall()

    return {
        "items": [_row_to_item(dict(row)) for row in rows],
        "total": int(total_row["total"] or 0) if total_row else 0,
        "page": page,
        "page_size": page_size,
        "summary": {
            "bullish": _summary_count(summary_rows, "bullish"),
            "bearish": _summary_count(summary_rows, "bearish"),
            "neutral": _summary_count(summary_rows, "neutral"),
        },
    }


def _normalize_change_row(row: dict[str, Any], *, trade_date: str, fetched_at: str) -> dict[str, Any]:
    change_type = _to_int(row.get("t")) or 0
    event_time = _format_event_time(row.get("tm"))
    stock_code = normalize_stock_code(str(row.get("c") or ""))
    raw_info = str(row.get("i") or "")
    item: dict[str, Any] = {
        "trade_date": trade_date,
        "event_time": event_time,
        "stock_code": stock_code,
        "stock_name": str(row.get("n") or stock_code).strip(),
        "market_code": _to_int(row.get("m")),
        "market": _market_from_code(stock_code),
        "change_type": change_type,
        "type_name": CHANGE_TYPE_NAMES.get(change_type, f"类型{change_type}"),
        "direction": _direction_for_type(change_type),
        "price": None,
        "change_pct": None,
        "volume": None,
        "amount": None,
        "raw_info": raw_info,
        "fetched_at": fetched_at,
    }
    _parse_change_info(raw_info, item)
    item["event_key"] = _build_event_key(item)
    return item


def _parse_change_info(raw_info: str, item: dict[str, Any]) -> None:
    parts = [part.strip() for part in raw_info.split(",")]
    change_type = int(item.get("change_type") or 0)

    if change_type in {8201, 8202, 8203, 8204, 8207, 8208, 8209, 8210}:
        item["change_pct"] = _rate_to_percent(parts, 0)
        item["price"] = _part_float(parts, 1)
        return

    if change_type in {8193, 8194, 64, 128}:
        item["volume"] = _part_float(parts, 0)
        item["price"] = _part_float(parts, 1)
        item["change_pct"] = _rate_to_percent(parts, 2)
        item["amount"] = _part_float(parts, 3)
        return

    if change_type in {4, 8}:
        item["price"] = _part_float(parts, 0)
        item["volume"] = _part_float(parts, 1)
        item["change_pct"] = _rate_to_percent(parts, 3)
        return

    if change_type in {16, 32}:
        item["price"] = _part_float(parts, 0)
        item["change_pct"] = _rate_to_percent(parts, 1)
        return

    if change_type in {8213, 8214}:
        item["price"] = _part_float(parts, 0)
        item["change_pct"] = _rate_to_percent(parts, 2)
        return

    if change_type in {8215, 8216}:
        item["change_pct"] = _rate_to_percent(parts, 0)
        item["price"] = _part_float(parts, 1)
        return

    item["volume"] = _part_float(parts, 0)
    item["price"] = _part_float(parts, 1)
    item["change_pct"] = _rate_to_percent(parts, 2)
    item["amount"] = _part_float(parts, 3)


def _loads_json_or_jsonp(text: str) -> dict[str, Any]:
    stripped = text.strip()
    match = re.match(r"^[\w$]+\((.*)\)$", stripped, re.DOTALL)
    if match:
        stripped = match.group(1)
    return json.loads(stripped)


def _parse_change_types(change_types: str | list[int] | None, *, allow_empty: bool = False) -> list[int]:
    if change_types is None:
        return [] if allow_empty else list(ALL_CHANGE_TYPES)
    if isinstance(change_types, str):
        raw_items = [item.strip() for item in change_types.split(",") if item.strip()]
    else:
        raw_items = list(change_types)

    parsed: list[int] = []
    for raw_item in raw_items:
        value = _to_int(raw_item)
        if value is None or value not in CHANGE_TYPE_NAMES or value in parsed:
            continue
        parsed.append(value)
    if parsed or allow_empty:
        return parsed
    return list(ALL_CHANGE_TYPES)


def _format_event_time(value: Any) -> str:
    raw = str(value or "").strip()
    if raw.isdigit():
        raw = raw.zfill(6)
        return f"{raw[:2]}:{raw[2:4]}:{raw[4:6]}"
    return datetime.now().strftime("%H:%M:%S")


def _resolve_event_trade_date(now: datetime) -> str:
    if now.weekday() < 5:
        return now.date().isoformat()
    offset = now.weekday() - 4
    return (now.date() - timedelta(days=offset)).isoformat()


def _build_event_key(item: dict[str, Any]) -> str:
    return "|".join(
        [
            str(item.get("trade_date") or ""),
            str(item.get("event_time") or ""),
            str(item.get("stock_code") or ""),
            str(item.get("change_type") or ""),
            _stable_number(item.get("price")),
            _stable_number(item.get("volume")),
            _stable_number(item.get("amount")),
        ]
    )


def _stable_number(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return ""
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _row_to_item(row: dict[str, Any]) -> dict[str, Any]:
    row["market"] = _market_from_code(str(row.get("stock_code") or ""))
    return row


def _market_from_code(stock_code: str) -> str:
    code = normalize_stock_code(stock_code)
    if code.startswith(("600", "601", "603", "605", "688", "689")):
        return "SH"
    if code.startswith(("000", "001", "002", "003", "300", "301")):
        return "SZ"
    if code.startswith(("430", "440", "830", "831", "832", "833", "834", "835", "836", "837", "838", "839", "870", "871", "872", "873", "874", "875", "876", "877", "878", "879", "880", "920")):
        return "BJ"
    return ""


def _direction_for_type(change_type: int) -> str:
    if change_type in BULLISH_CHANGE_TYPES:
        return "bullish"
    if change_type in BEARISH_CHANGE_TYPES:
        return "bearish"
    return "neutral"


def _summary_count(rows: list[Any], direction: str) -> int:
    for row in rows:
        if row["direction"] == direction:
            return int(row["count"] or 0)
    return 0


def _normalize_date_text(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10]).isoformat()
    except ValueError:
        return None


def _rate_to_percent(parts: list[str], index: int) -> float | None:
    value = _part_float(parts, index)
    if value is None:
        return None
    return value * 100


def _part_float(parts: list[str], index: int) -> float | None:
    if index >= len(parts):
        return None
    return _to_float(parts[index])


def _to_int(value: Any) -> int | None:
    if value in (None, "", "--"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    if value in (None, "", "--"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _utc_now_str() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
