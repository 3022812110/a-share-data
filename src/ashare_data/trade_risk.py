from __future__ import annotations

from typing import Any, Mapping, Sequence


RISK_POLICY_VERSION = "2026-07-20.v2"
MIN_MARKET_STOCK_COUNT = 3000
MAX_DAILY_LOSS_PCT = -2.0
MAX_ACCOUNT_LOSS_PCT = -8.0


MARKET_STATS_SQL = """
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


def load_market_risk_context(connection, *, expected_trade_date: str | None = None) -> dict[str, Any]:
    row = connection.execute(MARKET_STATS_SQL).fetchone()
    return build_market_risk_context(row, expected_trade_date=expected_trade_date)


def build_market_risk_context(
    row: Mapping[str, Any] | None,
    *,
    expected_trade_date: str | None = None,
) -> dict[str, Any]:
    market = dict(row) if row else {}
    stock_count = int(market.get("stock_count") or 0)
    rising_count = int(market.get("rising_count") or 0)
    falling_count = int(market.get("falling_count") or 0)
    limit_up_count = int(market.get("limit_up_count") or 0)
    limit_down_count = int(market.get("limit_down_count") or 0)
    rising_ratio = round((rising_count / stock_count) * 100, 2) if stock_count else 0.0
    falling_ratio = round((falling_count / stock_count) * 100, 2) if stock_count else 0.0
    turnover_yi = float(market.get("turnover_yi") or 0)
    latest_trade_time = str(market.get("latest_trade_time") or "")
    latest_trade_date = latest_trade_time[:10] if len(latest_trade_time) >= 10 else None

    data_reasons: list[str] = []
    if stock_count < MIN_MARKET_STOCK_COUNT:
        data_reasons.append(f"全市场快照仅 {stock_count} 只，低于风控要求 {MIN_MARKET_STOCK_COUNT} 只")
    if not latest_trade_date:
        data_reasons.append("全市场快照缺少交易时间")
    elif expected_trade_date and latest_trade_date != expected_trade_date:
        data_reasons.append(f"行情日期为 {latest_trade_date}，预期交易日为 {expected_trade_date}")

    extreme_reasons: list[str] = []
    if rising_ratio <= 20:
        extreme_reasons.append(f"上涨家数占比仅 {rising_ratio:.2f}%")
    if limit_down_count >= 100:
        extreme_reasons.append(f"跌停家数达到 {limit_down_count} 家")
    if falling_ratio >= 75 and limit_down_count >= 30:
        extreme_reasons.append(f"下跌家数占比达到 {falling_ratio:.2f}%")

    if data_reasons:
        regime = "数据异常"
        strategy = "行情数据不完整或日期不一致，暂停开新仓。"
        gate_status = "blocked"
        gate_label = "暂停开仓"
        gate_reasons = data_reasons
        max_total_position_pct = 0.0
        max_single_position_pct = 0.0
    elif extreme_reasons:
        regime = "极弱"
        strategy = "市场处于极端风险状态，暂停开新仓，只允许减仓和风险处置。"
        gate_status = "blocked"
        gate_label = "暂停开仓"
        gate_reasons = extreme_reasons
        max_total_position_pct = 0.0
        max_single_position_pct = 0.0
    elif rising_ratio <= 40 or limit_down_count > limit_up_count:
        regime = "偏弱"
        strategy = "只允许极小仓试错，已有仓位达到上限时不再开仓。"
        gate_status = "limited"
        gate_label = "限制开仓"
        gate_reasons = [f"上涨家数占比 {rising_ratio:.2f}%，跌停 {limit_down_count} 家"]
        max_total_position_pct = 10.0
        max_single_position_pct = 5.0
    elif rising_ratio >= 65 and limit_up_count >= max(30, limit_down_count * 8):
        regime = "偏强"
        strategy = "可以顺势参与，但仍需控制单票和账户总仓位。"
        gate_status = "open"
        gate_label = "允许开仓"
        gate_reasons = [f"上涨家数占比 {rising_ratio:.2f}%，涨停家数明显占优"]
        max_total_position_pct = 60.0
        max_single_position_pct = 12.0
    else:
        regime = "震荡"
        strategy = "只做确认度较高的机会，保留大部分现金。"
        gate_status = "open"
        gate_label = "谨慎开仓"
        gate_reasons = [f"上涨家数占比 {rising_ratio:.2f}%，市场分化"]
        max_total_position_pct = 35.0
        max_single_position_pct = 10.0

    return {
        "stock_count": stock_count,
        "rising_count": rising_count,
        "falling_count": falling_count,
        "rising_ratio": rising_ratio,
        "falling_ratio": falling_ratio,
        "limit_up_count": limit_up_count,
        "limit_down_count": limit_down_count,
        "turnover_yi": round(turnover_yi, 2),
        "latest_trade_time": market.get("latest_trade_time"),
        "latest_fetch": market.get("latest_fetch"),
        "expected_trade_date": expected_trade_date,
        "regime": regime,
        "strategy": strategy,
        "trade_gate": {
            "status": gate_status,
            "label": gate_label,
            "allow_new_positions": gate_status != "blocked",
            "reasons": gate_reasons,
            "max_total_position_pct": max_total_position_pct,
            "max_single_position_pct": max_single_position_pct,
            "policy_version": RISK_POLICY_VERSION,
        },
    }


def evaluate_buy_order_risk(
    *,
    market_context: Mapping[str, Any],
    total_assets: float,
    current_market_value: float,
    current_stock_value: float,
    order_cash: float,
    daily_pnl: float = 0.0,
    account_return_pct: float = 0.0,
    stock_change_pct: float | None = None,
) -> dict[str, Any]:
    gate = dict(market_context.get("trade_gate") or {})
    reasons: list[str] = []
    if not gate.get("allow_new_positions", False):
        reasons.extend(str(item) for item in gate.get("reasons") or ["当前市场风控禁止开新仓"])

    assets = max(float(total_assets or 0), 0.0)
    if assets <= 0:
        reasons.append("账户总资产无效")

    max_total_pct = float(gate.get("max_total_position_pct") or 0)
    max_single_pct = float(gate.get("max_single_position_pct") or 0)
    projected_total_pct = ((float(current_market_value or 0) + float(order_cash or 0)) / assets * 100) if assets else 0.0
    projected_single_pct = ((float(current_stock_value or 0) + float(order_cash or 0)) / assets * 100) if assets else 0.0
    daily_pnl_pct = (float(daily_pnl or 0) / assets * 100) if assets else 0.0

    if assets and projected_total_pct > max_total_pct + 0.01:
        reasons.append(f"下单后总仓位约 {projected_total_pct:.2f}%，超过当前市场上限 {max_total_pct:.2f}%")
    if assets and projected_single_pct > max_single_pct + 0.01:
        reasons.append(f"下单后单票仓位约 {projected_single_pct:.2f}%，超过上限 {max_single_pct:.2f}%")
    if daily_pnl_pct <= MAX_DAILY_LOSS_PCT:
        reasons.append(f"账户当日亏损约 {daily_pnl_pct:.2f}%，触发单日亏损熔断")
    if float(account_return_pct or 0) <= MAX_ACCOUNT_LOSS_PCT:
        reasons.append(f"账户累计收益 {float(account_return_pct):.2f}%，触发累计亏损熔断")
    if stock_change_pct is not None and float(stock_change_pct) >= 9.5:
        reasons.append(f"个股当前涨幅 {float(stock_change_pct):.2f}%，禁止在接近涨停时追买")

    return {
        "allowed": not reasons,
        "reasons": reasons,
        "policy_version": RISK_POLICY_VERSION,
        "metrics": {
            "projected_total_position_pct": round(projected_total_pct, 2),
            "projected_single_position_pct": round(projected_single_pct, 2),
            "daily_pnl_pct": round(daily_pnl_pct, 2),
            "account_return_pct": round(float(account_return_pct or 0), 2),
            "max_total_position_pct": max_total_pct,
            "max_single_position_pct": max_single_pct,
        },
    }


def build_portfolio_risk_diagnosis(
    *,
    account: Mapping[str, Any],
    positions: Sequence[Mapping[str, Any]],
    market_context: Mapping[str, Any],
) -> dict[str, Any]:
    total_assets = float(account.get("total_assets") or 0)
    market_value = float(account.get("market_value") or 0)
    position_pct = (market_value / total_assets * 100) if total_assets else 0.0
    daily_return_pct = float(account.get("daily_return_pct") or 0)
    drawdown_pct = float(account.get("drawdown_pct") or 0)
    gate = dict(market_context.get("trade_gate") or {})
    max_total_pct = float(gate.get("max_total_position_pct") or 0)

    flags: list[str] = []
    urgent_flags: list[str] = []
    position_actions: list[dict[str, Any]] = []
    for position in positions:
        current_price = float(position.get("current_price") or 0)
        stop_loss_price = float(position.get("stop_loss_price") or 0)
        item_market_value = float(position.get("market_value") or 0)
        item_position_pct = (item_market_value / total_assets * 100) if total_assets else 0.0
        change_pct = float(position.get("change_pct") or 0)
        reasons: list[str] = []
        action = "observe"
        label = "继续观察"
        if stop_loss_price > 0 and current_price > 0 and current_price <= stop_loss_price:
            reasons.append(f"现价 {current_price:.2f} 已不高于止损位 {stop_loss_price:.2f}")
            action = "review_reduce"
            label = "优先检查是否减仓"
        if change_pct <= -7:
            reasons.append(f"当日跌幅 {change_pct:.2f}% 较大")
            action = "review_reduce"
            label = "优先检查是否减仓"
        if item_position_pct >= 20:
            reasons.append(f"单票占总资产 {item_position_pct:.2f}%，集中度较高")
            if action == "observe":
                action = "reduce_concentration"
                label = "避免继续加仓"
        if reasons:
            position_actions.append(
                {
                    "stock_code": position.get("stock_code"),
                    "stock_name": position.get("stock_name"),
                    "action": action,
                    "label": label,
                    "reasons": reasons,
                    "position_pct": round(item_position_pct, 2),
                }
            )

    if not gate.get("allow_new_positions", False):
        flags.append(f"市场风控为“{gate.get('label') or '暂停开仓'}”")
    if market_value > 0 and position_pct > max_total_pct + 0.01:
        flags.append(f"当前仓位 {position_pct:.2f}%，高于当前环境上限 {max_total_pct:.2f}%")
    if daily_return_pct <= MAX_DAILY_LOSS_PCT:
        urgent_flags.append(f"账户当日收益 {daily_return_pct:.2f}%，达到亏损警戒线")
    if drawdown_pct <= MAX_ACCOUNT_LOSS_PCT:
        urgent_flags.append(f"账户从历史高点回撤 {drawdown_pct:.2f}%，达到回撤警戒线")
    if position_actions:
        urgent_count = sum(1 for item in position_actions if item["action"] == "review_reduce")
        if urgent_count:
            urgent_flags.append(f"有 {urgent_count} 只持仓触发价格风险检查")

    if urgent_flags:
        level = "high"
        label = "需要处理风险"
        summary = "暂停新增买入，优先核对触发止损或大幅下跌的持仓。"
    elif flags and market_value > 0:
        level = "high" if not gate.get("allow_new_positions", False) else "medium"
        label = "只减不加"
        summary = "当前市场不支持继续扩仓，先保留现金并逐只检查现有仓位。"
    elif not positions:
        level = "low"
        label = "保持等待"
        summary = "账户没有持仓，等待系统重新开放买入并出现合格建议。"
    else:
        level = "low"
        label = "继续观察"
        summary = "暂未触发账户级风险处理条件，按原计划和止损位跟踪。"

    return {
        "level": level,
        "label": label,
        "summary": summary,
        "needs_action": bool(urgent_flags or (flags and market_value > 0)),
        "flags": [*urgent_flags, *flags],
        "position_actions": position_actions,
        "metrics": {
            "position_pct": round(position_pct, 2),
            "market_position_limit_pct": max_total_pct,
            "daily_return_pct": round(daily_return_pct, 2),
            "drawdown_pct": round(drawdown_pct, 2),
        },
        "policy_version": RISK_POLICY_VERSION,
    }
