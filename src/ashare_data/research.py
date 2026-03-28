from __future__ import annotations

from typing import Any

import pandas as pd

from .akshare_client import get_stock_profile


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _signal_text(flag: bool | None, true_text: str, false_text: str) -> str:
    if flag is None:
        return "数据不足"
    return true_text if flag else false_text


def build_stock_research_card(snapshot: dict[str, Any] | None, daily_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not snapshot:
        return {}

    frame = pd.DataFrame(daily_rows)
    if not frame.empty:
        frame["trade_date"] = pd.to_datetime(frame["trade_date"])
        for column in ["open", "close", "high", "low", "volume", "amount", "change_pct", "turnover_ratio"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame.dropna(subset=["close"]).sort_values("trade_date")

    latest_close = _safe_float(snapshot.get("price"))
    ma20 = ma60 = return_5d_pct = return_20d_pct = volatility_20d = support_price = resistance_price = None
    above_ma20 = above_ma60 = None

    if not frame.empty:
        frame["ma20"] = frame["close"].rolling(20).mean()
        frame["ma60"] = frame["close"].rolling(60).mean()
        ma20 = _safe_float(frame["ma20"].iloc[-1])
        ma60 = _safe_float(frame["ma60"].iloc[-1])
        if len(frame) >= 6:
            return_5d_pct = ((frame["close"].iloc[-1] / frame["close"].iloc[-6]) - 1.0) * 100
        if len(frame) >= 21:
            return_20d_pct = ((frame["close"].iloc[-1] / frame["close"].iloc[-21]) - 1.0) * 100
            volatility_20d = float(frame["change_pct"].tail(20).std())
            support_price = float(frame["low"].tail(20).min())
            resistance_price = float(frame["high"].tail(20).max())
        if latest_close is not None and ma20 is not None:
            above_ma20 = latest_close >= ma20
        if latest_close is not None and ma60 is not None:
            above_ma60 = latest_close >= ma60

    change_pct = _safe_float(snapshot.get("change_pct")) or 0.0
    turnover_ratio = _safe_float(snapshot.get("turnover_ratio")) or 0.0
    volume_ratio = _safe_float(snapshot.get("volume_ratio")) or 0.0
    pe_ratio = _safe_float(snapshot.get("pe_ratio"))

    bull_points: list[str] = []
    risk_points: list[str] = []
    score = 0

    if above_ma20:
        score += 1
        bull_points.append("价格位于20日均线之上")
    else:
        risk_points.append("价格仍在20日均线下方或刚跌破")

    if above_ma60:
        score += 1
        bull_points.append("中期趋势仍强于60日均线")
    elif ma60 is not None:
        risk_points.append("中期趋势未站回60日均线")

    if volume_ratio >= 1.5:
        score += 1
        bull_points.append(f"量比活跃 {volume_ratio:.2f}")
    else:
        risk_points.append(f"量比偏弱 {volume_ratio:.2f}")

    if turnover_ratio >= 2:
        bull_points.append(f"换手率具备活跃度 {turnover_ratio:.2f}%")
    if return_20d_pct is not None and return_20d_pct < -8:
        risk_points.append(f"20日跌幅较大 {return_20d_pct:.2f}%")
    elif return_20d_pct is not None and return_20d_pct > 8:
        bull_points.append(f"20日趋势收益 {return_20d_pct:.2f}%")

    if change_pct >= 3:
        bull_points.append(f"最新涨幅较强 {change_pct:.2f}%")
    elif change_pct <= -3:
        risk_points.append(f"最新跌幅偏大 {change_pct:.2f}%")

    if pe_ratio is not None and pe_ratio > 80:
        risk_points.append(f"估值偏高 PE {pe_ratio:.2f}")
    elif pe_ratio is not None and 0 < pe_ratio <= 40:
        bull_points.append(f"估值相对可接受 PE {pe_ratio:.2f}")

    if score >= 3 and change_pct >= 0:
        verdict = "看多"
        confidence = "中"
        style = "趋势跟踪 / 2-5日"
    elif score >= 2:
        verdict = "观察"
        confidence = "中低"
        style = "观察等待 / 回踩确认"
    else:
        verdict = "回避"
        confidence = "中"
        style = "暂不参与"

    summary = f"{snapshot.get('stock_name')} 当前更适合{style}。{_signal_text(above_ma20, '短期趋势未坏。', '短期趋势仍弱。')}"
    if snapshot.get("notes"):
        bull_points.append("已记录自选备注，可结合个人交易计划执行")

    profile = get_stock_profile(str(snapshot.get("stock_code")))

    return {
        "profile": profile,
        "signals": {
            "latest_close": latest_close,
            "ma20": ma20,
            "ma60": ma60,
            "return_5d_pct": float(round(return_5d_pct, 2)) if return_5d_pct is not None else None,
            "return_20d_pct": float(round(return_20d_pct, 2)) if return_20d_pct is not None else None,
            "volatility_20d": float(round(volatility_20d, 2)) if volatility_20d is not None else None,
            "above_ma20": above_ma20,
            "above_ma60": above_ma60,
            "support_price": round(support_price, 2) if support_price is not None else None,
            "resistance_price": round(resistance_price, 2) if resistance_price is not None else None,
        },
        "ai_view": {
            "verdict": verdict,
            "confidence": confidence,
            "style": style,
            "summary": summary,
            "bull_points": bull_points[:4],
            "risk_points": risk_points[:4],
            "updated_at": snapshot.get("fetched_at"),
        },
    }
