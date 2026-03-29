from __future__ import annotations

from datetime import datetime

from .db import get_connection, init_db
from .watchlist import normalize_stock_code


DEFAULT_ACCOUNT_ID = "default"

COMMISSION_RATE = 0.0003
COMMISSION_MIN = 5.0
STAMP_DUTY_RATE = 0.0005
TRANSFER_FEE_RATE = 0.00001
SLIPPAGE_RATE = 0.0005


def _utc_now_str() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _trade_date_from_text(trade_time: str | None, fallback: str) -> str:
    text = (trade_time or fallback or "").strip()
    return text[:10] if len(text) >= 10 else datetime.utcnow().strftime("%Y-%m-%d")


def _normalize_quantity(quantity: int) -> int:
    amount = int(quantity)
    if amount <= 0:
        raise ValueError("quantity must be greater than 0")
    if amount % 100 != 0:
        raise ValueError("quantity must be a multiple of 100")
    return amount


def _normalize_plan_payload(plan: dict[str, object] | None) -> dict[str, object]:
    if not plan:
        return {}
    planned_holding_days = plan.get("planned_holding_days")
    return {
        "entry_reason": _clean_text(plan.get("entry_reason")),
        "planned_holding_days": int(planned_holding_days) if planned_holding_days not in (None, "") else None,
        "stop_loss_price": float(plan["stop_loss_price"]) if plan.get("stop_loss_price") not in (None, "") else None,
        "take_profit_price": float(plan["take_profit_price"]) if plan.get("take_profit_price") not in (None, "") else None,
        "invalidation_condition": _clean_text(plan.get("invalidation_condition")),
        "plan_note": _clean_text(plan.get("plan_note")),
    }


def _normalize_review_payload(review: dict[str, object] | None) -> dict[str, object]:
    if not review:
        return {}
    return {
        "exit_reason": _clean_text(review.get("exit_reason")),
        "review_rating": _clean_text(review.get("review_rating")),
        "review_summary": _clean_text(review.get("review_summary")),
        "lessons_learned": _clean_text(review.get("lessons_learned")),
    }


def _snapshot_for_code(connection, stock_code: str):
    return connection.execute(
        """
        SELECT stock_code, stock_name, market, price, trade_time, fetched_at
        FROM stock_market_snapshot
        WHERE stock_code = ?
        """,
        (stock_code,),
    ).fetchone()


def _account_row(connection, account_id: str = DEFAULT_ACCOUNT_ID):
    row = connection.execute(
        """
        SELECT account_id, account_name, initial_cash, cash_balance, created_at, updated_at
        FROM paper_accounts
        WHERE account_id = ?
        """,
        (account_id,),
    ).fetchone()
    if not row:
        raise RuntimeError("paper account not initialized")
    return row


def _active_plan(connection, account_id: str, stock_code: str):
    return connection.execute(
        """
        SELECT *
        FROM paper_trade_plans
        WHERE account_id = ? AND stock_code = ? AND status = 'open'
        ORDER BY id DESC
        LIMIT 1
        """,
        (account_id, stock_code),
    ).fetchone()


def _resolve_plan_fields(plan: dict[str, object], *, fallback_note: str = "", existing=None) -> dict[str, object]:
    return {
        "entry_reason": plan.get("entry_reason")
        or (existing["entry_reason"] if existing else None)
        or _clean_text(fallback_note)
        or "未填写计划",
        "planned_holding_days": plan.get("planned_holding_days")
        if plan.get("planned_holding_days") is not None
        else (existing["planned_holding_days"] if existing else None),
        "stop_loss_price": plan.get("stop_loss_price")
        if plan.get("stop_loss_price") is not None
        else (existing["stop_loss_price"] if existing else None),
        "take_profit_price": plan.get("take_profit_price")
        if plan.get("take_profit_price") is not None
        else (existing["take_profit_price"] if existing else None),
        "invalidation_condition": plan.get("invalidation_condition")
        or (existing["invalidation_condition"] if existing else None),
        "plan_note": plan.get("plan_note")
        or (existing["plan_note"] if existing else None)
        or _clean_text(fallback_note),
    }


def _trade_rules_payload() -> dict[str, object]:
    return {
        "commission_rate": COMMISSION_RATE,
        "commission_min": COMMISSION_MIN,
        "stamp_duty_rate": STAMP_DUTY_RATE,
        "transfer_fee_rate": TRANSFER_FEE_RATE,
        "slippage_rate": SLIPPAGE_RATE,
        "summary": "模拟盘按A股整手交易、T+1、双边佣金+过户费、卖出印花税、固定滑点执行。",
    }


def _estimate_trade(quoted_price: float, quantity: int, *, side: str, market: str | None) -> dict[str, float]:
    slippage_direction = 1.0 + SLIPPAGE_RATE if side == "buy" else 1.0 - SLIPPAGE_RATE
    execution_price = round(quoted_price * slippage_direction, 4)
    gross_amount = round(execution_price * quantity, 2)
    commission_fee = round(max(gross_amount * COMMISSION_RATE, COMMISSION_MIN), 2)
    transfer_fee = round(gross_amount * TRANSFER_FEE_RATE, 2) if market in {"SH", "SZ", "BJ"} else 0.0
    stamp_duty_fee = round(gross_amount * STAMP_DUTY_RATE, 2) if side == "sell" else 0.0
    total_fees = round(commission_fee + transfer_fee + stamp_duty_fee, 2)
    cash_delta = round(gross_amount + total_fees, 2) if side == "buy" else round(gross_amount - total_fees, 2)
    return {
        "quoted_price": round(quoted_price, 4),
        "execution_price": execution_price,
        "gross_amount": gross_amount,
        "commission_fee": commission_fee,
        "transfer_fee": transfer_fee,
        "stamp_duty_fee": stamp_duty_fee,
        "slippage_rate": SLIPPAGE_RATE,
        "total_fees": total_fees,
        "cash_delta": cash_delta,
    }


def _sellable_quantity(connection, account_id: str, stock_code: str, current_trade_date: str) -> int:
    row = connection.execute(
        """
        SELECT COALESCE(SUM(remaining_quantity), 0) AS sellable_quantity
        FROM paper_position_lots
        WHERE account_id = ?
          AND stock_code = ?
          AND remaining_quantity > 0
          AND trade_date < ?
        """,
        (account_id, stock_code, current_trade_date),
    ).fetchone()
    return int(row["sellable_quantity"] or 0) if row else 0


def _sync_position_from_lots(connection, account_id: str, stock_code: str, snapshot, now: str) -> tuple[int, float]:
    lot_summary = connection.execute(
        """
        SELECT
            COALESCE(SUM(remaining_quantity), 0) AS quantity,
            CASE
                WHEN COALESCE(SUM(remaining_quantity), 0) > 0
                THEN SUM(remaining_quantity * cost_price) / SUM(remaining_quantity)
                ELSE NULL
            END AS avg_cost,
            MIN(created_at) AS opened_at
        FROM paper_position_lots
        WHERE account_id = ?
          AND stock_code = ?
          AND remaining_quantity > 0
        """,
        (account_id, stock_code),
    ).fetchone()
    quantity = int(lot_summary["quantity"] or 0)
    avg_cost = float(lot_summary["avg_cost"] or 0)
    if quantity <= 0:
        connection.execute(
            """
            DELETE FROM paper_positions
            WHERE account_id = ? AND stock_code = ?
            """,
            (account_id, stock_code),
        )
        return 0, 0.0

    connection.execute(
        """
        INSERT INTO paper_positions (
            account_id, stock_code, stock_name, market, quantity, avg_cost, opened_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(account_id, stock_code) DO UPDATE SET
            stock_name = excluded.stock_name,
            market = excluded.market,
            quantity = excluded.quantity,
            avg_cost = excluded.avg_cost,
            updated_at = excluded.updated_at
        """,
        (
            account_id,
            stock_code,
            snapshot["stock_name"],
            snapshot["market"],
            quantity,
            round(avg_cost, 4),
            lot_summary["opened_at"] or now,
            now,
        ),
    )
    return quantity, round(avg_cost, 4)


def _consume_sell_lots(connection, account_id: str, stock_code: str, quantity: int, current_trade_date: str, now: str) -> float:
    remaining_to_sell = quantity
    total_cost = 0.0
    lots = connection.execute(
        """
        SELECT id, remaining_quantity, cost_price
        FROM paper_position_lots
        WHERE account_id = ?
          AND stock_code = ?
          AND remaining_quantity > 0
          AND trade_date < ?
        ORDER BY trade_date ASC, id ASC
        """,
        (account_id, stock_code, current_trade_date),
    ).fetchall()
    for lot in lots:
        if remaining_to_sell <= 0:
            break
        available = int(lot["remaining_quantity"])
        used = min(available, remaining_to_sell)
        total_cost += used * float(lot["cost_price"])
        connection.execute(
            """
            UPDATE paper_position_lots
            SET remaining_quantity = ?, updated_at = ?
            WHERE id = ?
            """,
            (available - used, now, int(lot["id"])),
        )
        remaining_to_sell -= used
    if remaining_to_sell > 0:
        raise ValueError("insufficient sellable quantity")
    return round(total_cost, 2)


def _create_trade_plan(
    connection,
    *,
    account_id: str,
    snapshot,
    trade_id: int | None,
    opened_at: str,
    plan: dict[str, object],
    note: str,
) -> int:
    fields = _resolve_plan_fields(plan, fallback_note=note)
    cursor = connection.execute(
        """
        INSERT INTO paper_trade_plans (
            account_id, stock_code, stock_name, market, status,
            opened_trade_id, entry_reason, planned_holding_days,
            stop_loss_price, take_profit_price, invalidation_condition,
            plan_note, opened_at, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            account_id,
            snapshot["stock_code"],
            snapshot["stock_name"],
            snapshot["market"],
            trade_id,
            fields["entry_reason"],
            fields["planned_holding_days"],
            fields["stop_loss_price"],
            fields["take_profit_price"],
            fields["invalidation_condition"],
            fields["plan_note"],
            opened_at,
            opened_at,
            opened_at,
        ),
    )
    return int(cursor.lastrowid)


def _update_open_plan(
    connection,
    plan_row,
    *,
    plan: dict[str, object],
    note: str,
    updated_at: str,
    trade_id: int | None = None,
) -> None:
    fields = _resolve_plan_fields(plan, fallback_note=note, existing=plan_row)
    connection.execute(
        """
        UPDATE paper_trade_plans
        SET opened_trade_id = COALESCE(opened_trade_id, ?),
            entry_reason = ?,
            planned_holding_days = ?,
            stop_loss_price = ?,
            take_profit_price = ?,
            invalidation_condition = ?,
            plan_note = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            trade_id,
            fields["entry_reason"],
            fields["planned_holding_days"],
            fields["stop_loss_price"],
            fields["take_profit_price"],
            fields["invalidation_condition"],
            fields["plan_note"],
            updated_at,
            int(plan_row["id"]),
        ),
    )


def _close_plan(connection, plan_row, *, trade_id: int, closed_at: str, review: dict[str, object]) -> None:
    connection.execute(
        """
        UPDATE paper_trade_plans
        SET status = 'closed',
            closed_trade_id = ?,
            closed_at = ?,
            exit_reason = COALESCE(?, exit_reason),
            review_rating = COALESCE(?, review_rating),
            review_summary = COALESCE(?, review_summary),
            lessons_learned = COALESCE(?, lessons_learned),
            updated_at = ?
        WHERE id = ?
        """,
        (
            trade_id,
            closed_at,
            review.get("exit_reason"),
            review.get("review_rating"),
            review.get("review_summary"),
            review.get("lessons_learned"),
            closed_at,
            int(plan_row["id"]),
        ),
    )


def get_paper_portfolio(account_id: str = DEFAULT_ACCOUNT_ID) -> dict[str, object]:
    init_db()
    with get_connection() as connection:
        account = dict(_account_row(connection, account_id))
        position_rows = connection.execute(
            """
            SELECT
                p.stock_code,
                COALESCE(s.stock_name, p.stock_name) AS stock_name,
                COALESCE(s.market, p.market) AS market,
                p.quantity,
                p.avg_cost,
                p.opened_at,
                s.price AS current_price,
                s.change_pct,
                s.trade_time,
                tp.id AS plan_id,
                tp.entry_reason,
                tp.planned_holding_days,
                tp.stop_loss_price,
                tp.take_profit_price,
                tp.invalidation_condition,
                tp.plan_note,
                tp.opened_at AS plan_opened_at,
                (
                    SELECT COALESCE(SUM(l.remaining_quantity), 0)
                    FROM paper_position_lots l
                    WHERE l.account_id = p.account_id
                      AND l.stock_code = p.stock_code
                      AND l.remaining_quantity > 0
                      AND l.trade_date < CASE
                          WHEN s.trade_time IS NOT NULL THEN substr(s.trade_time, 1, 10)
                          ELSE substr(p.updated_at, 1, 10)
                      END
                ) AS sellable_quantity,
                CASE
                    WHEN s.price IS NOT NULL THEN ROUND(p.quantity * s.price, 2)
                    ELSE NULL
                END AS market_value,
                CASE
                    WHEN s.price IS NOT NULL THEN ROUND((s.price - p.avg_cost) * p.quantity, 2)
                    ELSE NULL
                END AS unrealized_pnl
            FROM paper_positions p
            LEFT JOIN stock_market_snapshot s ON s.stock_code = p.stock_code
            LEFT JOIN paper_trade_plans tp ON tp.id = (
                SELECT id
                FROM paper_trade_plans
                WHERE account_id = p.account_id
                  AND stock_code = p.stock_code
                  AND status = 'open'
                ORDER BY id DESC
                LIMIT 1
            )
            WHERE p.account_id = ?
            ORDER BY p.updated_at DESC, p.stock_code
            """,
            (account_id,),
        ).fetchall()
        trade_rows = connection.execute(
            """
            SELECT
                t.id,
                t.stock_code,
                t.stock_name,
                t.market,
                t.plan_id,
                t.side,
                t.quantity,
                t.quoted_price,
                t.price,
                t.amount,
                t.gross_amount,
                t.total_fees,
                t.commission_fee,
                t.stamp_duty_fee,
                t.transfer_fee,
                t.slippage_rate,
                t.net_amount,
                t.realized_pnl,
                t.note,
                t.trade_time,
                t.created_at,
                tp.status AS plan_status,
                tp.entry_reason,
                tp.planned_holding_days,
                tp.exit_reason,
                tp.review_rating,
                tp.review_summary,
                tp.lessons_learned
            FROM paper_trades t
            LEFT JOIN paper_trade_plans tp ON tp.id = t.plan_id
            WHERE t.account_id = ?
            ORDER BY t.trade_time DESC, t.id DESC
            LIMIT 60
            """,
            (account_id,),
        ).fetchall()
        realized_pnl_row = connection.execute(
            """
            SELECT COALESCE(SUM(realized_pnl), 0) AS realized_pnl
            FROM paper_trades
            WHERE account_id = ?
            """,
            (account_id,),
        ).fetchone()
        fee_row = connection.execute(
            """
            SELECT COALESCE(SUM(total_fees), 0) AS total_fees
            FROM paper_trades
            WHERE account_id = ?
            """,
            (account_id,),
        ).fetchone()

    positions = []
    for row in position_rows:
        item = dict(row)
        item["sellable_quantity"] = int(item["sellable_quantity"] or 0)
        item["frozen_quantity"] = max(int(item["quantity"] or 0) - item["sellable_quantity"], 0)
        positions.append(item)
    trades = [dict(row) for row in trade_rows]
    market_value = round(sum(float(item["market_value"] or 0) for item in positions), 2)
    unrealized_pnl = round(sum(float(item["unrealized_pnl"] or 0) for item in positions), 2)
    cash_balance = float(account["cash_balance"])
    total_assets = round(cash_balance + market_value, 2)
    initial_cash = float(account["initial_cash"])
    total_return_pct = round(((total_assets / initial_cash) - 1.0) * 100, 2) if initial_cash else 0.0

    return {
        "account": {
            **account,
            "market_value": market_value,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": round(float(realized_pnl_row["realized_pnl"] or 0), 2),
            "total_fees": round(float(fee_row["total_fees"] or 0), 2),
            "total_assets": total_assets,
            "position_count": len(positions),
            "total_return_pct": total_return_pct,
            "trade_rules": _trade_rules_payload(),
        },
        "positions": positions,
        "trades": trades,
    }


def execute_paper_order(
    *,
    stock_code: str,
    side: str,
    quantity: int,
    price: float | None = None,
    note: str = "",
    plan: dict[str, object] | None = None,
    review: dict[str, object] | None = None,
    account_id: str = DEFAULT_ACCOUNT_ID,
) -> dict[str, object]:
    init_db()
    normalized_code = normalize_stock_code(stock_code)
    normalized_side = side.strip().lower()
    if normalized_side not in {"buy", "sell"}:
        raise ValueError("side must be buy or sell")
    normalized_quantity = _normalize_quantity(quantity)
    normalized_plan = _normalize_plan_payload(plan)
    normalized_review = _normalize_review_payload(review)

    with get_connection() as connection:
        account = _account_row(connection, account_id)
        snapshot = _snapshot_for_code(connection, normalized_code)
        if not snapshot:
            raise ValueError("stock snapshot not found")

        market_price = float(snapshot["price"] or 0)
        if market_price <= 0 and price is None:
            raise ValueError("current price is unavailable")

        quoted_price = float(price) if price is not None else market_price
        if quoted_price <= 0:
            raise ValueError("price must be greater than 0")

        now = _utc_now_str()
        trade_time = snapshot["trade_time"] or now
        trade_date = _trade_date_from_text(trade_time, now)
        estimate = _estimate_trade(quoted_price, normalized_quantity, side=normalized_side, market=snapshot["market"])
        active_plan = _active_plan(connection, account_id, normalized_code)
        cash_balance = float(account["cash_balance"])
        realized_pnl = 0.0

        if normalized_side == "buy":
            if cash_balance < estimate["cash_delta"]:
                raise ValueError("insufficient cash balance")
            lot_cost_price = round(estimate["cash_delta"] / normalized_quantity, 4)
            connection.execute(
                """
                INSERT INTO paper_position_lots (
                    account_id, stock_code, stock_name, market, trade_date, trade_time,
                    quantity, remaining_quantity, cost_price, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account_id,
                    normalized_code,
                    snapshot["stock_name"],
                    snapshot["market"],
                    trade_date,
                    trade_time,
                    normalized_quantity,
                    normalized_quantity,
                    lot_cost_price,
                    now,
                    now,
                ),
            )
            cash_balance -= estimate["cash_delta"]
            next_quantity, next_avg_cost = _sync_position_from_lots(connection, account_id, normalized_code, snapshot, now)
        else:
            sellable_quantity = _sellable_quantity(connection, account_id, normalized_code, trade_date)
            if sellable_quantity < normalized_quantity:
                raise ValueError(f"T+1限制：今日可卖 {sellable_quantity} 股，无法卖出 {normalized_quantity} 股")
            cost_basis = _consume_sell_lots(connection, account_id, normalized_code, normalized_quantity, trade_date, now)
            cash_balance += estimate["cash_delta"]
            realized_pnl = round(estimate["cash_delta"] - cost_basis, 2)
            next_quantity, next_avg_cost = _sync_position_from_lots(connection, account_id, normalized_code, snapshot, now)

        connection.execute(
            """
            UPDATE paper_accounts
            SET cash_balance = ?, updated_at = ?
            WHERE account_id = ?
            """,
            (round(cash_balance, 2), now, account_id),
        )

        active_plan_id = int(active_plan["id"]) if active_plan else None
        trade_cursor = connection.execute(
            """
            INSERT INTO paper_trades (
                account_id, stock_code, stock_name, market, plan_id, side, quantity,
                quoted_price, price, amount, gross_amount, commission_fee, stamp_duty_fee,
                transfer_fee, slippage_rate, total_fees, net_amount, realized_pnl,
                note, trade_time, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account_id,
                normalized_code,
                snapshot["stock_name"],
                snapshot["market"],
                active_plan_id,
                normalized_side,
                normalized_quantity,
                estimate["quoted_price"],
                estimate["execution_price"],
                estimate["gross_amount"],
                estimate["gross_amount"],
                estimate["commission_fee"],
                estimate["stamp_duty_fee"],
                estimate["transfer_fee"],
                estimate["slippage_rate"],
                estimate["total_fees"],
                estimate["cash_delta"],
                realized_pnl,
                note.strip(),
                trade_time,
                now,
            ),
        )
        trade_id = int(trade_cursor.lastrowid)

        if normalized_side == "buy":
            if active_plan:
                _update_open_plan(
                    connection,
                    active_plan,
                    plan=normalized_plan,
                    note=note,
                    updated_at=now,
                    trade_id=trade_id,
                )
            else:
                created_plan_id = _create_trade_plan(
                    connection,
                    account_id=account_id,
                    snapshot=snapshot,
                    trade_id=trade_id,
                    opened_at=now,
                    plan=normalized_plan,
                    note=note,
                )
                connection.execute(
                    "UPDATE paper_trades SET plan_id = ? WHERE id = ?",
                    (created_plan_id, trade_id),
                )
        elif active_plan and next_quantity == 0:
            _close_plan(connection, active_plan, trade_id=trade_id, closed_at=now, review=normalized_review)

    portfolio = get_paper_portfolio(account_id=account_id)
    return {
        "status": "ok",
        "stock_code": normalized_code,
        "side": normalized_side,
        "quantity": normalized_quantity,
        "quoted_price": estimate["quoted_price"],
        "price": estimate["execution_price"],
        "amount": estimate["gross_amount"],
        "gross_amount": estimate["gross_amount"],
        "total_fees": estimate["total_fees"],
        "net_amount": estimate["cash_delta"],
        "realized_pnl": realized_pnl,
        "position_quantity": next_quantity,
        "avg_cost": next_avg_cost,
        "portfolio": portfolio,
    }


def upsert_trade_plan(
    *,
    stock_code: str,
    entry_reason: str | None = None,
    planned_holding_days: int | None = None,
    stop_loss_price: float | None = None,
    take_profit_price: float | None = None,
    invalidation_condition: str | None = None,
    plan_note: str | None = None,
    account_id: str = DEFAULT_ACCOUNT_ID,
) -> dict[str, object]:
    init_db()
    normalized_code = normalize_stock_code(stock_code)
    normalized_plan = _normalize_plan_payload(
        {
            "entry_reason": entry_reason,
            "planned_holding_days": planned_holding_days,
            "stop_loss_price": stop_loss_price,
            "take_profit_price": take_profit_price,
            "invalidation_condition": invalidation_condition,
            "plan_note": plan_note,
        }
    )
    now = _utc_now_str()
    with get_connection() as connection:
        snapshot = _snapshot_for_code(connection, normalized_code)
        if not snapshot:
            raise ValueError("stock snapshot not found")
        plan_row = _active_plan(connection, account_id, normalized_code)
        if plan_row:
            _update_open_plan(connection, plan_row, plan=normalized_plan, note=plan_note or "", updated_at=now)
            plan_id = int(plan_row["id"])
        else:
            plan_id = _create_trade_plan(
                connection,
                account_id=account_id,
                snapshot=snapshot,
                trade_id=None,
                opened_at=now,
                plan=normalized_plan,
                note=plan_note or "",
            )
        updated = connection.execute(
            """
            SELECT *
            FROM paper_trade_plans
            WHERE id = ?
            """,
            (plan_id,),
        ).fetchone()
    return dict(updated)


def update_trade_review(
    plan_id: int,
    *,
    exit_reason: str | None = None,
    review_rating: str | None = None,
    review_summary: str | None = None,
    lessons_learned: str | None = None,
    account_id: str = DEFAULT_ACCOUNT_ID,
) -> dict[str, object]:
    init_db()
    normalized_review = _normalize_review_payload(
        {
            "exit_reason": exit_reason,
            "review_rating": review_rating,
            "review_summary": review_summary,
            "lessons_learned": lessons_learned,
        }
    )
    now = _utc_now_str()
    with get_connection() as connection:
        plan_row = connection.execute(
            """
            SELECT *
            FROM paper_trade_plans
            WHERE id = ? AND account_id = ?
            """,
            (int(plan_id), account_id),
        ).fetchone()
        if not plan_row:
            raise ValueError("trade plan not found")
        connection.execute(
            """
            UPDATE paper_trade_plans
            SET exit_reason = COALESCE(?, exit_reason),
                review_rating = COALESCE(?, review_rating),
                review_summary = COALESCE(?, review_summary),
                lessons_learned = COALESCE(?, lessons_learned),
                updated_at = ?
            WHERE id = ?
            """,
            (
                normalized_review.get("exit_reason"),
                normalized_review.get("review_rating"),
                normalized_review.get("review_summary"),
                normalized_review.get("lessons_learned"),
                now,
                int(plan_id),
            ),
        )
        updated = connection.execute(
            """
            SELECT *
            FROM paper_trade_plans
            WHERE id = ?
            """,
            (int(plan_id),),
        ).fetchone()
    return dict(updated)
