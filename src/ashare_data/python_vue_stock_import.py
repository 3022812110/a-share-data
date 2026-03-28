from __future__ import annotations

import sqlite3
from pathlib import Path

from .db import get_connection, init_db
from .stock_market import sync_stock_market_snapshot
from .watchlist import normalize_stock_code, upsert_imported_watchlist_item


DEFAULT_SOURCE_DB = Path("/Users/zhangmi/Desktop/Work/python-vue-stock/db.sqlite3")


def import_python_vue_stock_db(
    source_db_path: str | Path = DEFAULT_SOURCE_DB,
    *,
    sync_snapshot: bool = True,
    prune_extra: bool = True,
) -> dict[str, object]:
    init_db()

    source_path = Path(source_db_path)
    if not source_path.exists():
        raise FileNotFoundError(f"source db not found: {source_path}")

    source_connection = sqlite3.connect(source_path)
    source_connection.row_factory = sqlite3.Row
    try:
        rows = source_connection.execute(
            """
            SELECT
                code,
                house,
                name,
                buy_price,
                stop_surplus,
                stop_loss
            FROM StockModel_stockzcw
            ORDER BY code
            """
        ).fetchall()
    finally:
        source_connection.close()

    imported_codes: list[str] = []
    catalog_rows: list[tuple[str, str, str, str, str, str]] = []

    with get_connection() as connection:
        now = connection.execute("SELECT strftime('%Y-%m-%dT%H:%M:%SZ', 'now')").fetchone()[0]
        for row in rows:
            stock_code = normalize_stock_code(str(row["code"]))
            if not stock_code:
                continue
            stock_name = (row["name"] or stock_code).strip()
            market = (row["house"] or "").strip().upper()

            upsert_imported_watchlist_item(
                stock_code,
                display_name=stock_name,
                notes="Imported candidate",
                buy_price=row["buy_price"],
                take_profit_price=row["stop_surplus"],
                stop_loss_price=row["stop_loss"],
            )
            catalog_rows.append(
                (
                    stock_code,
                    stock_name,
                    "python-vue-stock",
                    market,
                    "imported-watchlist",
                    now,
                )
            )
            imported_codes.append(stock_code)

        imported_code_set = set(imported_codes)
        if prune_extra and imported_code_set:
            placeholders = ", ".join("?" for _ in imported_code_set)
            connection.execute(
                f"DELETE FROM watchlist WHERE origin = 'imported' AND stock_code NOT IN ({placeholders})",
                tuple(imported_code_set),
            )

        if catalog_rows:
            connection.executemany(
                """
                INSERT INTO stock_catalog (stock_code, stock_name, source, market, group_name, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(stock_code) DO UPDATE SET
                    stock_name = excluded.stock_name,
                    source = excluded.source,
                    market = excluded.market,
                    group_name = excluded.group_name,
                    updated_at = excluded.updated_at
                """,
                catalog_rows,
            )

    sync_result: dict[str, object] | None = None
    if sync_snapshot and imported_codes:
        sync_result = sync_stock_market_snapshot(stock_codes=imported_codes)

    return {
        "imported_count": len(imported_codes),
        "sync_result": sync_result,
        "prune_extra": prune_extra,
    }
