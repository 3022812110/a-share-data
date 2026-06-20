from __future__ import annotations

import json
from typing import Any

from .api_queries import load_stock_detail
from .db import get_connection, init_db
from .market_feeds import load_market_insights
from .paper_trading import DEFAULT_ACCOUNT_ID, execute_paper_order, get_paper_portfolio, upsert_trade_plan
from .screening_ai import (
    API_KEY_REQUIRED_PROVIDERS,
    DEFAULT_BASE_URLS,
    SUPPORTED_PROVIDERS,
    _call_provider,
    _clamp_float,
    _clamp_int,
    _parse_json_object,
)


DEFAULT_TRADE_SYSTEM_PROMPT = (
    "你是A股交易计划助手。"
    "你的任务不是空泛点评，而是基于当前个股、持仓、交易计划和历史复盘，输出可以执行的交易票据。"
)
ALLOWED_ACTIONS = {"buy", "watch", "hold", "reduce", "sell", "avoid"}
ALLOWED_LEVELS = {"高", "中", "低"}


def generate_ai_trade_decision(
    *,
    stock_code: str,
    settings: dict[str, Any],
    account_id: str = DEFAULT_ACCOUNT_ID,
) -> dict[str, Any]:
    init_db()
    prepared = _prepare_ai_settings(settings)
    detail = load_stock_detail(stock_code)
    snapshot = detail.get("snapshot")
    if not snapshot:
        raise ValueError("未找到该股票快照")

    portfolio = get_paper_portfolio(account_id=account_id)
    recent_decisions = list_ai_trade_decisions(account_id=account_id, stock_code=stock_code, limit=6)
    messages = [
        {
            "role": "user",
            "content": _build_trade_user_prompt(
                snapshot=snapshot,
                detail=detail,
                portfolio=portfolio,
                recent_decisions=recent_decisions,
            ),
        }
    ]
    response_text = _call_provider(
        provider=prepared["provider"],
        model=prepared["model"],
        api_key=prepared["api_key"],
        base_url=prepared["base_url"],
        system_prompt=prepared["system_prompt"],
        messages=messages,
        temperature=prepared["temperature"],
        max_tokens=prepared["max_tokens"],
    )
    decision = _parse_trade_decision(response_text, snapshot=snapshot, portfolio=portfolio)
    return _insert_trade_decision(
        account_id=account_id,
        provider=prepared["provider"],
        model=prepared["model"],
        raw_response=response_text,
        decision=decision,
    )


def list_ai_trade_decisions(
    *,
    account_id: str = DEFAULT_ACCOUNT_ID,
    stock_code: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    init_db()
    params: list[object] = [account_id]
    where_sql = "WHERE account_id = ?"
    if stock_code:
        where_sql += " AND stock_code = ?"
        params.append(stock_code)
    params.append(max(1, min(limit, 100)))

    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT *
            FROM ai_trade_decisions
            {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [_decision_row_to_dict(row) for row in rows]


def get_latest_ai_trade_decision(
    stock_code: str,
    *,
    account_id: str = DEFAULT_ACCOUNT_ID,
) -> dict[str, Any] | None:
    decisions = list_ai_trade_decisions(account_id=account_id, stock_code=stock_code, limit=1)
    return decisions[0] if decisions else None


def generate_trade_recommendations(
    *,
    account_id: str = DEFAULT_ACCOUNT_ID,
    limit: int = 6,
) -> dict[str, Any]:
    """Build deterministic account-level training recommendations from local market data."""
    init_db()
    portfolio = get_paper_portfolio(account_id=account_id)
    account = portfolio.get("account") or {}
    cash_balance = float(account.get("cash_balance") or 0)
    total_assets = float(account.get("total_assets") or cash_balance or 0)
    target_limit = max(1, min(int(limit or 6), 12))

    with get_connection() as connection:
        market_row = connection.execute(
            """
            SELECT
                COUNT(*) AS stock_count,
                SUM(CASE WHEN change_pct > 0 THEN 1 ELSE 0 END) AS rising_count,
                SUM(CASE WHEN change_pct < 0 THEN 1 ELSE 0 END) AS falling_count,
                SUM(CASE WHEN change_pct >= 9.8 THEN 1 ELSE 0 END) AS limit_up_count,
                SUM(CASE WHEN change_pct <= -9.8 THEN 1 ELSE 0 END) AS limit_down_count,
                ROUND(SUM(COALESCE(amount, 0)) / 10000, 2) AS turnover_yi,
                MAX(trade_time) AS latest_trade_time,
                MAX(fetched_at) AS latest_fetch
            FROM stock_market_snapshot
            WHERE market IN ('SH', 'SZ')
            """
        ).fetchone()
        candidate_rows = connection.execute(
            """
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
                s.amount,
                s.total_market_value,
                s.trade_time,
                s.fetched_at
            FROM stock_market_snapshot s
            WHERE s.market IN ('SH', 'SZ')
              AND s.price BETWEEN 5 AND 150
              AND s.change_pct BETWEEN 2 AND 8.5
              AND s.turnover_ratio BETWEEN 3 AND 18
              AND s.volume_ratio BETWEEN 0.9 AND 3.2
              AND s.amount >= 50000
              AND s.total_market_value BETWEEN 80 AND 5000
              AND s.stock_name NOT LIKE '%ST%'
              AND s.stock_name NOT LIKE 'C%'
              AND (
                  s.pe_ratio IS NULL
                  OR (s.pe_ratio > 0 AND s.pe_ratio <= 100)
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM paper_positions p
                  WHERE p.account_id = ?
                    AND p.stock_code = s.stock_code
              )
            ORDER BY s.amount DESC
            LIMIT 180
            """,
            (account_id,),
        ).fetchall()

    market_context = _build_recommendation_market_context(market_row)
    try:
        insights = load_market_insights(max_age_seconds=900)
    except Exception:
        insights = {}
    topic_context = _build_recommendation_topic_context(insights)

    scored_candidates = []
    for row in candidate_rows:
        candidate = dict(row)
        theme_tags = _infer_theme_tags(candidate["stock_name"], candidate["stock_code"])
        score = _score_recommendation_candidate(
            candidate,
            market_context=market_context,
            theme_tags=theme_tags,
            topic_context=topic_context,
            total_assets=total_assets,
        )
        candidate["score"] = score
        candidate["theme_tags"] = theme_tags
        scored_candidates.append(candidate)

    scored_candidates.sort(key=lambda item: (item["score"], item.get("amount") or 0), reverse=True)

    target_deploy_cash = max(0.0, min(cash_balance * 0.7, total_assets * 0.7))
    per_position_cap = max(0.0, min(cash_balance * 0.3, total_assets * 0.25))
    planned_cash = 0.0
    recommendations: list[dict[str, Any]] = []

    for candidate in scored_candidates:
        if len(recommendations) >= target_limit:
            break
        remaining_budget = target_deploy_cash - planned_cash
        if remaining_budget <= 0:
            break

        price = float(candidate.get("price") or 0)
        if price <= 0:
            continue
        lot_cash = price * 100
        if lot_cash > cash_balance - planned_cash:
            continue
        if lot_cash > total_assets * 0.35:
            continue

        quantity_budget = min(per_position_cap, remaining_budget)
        quantity = int(quantity_budget // price // 100) * 100
        if quantity < 100:
            quantity = 100 if lot_cash <= remaining_budget else 0
        if quantity < 100:
            continue

        recommendation = _build_recommendation_item(
            candidate,
            quantity=quantity,
            market_context=market_context,
            topic_context=topic_context,
            total_assets=total_assets,
        )
        recommendations.append(recommendation)
        planned_cash += float(recommendation["estimated_cash"])

    return {
        "account": {
            "cash_balance": round(cash_balance, 2),
            "total_assets": round(total_assets, 2),
            "target_deploy_cash": round(target_deploy_cash, 2),
            "planned_cash": round(planned_cash, 2),
            "planned_position_pct": round((planned_cash / total_assets) * 100, 2) if total_assets else 0,
        },
        "market_context": market_context,
        "topic_context": topic_context,
        "recommendations": recommendations,
        "rules": [
            "9:35 后再确认盘面，不用集合竞价冲进去。",
            "单票高开超过 4% 先跳过，等回落或下一次信号。",
            "模拟账户优先训练仓位和止损，不用急着把上一笔亏损赚回来。",
            "盘后模拟提前买入可以复盘，但要标记为盘后单，避免和次日真实开盘买点混在一起。",
        ],
    }


def _build_recommendation_market_context(row) -> dict[str, Any]:
    market = dict(row) if row else {}
    stock_count = int(market.get("stock_count") or 0)
    rising_count = int(market.get("rising_count") or 0)
    falling_count = int(market.get("falling_count") or 0)
    limit_up_count = int(market.get("limit_up_count") or 0)
    limit_down_count = int(market.get("limit_down_count") or 0)
    rising_ratio = round((rising_count / stock_count) * 100, 2) if stock_count else 0
    turnover_yi = float(market.get("turnover_yi") or 0)

    if rising_ratio >= 65 and limit_up_count >= max(30, limit_down_count * 8):
        regime = "偏强"
        strategy = "可做小仓顺势，但避免追高潮。"
    elif rising_ratio <= 40 or limit_down_count > limit_up_count:
        regime = "偏弱"
        strategy = "以观察为主，只允许极小仓试错。"
    else:
        regime = "震荡"
        strategy = "只做强主线低吸，减少后排交易。"

    return {
        "stock_count": stock_count,
        "rising_count": rising_count,
        "falling_count": falling_count,
        "rising_ratio": rising_ratio,
        "limit_up_count": limit_up_count,
        "limit_down_count": limit_down_count,
        "turnover_yi": round(turnover_yi, 2),
        "latest_trade_time": market.get("latest_trade_time"),
        "latest_fetch": market.get("latest_fetch"),
        "regime": regime,
        "strategy": strategy,
    }


def _build_recommendation_topic_context(insights: dict[str, Any]) -> dict[str, Any]:
    hot_words = [
        str(item.get("word") or "").strip()
        for item in insights.get("hot_words") or []
        if str(item.get("word") or "").strip()
    ][:10]
    hot_topics = [
        {
            "title": item.get("title"),
            "stock_names": item.get("stock_names") or [],
            "url": item.get("url"),
        }
        for item in (insights.get("hot_topics") or [])[:5]
    ]
    sector_rankings = insights.get("sector_rankings") or {}
    sectors = [
        str(item.get("name") or "").strip()
        for item in [
            *(sector_rankings.get("industry") or [])[:4],
            *(sector_rankings.get("concept") or [])[:4],
        ]
        if str(item.get("name") or "").strip()
    ]
    sentiment = insights.get("sentiment") or {}
    return {
        "sentiment": {
            "label": sentiment.get("label") or "中性",
            "score": sentiment.get("score") or 50,
            "description": sentiment.get("description") or "热点数据不足，按盘面强弱处理。",
        },
        "hot_words": hot_words,
        "hot_topics": hot_topics,
        "sectors": sectors,
        "generated_at": insights.get("generated_at"),
    }


def _infer_theme_tags(stock_name: str, stock_code: str) -> list[str]:
    name = str(stock_name or "")
    code = str(stock_code or "")
    tags: list[str] = []
    theme_keywords = [
        ("算力通信", ("网宿", "中际", "新易盛", "天孚", "光迅", "亨通", "长飞", "通信", "光电", "光纤", "数据")),
        ("半导体电子", ("长电", "通富", "华天", "晶方", "兆易", "澜起", "聚辰", "江波龙", "芯", "微电", "电子", "封测", "半导体")),
        ("AI应用", ("蓝色光标", "传媒", "软件", "信息", "智能")),
        ("新能源", ("宁德", "欣旺达", "鹏辉", "金风", "风电", "锂", "电气", "电源", "储能", "光伏")),
        ("高端制造", ("西电", "中材", "激光", "机器人", "航天", "军工")),
        ("资源周期", ("铜", "锡", "钴", "稀土", "矿", "材料")),
    ]
    for tag, keywords in theme_keywords:
        if any(keyword in name for keyword in keywords):
            tags.append(tag)
    if code.startswith(("300", "301", "688")) and "成长股" not in tags:
        tags.append("成长股")
    return tags[:3]


def _score_recommendation_candidate(
    candidate: dict[str, Any],
    *,
    market_context: dict[str, Any],
    theme_tags: list[str],
    topic_context: dict[str, Any],
    total_assets: float,
) -> float:
    price = float(candidate.get("price") or 0)
    change_pct = float(candidate.get("change_pct") or 0)
    turnover_ratio = float(candidate.get("turnover_ratio") or 0)
    volume_ratio = float(candidate.get("volume_ratio") or 0)
    pe_ratio = candidate.get("pe_ratio")
    amount_yi = float(candidate.get("amount") or 0) / 10000
    market_value = float(candidate.get("total_market_value") or 0)

    score = 0.0
    score += min(change_pct, 8) * 8
    score += max(0.0, 28 - abs(turnover_ratio - 7) * 2.2)
    score += max(0.0, 20 - abs(volume_ratio - 1.6) * 8)
    score += min(amount_yi / 4, 28)
    if 120 <= market_value <= 1200:
        score += 18
    elif 80 <= market_value < 120 or 1200 < market_value <= 3000:
        score += 10
    else:
        score += 5

    if pe_ratio is not None:
        pe = float(pe_ratio)
        if 0 < pe <= 60:
            score += 12
        elif 60 < pe <= 90:
            score += 5

    topic_text = " ".join(
        [
            *[str(item) for item in topic_context.get("hot_words") or []],
            *[str(item) for item in topic_context.get("sectors") or []],
        ]
    )
    if theme_tags:
        score += 8
    topic_matches = {
        "算力通信": ("算力", "通信", "数据中心", "CPO", "光模块"),
        "半导体电子": ("半导体", "芯片", "存储", "封测", "电子"),
        "AI应用": ("AI", "人工智能", "传媒", "软件"),
        "新能源": ("新能源", "锂", "储能", "光伏", "风电"),
        "高端制造": ("机器人", "军工", "航天", "高端制造"),
        "资源周期": ("有色", "铜", "锡", "钴", "稀土"),
    }
    if any(any(keyword in topic_text for keyword in topic_matches.get(tag, (tag,))) for tag in theme_tags):
        score += 12
    if any(tag in {"算力通信", "半导体电子", "AI应用"} for tag in theme_tags):
        score += 8

    if change_pct > 7:
        score -= (change_pct - 7) * 4
    if turnover_ratio > 14:
        score -= (turnover_ratio - 14) * 1.5
    if price * 100 > total_assets * 0.28:
        score -= 16
    if market_context.get("regime") == "偏弱":
        score -= 10

    return round(score, 2)


def _build_recommendation_item(
    candidate: dict[str, Any],
    *,
    quantity: int,
    market_context: dict[str, Any],
    topic_context: dict[str, Any],
    total_assets: float,
) -> dict[str, Any]:
    price = float(candidate.get("price") or 0)
    change_pct = float(candidate.get("change_pct") or 0)
    turnover_ratio = float(candidate.get("turnover_ratio") or 0)
    volume_ratio = float(candidate.get("volume_ratio") or 0)
    amount_yi = round(float(candidate.get("amount") or 0) / 10000, 2)
    stop_loss_pct = 0.065 if change_pct >= 5 or turnover_ratio >= 10 else 0.055
    target_pct = 0.12 if change_pct >= 5 else 0.1
    risk_level = "高" if change_pct >= 7 or turnover_ratio >= 12 else "中"
    confidence = "中"
    if market_context.get("regime") == "偏强" and amount_yi >= 20 and candidate.get("theme_tags"):
        confidence = "高"

    entry_zone_low = round(price * (0.985 if change_pct < 5 else 0.97), 2)
    entry_zone_high = round(price * 1.015, 2)
    estimated_cash = round(price * quantity, 2)
    stop_loss_price = round(price * (1 - stop_loss_pct), 2)
    take_profit_price = round(price * (1 + target_pct), 2)
    position_pct = round((estimated_cash / total_assets) * 100, 2) if total_assets else 0
    theme_tags = candidate.get("theme_tags") or ["活跃股"]

    reasons = [
        f"市场环境{market_context.get('regime')}，上涨家数占比 {market_context.get('rising_ratio')}%。",
        f"个股涨幅 {change_pct:.2f}%，有强度但未进入 20cm 极端追高区。",
        f"换手 {turnover_ratio:.2f}%，量比 {volume_ratio:.2f}，成交约 {amount_yi:.2f} 亿，流动性适合训练。",
        f"主题标签：{'、'.join(theme_tags)}。",
    ]

    return {
        "stock_code": candidate.get("stock_code"),
        "market": candidate.get("market"),
        "stock_name": candidate.get("stock_name"),
        "action": "buy",
        "price": round(price, 2),
        "change_pct": round(change_pct, 2),
        "turnover_ratio": round(turnover_ratio, 2),
        "volume_ratio": round(volume_ratio, 2),
        "pe_ratio": candidate.get("pe_ratio"),
        "amount_yi": amount_yi,
        "total_market_value": candidate.get("total_market_value"),
        "score": candidate.get("score"),
        "theme_tags": theme_tags,
        "recommended_quantity": quantity,
        "estimated_cash": estimated_cash,
        "position_size_pct": position_pct,
        "entry_zone_low": entry_zone_low,
        "entry_zone_high": entry_zone_high,
        "stop_loss_price": stop_loss_price,
        "take_profit_price": take_profit_price,
        "planned_holding_days": 3,
        "confidence": confidence,
        "risk_level": risk_level,
        "entry_reason": f"{'、'.join(theme_tags)}方向活跃，放量上行但仓位可控。",
        "invalidation_condition": "高开超过4%不追；跌破止损位、放量长阴或主题退潮则退出。",
        "plan_note": "系统训练推荐：按小仓位试单，复盘重点看主线是否延续和止损是否执行。",
        "reasons": reasons,
        "news_context": {
            "sentiment": topic_context.get("sentiment"),
            "hot_words": topic_context.get("hot_words", [])[:6],
            "hot_topics": topic_context.get("hot_topics", [])[:3],
        },
    }


def apply_ai_trade_decision(
    decision_id: int,
    *,
    execute_order: bool = False,
    account_id: str = DEFAULT_ACCOUNT_ID,
) -> dict[str, Any]:
    init_db()
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM ai_trade_decisions
            WHERE id = ? AND account_id = ?
            """,
            (int(decision_id), account_id),
        ).fetchone()
        if not row:
            raise ValueError("AI 交易票据不存在")

    decision = _decision_row_to_dict(row)
    plan = upsert_trade_plan(
        stock_code=decision["stock_code"],
        entry_reason=decision.get("entry_reason"),
        planned_holding_days=decision.get("planned_holding_days"),
        stop_loss_price=decision.get("stop_loss_price"),
        take_profit_price=decision.get("take_profit_price"),
        invalidation_condition=decision.get("invalidation_condition"),
        plan_note=decision.get("plan_note"),
        account_id=account_id,
    )

    order_result = None
    status = "applied"
    executed_trade_id = None
    if execute_order:
        side = _decision_action_to_side(decision["action"])
        if not side:
            raise ValueError("这条 AI 票据不是可直接执行的交易动作")
        order_result = execute_paper_order(
            stock_code=decision["stock_code"],
            side=side,
            quantity=_resolve_execution_quantity(decision),
            note=f"执行 AI 建议 #{decision['id']}",
            plan={
                "entry_reason": decision.get("entry_reason"),
                "planned_holding_days": decision.get("planned_holding_days"),
                "stop_loss_price": decision.get("stop_loss_price"),
                "take_profit_price": decision.get("take_profit_price"),
                "invalidation_condition": decision.get("invalidation_condition"),
                "plan_note": decision.get("plan_note"),
            }
            if side == "buy"
            else None,
            account_id=account_id,
        )
        executed_trade_id = order_result.get("trade_id")
        status = "executed"

    updated_at = _utc_now_str()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE ai_trade_decisions
            SET status = ?,
                applied_plan_id = ?,
                executed_trade_id = COALESCE(?, executed_trade_id),
                updated_at = ?
            WHERE id = ?
            """,
            (status, int(plan["id"]), executed_trade_id, updated_at, int(decision_id)),
        )

        updated = connection.execute(
            """
            SELECT *
            FROM ai_trade_decisions
            WHERE id = ?
            """,
            (int(decision_id),),
        ).fetchone()

    return {
        "status": "ok",
        "decision": _decision_row_to_dict(updated),
        "plan": plan,
        "order": order_result,
    }


def sync_ai_trade_review(
    plan_id: int,
    *,
    exit_reason: str | None = None,
    review_rating: str | None = None,
    review_summary: str | None = None,
    lessons_learned: str | None = None,
    account_id: str = DEFAULT_ACCOUNT_ID,
) -> dict[str, Any] | None:
    init_db()
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM ai_trade_decisions
            WHERE account_id = ?
              AND applied_plan_id = ?
            ORDER BY
                CASE WHEN executed_trade_id IS NOT NULL THEN 0 ELSE 1 END,
                updated_at DESC,
                id DESC
            LIMIT 1
            """,
            (account_id, int(plan_id)),
        ).fetchone()
        if not row:
            return None

        reviewed_at = _utc_now_str()
        connection.execute(
            """
            UPDATE ai_trade_decisions
            SET exit_reason = COALESCE(?, exit_reason),
                review_rating = COALESCE(?, review_rating),
                review_summary = COALESCE(?, review_summary),
                lessons_learned = COALESCE(?, lessons_learned),
                reviewed_at = ?,
                status = CASE
                    WHEN status IN ('applied', 'executed') THEN 'reviewed'
                    ELSE status
                END,
                updated_at = ?
            WHERE id = ?
            """,
            (
                exit_reason,
                review_rating,
                review_summary,
                lessons_learned,
                reviewed_at,
                reviewed_at,
                int(row["id"]),
            ),
        )
        updated = connection.execute(
            """
            SELECT *
            FROM ai_trade_decisions
            WHERE id = ?
            """,
            (int(row["id"]),),
        ).fetchone()
    return _decision_row_to_dict(updated)


def _prepare_ai_settings(settings: dict[str, Any]) -> dict[str, Any]:
    provider = str(settings.get("provider") or "").strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError("暂不支持该 AI 服务商")

    model = str(settings.get("model") or "").strip()
    if not model:
        raise ValueError("请选择模型")

    api_key = str(settings.get("apiKey") or "").strip()
    base_url = str(settings.get("baseUrl") or "").strip() or DEFAULT_BASE_URLS.get(provider, "")
    if provider in API_KEY_REQUIRED_PROVIDERS and not api_key:
        raise ValueError("当前服务商需要 API Key")
    if provider == "custom" and not base_url:
        raise ValueError("自定义兼容接口需要填写 Base URL")

    system_prompt = str(settings.get("systemPrompt") or "").strip()
    combined_prompt = "\n\n".join(
        item
        for item in [system_prompt, DEFAULT_TRADE_SYSTEM_PROMPT]
        if item
    )
    return {
        "provider": provider,
        "model": model,
        "api_key": api_key,
        "base_url": base_url,
        "temperature": _clamp_float(settings.get("temperature"), default=0.2, minimum=0.0, maximum=1.5),
        "max_tokens": _clamp_int(settings.get("maxTokens"), default=2400, minimum=512, maximum=12000),
        "system_prompt": combined_prompt,
    }


def _build_trade_user_prompt(
    *,
    snapshot: dict[str, Any],
    detail: dict[str, Any],
    portfolio: dict[str, Any],
    recent_decisions: list[dict[str, Any]],
) -> str:
    research = detail.get("research") or {}
    feeds = detail.get("feeds") or {}
    ai_view = research.get("ai_view") or {}
    signals = research.get("signals") or {}
    position = next(
        (item for item in (portfolio.get("positions") or []) if item.get("stock_code") == snapshot.get("stock_code")),
        None,
    )
    recent_trades = [
        {
            "trade_time": item.get("trade_time"),
            "stock_code": item.get("stock_code"),
            "stock_name": item.get("stock_name"),
            "side": item.get("side"),
            "quantity": item.get("quantity"),
            "price": item.get("price"),
            "realized_pnl": item.get("realized_pnl"),
            "review_rating": item.get("review_rating"),
            "review_summary": item.get("review_summary"),
        }
        for item in (portfolio.get("trades") or [])[:12]
    ]
    notices = feeds.get("notices") or []
    reports = feeds.get("research_reports") or []
    telegraphs = feeds.get("telegraphs") or []
    margin_financing = feeds.get("margin_financing") or []

    context = {
        "target_stock": {
            "stock_code": snapshot.get("stock_code"),
            "stock_name": snapshot.get("stock_name"),
            "market": snapshot.get("market"),
            "price": snapshot.get("price"),
            "change_pct": snapshot.get("change_pct"),
            "turnover_ratio": snapshot.get("turnover_ratio"),
            "volume_ratio": snapshot.get("volume_ratio"),
            "pe_ratio": snapshot.get("pe_ratio"),
            "pb_ratio": snapshot.get("pb_ratio"),
            "total_market_value": snapshot.get("total_market_value"),
            "buy_price": snapshot.get("buy_price"),
            "take_profit_price": snapshot.get("take_profit_price"),
            "stop_loss_price": snapshot.get("stop_loss_price"),
            "default_trade_quantity": snapshot.get("default_trade_quantity"),
            "paper_quantity": snapshot.get("paper_quantity"),
            "paper_avg_cost": snapshot.get("paper_avg_cost"),
        },
        "research_card": {
            "verdict": ai_view.get("verdict"),
            "summary": ai_view.get("summary"),
            "bull_points": ai_view.get("bull_points") or [],
            "risk_points": ai_view.get("risk_points") or [],
            "confidence": ai_view.get("confidence"),
            "support_price": signals.get("support_price"),
            "resistance_price": signals.get("resistance_price"),
            "ma20": signals.get("ma20"),
            "ma60": signals.get("ma60"),
            "return_5d_pct": signals.get("return_5d_pct"),
            "return_20d_pct": signals.get("return_20d_pct"),
            "volatility_20d": signals.get("volatility_20d"),
        },
        "event_context": {
            "latest_notices": [
                {
                    "notice_date": item.get("notice_date"),
                    "title": item.get("title"),
                    "notice_type": item.get("notice_type"),
                }
                for item in notices[:4]
            ],
            "latest_reports": [
                {
                    "publish_date": item.get("publish_date"),
                    "title": item.get("title"),
                    "rating": item.get("rating"),
                    "org_name": item.get("org_name"),
                }
                for item in reports[:4]
            ],
            "latest_telegraphs": [
                {
                    "published_at": item.get("published_at"),
                    "title": item.get("title"),
                    "content": item.get("content"),
                }
                for item in telegraphs[:4]
            ],
            "margin_financing": [
                {
                    "trade_date": item.get("trade_date"),
                    "financing_balance": item.get("financing_balance"),
                    "financing_buy_amount": item.get("financing_buy_amount"),
                    "financing_repay_amount": item.get("financing_repay_amount"),
                    "financing_net_buy_amount": item.get("financing_net_buy_amount"),
                    "margin_balance": item.get("margin_balance"),
                }
                for item in margin_financing[:5]
            ],
        },
        "portfolio_context": {
            "account": portfolio.get("account"),
            "current_position": position,
            "recent_trades": recent_trades,
        },
        "recent_ai_decisions": recent_decisions[:6],
    }
    return "\n\n".join(
        [
            "请基于下面这只股票和当前模拟账户，输出一张结构化交易票据。",
            (
                "输出要求："
                "1. 只使用中文。"
                "2. 必须输出 JSON 对象，不要 Markdown 代码块。"
                "3. action 只能是 buy/watch/hold/reduce/sell/avoid。"
                "4. confidence 和 risk_level 只能是 高/中/低。"
                "5. quantity 必须是 100 的整数倍；如果不适合执行，填 0。"
                "6. summary 要先给结论，再给一句核心原因。"
                "7. reasoning 要给 3-5 条简短理由。"
                "8. 如果当前更适合观察而不是交易，action 应该是 watch 或 avoid。"
            ),
            (
                'JSON 格式固定为：'
                '{"action":"buy","summary":"",'
                '"entry_reason":"",'
                '"planned_holding_days":3,'
                '"buy_price":0,'
                '"stop_loss_price":0,'
                '"take_profit_price":0,'
                '"invalidation_condition":"",'
                '"plan_note":"",'
                '"quantity":100,'
                '"position_size_pct":10,'
                '"confidence":"中",'
                '"risk_level":"高",'
                '"reasoning":[""]}'
            ),
            f"输入上下文：{json.dumps(context, ensure_ascii=False)}",
        ]
    )


def _parse_trade_decision(
    response_text: str,
    *,
    snapshot: dict[str, Any],
    portfolio: dict[str, Any],
) -> dict[str, Any]:
    parsed = _parse_json_object(response_text.strip())
    if not parsed:
        raise RuntimeError("AI 没有返回可解析的交易票据 JSON")

    action = str(parsed.get("action") or "watch").strip().lower()
    if action not in ALLOWED_ACTIONS:
        action = "watch"

    summary = str(parsed.get("summary") or "").strip() or "建议先观察，等待更明确的交易信号。"
    reasoning = parsed.get("reasoning") if isinstance(parsed.get("reasoning"), list) else []
    reasoning = [str(item).strip() for item in reasoning if str(item).strip()][:5]

    current_quantity = int(snapshot.get("paper_quantity") or 0)
    default_quantity = max(100, int(snapshot.get("default_trade_quantity") or 100))
    quantity = _normalize_quantity_candidate(parsed.get("quantity"), action=action, default_quantity=default_quantity, current_quantity=current_quantity)

    confidence = _normalize_level(parsed.get("confidence"), default="中")
    risk_level = _normalize_level(parsed.get("risk_level"), default="中")

    return {
        "stock_code": str(snapshot.get("stock_code") or "").strip(),
        "stock_name": str(snapshot.get("stock_name") or "").strip(),
        "action": action,
        "summary": summary,
        "entry_reason": str(parsed.get("entry_reason") or parsed.get("reason") or summary).strip(),
        "planned_holding_days": _normalize_optional_int(parsed.get("planned_holding_days"), minimum=1, maximum=120),
        "buy_price": _normalize_optional_price(parsed.get("buy_price")),
        "stop_loss_price": _normalize_optional_price(parsed.get("stop_loss_price") or snapshot.get("stop_loss_price")),
        "take_profit_price": _normalize_optional_price(parsed.get("take_profit_price") or snapshot.get("take_profit_price")),
        "invalidation_condition": str(parsed.get("invalidation_condition") or "").strip() or None,
        "plan_note": str(parsed.get("plan_note") or "").strip() or None,
        "quantity": quantity,
        "position_size_pct": _normalize_optional_float(parsed.get("position_size_pct"), minimum=0, maximum=100),
        "confidence": confidence,
        "risk_level": risk_level,
        "reasoning": reasoning,
        "has_position": current_quantity > 0,
        "portfolio_position_count": int((portfolio.get("account") or {}).get("position_count") or 0),
    }


def _normalize_optional_price(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return round(numeric, 3) if numeric > 0 else None


def _normalize_optional_int(value: Any, *, minimum: int, maximum: int) -> int | None:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return None
    return max(minimum, min(maximum, numeric))


def _normalize_optional_float(value: Any, *, minimum: float, maximum: float) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return round(max(minimum, min(maximum, numeric)), 2)


def _normalize_quantity_candidate(value: Any, *, action: str, default_quantity: int, current_quantity: int) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = 0

    if action in {"sell", "reduce"}:
        if current_quantity <= 0:
            return 0
        candidate = numeric if numeric > 0 else min(default_quantity, current_quantity)
        candidate = min(candidate, current_quantity)
    elif action == "buy":
        candidate = numeric if numeric > 0 else default_quantity
    else:
        return 0

    candidate = max(100, candidate)
    return (candidate // 100) * 100


def _normalize_level(value: Any, *, default: str) -> str:
    normalized = str(value or "").strip()
    return normalized if normalized in ALLOWED_LEVELS else default


def _insert_trade_decision(
    *,
    account_id: str,
    provider: str,
    model: str,
    raw_response: str,
    decision: dict[str, Any],
) -> dict[str, Any]:
    now = _utc_now_str()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO ai_trade_decisions (
                account_id, stock_code, stock_name, action, summary, entry_reason,
                planned_holding_days, buy_price, stop_loss_price, take_profit_price,
                invalidation_condition, plan_note, quantity, position_size_pct,
                confidence, risk_level, reasoning_json, provider, model, raw_response,
                status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'generated', ?, ?)
            """,
            (
                account_id,
                decision["stock_code"],
                decision["stock_name"],
                decision["action"],
                decision["summary"],
                decision["entry_reason"],
                decision["planned_holding_days"],
                decision["buy_price"],
                decision["stop_loss_price"],
                decision["take_profit_price"],
                decision["invalidation_condition"],
                decision["plan_note"],
                decision["quantity"],
                decision["position_size_pct"],
                decision["confidence"],
                decision["risk_level"],
                json.dumps(decision["reasoning"], ensure_ascii=False),
                provider,
                model,
                raw_response,
                now,
                now,
            ),
        )
        row = connection.execute(
            """
            SELECT *
            FROM ai_trade_decisions
            WHERE id = ?
            """,
            (int(cursor.lastrowid),),
        ).fetchone()
    return _decision_row_to_dict(row)


def _decision_row_to_dict(row) -> dict[str, Any]:
    item = dict(row)
    try:
        item["reasoning"] = json.loads(item.get("reasoning_json") or "[]")
    except ValueError:
        item["reasoning"] = []
    item.pop("reasoning_json", None)
    return item


def _decision_action_to_side(action: str) -> str | None:
    if action == "buy":
        return "buy"
    if action in {"sell", "reduce"}:
        return "sell"
    return None


def _resolve_execution_quantity(decision: dict[str, Any]) -> int:
    quantity = int(decision.get("quantity") or 0)
    if quantity <= 0:
        raise ValueError("这条 AI 票据没有可执行的交易数量")
    return quantity


def _utc_now_str() -> str:
    from datetime import datetime

    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
