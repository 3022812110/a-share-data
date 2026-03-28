from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ashare_data.db import DB_PATH, get_connection


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a quick read-only SQLite query.")
    parser.add_argument("--sql", required=True, help="A SELECT query to run against the local SQLite database.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sql = args.sql.strip()
    if not sql.lower().startswith("select"):
        raise SystemExit("Only SELECT queries are allowed.")

    with get_connection() as connection:
        cursor = connection.execute(sql)
        rows = cursor.fetchall()
        columns = [column[0] for column in cursor.description or []]

    print(f"database: {DB_PATH}")
    print("columns:", columns)
    for row in rows:
        print(dict(row))


if __name__ == "__main__":
    main()
