from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
import json
import re
from typing import Any

import requests

from .paper_trading import get_paper_portfolio


OPENAI_COMPAT_PROVIDERS = {"openai", "deepseek", "ollama", "custom"}
SUPPORTED_PROVIDERS = OPENAI_COMPAT_PROVIDERS | {"anthropic", "google"}
DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "ollama": "http://127.0.0.1:11434/v1",
    "anthropic": "https://api.anthropic.com",
    "google": "https://generativelanguage.googleapis.com/v1beta/models",
}
API_KEY_REQUIRED_PROVIDERS = {"openai", "deepseek", "anthropic", "google"}
DEFAULT_SYSTEM_PROMPT = "你是A股研究助手，优先解释当前候选池的机会、风险和观察重点。"
REQUEST_TIMEOUT_SECONDS = 60
MAX_HISTORY_MESSAGES = 10
MAX_CANDIDATE_ITEMS = 60
STOCK_CODE_MARKER_PREFIX = "[[STOCK_CODES:"
STOCK_CODE_MARKER_SUFFIX = "]]"
STREAM_HOLDBACK_CHARS = 64


@dataclass(slots=True)
class PreparedScreeningChat:
    provider: str
    model: str
    api_key: str
    base_url: str
    temperature: float
    max_tokens: int
    stock_lookup: dict[str, dict[str, Any]]
    combined_system_prompt: str
    normalized_messages: list[dict[str, str]]


def analyze_screening_chat(
    *,
    settings: dict[str, Any],
    messages: list[dict[str, Any]],
    summary: dict[str, Any] | None,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    prepared = _prepare_chat_request(
        settings=settings,
        messages=messages,
        summary=summary,
        items=items,
    )

    response_text = _call_provider(
        provider=prepared.provider,
        model=prepared.model,
        api_key=prepared.api_key,
        base_url=prepared.base_url,
        system_prompt=prepared.combined_system_prompt,
        messages=prepared.normalized_messages,
        temperature=prepared.temperature,
        max_tokens=prepared.max_tokens,
    )
    parsed = _parse_model_response(response_text, prepared.stock_lookup)
    if not parsed["content"]:
        raise RuntimeError("模型没有返回有效分析")

    return {
        "content": parsed["content"],
        "stock_codes": parsed["stock_codes"],
        "provider": prepared.provider,
        "model": prepared.model,
    }


def stream_screening_chat(
    *,
    settings: dict[str, Any],
    messages: list[dict[str, Any]],
    summary: dict[str, Any] | None,
    items: list[dict[str, Any]],
) -> Iterator[dict[str, Any]]:
    prepared = _prepare_chat_request(
        settings=settings,
        messages=messages,
        summary=summary,
        items=items,
    )

    accumulated = ""
    visible_buffer = ""
    marker_detected = False

    for chunk in _call_provider_stream(
        provider=prepared.provider,
        model=prepared.model,
        api_key=prepared.api_key,
        base_url=prepared.base_url,
        system_prompt=prepared.combined_system_prompt,
        messages=prepared.normalized_messages,
        temperature=prepared.temperature,
        max_tokens=prepared.max_tokens,
    ):
        if not chunk:
            continue

        accumulated += chunk
        if marker_detected:
            continue

        visible_buffer += chunk
        marker_index = visible_buffer.find(STOCK_CODE_MARKER_PREFIX)
        if marker_index != -1:
            visible_chunk = visible_buffer[:marker_index]
            if visible_chunk:
                yield {"event": "delta", "data": {"content": visible_chunk}}
            marker_detected = True
            continue

        if len(visible_buffer) > STREAM_HOLDBACK_CHARS:
            visible_chunk = visible_buffer[:-STREAM_HOLDBACK_CHARS]
            visible_buffer = visible_buffer[-STREAM_HOLDBACK_CHARS:]
            if visible_chunk:
                yield {"event": "delta", "data": {"content": visible_chunk}}

    parsed = _parse_model_response(accumulated, prepared.stock_lookup)
    if not parsed["content"]:
        raise RuntimeError("模型没有返回有效分析")

    yield {
        "event": "done",
        "data": {
            "content": parsed["content"],
            "stock_codes": parsed["stock_codes"],
            "provider": prepared.provider,
            "model": prepared.model,
        },
    }


def _prepare_chat_request(
    *,
    settings: dict[str, Any],
    messages: list[dict[str, Any]],
    summary: dict[str, Any] | None,
    items: list[dict[str, Any]],
) -> PreparedScreeningChat:
    provider = str(settings.get("provider") or "").strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError("暂不支持该 AI 服务商")

    model = str(settings.get("model") or "").strip()
    if not model:
        raise ValueError("请选择模型")

    api_key = str(settings.get("apiKey") or "").strip()
    base_url = str(settings.get("baseUrl") or "").strip()
    temperature = _clamp_float(settings.get("temperature"), default=0.3, minimum=0.0, maximum=2.0)
    max_tokens = _clamp_int(settings.get("maxTokens"), default=4000, minimum=256, maximum=16000)
    system_prompt = str(settings.get("systemPrompt") or "").strip() or DEFAULT_SYSTEM_PROMPT

    if provider in API_KEY_REQUIRED_PROVIDERS and not api_key:
        raise ValueError("当前服务商需要 API Key")
    if provider == "custom" and not base_url:
        raise ValueError("自定义兼容接口需要填写 Base URL")

    normalized_messages = _normalize_history(messages)
    if not normalized_messages or normalized_messages[-1]["role"] != "user":
        raise ValueError("请输入一个问题")

    portfolio = get_paper_portfolio()
    if not items and not (portfolio.get("positions") or portfolio.get("trades")):
        raise ValueError("当前还没有候选池，也没有模拟交易记录，先更新分析范围或做一笔模拟交易。")

    stock_lookup = _build_stock_lookup(items, portfolio=portfolio)
    combined_system_prompt = _build_system_prompt(
        system_prompt=system_prompt,
        summary=summary or {},
        items=items,
        portfolio=portfolio,
    )
    return PreparedScreeningChat(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        stock_lookup=stock_lookup,
        combined_system_prompt=combined_system_prompt,
        normalized_messages=normalized_messages,
    )


def _normalize_history(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for raw in messages:
        role = str(raw.get("role") or "").strip().lower()
        content = str(raw.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        normalized.append({"role": role, "content": content})

    while normalized and normalized[0]["role"] != "user":
        normalized.pop(0)

    collapsed: list[dict[str, str]] = []
    for message in normalized:
        if collapsed and collapsed[-1]["role"] == message["role"]:
            collapsed[-1]["content"] = f"{collapsed[-1]['content']}\n\n{message['content']}"
        else:
            collapsed.append(message)

    return collapsed[-MAX_HISTORY_MESSAGES:]


def _build_stock_lookup(items: list[dict[str, Any]], *, portfolio: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        stock_code = str(item.get("stock_code") or "").strip()
        if not re.fullmatch(r"\d{6}", stock_code):
            continue
        result[stock_code] = item
    for item in portfolio.get("positions") or []:
        stock_code = str(item.get("stock_code") or "").strip()
        if not re.fullmatch(r"\d{6}", stock_code):
            continue
        result.setdefault(stock_code, item)
    for item in portfolio.get("trades") or []:
        stock_code = str(item.get("stock_code") or "").strip()
        if not re.fullmatch(r"\d{6}", stock_code):
            continue
        result.setdefault(stock_code, item)
    return result


def _build_system_prompt(
    *,
    system_prompt: str,
    summary: dict[str, Any],
    items: list[dict[str, Any]],
    portfolio: dict[str, Any],
) -> str:
    prepared_items = [_serialize_candidate(item) for item in items[:MAX_CANDIDATE_ITEMS]]
    prepared_summary = {
        "preset": summary.get("preset"),
        "preset_label": summary.get("preset_label"),
        "scope": summary.get("scope"),
        "query": summary.get("query"),
        "candidate_count": summary.get("candidate_count"),
        "returned_count": summary.get("returned_count"),
        "applied_conditions": summary.get("applied_conditions") or [],
    }
    prepared_portfolio = _serialize_portfolio_context(portfolio)
    return "\n\n".join(
        [
            system_prompt,
            (
                "你正在为一个本地 A 股研究工作台做分析。"
                "你能看到当前候选池、模拟账户持仓、最近成交和对话历史。"
                "只能基于这些给定数据回答，不要臆造不存在的公告、研报、资金流或基本面结论。"
            ),
            (
                "回答要求："
                "1. 使用中文。"
                "2. 先给结论，再给理由。"
                "3. 如果用户问到某只股票，只要它出现在当前候选池、当前持仓或最近成交里，就可以分析；否则明确说明当前工作台没有这只股票的上下文。"
                "4. 若推荐或点评股票，请优先结合 ai_score、涨跌幅、量比、换手率、估值、持仓状态、交易计划和复盘结果。"
                "5. 如果用户问最近交易、持仓风险、哪笔交易最该处理，优先基于最近成交、当前持仓、盈亏、交易计划和复盘记录回答。"
                "6. stock_codes 最多返回 5 个，可以返回当前候选池、当前持仓或最近成交中的 6 位股票代码。"
                "7. 回答正文使用自然语言，不要使用 Markdown 代码块。"
                "8. 最后一行必须追加控制标记，格式固定为 [[STOCK_CODES:000001,600000]]；如果没有代码就输出 [[STOCK_CODES:]]。"
            ),
            f"当前筛选摘要：{json.dumps(prepared_summary, ensure_ascii=False)}",
            f"当前候选池（已按 ai_score 排序，最多 {MAX_CANDIDATE_ITEMS} 条）：{json.dumps(prepared_items, ensure_ascii=False)}",
            f"当前模拟账户与交易上下文：{json.dumps(prepared_portfolio, ensure_ascii=False)}",
        ]
    )


def _serialize_candidate(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "stock_code": item.get("stock_code"),
        "stock_name": item.get("stock_name"),
        "price": _safe_number(item.get("price")),
        "change_pct": _safe_number(item.get("change_pct")),
        "turnover_ratio": _safe_number(item.get("turnover_ratio")),
        "volume_ratio": _safe_number(item.get("volume_ratio")),
        "pe_ratio": _safe_number(item.get("pe_ratio")),
        "total_market_value": _safe_number(item.get("total_market_value")),
        "buy_price": _safe_number(item.get("buy_price")),
        "in_watchlist": bool(item.get("in_watchlist")),
        "ai_score": _safe_number(item.get("ai_score")),
        "reasons": item.get("reasons") or [],
    }


def _serialize_portfolio_context(portfolio: dict[str, Any]) -> dict[str, Any]:
    account = portfolio.get("account") or {}
    return {
        "account": {
            "cash_balance": _safe_number(account.get("cash_balance")),
            "market_value": _safe_number(account.get("market_value")),
            "unrealized_pnl": _safe_number(account.get("unrealized_pnl")),
            "realized_pnl": _safe_number(account.get("realized_pnl")),
            "total_assets": _safe_number(account.get("total_assets")),
            "total_return_pct": _safe_number(account.get("total_return_pct")),
            "position_count": account.get("position_count"),
        },
        "positions": [
            {
                "stock_code": item.get("stock_code"),
                "stock_name": item.get("stock_name"),
                "quantity": item.get("quantity"),
                "sellable_quantity": item.get("sellable_quantity"),
                "avg_cost": _safe_number(item.get("avg_cost")),
                "current_price": _safe_number(item.get("current_price")),
                "unrealized_pnl": _safe_number(item.get("unrealized_pnl")),
                "entry_reason": item.get("entry_reason"),
                "planned_holding_days": item.get("planned_holding_days"),
                "stop_loss_price": _safe_number(item.get("stop_loss_price")),
                "take_profit_price": _safe_number(item.get("take_profit_price")),
                "invalidation_condition": item.get("invalidation_condition"),
                "plan_note": item.get("plan_note"),
            }
            for item in (portfolio.get("positions") or [])[:12]
        ],
        "recent_trades": [
            {
                "stock_code": item.get("stock_code"),
                "stock_name": item.get("stock_name"),
                "side": item.get("side"),
                "quantity": item.get("quantity"),
                "price": _safe_number(item.get("price")),
                "amount": _safe_number(item.get("amount")),
                "realized_pnl": _safe_number(item.get("realized_pnl")),
                "trade_time": item.get("trade_time"),
                "entry_reason": item.get("entry_reason"),
                "planned_holding_days": item.get("planned_holding_days"),
                "exit_reason": item.get("exit_reason"),
                "review_rating": item.get("review_rating"),
                "review_summary": item.get("review_summary"),
                "lessons_learned": item.get("lessons_learned"),
            }
            for item in (portfolio.get("trades") or [])[:20]
        ],
    }


def _call_provider(
    *,
    provider: str,
    model: str,
    api_key: str,
    base_url: str,
    system_prompt: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> str:
    if provider in OPENAI_COMPAT_PROVIDERS:
        return _call_openai_compatible(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            system_prompt=system_prompt,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    if provider == "anthropic":
        return _call_anthropic(
            model=model,
            api_key=api_key,
            base_url=base_url,
            system_prompt=system_prompt,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    if provider == "google":
        return _call_google_gemini(
            model=model,
            api_key=api_key,
            base_url=base_url,
            system_prompt=system_prompt,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    raise ValueError("暂不支持该 AI 服务商")


def _call_provider_stream(
    *,
    provider: str,
    model: str,
    api_key: str,
    base_url: str,
    system_prompt: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> Iterator[str]:
    if provider in OPENAI_COMPAT_PROVIDERS:
        yield from _stream_openai_compatible(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            system_prompt=system_prompt,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return

    if provider == "anthropic":
        yield from _stream_anthropic(
            model=model,
            api_key=api_key,
            base_url=base_url,
            system_prompt=system_prompt,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return

    if provider == "google":
        yield from _chunk_text(
            _call_google_gemini(
                model=model,
                api_key=api_key,
                base_url=base_url,
                system_prompt=system_prompt,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )
        return

    raise ValueError("暂不支持该 AI 服务商")


def _call_openai_compatible(
    *,
    provider: str,
    model: str,
    api_key: str,
    base_url: str,
    system_prompt: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> str:
    endpoint = _build_openai_compatible_endpoint(provider=provider, base_url=base_url)
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    data = _post_json(
        endpoint,
        headers=headers,
        payload=payload,
        provider_label=provider,
    )
    choices = data.get("choices") or []
    message = choices[0].get("message") if choices else {}
    content = message.get("content") if isinstance(message, dict) else ""
    if isinstance(content, list):
        content = "\n".join(
            part.get("text", "") for part in content if isinstance(part, dict) and part.get("text")
        )
    return str(content or "").strip()


def _stream_openai_compatible(
    *,
    provider: str,
    model: str,
    api_key: str,
    base_url: str,
    system_prompt: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> Iterator[str]:
    endpoint = _build_openai_compatible_endpoint(provider=provider, base_url=base_url)
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    for _, data in _post_sse(
        endpoint,
        headers=headers,
        payload=payload,
        provider_label=provider,
    ):
        if data == "[DONE]":
            break
        try:
            payload = json.loads(data)
        except ValueError:
            continue
        choices = payload.get("choices") or []
        delta = choices[0].get("delta") if choices else {}
        content = delta.get("content") if isinstance(delta, dict) else ""
        if isinstance(content, list):
            content = "\n".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("text")
            )
        if isinstance(content, str) and content:
            yield content


def _call_anthropic(
    *,
    model: str,
    api_key: str,
    base_url: str,
    system_prompt: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> str:
    endpoint = _build_anthropic_endpoint(base_url)
    payload = {
        "model": model,
        "system": system_prompt,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    data = _post_json(
        endpoint,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        payload=payload,
        provider_label="Anthropic",
    )
    content = data.get("content") or []
    text_parts = []
    for part in content:
        if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
            text_parts.append(str(part["text"]))
    return "\n".join(text_parts).strip()


def _stream_anthropic(
    *,
    model: str,
    api_key: str,
    base_url: str,
    system_prompt: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> Iterator[str]:
    endpoint = _build_anthropic_endpoint(base_url)
    payload = {
        "model": model,
        "system": system_prompt,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    for event, data in _post_sse(
        endpoint,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        payload=payload,
        provider_label="Anthropic",
    ):
        if event != "content_block_delta":
            continue
        try:
            payload = json.loads(data)
        except ValueError:
            continue
        delta = payload.get("delta") or {}
        if delta.get("type") == "text_delta" and delta.get("text"):
            yield str(delta["text"])


def _call_google_gemini(
    *,
    model: str,
    api_key: str,
    base_url: str,
    system_prompt: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> str:
    endpoint = _build_google_endpoint(base_url, model)
    payload = {
        "systemInstruction": {
            "parts": [{"text": system_prompt}],
        },
        "contents": [
            {
                "role": "model" if message["role"] == "assistant" else "user",
                "parts": [{"text": message["content"]}],
            }
            for message in messages
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    data = _post_json(
        endpoint,
        headers={"Content-Type": "application/json"},
        payload=payload,
        provider_label="Google Gemini",
        params={"key": api_key},
    )
    candidates = data.get("candidates") or []
    parts = (((candidates[0] or {}).get("content") or {}).get("parts")) if candidates else []
    text_parts = [str(part.get("text")) for part in parts if isinstance(part, dict) and part.get("text")]
    return "\n".join(text_parts).strip()


def _post_json(
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    provider_label: str,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as error:
        raise RuntimeError(f"{provider_label} 请求失败：{error}") from error

    if not response.ok:
        raise RuntimeError(f"{provider_label} 返回错误：{_extract_error_message(response)}")

    try:
        return response.json()
    except ValueError as error:
        raise RuntimeError(f"{provider_label} 返回了无法解析的响应") from error


def _post_sse(
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    provider_label: str,
    params: dict[str, str] | None = None,
) -> Iterator[tuple[str, str]]:
    try:
        with requests.post(
            url,
            headers=headers,
            json=payload,
            params=params,
            timeout=(10, REQUEST_TIMEOUT_SECONDS),
            stream=True,
        ) as response:
            if not response.ok:
                raise RuntimeError(f"{provider_label} 返回错误：{_extract_error_message(response)}")
            yield from _iter_sse_events(response)
    except requests.RequestException as error:
        raise RuntimeError(f"{provider_label} 请求失败：{error}") from error


def _iter_sse_events(response: requests.Response) -> Iterator[tuple[str, str]]:
    event_name = "message"
    data_lines: list[str] = []

    for raw_line in response.iter_lines(decode_unicode=True):
        if raw_line is None:
            continue
        line = raw_line.strip()
        if not line:
            if data_lines:
                yield event_name, "\n".join(data_lines)
            event_name = "message"
            data_lines = []
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line[6:].strip() or "message"
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())

    if data_lines:
        yield event_name, "\n".join(data_lines)


def _build_openai_compatible_endpoint(*, provider: str, base_url: str) -> str:
    normalized = (base_url.strip() or DEFAULT_BASE_URLS[provider]).rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _build_anthropic_endpoint(base_url: str) -> str:
    normalized = (base_url.strip() or DEFAULT_BASE_URLS["anthropic"]).rstrip("/")
    if normalized.endswith("/messages"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/messages"
    return f"{normalized}/v1/messages"


def _build_google_endpoint(base_url: str, model: str) -> str:
    normalized = (base_url.strip() or DEFAULT_BASE_URLS["google"]).rstrip("/")
    if "{model}" in normalized:
        normalized = normalized.replace("{model}", model)
    if normalized.endswith(":generateContent"):
        return normalized
    if "/models/" in normalized:
        return f"{normalized}:generateContent"
    return f"{normalized}/{model}:generateContent"


def _extract_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or f"HTTP {response.status_code}"

    if isinstance(payload, dict):
        detail = payload.get("error") or payload.get("detail") or payload.get("message")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        if isinstance(detail, dict):
            message = detail.get("message") or detail.get("error") or detail.get("detail")
            if isinstance(message, str) and message.strip():
                return message.strip()
        return json.dumps(payload, ensure_ascii=False)
    return str(payload)


def _parse_model_response(response_text: str, candidate_lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    response_text = response_text.strip()
    control_answer, control_codes = _extract_control_stock_codes(response_text)
    if control_answer is not None:
        stock_codes = _sanitize_stock_codes(control_codes, candidate_lookup)
        if not stock_codes:
            stock_codes = _extract_stock_codes(control_answer, candidate_lookup)
        return {
            "content": control_answer,
            "stock_codes": stock_codes,
        }

    parsed_object = _parse_json_object(response_text)
    if parsed_object is None:
        stock_codes = _extract_stock_codes(response_text, candidate_lookup)
        return {
            "content": response_text,
            "stock_codes": stock_codes,
        }

    answer = str(parsed_object.get("answer") or parsed_object.get("content") or "").strip()
    if not answer:
        answer = response_text
    raw_codes = parsed_object.get("stock_codes") or parsed_object.get("codes") or []
    stock_codes = _sanitize_stock_codes(raw_codes, candidate_lookup)
    if not stock_codes:
        stock_codes = _extract_stock_codes(answer, candidate_lookup)
    return {
        "content": answer,
        "stock_codes": stock_codes,
    }


def _parse_json_object(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    for candidate in (cleaned, _extract_braced_json(cleaned)):
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _extract_control_stock_codes(text: str) -> tuple[str, list[str]] | tuple[None, None]:
    match = re.search(r"\[\[STOCK_CODES:([0-9,\s]*)\]\]", text)
    if not match:
        return None, None

    raw_codes = [part.strip() for part in match.group(1).split(",") if part.strip()]
    answer = f"{text[:match.start()]}{text[match.end():]}".strip()
    return answer, raw_codes


def _extract_braced_json(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def _extract_stock_codes(text: str, candidate_lookup: dict[str, dict[str, Any]]) -> list[str]:
    raw_codes = re.findall(r"\b\d{6}\b", text)
    return _sanitize_stock_codes(raw_codes, candidate_lookup)


def _sanitize_stock_codes(raw_codes: Any, candidate_lookup: dict[str, dict[str, Any]]) -> list[str]:
    if not isinstance(raw_codes, list):
        return []
    normalized: list[str] = []
    for raw in raw_codes:
        stock_code = str(raw or "").strip()
        if stock_code in candidate_lookup and stock_code not in normalized:
            normalized.append(stock_code)
        if len(normalized) >= 5:
            break
    return normalized


def _chunk_text(text: str, *, chunk_size: int = 24) -> Iterator[str]:
    normalized = str(text or "")
    for index in range(0, len(normalized), chunk_size):
        chunk = normalized[index : index + chunk_size]
        if chunk:
            yield chunk


def _clamp_float(value: Any, *, default: float, minimum: float, maximum: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = default
    return max(minimum, min(maximum, numeric))


def _clamp_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = default
    return max(minimum, min(maximum, numeric))


def _safe_number(value: Any) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return int(numeric) if float(numeric).is_integer() else round(numeric, 4)
