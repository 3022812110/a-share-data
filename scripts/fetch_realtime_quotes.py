from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ashare_data.sync import sync_realtime_quotes_for_codes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch realtime quotes into SQLite.")
    parser.add_argument("--stock-codes", nargs="+", required=True, help="One or more A-share codes")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = sync_realtime_quotes_for_codes(args.stock_codes)
    print(f"synced realtime rows: {len(rows)}")
    for row in rows[:10]:
        print(f"{row['stock_code']} {row['stock_name']} {row['price']} {row['change_pct']}")


if __name__ == "__main__":
    main()
