from __future__ import annotations

from datetime import datetime

from .db import get_connection


def normalize_stock_code(stock_code: str) -> str:
    digits = "".join(char for char in stock_code.strip() if char.isdigit())
    if len(digits) == 6:
        return digits
    return stock_code.strip()


def normalize_trade_quantity(quantity: int | None) -> int:
    if quantity is None:
        return 100
    amount = int(quantity)
    if amount <= 0:
        raise ValueError("trade quantity must be greater than 0")
    if amount % 100 != 0:
        raise ValueError("trade quantity must be a multiple of 100")
    return amount


def upsert_watchlist_item(stock_code: str, display_name: str = "", notes: str = "") -> str:
    normalized_code = normalize_stock_code(stock_code)
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO watchlist (
                stock_code, display_name, notes, created_at, updated_at, is_active, origin, default_trade_quantity
            )
            VALUES (?, ?, ?, ?, ?, 1, 'user', 100)
            ON CONFLICT(stock_code) DO UPDATE SET
                display_name = excluded.display_name,
                notes = excluded.notes,
                updated_at = excluded.updated_at,
                is_active = 1,
                origin = 'user'
            """,
            (normalized_code, display_name.strip(), notes.strip(), now, now),
        )
    return normalized_code


def update_watchlist_targets(
    stock_code: str,
    *,
    buy_price: float | None = None,
    take_profit_price: float | None = None,
    stop_loss_price: float | None = None,
    display_name: str | None = None,
    notes: str | None = None,
    default_trade_quantity: int | None = None,
) -> str:
    normalized_code = normalize_stock_code(stock_code)
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    with get_connection() as connection:
        existing = connection.execute(
            """
            SELECT display_name, notes, default_trade_quantity
            FROM watchlist
            WHERE stock_code = ?
            """,
            (normalized_code,),
        ).fetchone()
        normalized_trade_quantity = normalize_trade_quantity(
            default_trade_quantity if default_trade_quantity is not None else (existing["default_trade_quantity"] if existing else 100)
        )
        connection.execute(
            """
            INSERT INTO watchlist (
                stock_code, display_name, notes, created_at, updated_at,
                buy_price, take_profit_price, stop_loss_price, is_active, origin, default_trade_quantity
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 'user', ?)
            ON CONFLICT(stock_code) DO UPDATE SET
                display_name = excluded.display_name,
                notes = excluded.notes,
                buy_price = excluded.buy_price,
                take_profit_price = excluded.take_profit_price,
                stop_loss_price = excluded.stop_loss_price,
                default_trade_quantity = excluded.default_trade_quantity,
                updated_at = excluded.updated_at,
                is_active = 1,
                origin = 'user'
            """,
            (
                normalized_code,
                (display_name if display_name is not None else (existing["display_name"] if existing else "")).strip(),
                (notes if notes is not None else (existing["notes"] if existing else "")).strip(),
                now,
                now,
                buy_price,
                take_profit_price,
                stop_loss_price,
                normalized_trade_quantity,
            ),
        )
    return normalized_code


def bulk_upsert_watchlist_items(stock_codes: list[str]) -> list[str]:
    inserted: list[str] = []
    for code in stock_codes:
        normalized = normalize_stock_code(code)
        if normalized and normalized not in inserted:
            upsert_watchlist_item(normalized)
            inserted.append(normalized)
    return inserted


def upsert_imported_watchlist_item(
    stock_code: str,
    *,
    display_name: str = "",
    notes: str = "",
    buy_price: float | None = None,
    take_profit_price: float | None = None,
    stop_loss_price: float | None = None,
    default_trade_quantity: int | None = None,
) -> str:
    normalized_code = normalize_stock_code(stock_code)
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    with get_connection() as connection:
        existing = connection.execute(
            """
            SELECT is_active, default_trade_quantity
            FROM watchlist
            WHERE stock_code = ?
            """,
            (normalized_code,),
        ).fetchone()
        is_active = int(existing["is_active"]) if existing and existing["is_active"] is not None else 0
        normalized_trade_quantity = normalize_trade_quantity(
            default_trade_quantity if default_trade_quantity is not None else (existing["default_trade_quantity"] if existing else 100)
        )
        connection.execute(
            """
            INSERT INTO watchlist (
                stock_code, display_name, notes, created_at, updated_at,
                buy_price, take_profit_price, stop_loss_price, is_active, origin, default_trade_quantity
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'imported', ?)
            ON CONFLICT(stock_code) DO UPDATE SET
                display_name = excluded.display_name,
                notes = excluded.notes,
                buy_price = excluded.buy_price,
                take_profit_price = excluded.take_profit_price,
                stop_loss_price = excluded.stop_loss_price,
                default_trade_quantity = excluded.default_trade_quantity,
                updated_at = excluded.updated_at,
                origin = 'imported'
            """,
            (
                normalized_code,
                display_name.strip(),
                notes.strip(),
                now,
                now,
                buy_price,
                take_profit_price,
                stop_loss_price,
                is_active,
                normalized_trade_quantity,
            ),
        )
    return normalized_code


def delete_watchlist_item(stock_code: str) -> None:
    normalized_code = normalize_stock_code(stock_code)
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE watchlist
            SET is_active = 0,
                updated_at = ?
            WHERE stock_code = ?
            """,
            (datetime.utcnow().replace(microsecond=0).isoformat() + "Z", normalized_code),
        )


def mark_watchlist_synced(stock_codes: list[str]) -> None:
    if not stock_codes:
        return
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    with get_connection() as connection:
        connection.executemany(
            "UPDATE watchlist SET last_synced_at = ?, updated_at = ? WHERE stock_code = ? AND is_active = 1",
            [(now, now, normalize_stock_code(code)) for code in stock_codes],
        )
