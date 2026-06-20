from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .collectors import fetch_trade_calendar
from .db import get_connection, init_db


CHINA_TZ = ZoneInfo("Asia/Shanghai")
MORNING_OPEN = time(9, 30)
MORNING_CLOSE = time(11, 30)
AFTERNOON_OPEN = time(13, 0)
AFTERNOON_CLOSE = time(15, 0)


def china_now() -> datetime:
    return datetime.now(CHINA_TZ)


def china_now_str(now: datetime | None = None) -> str:
    current = _normalize_now(now)
    return current.strftime("%Y-%m-%d %H:%M:%S")


def sync_trade_calendar_year(year: int) -> int:
    init_db()
    frame = fetch_trade_calendar(year=year)
    if frame is None or frame.empty:
        return 0
    rows = frame.to_dict(orient="records")
    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO trade_calendar (trade_date, trade_status, day_week, fetched_at)
            VALUES (:trade_date, :trade_status, :day_week, :fetched_at)
            ON CONFLICT(trade_date) DO UPDATE SET
                trade_status = excluded.trade_status,
                day_week = excluded.day_week,
                fetched_at = excluded.fetched_at
            """,
            rows,
        )
    return len(rows)


def ensure_trade_calendar(target_date: date | None = None) -> bool:
    selected_date = target_date or china_now().date()
    init_db()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT 1 FROM trade_calendar WHERE trade_date = ?",
            (selected_date.isoformat(),),
        ).fetchone()
    if row:
        return True
    try:
        sync_trade_calendar_year(selected_date.year)
    except Exception:
        return False
    with get_connection() as connection:
        row = connection.execute(
            "SELECT 1 FROM trade_calendar WHERE trade_date = ?",
            (selected_date.isoformat(),),
        ).fetchone()
    return bool(row)


def get_a_share_market_status(now: datetime | None = None, *, refresh_if_missing: bool = False) -> dict[str, object]:
    current = _normalize_now(now)
    current_date = current.date()
    calendar_ready = ensure_trade_calendar(current_date) if refresh_if_missing else _calendar_has_date(current_date)
    calendar_row = _calendar_row(current_date) if calendar_ready else None
    is_trading_day = bool(calendar_row and int(calendar_row["trade_status"]) == 1)
    session = _session_for_time(current.time()) if is_trading_day else "closed"
    is_open = is_trading_day and session in {"morning", "afternoon"}

    if not calendar_ready:
        reason = "交易日历缺失，为避免节假日误成交，模拟盘已暂停交易"
    elif not is_trading_day:
        reason = "A股休市日，模拟盘不能买卖"
    elif session == "pre_open":
        reason = "A股尚未开盘，09:30 后可交易"
    elif session == "lunch_break":
        reason = "A股午间休市，13:00 后可交易"
    elif session == "closed":
        reason = "A股已收盘，模拟盘不能买卖"
    else:
        reason = "A股交易时段，模拟盘可买卖"

    next_open = _find_next_open(current) if calendar_ready and not is_open else None
    return {
        "market": "A股",
        "timezone": "Asia/Shanghai",
        "current_time": china_now_str(current),
        "trade_date": current_date.isoformat(),
        "calendar_ready": calendar_ready,
        "is_trading_day": is_trading_day,
        "is_open": is_open,
        "session": session,
        "reason": reason,
        "next_open": next_open,
        "sessions": [
            {"label": "上午", "start": "09:30:00", "end": "11:30:00"},
            {"label": "下午", "start": "13:00:00", "end": "15:00:00"},
        ],
    }


def require_a_share_market_open(now: datetime | None = None) -> dict[str, object]:
    status = get_a_share_market_status(now, refresh_if_missing=True)
    if not status["is_open"]:
        message = str(status["reason"])
        if status.get("next_open"):
            message += f"，下次开市：{status['next_open']}"
        raise ValueError(message)
    return status


def _normalize_now(now: datetime | None) -> datetime:
    if now is None:
        return china_now()
    if now.tzinfo is None:
        return now.replace(tzinfo=CHINA_TZ)
    return now.astimezone(CHINA_TZ)


def _calendar_has_date(target_date: date) -> bool:
    init_db()
    with get_connection() as connection:
        return bool(
            connection.execute(
                "SELECT 1 FROM trade_calendar WHERE trade_date = ?",
                (target_date.isoformat(),),
            ).fetchone()
        )


def _calendar_row(target_date: date):
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT trade_date, trade_status, day_week, fetched_at
            FROM trade_calendar
            WHERE trade_date = ?
            """,
            (target_date.isoformat(),),
        ).fetchone()


def _session_for_time(current_time: time) -> str:
    if current_time < MORNING_OPEN:
        return "pre_open"
    if MORNING_OPEN <= current_time <= MORNING_CLOSE:
        return "morning"
    if MORNING_CLOSE < current_time < AFTERNOON_OPEN:
        return "lunch_break"
    if AFTERNOON_OPEN <= current_time <= AFTERNOON_CLOSE:
        return "afternoon"
    return "closed"


def _find_next_open(current: datetime) -> str | None:
    if _is_open_day(current.date()):
        if current.time() < MORNING_OPEN:
            return f"{current.date().isoformat()} 09:30:00"
        if MORNING_CLOSE < current.time() < AFTERNOON_OPEN:
            return f"{current.date().isoformat()} 13:00:00"

    for offset in range(1, 32):
        candidate = current.date() + timedelta(days=offset)
        if not _calendar_has_date(candidate):
            try:
                sync_trade_calendar_year(candidate.year)
            except Exception:
                return None
        if _is_open_day(candidate):
            return f"{candidate.isoformat()} 09:30:00"
    return None


def _is_open_day(target_date: date) -> bool:
    row = _calendar_row(target_date)
    return bool(row and int(row["trade_status"]) == 1)
