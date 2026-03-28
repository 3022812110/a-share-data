from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ashare_data.collectors import fetch_trade_calendar
from ashare_data.db import get_connection, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch trade calendar into SQLite.")
    parser.add_argument("--year", type=int, default=None, help="Calendar year, for example 2026.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_db()
    frame = fetch_trade_calendar(year=args.year)

    with get_connection() as connection:
        rows = frame.to_dict(orient="records")
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

    print(f"synced trade_calendar rows: {len(frame)}")


if __name__ == "__main__":
    main()
