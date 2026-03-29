from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def main() -> None:
    reload_enabled = os.environ.get("API_RELOAD", "").strip().lower() in {"1", "true", "yes", "on"}
    uvicorn.run("ashare_data.api_app:app", host="127.0.0.1", port=8001, reload=reload_enabled)


if __name__ == "__main__":
    main()
