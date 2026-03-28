from __future__ import annotations

import sys
from pathlib import Path

import uvicorn


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def main() -> None:
    uvicorn.run("ashare_data.api_app:app", host="127.0.0.1", port=8001, reload=True)


if __name__ == "__main__":
    main()
