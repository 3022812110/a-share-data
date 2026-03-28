from __future__ import annotations

from datetime import datetime

import adata
import pandas as pd

from .watchlist import normalize_stock_code


def fetch_realtime_quotes(stock_codes: list[str]) -> pd.DataFrame:
    normalized_codes = [normalize_stock_code(code) for code in stock_codes if normalize_stock_code(code)]
    if not normalized_codes:
        return pd.DataFrame()

    frame = adata.stock.market.sina_market.list_market_current(code_list=normalized_codes)
    if frame is None or frame.empty:
        return pd.DataFrame()

    result = frame.copy()
    result["stock_code"] = result["stock_code"].astype(str)
    result["stock_name"] = result["short_name"].astype(str)
    result["price"] = pd.to_numeric(result["price"], errors="coerce")
    result["change_amount"] = pd.to_numeric(result["change"], errors="coerce")
    result["change_pct"] = pd.to_numeric(result["change_pct"], errors="coerce")
    result["volume"] = pd.to_numeric(result["volume"], errors="coerce")
    result["amount"] = pd.to_numeric(result["amount"], errors="coerce")
    result["source"] = "sina"
    result["trade_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result["fetched_at"] = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    return result[
        [
            "stock_code",
            "stock_name",
            "price",
            "change_amount",
            "change_pct",
            "volume",
            "amount",
            "source",
            "trade_time",
            "fetched_at",
        ]
    ]
