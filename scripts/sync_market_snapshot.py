from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ashare_data.stock_market import sync_stock_market_snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync full A-share market snapshot into SQLite.")
    parser.add_argument("--trade-date", help="Optional trade date in YYYY-MM-DD format", default=None)
    parser.add_argument("--stock-codes", nargs="*", help="Optional subset of stock codes", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = sync_stock_market_snapshot(
        trade_date=args.trade_date,
        stock_codes=args.stock_codes,
    )
    print(result)


if __name__ == "__main__":
    main()
