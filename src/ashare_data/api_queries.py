from __future__ import annotations

from datetime import datetime, timedelta
import json
import sqlite3

from .db import get_connection
from .research import build_stock_research_card
from .sync import sync_daily_bars_for_codes


SORTABLE_COLUMNS = {
    "stock_code": "s.stock_code",
    "stock_name": "s.stock_name",
    "price": "s.price",
    "change_pct": "s.change_pct",
    "turnover_ratio": "s.turnover_ratio",
    "volume_ratio": "s.volume_ratio",
    "pe_ratio": "s.pe_ratio",
    "pb_ratio": "s.pb_ratio",
    "circulating_market_value": "s.circulating_market_value",
    "total_market_value": "s.total_market_value",
    "buy_distance_pct": """
        CASE
            WHEN COALESCE(w.buy_price, wi.buy_price) IS NOT NULL
             AND COALESCE(w.buy_price, wi.buy_price) != 0
             AND s.price IS NOT NULL
            THEN ((s.price / COALESCE(w.buy_price, wi.buy_price)) - 1.0) * 100
            ELSE NULL
        END
    """,
}

SCREENING_PRESETS = {
    "momentum": {
        "label": "强势动量",
        "min_price": 5.0,
        "max_price": None,
        "min_change_pct": 2.0,
        "min_turnover_ratio": 2.0,
        "min_volume_ratio": 1.2,
        "min_total_market_value": 30.0,
        "max_total_market_value": None,
        "max_pe_ratio": None,
    },
    "rebound": {
        "label": "放量回升",
        "min_price": 3.0,
        "max_price": None,
        "min_change_pct": 0.5,
        "min_turnover_ratio": 1.0,
        "min_volume_ratio": 1.0,
        "min_total_market_value": None,
        "max_total_market_value": None,
        "max_pe_ratio": None,
    },
}


def _dicts(rows: list[sqlite3.Row]) -> list[dict[str, object]]:
    return [dict(row) for row in rows]


def _format_condition_text(label: str, value: float | None, suffix: str = "") -> str | None:
    if value is None:
        return None
    if float(value).is_integer():
        number = str(int(value))
    else:
        number = f"{value:.2f}"
    return f"{label}{number}{suffix}"


def _build_screening_config(
    *,
    preset: str,
    query: str,
    min_change_pct: float | None,
    min_turnover_ratio: float | None,
    min_volume_ratio: float | None,
    min_price: float | None,
    max_price: float | None,
    max_pe_ratio: float | None,
    min_total_market_value: float | None,
    max_total_market_value: float | None,
) -> tuple[dict[str, float | str | None], list[str]]:
    config = dict(SCREENING_PRESETS.get(preset, SCREENING_PRESETS["momentum"]))
    applied_conditions = [f"策略：{config['label']}"]
    query_text = query.strip()

    if query_text:
        if any(keyword in query_text for keyword in ("放量", "爆量")):
            config["min_volume_ratio"] = max(float(config["min_volume_ratio"] or 0), 1.8)
            applied_conditions.append("关键词：放量")
        if any(keyword in query_text for keyword in ("强势", "突破", "新高", "趋势")):
            config["min_change_pct"] = max(float(config["min_change_pct"] or 0), 3.0)
            config["min_turnover_ratio"] = max(float(config["min_turnover_ratio"] or 0), 2.5)
            applied_conditions.append("关键词：强势突破")
        if any(keyword in query_text for keyword in ("反弹", "回升", "修复")):
            config["min_change_pct"] = max(float(config["min_change_pct"] or 0), 1.0)
            config["min_volume_ratio"] = max(float(config["min_volume_ratio"] or 0), 1.3)
            applied_conditions.append("关键词：回升修复")
        if any(keyword in query_text for keyword in ("低价", "低位")):
            current_max = config["max_price"]
            config["max_price"] = 20.0 if current_max is None else min(float(current_max), 20.0)
            applied_conditions.append("关键词：价格不高于20元")
        if any(keyword in query_text for keyword in ("高换手", "活跃")):
            config["min_turnover_ratio"] = max(float(config["min_turnover_ratio"] or 0), 3.0)
            applied_conditions.append("关键词：高换手")
        if any(keyword in query_text for keyword in ("低估", "估值低")):
            current_max = config["max_pe_ratio"]
            config["max_pe_ratio"] = 30.0 if current_max is None else min(float(current_max), 30.0)
            applied_conditions.append("关键词：低估值")
        if "大市值" in query_text:
            config["min_total_market_value"] = max(float(config["min_total_market_value"] or 0), 200.0)
            applied_conditions.append("关键词：大市值")
        if "小市值" in query_text:
            current_max = config["max_total_market_value"]
            config["max_total_market_value"] = 300.0 if current_max is None else min(float(current_max), 300.0)
            applied_conditions.append("关键词：小市值")

    overrides = {
        "min_change_pct": min_change_pct,
        "min_turnover_ratio": min_turnover_ratio,
        "min_volume_ratio": min_volume_ratio,
        "min_price": min_price,
        "max_price": max_price,
        "max_pe_ratio": max_pe_ratio,
        "min_total_market_value": min_total_market_value,
        "max_total_market_value": max_total_market_value,
    }
    override_labels = {
        "min_change_pct": ("涨幅至少", "%"),
        "min_turnover_ratio": ("换手率至少", "%"),
        "min_volume_ratio": ("量比至少", ""),
        "min_price": ("价格不低于", "元"),
        "max_price": ("价格不高于", "元"),
        "max_pe_ratio": ("PE 不高于", ""),
        "min_total_market_value": ("总市值不低于", "亿"),
        "max_total_market_value": ("总市值不高于", "亿"),
    }
    for key, value in overrides.items():
        if value is None:
            continue
        config[key] = value
        condition = _format_condition_text(override_labels[key][0], value, override_labels[key][1])
        if condition:
            applied_conditions.append(condition)

    return config, applied_conditions


def load_market_overview() -> dict[str, object]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS stock_count,
                SUM(CASE WHEN change_pct > 0 THEN 1 ELSE 0 END) AS rising_count,
                SUM(CASE WHEN change_pct < 0 THEN 1 ELSE 0 END) AS falling_count,
                SUM(CASE WHEN change_pct >= 9.8 THEN 1 ELSE 0 END) AS limit_up_count,
                SUM(CASE WHEN change_pct <= -9.8 THEN 1 ELSE 0 END) AS limit_down_count,
                ROUND(SUM(COALESCE(amount, 0)) / 100000000, 2) AS total_turnover_yi,
                MAX(fetched_at) AS latest_fetch,
                MAX(trade_time) AS latest_trade_time,
                (SELECT COUNT(*) FROM watchlist WHERE is_active = 1) AS watchlist_count
            FROM stock_market_snapshot
            """
        ).fetchone()
        index_rows = connection.execute(
            """
            SELECT index_code, index_name, price, change_amount, change_pct, amount, trade_time, fetched_at
            FROM market_index_snapshot
            ORDER BY CASE index_code
                WHEN 'sh000001' THEN 1
                WHEN 'sz399001' THEN 2
                WHEN 'sz399006' THEN 3
                WHEN 'sh000300' THEN 4
                ELSE 99
            END, index_code
            """
        ).fetchall()
        overview_cache = connection.execute(
            """
            SELECT payload_json, fetched_at
            FROM market_overview_cache
            WHERE cache_key = 'latest'
            """
        ).fetchone()

    result = dict(row) if row else {}
    result["major_indices"] = _dicts(index_rows)
    result["exchange_overview"] = json.loads(overview_cache["payload_json"]) if overview_cache else {}
    result["exchange_overview_fetched_at"] = overview_cache["fetched_at"] if overview_cache else None
    return result


def load_market_page(
    *,
    page: int = 1,
    page_size: int = 100,
    search: str = "",
    sort_by: str = "change_pct",
    sort_order: str = "desc",
    watchlist_only: bool = False,
) -> dict[str, object]:
    page = max(1, page)
    page_size = max(10, min(page_size, 200))
    offset = (page - 1) * page_size
    search_term = f"%{search.strip()}%"
    sort_sql = SORTABLE_COLUMNS.get(sort_by, SORTABLE_COLUMNS["change_pct"])
    direction = "ASC" if sort_order.lower() == "asc" else "DESC"

    conditions = [
        "(? = '' OR s.stock_code LIKE ? OR s.stock_name LIKE ?)",
    ]
    params: list[object] = [search.strip(), search_term, search_term]
    if watchlist_only:
        conditions.append("COALESCE(w.is_active, 0) = 1")

    where_sql = " AND ".join(conditions)

    with get_connection() as connection:
        total_row = connection.execute(
            f"""
            SELECT COUNT(*) AS total
            FROM stock_market_snapshot s
            LEFT JOIN watchlist w ON w.stock_code = s.stock_code
            LEFT JOIN watchlist wi ON wi.stock_code = s.stock_code
            WHERE {where_sql}
            """,
            params,
        ).fetchone()

        rows = connection.execute(
            f"""
            SELECT
                s.stock_code,
                s.market,
                s.stock_name,
                s.price,
                s.change_amount,
                s.change_pct,
                s.turnover_ratio,
                s.volume_ratio,
                s.pe_ratio,
                s.pb_ratio,
                s.circulating_market_value,
                s.total_market_value,
                s.trade_time,
                s.fetched_at,
                COALESCE(w.display_name, wi.display_name) AS display_name,
                COALESCE(w.notes, wi.notes) AS notes,
                COALESCE(w.buy_price, wi.buy_price) AS buy_price,
                COALESCE(w.take_profit_price, wi.take_profit_price) AS take_profit_price,
                COALESCE(w.stop_loss_price, wi.stop_loss_price) AS stop_loss_price,
                COALESCE(w.default_trade_quantity, wi.default_trade_quantity, 100) AS default_trade_quantity,
                w.last_synced_at,
                CASE
                    WHEN COALESCE(w.is_active, 0) = 1 THEN 1
                    ELSE 0
                END AS in_watchlist,
                CASE
                    WHEN COALESCE(w.buy_price, wi.buy_price) IS NOT NULL
                     AND COALESCE(w.buy_price, wi.buy_price) != 0
                     AND s.price IS NOT NULL
                    THEN ROUND(((s.price / COALESCE(w.buy_price, wi.buy_price)) - 1.0) * 100, 2)
                    ELSE NULL
                END AS buy_distance_pct,
                CASE
                    WHEN COALESCE(w.take_profit_price, wi.take_profit_price) IS NOT NULL
                     AND s.price IS NOT NULL AND s.price != 0
                    THEN ROUND(((COALESCE(w.take_profit_price, wi.take_profit_price) / s.price) - 1.0) * 100, 2)
                    ELSE NULL
                END AS upside_to_target_pct,
                CASE
                    WHEN COALESCE(w.stop_loss_price, wi.stop_loss_price) IS NOT NULL
                     AND s.price IS NOT NULL AND s.price != 0
                    THEN ROUND(((COALESCE(w.stop_loss_price, wi.stop_loss_price) / s.price) - 1.0) * 100, 2)
                    ELSE NULL
                END AS downside_to_stop_pct
            FROM stock_market_snapshot s
            LEFT JOIN watchlist w ON w.stock_code = s.stock_code AND w.is_active = 1
            LEFT JOIN watchlist wi ON wi.stock_code = s.stock_code
            WHERE {where_sql}
            ORDER BY {sort_sql} {direction}, s.stock_code ASC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()

    total = int(total_row["total"]) if total_row and total_row["total"] is not None else 0
    return {
        "items": _dicts(rows),
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def load_stock_detail(stock_code: str) -> dict[str, object]:
    with get_connection() as connection:
        snapshot_row = connection.execute(
            """
            SELECT
                s.*,
                COALESCE(w.display_name, wi.display_name) AS display_name,
                COALESCE(w.notes, wi.notes) AS notes,
                COALESCE(w.buy_price, wi.buy_price) AS buy_price,
                COALESCE(w.take_profit_price, wi.take_profit_price) AS take_profit_price,
                COALESCE(w.stop_loss_price, wi.stop_loss_price) AS stop_loss_price,
                COALESCE(w.default_trade_quantity, wi.default_trade_quantity, 100) AS default_trade_quantity,
                CASE WHEN COALESCE(w.is_active, 0) = 1 THEN 1 ELSE 0 END AS in_watchlist,
                p.quantity AS paper_quantity,
                p.avg_cost AS paper_avg_cost,
                tp.id AS paper_plan_id,
                tp.entry_reason AS paper_entry_reason,
                tp.planned_holding_days AS paper_planned_holding_days,
                tp.stop_loss_price AS paper_stop_loss_price,
                tp.take_profit_price AS paper_take_profit_price,
                tp.invalidation_condition AS paper_invalidation_condition,
                tp.plan_note AS paper_plan_note
            FROM stock_market_snapshot s
            LEFT JOIN watchlist w ON w.stock_code = s.stock_code AND w.is_active = 1
            LEFT JOIN watchlist wi ON wi.stock_code = s.stock_code
            LEFT JOIN paper_positions p ON p.account_id = 'default' AND p.stock_code = s.stock_code
            LEFT JOIN paper_trade_plans tp ON tp.id = (
                SELECT id
                FROM paper_trade_plans
                WHERE account_id = 'default'
                  AND stock_code = s.stock_code
                  AND status = 'open'
                ORDER BY id DESC
                LIMIT 1
            )
            WHERE s.stock_code = ?
            """,
            (stock_code,),
        ).fetchone()
        daily_rows = connection.execute(
            """
            SELECT
                trade_date,
                open,
                close,
                high,
                low,
                volume,
                amount,
                change_pct,
                turnover_ratio,
                source
            FROM daily_bars
            WHERE stock_code = ?
            ORDER BY trade_date DESC
            LIMIT 120
            """,
            (stock_code,),
        ).fetchall()

    should_refresh_bars = False
    if not daily_rows:
        should_refresh_bars = True
    else:
        latest_daily_date = str(daily_rows[0]["trade_date"])
        should_refresh_bars = latest_daily_date < (datetime.now().date() - timedelta(days=7)).isoformat()

    if should_refresh_bars:
        sync_daily_bars_for_codes(
            stock_codes=[stock_code],
            start_date=(datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d"),
            end_date=datetime.now().strftime("%Y-%m-%d"),
        )
        with get_connection() as connection:
            daily_rows = connection.execute(
                """
                SELECT
                    trade_date,
                    open,
                    close,
                    high,
                    low,
                    volume,
                    amount,
                    change_pct,
                    turnover_ratio,
                    source
                FROM daily_bars
                WHERE stock_code = ?
                ORDER BY trade_date DESC
                LIMIT 120
                """,
                (stock_code,),
            ).fetchall()

    snapshot = dict(snapshot_row) if snapshot_row else None
    daily_bars = _dicts(daily_rows)
    research = build_stock_research_card(snapshot, daily_bars)

    return {
        "snapshot": snapshot,
        "daily_bars": daily_bars,
        "research": research,
    }


def load_ai_screening(
    *,
    preset: str = "momentum",
    limit: int = 60,
    query: str = "",
    scope: str = "all",
    min_change_pct: float | None = None,
    min_turnover_ratio: float | None = None,
    min_volume_ratio: float | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    max_pe_ratio: float | None = None,
    min_total_market_value: float | None = None,
    max_total_market_value: float | None = None,
) -> dict[str, object]:
    limit = max(10, min(limit, 200))
    config, applied_conditions = _build_screening_config(
        preset=preset,
        query=query,
        min_change_pct=min_change_pct,
        min_turnover_ratio=min_turnover_ratio,
        min_volume_ratio=min_volume_ratio,
        min_price=min_price,
        max_price=max_price,
        max_pe_ratio=max_pe_ratio,
        min_total_market_value=min_total_market_value,
        max_total_market_value=max_total_market_value,
    )

    where_clauses = [
        "s.price IS NOT NULL",
        "s.change_pct IS NOT NULL",
        "s.turnover_ratio IS NOT NULL",
        "s.volume_ratio IS NOT NULL",
        "s.market IN ('SH', 'SZ', 'BJ')",
    ]
    if scope == "watchlist":
        where_clauses.append("COALESCE(w.is_active, 0) = 1")

    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT
                s.stock_code,
                s.market,
                s.stock_name,
                s.price,
                s.change_pct,
                s.turnover_ratio,
                s.volume_ratio,
                s.pe_ratio,
                s.pb_ratio,
                s.circulating_market_value,
                s.total_market_value,
                s.trade_time,
                COALESCE(w.display_name, wi.display_name) AS display_name,
                COALESCE(w.buy_price, wi.buy_price) AS buy_price,
                COALESCE(w.default_trade_quantity, wi.default_trade_quantity, 100) AS default_trade_quantity,
                CASE WHEN COALESCE(w.is_active, 0) = 1 THEN 1 ELSE 0 END AS in_watchlist
            FROM stock_market_snapshot s
            LEFT JOIN watchlist w ON w.stock_code = s.stock_code AND w.is_active = 1
            LEFT JOIN watchlist wi ON wi.stock_code = s.stock_code
            WHERE {" AND ".join(where_clauses)}
            """
        ).fetchall()

    candidates: list[dict[str, object]] = []
    for row in rows:
        item = dict(row)
        price = float(item["price"] or 0)
        change_pct = float(item["change_pct"] or 0)
        turnover_ratio = float(item["turnover_ratio"] or 0)
        volume_ratio = float(item["volume_ratio"] or 0)
        pe_ratio = item["pe_ratio"]
        total_market_value = float(item["total_market_value"] or 0)
        reasons: list[str] = []

        if config["min_price"] is not None and price < float(config["min_price"]):
            continue
        if config["max_price"] is not None and price > float(config["max_price"]):
            continue
        if config["min_change_pct"] is not None and change_pct < float(config["min_change_pct"]):
            continue
        if config["min_turnover_ratio"] is not None and turnover_ratio < float(config["min_turnover_ratio"]):
            continue
        if config["min_volume_ratio"] is not None and volume_ratio < float(config["min_volume_ratio"]):
            continue
        if config["min_total_market_value"] is not None and total_market_value < float(config["min_total_market_value"]):
            continue
        if config["max_total_market_value"] is not None and total_market_value > float(config["max_total_market_value"]):
            continue
        if config["max_pe_ratio"] is not None:
            if pe_ratio is None or float(pe_ratio) <= 0 or float(pe_ratio) > float(config["max_pe_ratio"]):
                continue

        score = (
            min(change_pct, 10) * 12
            + min(volume_ratio, 4) * 18
            + min(turnover_ratio, 15) * 5
        )
        if preset == "rebound":
            score += min(max(change_pct, 0), 8) * 4

        if total_market_value:
            if 50 <= total_market_value <= 1200:
                score += 18
                reasons.append("市值区间适中")
            elif total_market_value < 50:
                score += 6
            else:
                score += 10

        if pe_ratio is not None and float(pe_ratio) > 0:
            pe = float(pe_ratio)
            if pe <= 60:
                score += 10
                reasons.append(f"估值不过热 PE {pe:.2f}")

        if item["in_watchlist"]:
            score += 6
            reasons.append("已在自选池")

        reasons.append(f"量比 {volume_ratio:.2f}")
        reasons.append(f"换手率 {turnover_ratio:.2f}%")
        reasons.append(f"涨幅 {change_pct:.2f}%")

        item["ai_score"] = round(score, 2)
        item["reasons"] = reasons
        candidates.append(item)

    candidates.sort(key=lambda item: (item["ai_score"], item["change_pct"], item["volume_ratio"]), reverse=True)
    summary = {
        "preset": preset,
        "preset_label": config["label"],
        "scope": scope,
        "query": query.strip(),
        "candidate_count": len(candidates),
        "returned_count": min(limit, len(candidates)),
        "applied_conditions": applied_conditions,
    }
    return {
        "summary": summary,
        "items": candidates[:limit],
    }
