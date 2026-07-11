from __future__ import annotations

import os
import threading
from datetime import timedelta
from typing import Any

from .data_health import expected_latest_trade_date, load_data_health
from .db import get_connection
from .stock_market import sync_stock_market_snapshot
from .sync import sync_daily_bars_for_codes


_REFRESH_LOCK = threading.Lock()
_STOP_EVENT = threading.Event()
_THREAD: threading.Thread | None = None


def sync_tracked_snapshot_daily_bars(stock_codes: list[str]) -> int:
    """Use the complete daily fields already present in the live snapshot as a last-resort daily bar."""
    if not stock_codes:
        return 0
    expected_date = expected_latest_trade_date().isoformat()
    placeholders = ", ".join("?" for _ in stock_codes)
    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT
                stock_code,
                trade_time,
                substr(trade_time, 1, 10) AS trade_date,
                open,
                price AS close,
                high,
                low,
                volume,
                amount,
                change_pct,
                change_amount AS change,
                turnover_ratio,
                pre_close,
                'market_snapshot' AS source,
                1 AS adjust_type,
                1 AS k_type,
                fetched_at
            FROM stock_market_snapshot
            WHERE stock_code IN ({placeholders})
              AND substr(trade_time, 1, 10) = ?
            """,
            [*stock_codes, expected_date],
        ).fetchall()
        connection.executemany(
            """
            INSERT INTO daily_bars (
                stock_code, trade_time, trade_date, open, close, high, low,
                volume, amount, change_pct, change, turnover_ratio, pre_close,
                source, adjust_type, k_type, fetched_at
            )
            VALUES (
                :stock_code, :trade_time, :trade_date, :open, :close, :high, :low,
                :volume, :amount, :change_pct, :change, :turnover_ratio, :pre_close,
                :source, :adjust_type, :k_type, :fetched_at
            )
            ON CONFLICT(stock_code, trade_date, adjust_type, k_type) DO UPDATE SET
                trade_time = excluded.trade_time,
                open = excluded.open,
                close = excluded.close,
                high = excluded.high,
                low = excluded.low,
                volume = excluded.volume,
                amount = excluded.amount,
                change_pct = excluded.change_pct,
                change = excluded.change,
                turnover_ratio = excluded.turnover_ratio,
                pre_close = excluded.pre_close,
                source = excluded.source,
                fetched_at = excluded.fetched_at
            """,
            [dict(row) for row in rows],
        )
    return len(rows)


def refresh_market_data(*, background: bool = False) -> dict[str, Any]:
    if not _REFRESH_LOCK.acquire(blocking=not background):
        return {"status": "already_running", "data_health": load_data_health()}
    try:
        result = sync_stock_market_snapshot()
        with get_connection() as connection:
            tracked_rows = connection.execute(
                """
                SELECT stock_code FROM watchlist WHERE is_active = 1
                UNION
                SELECT stock_code FROM paper_positions WHERE quantity > 0
                ORDER BY stock_code
                """
            ).fetchall()
        tracked_codes = [row["stock_code"] for row in tracked_rows]
        daily_results: list[dict[str, Any]] = []
        if tracked_codes:
            end_date = expected_latest_trade_date()
            start_date = end_date - timedelta(days=45)
            try:
                daily_results = sync_daily_bars_for_codes(
                    tracked_codes,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                )
            except Exception:
                daily_results = []
            snapshot_bar_count = sync_tracked_snapshot_daily_bars(tracked_codes)
        else:
            snapshot_bar_count = 0
        result["tracked_daily_bars"] = daily_results
        result["snapshot_daily_bar_count"] = snapshot_bar_count
        result["status"] = "completed"
        result["data_health"] = load_data_health()
        return result
    finally:
        _REFRESH_LOCK.release()


def _scheduler_loop() -> None:
    while not _STOP_EVENT.is_set():
        try:
            health = load_data_health()
            if health.get("needs_refresh"):
                refresh_market_data(background=True)
        except Exception:
            # Upstream providers are best effort. A later scheduler tick or the
            # manual refresh button can recover without taking the API down.
            pass
        _STOP_EVENT.wait(180)


def start_market_refresh_scheduler() -> None:
    global _THREAD
    if os.environ.get("DISABLE_MARKET_AUTO_REFRESH") == "1":
        return
    if _THREAD and _THREAD.is_alive():
        return
    _STOP_EVENT.clear()
    _THREAD = threading.Thread(target=_scheduler_loop, name="market-refresh", daemon=True)
    _THREAD.start()


def stop_market_refresh_scheduler() -> None:
    _STOP_EVENT.set()
