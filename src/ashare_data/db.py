from __future__ import annotations

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "market.db"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS trade_calendar (
                trade_date TEXT PRIMARY KEY,
                trade_status INTEGER NOT NULL,
                day_week INTEGER NOT NULL,
                fetched_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS daily_bars (
                stock_code TEXT NOT NULL,
                trade_time TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                open REAL,
                close REAL,
                high REAL,
                low REAL,
                volume REAL,
                amount REAL,
                change_pct REAL,
                change REAL,
                turnover_ratio REAL,
                pre_close REAL,
                source TEXT NOT NULL DEFAULT 'adata',
                adjust_type INTEGER NOT NULL,
                k_type INTEGER NOT NULL,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (stock_code, trade_date, adjust_type, k_type)
            );

            CREATE INDEX IF NOT EXISTS idx_daily_bars_stock_date
            ON daily_bars (stock_code, trade_date DESC);

            CREATE TABLE IF NOT EXISTS watchlist (
                stock_code TEXT PRIMARY KEY,
                display_name TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_synced_at TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                origin TEXT NOT NULL DEFAULT 'user'
            );

            CREATE TABLE IF NOT EXISTS stock_catalog (
                stock_code TEXT PRIMARY KEY,
                stock_name TEXT NOT NULL,
                source TEXT NOT NULL,
                market TEXT,
                group_name TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS realtime_quotes (
                stock_code TEXT PRIMARY KEY,
                stock_name TEXT,
                price REAL,
                change_amount REAL,
                change_pct REAL,
                volume REAL,
                amount REAL,
                source TEXT NOT NULL,
                trade_time TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS stock_market_snapshot (
                stock_code TEXT PRIMARY KEY,
                market TEXT,
                stock_name TEXT NOT NULL,
                price REAL,
                change_amount REAL,
                change_pct REAL,
                turnover_ratio REAL,
                volume_ratio REAL,
                pe_ratio REAL,
                pb_ratio REAL,
                amplitude REAL,
                open REAL,
                high REAL,
                low REAL,
                pre_close REAL,
                volume REAL,
                amount REAL,
                circulating_market_value REAL,
                total_market_value REAL,
                source TEXT NOT NULL,
                trade_time TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_stock_market_snapshot_change_pct
            ON stock_market_snapshot (change_pct DESC, stock_code ASC);

            CREATE TABLE IF NOT EXISTS market_index_snapshot (
                index_code TEXT PRIMARY KEY,
                index_name TEXT NOT NULL,
                price REAL,
                change_amount REAL,
                change_pct REAL,
                open REAL,
                high REAL,
                low REAL,
                pre_close REAL,
                volume REAL,
                amount REAL,
                source TEXT NOT NULL,
                trade_time TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS market_overview_cache (
                cache_key TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                source TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS stock_profile_cache (
                stock_code TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                source TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS paper_accounts (
                account_id TEXT PRIMARY KEY,
                account_name TEXT NOT NULL,
                initial_cash REAL NOT NULL,
                cash_balance REAL NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS paper_positions (
                account_id TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                market TEXT,
                quantity INTEGER NOT NULL,
                avg_cost REAL NOT NULL,
                opened_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (account_id, stock_code)
            );

            CREATE TABLE IF NOT EXISTS paper_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                market TEXT,
                plan_id INTEGER,
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                quoted_price REAL,
                price REAL NOT NULL,
                amount REAL NOT NULL,
                gross_amount REAL,
                commission_fee REAL NOT NULL DEFAULT 0,
                stamp_duty_fee REAL NOT NULL DEFAULT 0,
                transfer_fee REAL NOT NULL DEFAULT 0,
                slippage_rate REAL NOT NULL DEFAULT 0,
                total_fees REAL NOT NULL DEFAULT 0,
                net_amount REAL,
                realized_pnl REAL NOT NULL DEFAULT 0,
                note TEXT,
                trade_time TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_paper_trades_account_time
            ON paper_trades (account_id, trade_time DESC, id DESC);

            CREATE TABLE IF NOT EXISTS paper_position_lots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                market TEXT,
                trade_date TEXT NOT NULL,
                trade_time TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                remaining_quantity INTEGER NOT NULL,
                cost_price REAL NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_paper_position_lots_account_code
            ON paper_position_lots (account_id, stock_code, trade_date ASC, id ASC);

            CREATE TABLE IF NOT EXISTS paper_trade_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                market TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                opened_trade_id INTEGER,
                closed_trade_id INTEGER,
                entry_reason TEXT,
                planned_holding_days INTEGER,
                stop_loss_price REAL,
                take_profit_price REAL,
                invalidation_condition TEXT,
                plan_note TEXT,
                exit_reason TEXT,
                review_rating TEXT,
                review_summary TEXT,
                lessons_learned TEXT,
                opened_at TEXT NOT NULL,
                closed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_paper_trade_plans_account_status
            ON paper_trade_plans (account_id, status, updated_at DESC, id DESC);

            CREATE TABLE IF NOT EXISTS ai_trade_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                action TEXT NOT NULL,
                summary TEXT,
                entry_reason TEXT,
                planned_holding_days INTEGER,
                buy_price REAL,
                stop_loss_price REAL,
                take_profit_price REAL,
                invalidation_condition TEXT,
                plan_note TEXT,
                quantity INTEGER,
                position_size_pct REAL,
                confidence TEXT,
                risk_level TEXT,
                reasoning_json TEXT,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                raw_response TEXT,
                status TEXT NOT NULL DEFAULT 'generated',
                applied_plan_id INTEGER,
                executed_trade_id INTEGER,
                exit_reason TEXT,
                review_rating TEXT,
                review_summary TEXT,
                lessons_learned TEXT,
                reviewed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_ai_trade_decisions_account_created
            ON ai_trade_decisions (account_id, created_at DESC, id DESC);

            CREATE INDEX IF NOT EXISTS idx_ai_trade_decisions_stock_created
            ON ai_trade_decisions (stock_code, created_at DESC, id DESC);

            CREATE TABLE IF NOT EXISTS screening_chat_sessions (
                context_key TEXT PRIMARY KEY,
                summary_json TEXT NOT NULL,
                messages_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_screening_chat_sessions_updated
            ON screening_chat_sessions (updated_at DESC, context_key ASC);
            """
        )
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(daily_bars)").fetchall()
        }
        if "source" not in columns:
            connection.execute(
                "ALTER TABLE daily_bars ADD COLUMN source TEXT NOT NULL DEFAULT 'adata'"
            )
        watchlist_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(watchlist)").fetchall()
        }
        if "last_synced_at" not in watchlist_columns:
            connection.execute(
                "ALTER TABLE watchlist ADD COLUMN last_synced_at TEXT"
            )
        if "buy_price" not in watchlist_columns:
            connection.execute(
                "ALTER TABLE watchlist ADD COLUMN buy_price REAL"
            )
        if "take_profit_price" not in watchlist_columns:
            connection.execute(
                "ALTER TABLE watchlist ADD COLUMN take_profit_price REAL"
            )
        if "stop_loss_price" not in watchlist_columns:
            connection.execute(
                "ALTER TABLE watchlist ADD COLUMN stop_loss_price REAL"
            )
        if "is_active" not in watchlist_columns:
            connection.execute(
                "ALTER TABLE watchlist ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"
            )
        if "origin" not in watchlist_columns:
            connection.execute(
                "ALTER TABLE watchlist ADD COLUMN origin TEXT NOT NULL DEFAULT 'user'"
            )
        if "default_trade_quantity" not in watchlist_columns:
            connection.execute(
                "ALTER TABLE watchlist ADD COLUMN default_trade_quantity INTEGER NOT NULL DEFAULT 100"
            )
        paper_trade_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(paper_trades)").fetchall()
        }
        if "plan_id" not in paper_trade_columns:
            connection.execute(
                "ALTER TABLE paper_trades ADD COLUMN plan_id INTEGER"
            )
        for column_name, column_sql in (
            ("quoted_price", "ALTER TABLE paper_trades ADD COLUMN quoted_price REAL"),
            ("gross_amount", "ALTER TABLE paper_trades ADD COLUMN gross_amount REAL"),
            ("commission_fee", "ALTER TABLE paper_trades ADD COLUMN commission_fee REAL NOT NULL DEFAULT 0"),
            ("stamp_duty_fee", "ALTER TABLE paper_trades ADD COLUMN stamp_duty_fee REAL NOT NULL DEFAULT 0"),
            ("transfer_fee", "ALTER TABLE paper_trades ADD COLUMN transfer_fee REAL NOT NULL DEFAULT 0"),
            ("slippage_rate", "ALTER TABLE paper_trades ADD COLUMN slippage_rate REAL NOT NULL DEFAULT 0"),
            ("total_fees", "ALTER TABLE paper_trades ADD COLUMN total_fees REAL NOT NULL DEFAULT 0"),
            ("net_amount", "ALTER TABLE paper_trades ADD COLUMN net_amount REAL"),
        ):
            if column_name not in paper_trade_columns:
                connection.execute(column_sql)
        ai_trade_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(ai_trade_decisions)").fetchall()
        }
        for column_name, column_sql in (
            ("exit_reason", "ALTER TABLE ai_trade_decisions ADD COLUMN exit_reason TEXT"),
            ("review_rating", "ALTER TABLE ai_trade_decisions ADD COLUMN review_rating TEXT"),
            ("review_summary", "ALTER TABLE ai_trade_decisions ADD COLUMN review_summary TEXT"),
            ("lessons_learned", "ALTER TABLE ai_trade_decisions ADD COLUMN lessons_learned TEXT"),
            ("reviewed_at", "ALTER TABLE ai_trade_decisions ADD COLUMN reviewed_at TEXT"),
        ):
            if column_name not in ai_trade_columns:
                connection.execute(column_sql)
        connection.execute(
            """
            UPDATE watchlist
            SET is_active = 0,
                origin = 'imported'
            WHERE notes IN ('Imported from python-vue-stock', 'Imported candidate')
            """
        )

        stock_catalog_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(stock_catalog)").fetchall()
        }
        if "market" not in stock_catalog_columns:
            connection.execute(
                "ALTER TABLE stock_catalog ADD COLUMN market TEXT"
            )
        account_exists = connection.execute(
            "SELECT 1 FROM paper_accounts WHERE account_id = 'default' LIMIT 1"
        ).fetchone()
        if not account_exists:
            connection.execute(
                """
                INSERT INTO paper_accounts (
                    account_id, account_name, initial_cash, cash_balance, created_at, updated_at
                )
                VALUES ('default', 'AI 模拟账户', 20000, 20000, datetime('now'), datetime('now'))
                """
            )
        connection.execute(
            """
            INSERT INTO paper_position_lots (
                account_id, stock_code, stock_name, market,
                trade_date, trade_time, quantity, remaining_quantity,
                cost_price, created_at, updated_at
            )
            SELECT
                p.account_id,
                p.stock_code,
                p.stock_name,
                p.market,
                substr(p.opened_at, 1, 10),
                p.opened_at,
                p.quantity,
                p.quantity,
                p.avg_cost,
                p.opened_at,
                p.updated_at
            FROM paper_positions p
            WHERE NOT EXISTS (
                SELECT 1
                FROM paper_position_lots l
                WHERE l.account_id = p.account_id
                  AND l.stock_code = p.stock_code
                  AND l.remaining_quantity > 0
            )
            """
        )
