from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from typing import Any, Sequence
from uuid import uuid4

import pandas as pd

from .backtesting import ensure_daily_bars_for_backtest
from .db import get_connection, init_db
from .market_regime import ensure_market_index_history
from .strategy_lab import DEFAULT_LOOKBACK_DAYS, MIN_WALK_FORWARD_BARS, evaluate_strategy_walk_forward
from .watchlist import normalize_stock_code


VALIDATION_CACHE_HOURS = 24
MAX_PREVALIDATION_STOCKS = 12


_STATE_LOCK = threading.Lock()
_JOB_STATE: dict[str, Any] = {
    "job_id": None,
    "status": "idle",
    "total": 0,
    "completed": 0,
    "current_stock_code": None,
    "cached_count": 0,
    "errors": [],
    "started_at": None,
    "finished_at": None,
}


def _utc_now_str() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _state_snapshot() -> dict[str, Any]:
    with _STATE_LOCK:
        state = dict(_JOB_STATE)
        state["errors"] = list(_JOB_STATE.get("errors") or [])
    total = int(state.get("total") or 0)
    completed = int(state.get("completed") or 0)
    state["progress_pct"] = round(completed / total * 100, 2) if total else 0.0
    return state


def get_candidate_prevalidation_status() -> dict[str, Any]:
    init_db()
    state = _state_snapshot()
    cutoff = (datetime.utcnow() - timedelta(hours=VALIDATION_CACHE_HOURS)).replace(microsecond=0).isoformat() + "Z"
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(DISTINCT stock_code) AS cached_count
            FROM strategy_candidate_validations
            WHERE created_at >= ?
            """,
            (cutoff,),
        ).fetchone()
    state["cached_count"] = int(row["cached_count"] or 0) if row else 0
    state["cache_hours"] = VALIDATION_CACHE_HOURS
    return state


def load_candidate_validations(
    stock_codes: Sequence[str],
    *,
    max_age_hours: int = VALIDATION_CACHE_HOURS,
) -> dict[str, dict[str, Any]]:
    normalized_codes = []
    for value in stock_codes:
        code = normalize_stock_code(str(value))
        if code and code not in normalized_codes:
            normalized_codes.append(code)
    if not normalized_codes:
        return {}
    cutoff = (datetime.utcnow() - timedelta(hours=max(1, int(max_age_hours)))).replace(microsecond=0).isoformat() + "Z"
    placeholders = ",".join("?" for _ in normalized_codes)
    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT id, stock_code, data_end_date, status, result_json, created_at
            FROM strategy_candidate_validations
            WHERE stock_code IN ({placeholders})
              AND created_at >= ?
            ORDER BY stock_code ASC, created_at DESC, id DESC
            """,
            (*normalized_codes, cutoff),
        ).fetchall()
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = str(row["stock_code"])
        if code in latest:
            continue
        try:
            result = json.loads(row["result_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        latest[code] = {
            **result,
            "validation_id": int(row["id"]),
            "validation_status": row["status"],
            "validated_at": row["created_at"],
            "data_end_date": row["data_end_date"] or result.get("data_end_date"),
        }
    return latest


def start_candidate_prevalidation(stock_codes: Sequence[str]) -> dict[str, Any]:
    init_db()
    normalized_codes = []
    for value in stock_codes:
        code = normalize_stock_code(str(value))
        if code and code not in normalized_codes:
            normalized_codes.append(code)
    normalized_codes = normalized_codes[:MAX_PREVALIDATION_STOCKS]
    if not normalized_codes:
        return get_candidate_prevalidation_status()

    with _STATE_LOCK:
        if _JOB_STATE.get("status") == "running":
            return _state_snapshot_unlocked()

    cached = load_candidate_validations(normalized_codes)
    pending = [code for code in normalized_codes if code not in cached]
    now = _utc_now_str()
    with _STATE_LOCK:
        _JOB_STATE.update(
            {
                "job_id": uuid4().hex[:12],
                "status": "completed" if not pending else "running",
                "total": len(normalized_codes),
                "completed": len(normalized_codes) - len(pending),
                "current_stock_code": None,
                "cached_count": len(cached),
                "errors": [],
                "started_at": now,
                "finished_at": now if not pending else None,
            }
        )
        state = _state_snapshot_unlocked()
    if not pending:
        return state

    worker = threading.Thread(
        target=_run_prevalidation_job,
        args=(pending,),
        name=f"strategy-prevalidation-{state['job_id']}",
        daemon=True,
    )
    worker.start()
    return state


def _state_snapshot_unlocked() -> dict[str, Any]:
    state = dict(_JOB_STATE)
    state["errors"] = list(_JOB_STATE.get("errors") or [])
    total = int(state.get("total") or 0)
    completed = int(state.get("completed") or 0)
    state["progress_pct"] = round(completed / total * 100, 2) if total else 0.0
    return state


def _run_prevalidation_job(stock_codes: Sequence[str]) -> None:
    errors: list[dict[str, str]] = []
    try:
        market_frame = ensure_market_index_history(min_bars=MIN_WALK_FORWARD_BARS)
    except Exception as error:
        market_frame = pd.DataFrame()
        errors.append({"stock_code": "MARKET", "error": str(error)})

    for stock_code in stock_codes:
        with _STATE_LOCK:
            _JOB_STATE["current_stock_code"] = stock_code
        try:
            frame = ensure_daily_bars_for_backtest(
                stock_code,
                lookback_days=DEFAULT_LOOKBACK_DAYS,
                min_bars=MIN_WALK_FORWARD_BARS,
            )
            evaluation = evaluate_strategy_walk_forward(
                frame,
                stock_code=stock_code,
                market_frame=market_frame,
            )
            record = _build_validation_record(stock_code, evaluation)
            _persist_validation_record(
                stock_code,
                status=str(record.get("validation_status") or evaluation.get("status") or "error"),
                data_end_date=record.get("data_end_date"),
                result=record,
            )
        except Exception as error:
            errors.append({"stock_code": stock_code, "error": str(error)})
            _persist_validation_record(
                stock_code,
                status="error",
                data_end_date=None,
                result={
                    "stock_code": stock_code,
                    "validation_status": "error",
                    "reason": str(error),
                },
            )
        finally:
            with _STATE_LOCK:
                _JOB_STATE["completed"] = int(_JOB_STATE.get("completed") or 0) + 1
                _JOB_STATE["errors"] = list(errors)

    with _STATE_LOCK:
        _JOB_STATE["status"] = "completed_with_errors" if errors else "completed"
        _JOB_STATE["current_stock_code"] = None
        _JOB_STATE["finished_at"] = _utc_now_str()
        _JOB_STATE["errors"] = list(errors)


def _build_validation_record(stock_code: str, evaluation: dict[str, Any]) -> dict[str, Any]:
    if evaluation.get("status") != "ok":
        return {
            **evaluation,
            "stock_code": stock_code,
            "validation_status": str(evaluation.get("status") or "insufficient_data"),
        }
    best_strategy = evaluation["strategies"][0]
    aggregate = best_strategy["aggregate"]
    return {
        "stock_code": stock_code,
        "validation_status": "ok",
        "bars": evaluation["bars"],
        "data_start_date": evaluation["data_start_date"],
        "data_end_date": evaluation["data_end_date"],
        "window_count": evaluation["window_count"],
        "best_strategy_key": best_strategy["key"],
        "best_strategy_name": best_strategy["name"],
        "robustness": aggregate["robustness"],
        "aggregate": aggregate,
        "strategies": evaluation["strategies"],
    }


def _persist_validation_record(
    stock_code: str,
    *,
    status: str,
    data_end_date: str | None,
    result: dict[str, Any],
) -> None:
    created_at = _utc_now_str()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO strategy_candidate_validations (
                stock_code, data_end_date, status, result_json, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                stock_code,
                data_end_date,
                status,
                json.dumps(result, ensure_ascii=False),
                created_at,
            ),
        )
