from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read_local_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for file_name in (".env.local", ".env"):
        env_path = PROJECT_ROOT / file_name
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    return values


def get_tushare_token() -> str:
    if os.environ.get("TUSHARE_TOKEN"):
        return os.environ["TUSHARE_TOKEN"].strip()
    if os.environ.get("TS_TOKEN"):
        return os.environ["TS_TOKEN"].strip()

    local_env = _read_local_env()
    for key in ("TUSHARE_TOKEN", "TS_TOKEN"):
        if local_env.get(key):
            return local_env[key].strip()
    return ""
