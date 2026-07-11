from __future__ import annotations

from datetime import date, datetime, timedelta
import json
from typing import Any

from .db import get_connection, init_db
from .market_clock import CHINA_TZ, china_now


def _normalize_now(now: datetime | None) -> datetime:
    if now is None:
        return china_now()
    if now.tzinfo is None:
        return now.replace(tzinfo=CHINA_TZ)
    return now.astimezone(CHINA_TZ)


def expected_latest_trade_date(now: datetime | None = None) -> date:
    """Return the latest trading day whose market data should already exist."""
    current = _normalize_now(now)
    init_db()
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT trade_date
            FROM trade_calendar
            WHERE trade_status = 1 AND trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT 2
            """,
            (current.date().isoformat(),),
        ).fetchall()

    if rows:
        latest = date.fromisoformat(rows[0]["trade_date"])
        # Before the open, yesterday's close is still the latest complete snapshot.
        if latest == current.date() and current.time().hour < 9 and len(rows) > 1:
            return date.fromisoformat(rows[1]["trade_date"])
        return latest

    fallback = current.date()
    if current.time().hour < 9:
        fallback -= timedelta(days=1)
    while fallback.weekday() >= 5:
        fallback -= timedelta(days=1)
    return fallback


def _dataset(
    *,
    key: str,
    label: str,
    latest: str | None,
    status: str,
    detail: str,
    count: int = 0,
    coverage: float | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "latest": latest,
        "status": status,
        "detail": detail,
        "count": count,
        "coverage": coverage,
    }


def _parse_cache_report_date(payload_json: str | None) -> str | None:
    if not payload_json:
        return None
    try:
        value = json.loads(payload_json).get("report_date")
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if value is None:
        return None
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text[:10] if len(text) >= 10 else text


def load_data_health(now: datetime | None = None) -> dict[str, Any]:
    current = _normalize_now(now)
    expected_date = expected_latest_trade_date(current).isoformat()
    market_is_open = current.weekday() < 5 and (
        (9 <= current.hour < 12) or (13 <= current.hour < 15) or (current.hour == 15 and current.minute == 0)
    )

    with get_connection() as connection:
        snapshot = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN substr(trade_time, 1, 10) >= ? THEN 1 ELSE 0 END) AS fresh,
                MIN(trade_time) AS oldest,
                MAX(trade_time) AS latest,
                MAX(fetched_at) AS fetched_at
            FROM stock_market_snapshot
            """,
            (expected_date,),
        ).fetchone()
        catalog = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN substr(updated_at, 1, 10) >= ? THEN 1 ELSE 0 END) AS fresh,
                MAX(updated_at) AS latest
            FROM stock_catalog
            WHERE market IN ('SH', 'SZ', 'BJ')
            """,
            (expected_date,),
        ).fetchone()
        indices = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN substr(trade_time, 1, 10) >= ? THEN 1 ELSE 0 END) AS fresh,
                MAX(trade_time) AS latest,
                MAX(fetched_at) AS fetched_at
            FROM market_index_snapshot
            """,
            (expected_date,),
        ).fetchone()
        daily = connection.execute(
            """
            WITH tracked AS (
                SELECT stock_code FROM watchlist WHERE is_active = 1
                UNION
                SELECT stock_code FROM paper_positions WHERE quantity > 0
            ),
            latest_by_stock AS (
                SELECT stock_code, MAX(trade_date) AS latest_date
                FROM daily_bars
                WHERE stock_code IN (SELECT stock_code FROM tracked)
                GROUP BY stock_code
            )
            SELECT
                (SELECT COUNT(*) FROM tracked) AS total,
                SUM(CASE WHEN l.latest_date >= ? THEN 1 ELSE 0 END) AS fresh,
                MAX(l.latest_date) AS latest
            FROM tracked t
            LEFT JOIN latest_by_stock l ON l.stock_code = t.stock_code
            """,
            (expected_date,),
        ).fetchone()
        changes = connection.execute(
            """
            SELECT COUNT(*) AS total, MAX(trade_date) AS latest, MAX(fetched_at) AS fetched_at
            FROM stock_change_events
            """
        ).fetchone()
        overview = connection.execute(
            """
            SELECT payload_json, fetched_at
            FROM market_overview_cache
            WHERE cache_key = 'latest'
            """
        ).fetchone()

    snapshot_total = int(snapshot["total"] or 0)
    snapshot_fresh = int(snapshot["fresh"] or 0)
    snapshot_coverage = snapshot_fresh / snapshot_total if snapshot_total else 0.0
    snapshot_status = "healthy" if snapshot_coverage >= 0.98 else "stale"

    catalog_total = int(catalog["total"] or 0)
    catalog_fresh = int(catalog["fresh"] or 0)
    catalog_latest = catalog["latest"] if catalog else None
    catalog_latest_date = str(catalog_latest)[:10] if catalog_latest else None
    catalog_status = (
        "healthy"
        if catalog_total >= 5000 and catalog_fresh / max(catalog_total, 1) >= 0.98
        else "stale"
    )

    if market_is_open and snapshot_status == "healthy" and snapshot["fetched_at"]:
        try:
            fetched = datetime.fromisoformat(str(snapshot["fetched_at"]).replace("Z", "+00:00"))
            fetched = fetched.astimezone(CHINA_TZ)
            if current - fetched > timedelta(minutes=5):
                snapshot_status = "warning"
        except ValueError:
            snapshot_status = "warning"

    index_total = int(indices["total"] or 0)
    index_fresh = int(indices["fresh"] or 0)
    index_status = "healthy" if index_total >= 4 and index_fresh >= 4 else "stale"

    daily_total = int(daily["total"] or 0)
    daily_fresh = int(daily["fresh"] or 0)
    daily_coverage = daily_fresh / daily_total if daily_total else 0.0
    daily_status = "healthy" if not daily_total or daily_coverage >= 0.8 else "warning"

    overview_date = _parse_cache_report_date(overview["payload_json"] if overview else None)
    overview_status = "healthy" if overview_date and overview_date >= expected_date else "warning"
    changes_latest = changes["latest"] if changes else None
    changes_status = "healthy" if changes_latest and changes_latest >= expected_date else "warning"

    datasets = [
        _dataset(
            key="market_snapshot",
            label="全市场行情",
            latest=snapshot["latest"],
            status=snapshot_status,
            detail=f"{snapshot_fresh}/{snapshot_total} 只股票达到 {expected_date}",
            count=snapshot_total,
            coverage=round(snapshot_coverage, 4),
        ),
        _dataset(
            key="stock_catalog",
            label="股票目录",
            latest=catalog_latest,
            status=catalog_status,
            detail=f"沪深京共 {catalog_total} 只，{catalog_fresh} 只目录记录已在目标日校验",
            count=catalog_total,
            coverage=round(catalog_fresh / max(catalog_total, 1), 4),
        ),
        _dataset(
            key="major_indices",
            label="主要指数",
            latest=indices["latest"],
            status=index_status,
            detail=f"{index_fresh}/{max(index_total, 4)} 个指数达到 {expected_date}",
            count=index_total,
            coverage=round(index_fresh / max(index_total, 1), 4),
        ),
        _dataset(
            key="exchange_overview",
            label="交易所总览",
            latest=overview_date,
            status=overview_status,
            detail=f"报告日 {overview_date or '未知'}",
            count=1 if overview else 0,
        ),
        _dataset(
            key="daily_bars",
            label="本地日 K",
            latest=daily["latest"],
            status=daily_status,
            detail=(
                f"{daily_fresh}/{daily_total} 只跟踪股票达到 {expected_date}"
                if daily_total
                else "暂无需要维护日 K 的自选或持仓"
            ),
            count=daily_total,
            coverage=round(daily_coverage, 4),
        ),
        _dataset(
            key="stock_changes",
            label="盘中异动",
            latest=changes_latest,
            status=changes_status,
            detail=f"本地累计 {int(changes['total'] or 0)} 条",
            count=int(changes["total"] or 0),
        ),
    ]

    critical_keys = {"market_snapshot", "stock_catalog", "major_indices"}
    critical_stale = [item for item in datasets if item["key"] in critical_keys and item["status"] == "stale"]
    warnings = [item for item in datasets if item["status"] == "warning"]
    if critical_stale:
        status = "stale"
    elif warnings or any(item["status"] == "warning" for item in datasets if item["key"] in critical_keys):
        status = "warning"
    else:
        status = "healthy"

    return {
        "status": status,
        "needs_refresh": bool(critical_stale) or snapshot_status == "warning",
        "expected_trade_date": expected_date,
        "checked_at": current.strftime("%Y-%m-%d %H:%M:%S"),
        "datasets": datasets,
        "stale_count": len(critical_stale),
        "warning_count": len(warnings),
    }
