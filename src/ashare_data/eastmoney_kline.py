from __future__ import annotations

from time import time
from typing import Any

import requests


EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
INTERVAL_TO_KLT = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "60m": "60",
    "day": "101",
    "week": "102",
    "month": "103",
}
ADJUST_TO_FQT = {
    "none": "0",
    "raw": "0",
    "qfq": "1",
    "hfq": "2",
}

_SESSION = requests.Session()
_SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        ),
        "Referer": "https://quote.eastmoney.com/",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
)


def _to_float(value: str | float | int | None) -> float | None:
    if value in (None, "", "-", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def stock_code_to_secid(stock_code: str) -> str:
    normalized = stock_code.strip().upper()
    if not normalized:
        return ""

    if "." in normalized:
        code, suffix = normalized.split(".", 1)
        if suffix in {"SH", "SS"}:
            return f"1.{code}"
        if suffix in {"SZ", "BJ"}:
            return f"0.{code}"
        return ""

    if normalized.startswith("SH") and len(normalized) >= 8:
        return f"1.{normalized[2:]}"
    if normalized.startswith(("SZ", "BJ")) and len(normalized) >= 8:
        return f"0.{normalized[2:]}"

    if normalized.isdigit():
        if normalized.startswith("6"):
            return f"1.{normalized}"
        if normalized.startswith(("0", "3", "8", "9")):
            return f"0.{normalized}"

    return ""


def fetch_stock_kline(
    stock_code: str,
    *,
    interval: str = "day",
    adjust: str = "qfq",
    limit: int = 240,
    end: str = "20500101",
) -> dict[str, Any]:
    interval_key = interval.strip().lower()
    adjust_key = adjust.strip().lower()
    klt = INTERVAL_TO_KLT.get(interval_key)
    fqt = ADJUST_TO_FQT.get(adjust_key)
    secid = stock_code_to_secid(stock_code)

    if not secid:
        raise ValueError(f"unsupported stock code: {stock_code}")
    if not klt:
        raise ValueError(f"unsupported interval: {interval}")
    if fqt is None:
        raise ValueError(f"unsupported adjust mode: {adjust}")

    params = {
        "secid": secid,
        "klt": klt,
        "fqt": fqt,
        "end": end or "20500101",
        "lmt": str(max(20, min(int(limit), 1000))),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
        "wbp2u": "|0|0|0|web",
        "_": str(int(time() * 1000)),
    }

    response = _SESSION.get(EASTMONEY_KLINE_URL, params=params, timeout=15)
    response.raise_for_status()
    payload = response.json()

    if payload.get("rc") not in (0, None):
        raise ValueError(f"eastmoney rc error: {payload.get('rc')}")

    data = payload.get("data") or {}
    klines = data.get("klines") or []
    items: list[dict[str, Any]] = []
    for row in klines:
        parts = str(row).split(",")
        if len(parts) < 11:
            continue
        items.append(
            {
                "time": parts[0],
                "open": _to_float(parts[1]),
                "close": _to_float(parts[2]),
                "high": _to_float(parts[3]),
                "low": _to_float(parts[4]),
                "volume": _to_float(parts[5]),
                "amount": _to_float(parts[6]),
                "amplitude_pct": _to_float(parts[7]),
                "change_pct": _to_float(parts[8]),
                "change_amount": _to_float(parts[9]),
                "turnover_ratio": _to_float(parts[10]),
                "market_value": _to_float(parts[11]) if len(parts) > 11 else None,
            }
        )

    return {
        "stock_code": stock_code.upper(),
        "stock_name": data.get("name"),
        "market": data.get("market"),
        "secid": secid,
        "interval": interval_key,
        "interval_code": klt,
        "adjust": adjust_key,
        "items": items,
        "latest": items[-1] if items else None,
    }
