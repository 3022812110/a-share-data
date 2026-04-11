from __future__ import annotations

import json
from typing import Any

from .db import get_connection, init_db


def load_screening_chat_history(context_key: str) -> dict[str, Any]:
    init_db()
    normalized_key = str(context_key or "").strip()
    if not normalized_key:
        return {"context_key": "", "messages": [], "updated_at": None}

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT context_key, messages_json, updated_at
            FROM screening_chat_sessions
            WHERE context_key = ?
            """,
            (normalized_key,),
        ).fetchone()

    if not row:
        return {"context_key": normalized_key, "messages": [], "updated_at": None}

    try:
        messages = json.loads(row["messages_json"] or "[]")
    except ValueError:
        messages = []
    if not isinstance(messages, list):
        messages = []

    return {
        "context_key": row["context_key"],
        "messages": messages,
        "updated_at": row["updated_at"],
    }


def save_screening_chat_history(
    *,
    context_key: str,
    summary: dict[str, Any] | None,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    init_db()
    normalized_key = str(context_key or "").strip()
    if not normalized_key:
        raise ValueError("context_key is required")

    normalized_messages = _normalize_messages(messages)
    now = _utc_now_str()
    with get_connection() as connection:
        if normalized_messages:
            connection.execute(
                """
                INSERT INTO screening_chat_sessions (
                    context_key, summary_json, messages_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(context_key) DO UPDATE SET
                    summary_json = excluded.summary_json,
                    messages_json = excluded.messages_json,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized_key,
                    json.dumps(summary or {}, ensure_ascii=False),
                    json.dumps(normalized_messages, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        else:
            connection.execute(
                """
                DELETE FROM screening_chat_sessions
                WHERE context_key = ?
                """,
                (normalized_key,),
            )

    return {
        "context_key": normalized_key,
        "messages": normalized_messages,
        "updated_at": now if normalized_messages else None,
    }


def _normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in messages:
        role = str(item.get("role") or "").strip().lower()
        content = str(item.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue

        raw_codes = item.get("stockCodes") or item.get("stock_codes") or []
        stock_codes: list[str] = []
        if isinstance(raw_codes, list):
            for code in raw_codes[:8]:
                normalized_code = str(code or "").strip()
                if len(normalized_code) == 6 and normalized_code.isdigit() and normalized_code not in stock_codes:
                    stock_codes.append(normalized_code)

        normalized.append(
            {
                "id": str(item.get("id") or "").strip() or None,
                "role": role,
                "content": content,
                "stockCodes": stock_codes,
            }
        )
    return normalized[-40:]


def _utc_now_str() -> str:
    from datetime import datetime

    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
