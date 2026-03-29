from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .api_queries import load_ai_screening, load_market_overview, load_market_page, load_stock_detail
from .backtesting import run_backtest
from .db import init_db
from .eastmoney_kline import fetch_stock_kline
from .paper_trading import execute_paper_order, get_paper_portfolio, update_trade_review, upsert_trade_plan
from .stock_market import sync_stock_market_snapshot
from .watchlist import delete_watchlist_item, update_watchlist_targets


class RefreshRequest(BaseModel):
    stock_codes: list[str] | None = None
    trade_date: str | None = None


class WatchlistUpdateRequest(BaseModel):
    display_name: str | None = None
    notes: str | None = None
    buy_price: float | None = Field(default=None, ge=0)
    take_profit_price: float | None = Field(default=None, ge=0)
    stop_loss_price: float | None = Field(default=None, ge=0)
    default_trade_quantity: int | None = Field(default=None, ge=100)


class PaperOrderRequest(BaseModel):
    stock_code: str
    side: Literal["buy", "sell"]
    quantity: int = Field(ge=100)
    price: float | None = Field(default=None, gt=0)
    note: str = ""
    plan: dict[str, object] | None = None
    review: dict[str, object] | None = None


class PaperReviewRequest(BaseModel):
    exit_reason: str | None = None
    review_rating: Literal["good", "ok", "bad"] | None = None
    review_summary: str | None = None
    lessons_learned: str | None = None


class PaperPlanRequest(BaseModel):
    entry_reason: str | None = None
    planned_holding_days: int | None = Field(default=None, ge=1)
    stop_loss_price: float | None = Field(default=None, ge=0)
    take_profit_price: float | None = Field(default=None, ge=0)
    invalidation_condition: str | None = None
    plan_note: str | None = None


app = FastAPI(title="A-Share Data API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/summary")
def summary() -> dict[str, object]:
    return load_market_overview()


@app.get("/api/stocks")
def stocks(
    page: int = 1,
    page_size: int = 100,
    search: str = "",
    sort_by: str = "change_pct",
    sort_order: Literal["asc", "desc"] = "desc",
    watchlist_only: bool = False,
) -> dict[str, object]:
    return load_market_page(
        page=page,
        page_size=page_size,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        watchlist_only=watchlist_only,
    )


@app.get("/api/watchlist")
def watchlist(
    page: int = 1,
    page_size: int = 100,
    search: str = "",
    sort_by: str = "change_pct",
    sort_order: Literal["asc", "desc"] = "desc",
) -> dict[str, object]:
    return load_market_page(
        page=page,
        page_size=page_size,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        watchlist_only=True,
    )


@app.get("/api/screening")
def screening(
    preset: Literal["momentum", "rebound"] = "momentum",
    limit: int = 60,
    query: str = "",
    scope: Literal["all", "watchlist"] = "all",
    min_change_pct: float | None = None,
    min_turnover_ratio: float | None = None,
    min_volume_ratio: float | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    max_pe_ratio: float | None = None,
    min_total_market_value: float | None = None,
    max_total_market_value: float | None = None,
) -> dict[str, object]:
    return load_ai_screening(
        preset=preset,
        limit=limit,
        query=query,
        scope=scope,
        min_change_pct=min_change_pct,
        min_turnover_ratio=min_turnover_ratio,
        min_volume_ratio=min_volume_ratio,
        min_price=min_price,
        max_price=max_price,
        max_pe_ratio=max_pe_ratio,
        min_total_market_value=min_total_market_value,
        max_total_market_value=max_total_market_value,
    )


@app.post("/api/stocks/refresh")
def refresh_stocks(payload: RefreshRequest) -> dict[str, object]:
    return sync_stock_market_snapshot(
        trade_date=payload.trade_date,
        stock_codes=payload.stock_codes,
    )


@app.get("/api/stocks/{stock_code}")
def stock_detail(stock_code: str) -> dict[str, object]:
    result = load_stock_detail(stock_code)
    if not result["snapshot"]:
        raise HTTPException(status_code=404, detail="stock not found")
    return result


@app.get("/api/stocks/{stock_code}/kline")
def stock_kline(
    stock_code: str,
    interval: Literal["1m", "5m", "15m", "30m", "60m", "day", "week", "month"] = "day",
    adjust: Literal["none", "raw", "qfq", "hfq"] = "qfq",
    limit: int = 240,
) -> dict[str, object]:
    try:
        return fetch_stock_kline(
            stock_code,
            interval=interval,
            adjust=adjust,
            limit=limit,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # pragma: no cover - upstream response instability
        raise HTTPException(status_code=502, detail=f"kline fetch failed: {error}") from error


@app.get("/api/paper/portfolio")
def paper_portfolio() -> dict[str, object]:
    return get_paper_portfolio()


@app.post("/api/paper/orders")
def create_paper_order(payload: PaperOrderRequest) -> dict[str, object]:
    try:
        return execute_paper_order(
            stock_code=payload.stock_code,
            side=payload.side,
            quantity=payload.quantity,
            price=payload.price,
            note=payload.note,
            plan=payload.plan,
            review=payload.review,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.put("/api/paper/plans/{plan_id}/review")
def save_paper_review(plan_id: int, payload: PaperReviewRequest) -> dict[str, object]:
    try:
        plan = update_trade_review(
            plan_id,
            exit_reason=payload.exit_reason,
            review_rating=payload.review_rating,
            review_summary=payload.review_summary,
            lessons_learned=payload.lessons_learned,
        )
        return {"status": "ok", "plan": plan}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.put("/api/paper/plans/{stock_code}")
def save_trade_plan(stock_code: str, payload: PaperPlanRequest) -> dict[str, object]:
    try:
        plan = upsert_trade_plan(
            stock_code=stock_code,
            entry_reason=payload.entry_reason,
            planned_holding_days=payload.planned_holding_days,
            stop_loss_price=payload.stop_loss_price,
            take_profit_price=payload.take_profit_price,
            invalidation_condition=payload.invalidation_condition,
            plan_note=payload.plan_note,
        )
        return {"status": "ok", "plan": plan}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/backtest/{stock_code}")
def backtest(
    stock_code: str,
    fast_period: int = 5,
    slow_period: int = 20,
    initial_cash: float = 100000.0,
) -> dict[str, object]:
    try:
        return run_backtest(
            stock_code,
            fast_period=fast_period,
            slow_period=slow_period,
            initial_cash=initial_cash,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.put("/api/watchlist/{stock_code}")
def upsert_watchlist(stock_code: str, payload: WatchlistUpdateRequest) -> dict[str, object]:
    try:
        normalized_code = update_watchlist_targets(
            stock_code,
            display_name=payload.display_name,
            notes=payload.notes,
            buy_price=payload.buy_price,
            take_profit_price=payload.take_profit_price,
            stop_loss_price=payload.stop_loss_price,
            default_trade_quantity=payload.default_trade_quantity,
        )
        return {"stock_code": normalized_code, "status": "ok"}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.delete("/api/watchlist/{stock_code}")
def delete_watchlist(stock_code: str) -> dict[str, object]:
    delete_watchlist_item(stock_code)
    return {"stock_code": stock_code, "status": "ok"}
