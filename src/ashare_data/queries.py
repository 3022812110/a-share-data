from __future__ import annotations

import math

import pandas as pd

from .db import get_connection


def load_overview() -> dict[str, object]:
    with get_connection() as connection:
        trade_calendar_count = connection.execute(
            "SELECT COUNT(*) FROM trade_calendar"
        ).fetchone()[0]
        daily_bars_count = connection.execute(
            "SELECT COUNT(*) FROM daily_bars"
        ).fetchone()[0]
        stock_count = connection.execute(
            "SELECT COUNT(DISTINCT stock_code) FROM daily_bars"
        ).fetchone()[0]
        latest_trade_date_row = connection.execute(
            "SELECT MAX(trade_date) AS max_trade_date FROM daily_bars"
        ).fetchone()
        latest_fetch_row = connection.execute(
            """
            SELECT MAX(fetched_at) AS latest_fetch
            FROM (
                SELECT fetched_at FROM trade_calendar
                UNION ALL
                SELECT fetched_at FROM daily_bars
            )
            """
        ).fetchone()
        source_rows = connection.execute(
            """
            SELECT source, COUNT(*) AS cnt
            FROM daily_bars
            GROUP BY source
            ORDER BY cnt DESC
            """
        ).fetchall()

    return {
        "trade_calendar_count": trade_calendar_count,
        "daily_bars_count": daily_bars_count,
        "stock_count": stock_count,
        "latest_trade_date": latest_trade_date_row["max_trade_date"] if latest_trade_date_row else None,
        "latest_fetch": latest_fetch_row["latest_fetch"] if latest_fetch_row else None,
        "sources": {row["source"]: row["cnt"] for row in source_rows},
    }


def load_recent_trade_calendar(limit: int = 10) -> pd.DataFrame:
    with get_connection() as connection:
        return pd.read_sql_query(
            """
            SELECT trade_date, trade_status, day_week, fetched_at
            FROM trade_calendar
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            connection,
            params=(limit,),
        )


def load_stock_codes() -> list[str]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT stock_code
            FROM daily_bars
            ORDER BY stock_code
            """
        ).fetchall()
    return [row["stock_code"] for row in rows]


def load_stock_options() -> list[dict[str, str]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            WITH name_candidates AS (
                SELECT stock_code, display_name AS stock_name
                FROM watchlist
                WHERE display_name IS NOT NULL AND TRIM(display_name) != ''
                UNION ALL
                SELECT stock_code, stock_name
                FROM stock_catalog
            )
            SELECT
                d.stock_code,
                COALESCE(
                    (
                        SELECT stock_name
                        FROM name_candidates nc
                        WHERE nc.stock_code = d.stock_code
                        LIMIT 1
                    ),
                    d.stock_code
                ) AS stock_name
            FROM (
                SELECT DISTINCT stock_code
                FROM daily_bars
            ) d
            ORDER BY d.stock_code
            """
        ).fetchall()
    return [{"stock_code": row["stock_code"], "stock_name": row["stock_name"]} for row in rows]


def load_daily_bars(stock_code: str, limit: int = 120) -> pd.DataFrame:
    with get_connection() as connection:
        return pd.read_sql_query(
            """
            SELECT stock_code, trade_date, open, close, high, low, volume, amount, change_pct, turnover_ratio
                 , source
            FROM daily_bars
            WHERE stock_code = ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            connection,
            params=(stock_code, limit),
        )


def load_watchlist() -> pd.DataFrame:
    with get_connection() as connection:
        return pd.read_sql_query(
            """
            SELECT stock_code, display_name, notes, created_at, updated_at, last_synced_at
            FROM watchlist
            WHERE is_active = 1
            ORDER BY stock_code
            """,
            connection,
        )


def load_watchlist_snapshot() -> pd.DataFrame:
    with get_connection() as connection:
        return pd.read_sql_query(
            """
            WITH latest AS (
                SELECT d1.*
                FROM daily_bars d1
                INNER JOIN (
                    SELECT stock_code, MAX(trade_date) AS max_trade_date
                    FROM daily_bars
                    GROUP BY stock_code
                ) d2
                  ON d1.stock_code = d2.stock_code
                 AND d1.trade_date = d2.max_trade_date
            )
            SELECT
                w.stock_code,
                COALESCE(NULLIF(w.display_name, ''), w.stock_code) AS display_name,
                w.notes,
                w.last_synced_at,
                l.trade_date,
                l.close,
                l.change_pct,
                l.source
            FROM watchlist w
            LEFT JOIN latest l ON l.stock_code = w.stock_code
            WHERE w.is_active = 1
            ORDER BY w.stock_code
            """,
            connection,
        )


def load_realtime_quotes() -> pd.DataFrame:
    with get_connection() as connection:
        return pd.read_sql_query(
            """
            SELECT
                stock_code,
                stock_name,
                price,
                change_amount,
                change_pct,
                volume,
                amount,
                source,
                trade_time,
                fetched_at
            FROM realtime_quotes
            ORDER BY ABS(COALESCE(change_pct, 0)) DESC, stock_code
            """,
            connection,
        )


def load_analysis_table(stock_codes: list[str], lookback: int = 60) -> pd.DataFrame:
    if not stock_codes:
        return pd.DataFrame()

    records: list[dict] = []
    for stock_code in stock_codes:
        frame = load_daily_bars(stock_code, limit=max(lookback, 30))
        if frame.empty:
            continue
        chart_frame = frame.iloc[::-1].copy()
        chart_frame["close"] = pd.to_numeric(chart_frame["close"], errors="coerce")
        chart_frame["change_pct"] = pd.to_numeric(chart_frame["change_pct"], errors="coerce")
        chart_frame = chart_frame.dropna(subset=["close"])
        if chart_frame.empty:
            continue

        latest_close = float(chart_frame["close"].iloc[-1])
        latest_date = str(chart_frame["trade_date"].iloc[-1])
        ma5 = float(chart_frame["close"].tail(5).mean()) if len(chart_frame) >= 5 else math.nan
        ma20 = float(chart_frame["close"].tail(20).mean()) if len(chart_frame) >= 20 else math.nan
        prev_20 = float(chart_frame["close"].iloc[-20]) if len(chart_frame) >= 20 else math.nan
        return_20d = ((latest_close / prev_20) - 1.0) * 100 if prev_20 and not math.isnan(prev_20) else math.nan
        volatility_20d = (
            float(chart_frame["change_pct"].tail(20).std()) if len(chart_frame) >= 20 else math.nan
        )

        records.append(
            {
                "stock_code": stock_code,
                "latest_trade_date": latest_date,
                "latest_close": latest_close,
                "ma5": ma5,
                "ma20": ma20,
                "return_20d_pct": return_20d,
                "volatility_20d": volatility_20d,
                "above_ma20": None if math.isnan(ma20) else latest_close > ma20,
            }
        )

    if not records:
        return pd.DataFrame()

    frame = pd.DataFrame(records)
    return frame.sort_values(by=["return_20d_pct", "latest_close"], ascending=[False, False]).reset_index(drop=True)
