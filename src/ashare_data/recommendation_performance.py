from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Mapping, Sequence

from .db import get_connection, init_db
from .paper_trading import DEFAULT_ACCOUNT_ID


PERFORMANCE_HORIZONS = (1, 3, 5, 10, 20)


def _utc_now_str() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def calculate_forward_metrics(
    base_price: float,
    bars: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    price = float(base_price or 0)
    if price <= 0:
        return {}

    usable_bars = [
        dict(bar)
        for bar in bars
        if float(bar.get("close") or 0) > 0
    ][: max(PERFORMANCE_HORIZONS)]
    metrics: dict[str, dict[str, Any]] = {}
    for horizon in PERFORMANCE_HORIZONS:
        if len(usable_bars) < horizon:
            continue
        window = usable_bars[:horizon]
        end_bar = window[-1]
        end_close = float(end_bar.get("close") or 0)
        highs = [float(item.get("high") or item.get("close") or 0) for item in window]
        lows = [float(item.get("low") or item.get("close") or 0) for item in window]
        metrics[str(horizon)] = {
            "return_pct": round(((end_close / price) - 1) * 100, 2),
            "max_favorable_pct": round(((max(highs) / price) - 1) * 100, 2),
            "max_adverse_pct": round(((min(lows) / price) - 1) * 100, 2),
            "end_date": end_bar.get("trade_date"),
            "end_close": round(end_close, 3),
        }
    return metrics


def register_recommendation_items(
    connection,
    *,
    run_id: int,
    account_id: str,
    policy_version: str,
    market_context: Mapping[str, Any],
    recommendations: Sequence[Mapping[str, Any]],
    created_at: str,
) -> int:
    latest_trade_time = str(market_context.get("latest_trade_time") or "")
    recommendation_date = latest_trade_time[:10] if len(latest_trade_time) >= 10 else created_at[:10]
    rows = []
    for item in recommendations:
        if str(item.get("action") or "buy") != "buy":
            continue
        if int(item.get("recommended_quantity") or 0) < 100:
            continue
        base_price = float(item.get("price") or 0)
        stock_code = str(item.get("stock_code") or "").strip()
        if not stock_code or base_price <= 0:
            continue
        rows.append(
            {
                "run_id": int(run_id),
                "account_id": account_id,
                "stock_code": stock_code,
                "stock_name": item.get("stock_name"),
                "recommendation_date": recommendation_date,
                "base_price": base_price,
                "score": item.get("score"),
                "market_regime": market_context.get("regime"),
                "policy_version": policy_version,
                "created_at": created_at,
                "updated_at": created_at,
            }
        )
    if not rows:
        return 0
    connection.executemany(
        """
        INSERT INTO ai_recommendation_items (
            run_id, account_id, stock_code, stock_name, recommendation_date,
            base_price, score, market_regime, policy_version, created_at, updated_at
        )
        VALUES (
            :run_id, :account_id, :stock_code, :stock_name, :recommendation_date,
            :base_price, :score, :market_regime, :policy_version, :created_at, :updated_at
        )
        ON CONFLICT(run_id, stock_code) DO NOTHING
        """,
        rows,
    )
    return len(rows)


def refresh_recommendation_performance(
    *,
    account_id: str = DEFAULT_ACCOUNT_ID,
) -> int:
    init_db()
    with get_connection() as connection:
        items = connection.execute(
            """
            SELECT id, stock_code, recommendation_date, base_price
            FROM ai_recommendation_items
            WHERE account_id = ?
              AND evaluated_trade_days < ?
            ORDER BY recommendation_date, id
            """,
            (account_id, max(PERFORMANCE_HORIZONS)),
        ).fetchall()

        updates = []
        now = _utc_now_str()
        for item in items:
            bars = connection.execute(
                """
                SELECT trade_date, close, high, low
                FROM daily_bars
                WHERE stock_code = ?
                  AND trade_date > ?
                  AND adjust_type = 1
                  AND k_type = 1
                  AND close > 0
                ORDER BY trade_date
                LIMIT ?
                """,
                (item["stock_code"], item["recommendation_date"], max(PERFORMANCE_HORIZONS)),
            ).fetchall()
            metrics = calculate_forward_metrics(float(item["base_price"]), bars)
            evaluated_days = min(len(bars), max(PERFORMANCE_HORIZONS))
            latest_date = bars[evaluated_days - 1]["trade_date"] if evaluated_days else None
            updates.append(
                (
                    json.dumps(metrics, ensure_ascii=False),
                    evaluated_days,
                    latest_date,
                    now,
                    int(item["id"]),
                )
            )
        if updates:
            connection.executemany(
                """
                UPDATE ai_recommendation_items
                SET metrics_json = ?, evaluated_trade_days = ?,
                    latest_evaluated_date = ?, updated_at = ?
                WHERE id = ?
                """,
                updates,
            )
    return len(updates)


def load_recommendation_performance(
    *,
    account_id: str = DEFAULT_ACCOUNT_ID,
    limit: int = 60,
    refresh: bool = True,
) -> dict[str, Any]:
    init_db()
    if refresh:
        refresh_recommendation_performance(account_id=account_id)
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM ai_recommendation_items
            WHERE account_id = ?
            ORDER BY recommendation_date DESC, id DESC
            LIMIT ?
            """,
            (account_id, max(1, min(int(limit or 60), 300))),
        ).fetchall()

    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        try:
            item["metrics"] = json.loads(item.pop("metrics_json") or "{}")
        except ValueError:
            item["metrics"] = {}
        items.append(item)

    horizons = {
        str(horizon): _summarize_horizon(items, horizon)
        for horizon in PERFORMANCE_HORIZONS
    }
    five_day = horizons["5"]
    calibration = _calibration_summary(five_day)
    return {
        "calibration": calibration,
        "horizons": horizons,
        "by_regime": _summarize_by_regime(items, horizon=5),
        "tracked_count": len(items),
        "pending_count": sum(1 for item in items if int(item.get("evaluated_trade_days") or 0) < 5),
        "items": items,
        "updated_at": _utc_now_str(),
    }


def _summarize_horizon(items: Sequence[Mapping[str, Any]], horizon: int) -> dict[str, Any]:
    samples = [
        item["metrics"][str(horizon)]
        for item in items
        if str(horizon) in (item.get("metrics") or {})
    ]
    if not samples:
        return {
            "sample_count": 0,
            "win_count": 0,
            "win_rate_pct": None,
            "avg_return_pct": None,
            "avg_favorable_pct": None,
            "avg_adverse_pct": None,
        }
    returns = [float(item["return_pct"]) for item in samples]
    favorable = [float(item["max_favorable_pct"]) for item in samples]
    adverse = [float(item["max_adverse_pct"]) for item in samples]
    win_count = sum(1 for value in returns if value > 0)
    return {
        "sample_count": len(samples),
        "win_count": win_count,
        "win_rate_pct": round(win_count / len(samples) * 100, 2),
        "avg_return_pct": round(sum(returns) / len(returns), 2),
        "avg_favorable_pct": round(sum(favorable) / len(favorable), 2),
        "avg_adverse_pct": round(sum(adverse) / len(adverse), 2),
    }


def _summarize_by_regime(items: Sequence[Mapping[str, Any]], *, horizon: int) -> list[dict[str, Any]]:
    regimes = sorted({str(item.get("market_regime") or "未知") for item in items})
    return [
        {
            "market_regime": regime,
            **_summarize_horizon(
                [item for item in items if str(item.get("market_regime") or "未知") == regime],
                horizon,
            ),
        }
        for regime in regimes
    ]


def _calibration_summary(five_day: Mapping[str, Any]) -> dict[str, Any]:
    sample_count = int(five_day.get("sample_count") or 0)
    win_rate = five_day.get("win_rate_pct")
    average_return = five_day.get("avg_return_pct")
    if sample_count < 20:
        return {
            "status": "collecting",
            "label": "可信度积累中",
            "summary": f"已有 {sample_count} 个完整的5日样本，至少积累20个后再判断策略稳定性。",
        }
    if float(win_rate or 0) >= 55 and float(average_return or 0) > 0:
        return {
            "status": "stable",
            "label": "历史表现较稳",
            "summary": f"5日胜率 {float(win_rate):.2f}%，平均收益 {float(average_return):.2f}%。",
        }
    if float(win_rate or 0) < 45 or float(average_return or 0) < 0:
        return {
            "status": "tighten",
            "label": "建议继续收紧",
            "summary": f"5日胜率 {float(win_rate or 0):.2f}%，平均收益 {float(average_return or 0):.2f}%，当前规则需要降权。",
        }
    return {
        "status": "observe",
        "label": "历史表现待确认",
        "summary": f"5日胜率 {float(win_rate or 0):.2f}%，平均收益 {float(average_return or 0):.2f}%。",
    }
