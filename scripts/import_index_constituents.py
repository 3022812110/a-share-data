from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ashare_data.index_constituents import import_index_constituents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import HS300 or ZZ500 constituents into watchlist.")
    parser.add_argument("--index-name", choices=["沪深300", "中证500"], required=True)
    parser.add_argument("--date", required=True, help="Query date in YYYY-MM-DD format")
    return parser.parse_args()


def main() -> None:
    result = import_index_constituents(index_name=args.index_name, query_date=args.date)
    print(result)


if __name__ == "__main__":
    args = parse_args()
    main()
