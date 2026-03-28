from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ashare_data.sync import sync_daily_bars_for_codes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch daily bars into SQLite.")
    parser.add_argument(
        "--stock-codes",
        nargs="+",
        required=True,
        help="One or more A-share codes, for example 000001 600036 600519",
    )
    parser.add_argument("--start-date", required=True, help="Start date in YYYY-MM-DD format")
    parser.add_argument("--end-date", default=None, help="End date in YYYY-MM-DD format")
    parser.add_argument("--adjust-type", type=int, default=1, help="adata adjust_type, default 1")
    parser.add_argument("--k-type", type=int, default=1, help="adata k_type, default 1 for daily")
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    results = sync_daily_bars_for_codes(
        stock_codes=args.stock_codes,
        start_date=args.start_date,
        end_date=args.end_date,
        k_type=args.k_type,
        adjust_type=args.adjust_type,
    )
    total_rows = 0
    for result in results:
        total_rows += int(result["rows"])
        print(f"synced {result['stock_code']}: {result['rows']} rows via {result['source']}")

    print(f"synced total daily_bars rows: {total_rows}")


if __name__ == "__main__":
    main()
