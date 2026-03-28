from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ashare_data.queries import load_watchlist
from ashare_data.sync import sync_daily_bars_for_codes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync daily bars for every stock in watchlist.")
    parser.add_argument("--start-date", required=True, help="Start date in YYYY-MM-DD format")
    parser.add_argument("--end-date", default=None, help="End date in YYYY-MM-DD format")
    parser.add_argument("--adjust-type", type=int, default=1)
    parser.add_argument("--k-type", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    watchlist = load_watchlist()
    stock_codes = watchlist["stock_code"].tolist() if not watchlist.empty else []
    if not stock_codes:
        raise SystemExit("watchlist is empty")

    results = sync_daily_bars_for_codes(
        stock_codes=stock_codes,
        start_date=args.start_date,
        end_date=args.end_date,
        adjust_type=args.adjust_type,
        k_type=args.k_type,
    )
    for result in results:
        print(f"{result['stock_code']}: {result['rows']} rows via {result['source']}")


if __name__ == "__main__":
    main()
