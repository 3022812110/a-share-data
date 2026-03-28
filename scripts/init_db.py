from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ashare_data.db import DB_PATH, init_db


def main() -> None:
    init_db()
    print(f"database ready: {DB_PATH}")


if __name__ == "__main__":
    main()
