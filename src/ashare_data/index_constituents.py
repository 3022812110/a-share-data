from __future__ import annotations

from datetime import datetime

import baostock as bs
import pandas as pd

from .db import get_connection
from .watchlist import bulk_upsert_watchlist_items, normalize_stock_code, upsert_watchlist_item


def _query_rows(query_name: str, query_date: str) -> pd.DataFrame:
    login_result = bs.login()
    try:
        if login_result.error_code != "0":
            raise RuntimeError(login_result.error_msg)
        if query_name == "hs300":
            rs = bs.query_hs300_stocks(query_date)
        elif query_name == "zz500":
            rs = bs.query_zz500_stocks(query_date)
        else:
            raise ValueError(f"unsupported query_name: {query_name}")

        if rs.error_code != "0":
            raise RuntimeError(rs.error_msg)

        rows: list[list[str]] = []
        while rs.next():
            rows.append(rs.get_row_data())
    finally:
        bs.logout()

    if not rows:
        return pd.DataFrame(columns=["updateDate", "code", "code_name"])
    return pd.DataFrame(rows, columns=rs.fields)


def import_index_constituents(index_name: str, query_date: str) -> dict[str, object]:
    query_key = "hs300" if index_name == "沪深300" else "zz500"
    frame = _query_rows(query_key, query_date)
    if frame.empty:
        return {"index_name": index_name, "count": 0}

    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    catalog_rows = []
    imported_codes: list[str] = []
    for row in frame.to_dict(orient="records"):
        stock_code = normalize_stock_code(str(row["code"]).split(".", 1)[1])
        stock_name = str(row["code_name"])
        catalog_rows.append((stock_code, stock_name, "baostock", index_name, now))
        upsert_watchlist_item(stock_code, stock_name, index_name)
        imported_codes.append(stock_code)

    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO stock_catalog (stock_code, stock_name, source, group_name, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(stock_code) DO UPDATE SET
                stock_name = excluded.stock_name,
                source = excluded.source,
                group_name = excluded.group_name,
                updated_at = excluded.updated_at
            """,
            catalog_rows,
        )

    return {"index_name": index_name, "count": len(imported_codes), "stock_codes": imported_codes}
