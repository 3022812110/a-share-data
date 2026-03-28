from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ashare_data.python_vue_stock_import import DEFAULT_SOURCE_DB, import_python_vue_stock_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import stock pool data from python-vue-stock into a-share-data.")
    parser.add_argument(
        "--source-db",
        default=str(DEFAULT_SOURCE_DB),
        help="Path to python-vue-stock db.sqlite3",
    )
    parser.add_argument(
        "--skip-sync-snapshot",
        action="store_true",
        help="Only import the rows without refreshing realtime market snapshot",
    )
    parser.add_argument(
        "--keep-extra",
        action="store_true",
        help="Keep pre-existing watchlist/snapshot rows not present in python-vue-stock",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = import_python_vue_stock_db(
        args.source_db,
        sync_snapshot=not args.skip_sync_snapshot,
        prune_extra=not args.keep_extra,
    )
    print(result)


if __name__ == "__main__":
    main()
