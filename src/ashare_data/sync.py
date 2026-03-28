from __future__ import annotations

from .collectors import fetch_daily_bars
from .db import get_connection, init_db
from .market_data import fetch_realtime_quotes
from .watchlist import mark_watchlist_synced


def upsert_daily_bar_rows(rows: list[dict]) -> None:
    if not rows:
        return

    with get_connection() as connection:
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
            rows,
        )


def sync_daily_bars_for_codes(
    stock_codes: list[str],
    start_date: str,
    end_date: str | None = None,
    *,
    adjust_type: int = 1,
    k_type: int = 1,
) -> list[dict]:
    init_db()

    results: list[dict] = []
    synced_codes: list[str] = []
    for stock_code in stock_codes:
        frame = fetch_daily_bars(
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            adjust_type=adjust_type,
            k_type=k_type,
        )
        rows = frame.to_dict(orient="records")
        upsert_daily_bar_rows(rows)
        source = rows[0]["source"] if rows else "none"
        results.append(
            {
                "stock_code": stock_code,
                "rows": len(rows),
                "source": source,
            }
        )
        if rows:
            synced_codes.append(stock_code)

    mark_watchlist_synced(synced_codes)
    return results


def sync_realtime_quotes_for_codes(stock_codes: list[str]) -> list[dict]:
    init_db()
    frame = fetch_realtime_quotes(stock_codes)
    if frame.empty:
        return []

    rows = frame.to_dict(orient="records")
    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO realtime_quotes (
                stock_code, stock_name, price, change_amount, change_pct,
                volume, amount, source, trade_time, fetched_at
            )
            VALUES (
                :stock_code, :stock_name, :price, :change_amount, :change_pct,
                :volume, :amount, :source, :trade_time, :fetched_at
            )
            ON CONFLICT(stock_code) DO UPDATE SET
                stock_name = excluded.stock_name,
                price = excluded.price,
                change_amount = excluded.change_amount,
                change_pct = excluded.change_pct,
                volume = excluded.volume,
                amount = excluded.amount,
                source = excluded.source,
                trade_time = excluded.trade_time,
                fetched_at = excluded.fetched_at
            """,
            rows,
        )
    return rows
