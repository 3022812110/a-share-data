from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
import html
import re
from typing import Any

import requests

from .eastmoney_kline import stock_code_to_secid


_SESSION = requests.Session()
_SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
)

_MARKET_INSIGHTS_CACHE: dict[str, Any] = {"expires_at": None, "payload": None}

_SENTIMENT_POSITIVE_KEYWORDS = {
    "涨停": 3.0,
    "大涨": 2.5,
    "上涨": 1.4,
    "反弹": 1.6,
    "突破": 1.8,
    "回升": 1.2,
    "利好": 1.8,
    "新高": 1.8,
    "增持": 1.4,
    "超预期": 2.0,
    "订单": 1.1,
    "中标": 1.2,
    "回暖": 1.0,
    "修复": 1.0,
}

_SENTIMENT_NEGATIVE_KEYWORDS = {
    "跌停": 3.0,
    "大跌": 2.5,
    "下跌": 1.4,
    "回调": 1.6,
    "走弱": 1.5,
    "利空": 1.8,
    "减持": 1.8,
    "亏损": 1.6,
    "爆雷": 2.5,
    "终止": 1.4,
    "风险": 1.0,
    "问询": 1.1,
    "处罚": 1.8,
    "承压": 1.0,
    "下修": 1.2,
}

_HOT_WORD_STOPWORDS = {
    "财联社",
    "日电",
    "表示",
    "目前",
    "今日",
    "公司",
    "市场",
    "相关",
    "板块",
    "行业",
    "消息",
    "发布",
    "预计",
    "称",
    "将",
    "年",
    "月",
}


def _strip_html(text: str | None) -> str:
    raw = html.unescape(text or "")
    cleaned = re.sub(r"<[^>]+>", "", raw)
    return re.sub(r"\s+", " ", cleaned).strip()


def _normalize_stock_code(stock_code: str) -> str:
    code = stock_code.strip().upper()
    if "." in code:
        code = code.split(".", 1)[0]
    if code.startswith(("SH", "SZ", "BJ")):
        code = code[2:]
    return code


def _normalize_stock_security_code(stock_code: str) -> str:
    normalized = stock_code.strip().upper()
    if not normalized:
        return ""
    if "." in normalized:
        code, suffix = normalized.split(".", 1)
        suffix = suffix.upper()
        if suffix in {"SH", "SS"}:
            return f"{code}.SH"
        if suffix in {"SZ"}:
            return f"{code}.SZ"
        if suffix in {"BJ"}:
            return f"{code}.BJ"
        return code
    if normalized.startswith("SH") and len(normalized) >= 8:
        return f"{normalized[2:]}.SH"
    if normalized.startswith("SZ") and len(normalized) >= 8:
        return f"{normalized[2:]}.SZ"
    if normalized.startswith("BJ") and len(normalized) >= 8:
        return f"{normalized[2:]}.BJ"
    if normalized.isdigit():
        if normalized.startswith("6"):
            return f"{normalized}.SH"
        if normalized.startswith(("8", "4")):
            return f"{normalized}.BJ"
        return f"{normalized}.SZ"
    return normalized


def _to_float(value: Any) -> float | None:
    if value in (None, "", "-", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _utc_now_str() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _value_to_yi(value: Any) -> float | None:
    number = _to_float(value)
    if number is None:
        return None
    return number / 100000000


def _topic_url(htid: Any) -> str | None:
    if htid in (None, ""):
        return None
    return f"https://gubatopic.eastmoney.com/topic/{htid}.html"


def _clip_text(text: str | None, length: int = 80) -> str:
    if not text:
        return ""
    stripped = text.strip()
    if len(stripped) <= length:
        return stripped
    return stripped[: max(10, length - 1)] + "…"


def fetch_cls_market_telegraphs(*, limit: int = 50) -> list[dict[str, Any]]:
    response = _SESSION.get(
        "https://www.cls.cn/nodeapi/telegraphList",
        headers={
            "Host": "www.cls.cn",
            "Referer": "https://www.cls.cn/",
        },
        timeout=15,
    )
    response.raise_for_status()
    rows = ((response.json().get("data") or {}).get("roll_data")) or []
    items: list[dict[str, Any]] = []
    for row in rows[:limit]:
        subjects = row.get("subjects") or []
        subject_names = [
            _strip_html(subject.get("subject_name"))
            for subject in subjects
            if isinstance(subject, dict) and subject.get("subject_name")
        ]
        tags = []
        for tag in row.get("tags") or []:
            if isinstance(tag, dict):
                tag_name = _strip_html(tag.get("name") or tag.get("tag_name"))
            else:
                tag_name = _strip_html(str(tag))
            if tag_name:
                tags.append(tag_name)
        items.append(
            {
                "id": row.get("id"),
                "title": _strip_html(row.get("title")) or _clip_text(_strip_html(row.get("content")), 36),
                "content": _strip_html(row.get("content")),
                "published_at": row.get("ctime"),
                "is_red": (row.get("level") or "") != "C",
                "subject_names": subject_names,
                "tags": tags,
            }
        )
    return items


def fetch_hot_topics(*, limit: int = 8) -> list[dict[str, Any]]:
    response = _SESSION.post(
        "https://gubatopic.eastmoney.com/interface/GetData.aspx?path=newtopic/api/Topic/HomePageListRead",
        headers={
            "Host": "gubatopic.eastmoney.com",
            "Origin": "https://gubatopic.eastmoney.com",
            "Referer": "https://gubatopic.eastmoney.com/",
        },
        data={
            "param": f"ps={max(1, min(limit, 20))}&p=1&type=0",
            "path": "newtopic/api/Topic/HomePageListRead",
            "env": "2",
        },
        timeout=15,
    )
    response.raise_for_status()
    rows = response.json().get("re") or []
    items: list[dict[str, Any]] = []
    for row in rows[:limit]:
        stock_list = row.get("stock_list") or []
        stock_names = [
            _strip_html(stock.get("name"))
            for stock in stock_list[:3]
            if isinstance(stock, dict) and stock.get("name")
        ]
        items.append(
            {
                "topic_id": row.get("htid"),
                "title": _strip_html(row.get("nickname") or row.get("name")),
                "description": _clip_text(_strip_html(row.get("desc") or row.get("introduction")), 72),
                "heat": _to_float(row.get("clickNumber")),
                "post_count": _to_float(row.get("postNumber")),
                "stock_names": stock_names,
                "url": _topic_url(row.get("htid")),
            }
        )
    return items


def fetch_sector_money_ranks(*, category: str = "industry", limit: int = 8) -> list[dict[str, Any]]:
    fenlei = "0" if category == "industry" else "1"
    response = _SESSION.get(
        "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/MoneyFlow.ssl_bkzj_bk",
        params={
            "page": "1",
            "num": str(max(1, min(limit, 20))),
            "sort": "netamount",
            "asc": "0",
            "fenlei": fenlei,
        },
        headers={
            "Host": "vip.stock.finance.sina.com.cn",
            "Referer": "https://finance.sina.com.cn/",
        },
        timeout=15,
    )
    response.raise_for_status()
    rows = response.json() or []
    items: list[dict[str, Any]] = []
    for row in rows[:limit]:
        items.append(
            {
                "category_code": row.get("category"),
                "name": _strip_html(row.get("name")),
                "avg_price": _to_float(row.get("avg_price")),
                "avg_change_pct": (_to_float(row.get("avg_changeratio")) or 0) * 100,
                "turnover": _to_float(row.get("turnover")),
                "net_inflow_yi": _value_to_yi(row.get("netamount")),
                "inflow_yi": _value_to_yi(row.get("inamount")),
                "outflow_yi": _value_to_yi(row.get("outamount")),
                "ratio_amount_pct": (_to_float(row.get("ratioamount")) or 0) * 100,
                "leading_stock_code": _normalize_stock_code(str(row.get("ts_symbol") or "")),
                "leading_stock_name": _strip_html(row.get("ts_name")),
                "leading_stock_price": _to_float(row.get("ts_trade")),
                "leading_stock_change_pct": (_to_float(row.get("ts_changeratio")) or 0) * 100,
            }
        )
    return items


def _score_sentiment_text(text: str) -> float:
    score = 0.0
    for keyword, weight in _SENTIMENT_POSITIVE_KEYWORDS.items():
        if keyword in text:
            score += weight
    for keyword, weight in _SENTIMENT_NEGATIVE_KEYWORDS.items():
        if keyword in text:
            score -= weight
    return score


def _build_hot_words(telegraphs: list[dict[str, Any]], *, limit: int = 12) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()

    for item in telegraphs:
        for word in item.get("subject_names") or []:
            if word and word not in _HOT_WORD_STOPWORDS:
                counter[word] += 3
        for word in item.get("tags") or []:
            if word and word not in _HOT_WORD_STOPWORDS:
                counter[word] += 2

    if len(counter) < max(4, limit // 2):
        for item in telegraphs:
            text = f"{item.get('title') or ''} {item.get('content') or ''}"
            for word in re.findall(r"[\u4e00-\u9fffA-Za-z]{2,8}", text):
                if word in _HOT_WORD_STOPWORDS or word.isdigit():
                    continue
                counter[word] += 1

    return [
        {"word": word, "count": count}
        for word, count in counter.most_common(limit)
    ]


def _build_market_sentiment(telegraphs: list[dict[str, Any]]) -> dict[str, Any]:
    if not telegraphs:
        return {
            "score": 50,
            "label": "中性",
            "description": "暂未获取到足够的市场快讯。",
            "bullish_count": 0,
            "bearish_count": 0,
            "neutral_count": 0,
        }

    raw_score = 0.0
    bullish_count = 0
    bearish_count = 0
    neutral_count = 0

    for item in telegraphs:
        text = f"{item.get('title') or ''} {item.get('content') or ''}"
        score = _score_sentiment_text(text)
        if item.get("is_red"):
            score += 0.3
        raw_score += score
        if score > 0.8:
            bullish_count += 1
        elif score < -0.8:
            bearish_count += 1
        else:
            neutral_count += 1

    normalized = max(0, min(100, int(round(50 + raw_score * 3.5))))
    if normalized >= 66:
        label = "偏强"
        description = "快讯正向催化更多，热点延续性相对更好。"
    elif normalized <= 38:
        label = "偏弱"
        description = "负面扰动偏多，追高需要更谨慎。"
    else:
        label = "中性"
        description = "市场更偏轮动，适合等强弱进一步确认。"

    return {
        "score": normalized,
        "label": label,
        "description": description,
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "neutral_count": neutral_count,
    }


def load_market_insights(*, max_age_seconds: int = 300) -> dict[str, Any]:
    expires_at = _MARKET_INSIGHTS_CACHE.get("expires_at")
    payload = _MARKET_INSIGHTS_CACHE.get("payload")
    if isinstance(expires_at, datetime) and payload and datetime.utcnow() < expires_at:
        return payload

    try:
        telegraphs = fetch_cls_market_telegraphs(limit=40)
    except Exception:
        telegraphs = []

    try:
        hot_topics = fetch_hot_topics(limit=8)
    except Exception:
        hot_topics = []

    try:
        industry_ranks = fetch_sector_money_ranks(category="industry", limit=8)
    except Exception:
        industry_ranks = []

    try:
        concept_ranks = fetch_sector_money_ranks(category="concept", limit=8)
    except Exception:
        concept_ranks = []

    result = {
        "sentiment": _build_market_sentiment(telegraphs),
        "hot_words": _build_hot_words(telegraphs, limit=12),
        "hot_topics": hot_topics,
        "sector_rankings": {
            "industry": industry_ranks,
            "concept": concept_ranks,
        },
        "telegraph_sample": [
            {
                "title": item.get("title"),
                "published_at": item.get("published_at"),
                "subject_names": item.get("subject_names") or [],
            }
            for item in telegraphs[:6]
        ],
        "generated_at": _utc_now_str(),
    }

    _MARKET_INSIGHTS_CACHE["payload"] = result
    _MARKET_INSIGHTS_CACHE["expires_at"] = datetime.utcnow() + timedelta(seconds=max(60, max_age_seconds))
    return result


def fetch_cls_stock_news(keyword: str, *, limit: int = 8) -> list[dict[str, Any]]:
    search_word = keyword.strip()
    if not search_word:
        return []

    response = _SESSION.post(
        "https://www.cls.cn/api/csw?app=CailianpressWeb&os=web&sv=8.4.6&sign=9f8797a1f4de66c2370f7a03990d2737",
        headers={
            "Content-Type": "application/json",
            "Host": "www.cls.cn",
            "Origin": "https://www.cls.cn",
            "Referer": "https://www.cls.cn/telegraph",
        },
        json={
            "app": "CailianpressWeb",
            "os": "web",
            "sv": "8.4.6",
            "category": "",
            "keyword": search_word,
        },
        timeout=15,
    )
    response.raise_for_status()
    rows = response.json().get("list") or []
    items: list[dict[str, Any]] = []
    for row in rows[:limit]:
        title = _strip_html(row.get("title"))
        content = _strip_html(row.get("content"))
        items.append(
            {
                "id": row.get("id"),
                "title": title or content[:60],
                "content": content,
                "source": "财联社",
                "published_at": row.get("ctime"),
            }
        )
    return items


def fetch_stock_notices(stock_code: str, *, limit: int = 8) -> list[dict[str, Any]]:
    normalized_code = _normalize_stock_code(stock_code)
    response = _SESSION.get(
        (
            "https://np-anotice-stock.eastmoney.com/api/security/ann"
            f"?page_size={max(1, min(limit, 50))}&page_index=1"
            "&ann_type=SHA%2CCYB%2CSZA%2CBJA%2CINV&client_source=web&f_node=0"
            f"&stock_list={normalized_code}"
        ),
        headers={
            "Host": "np-anotice-stock.eastmoney.com",
            "Referer": "https://data.eastmoney.com/notices/hsa/5.html",
        },
        timeout=15,
    )
    response.raise_for_status()
    rows = ((response.json().get("data") or {}).get("list")) or []
    items: list[dict[str, Any]] = []
    for row in rows[:limit]:
        columns = row.get("columns") or []
        notice_type = ""
        if columns and isinstance(columns[0], dict):
            notice_type = str(columns[0].get("column_name") or "")
        art_code = str(row.get("art_code") or "")
        items.append(
            {
                "art_code": art_code,
                "title": _strip_html(row.get("title")),
                "notice_date": row.get("notice_date"),
                "display_time": row.get("display_time"),
                "notice_type": notice_type,
                "url": (
                    f"https://data.eastmoney.com/notices/detail/{normalized_code}/{art_code}.html"
                    if art_code
                    else None
                ),
            }
        )
    return items


def fetch_stock_research_reports(stock_code: str, *, limit: int = 8, lookback_days: int = 365) -> list[dict[str, Any]]:
    normalized_code = _normalize_stock_code(stock_code)
    today = date.today()
    begin_date = today - timedelta(days=max(30, lookback_days))
    response = _SESSION.post(
        "https://reportapi.eastmoney.com/report/list2",
        headers={
            "Host": "reportapi.eastmoney.com",
            "Origin": "https://data.eastmoney.com",
            "Referer": "https://data.eastmoney.com/report/stock.jshtml",
            "Content-Type": "application/json",
        },
        json={
            "beginTime": begin_date.isoformat(),
            "endTime": today.isoformat(),
            "industryCode": "*",
            "code": normalized_code,
            "pageNo": 1,
            "pageSize": max(1, min(limit, 20)),
            "p": 1,
            "pageNum": 1,
            "pageNumber": 1,
        },
        timeout=15,
    )
    response.raise_for_status()
    rows = response.json().get("data") or []
    items: list[dict[str, Any]] = []
    for row in rows[:limit]:
        encode_url = row.get("encodeUrl")
        items.append(
            {
                "info_code": row.get("infoCode"),
                "title": _strip_html(row.get("title")),
                "org_name": row.get("orgSName") or row.get("orgName"),
                "publish_date": row.get("publishDate"),
                "rating": row.get("emRatingName") or row.get("sRatingName"),
                "rating_change": row.get("ratingChange"),
                "author": row.get("author") or row.get("researcher"),
                "url": (
                    f"https://data.eastmoney.com/report/zw_brokerreport.jshtml?encodeUrl={encode_url}"
                    if encode_url
                    else None
                ),
            }
        )
    return items


def fetch_stock_capital_flows(stock_code: str, *, limit: int = 10) -> list[dict[str, Any]]:
    secid = stock_code_to_secid(stock_code)
    if not secid:
        return []

    response = _SESSION.get(
        "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get",
        params={
            "lmt": str(max(3, min(limit, 60))),
            "klt": "101",
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
            "ut": "b2884a393a59ad64002292a3e90d46a5",
            "secid": secid,
            "_": "1",
        },
        headers={
            "Host": "push2his.eastmoney.com",
            "Referer": "https://quote.eastmoney.com/",
        },
        timeout=15,
    )
    response.raise_for_status()
    rows = ((response.json().get("data") or {}).get("klines")) or []

    items: list[dict[str, Any]] = []
    for row in rows:
        parts = str(row).split(",")
        if len(parts) < 13:
            continue
        items.append(
            {
                "trade_date": parts[0],
                "main_net_inflow": _to_float(parts[1]),
                "retail_net_inflow": _to_float(parts[2]),
                "medium_net_inflow": _to_float(parts[3]),
                "large_net_inflow": _to_float(parts[4]),
                "extra_large_net_inflow": _to_float(parts[5]),
                "main_net_inflow_pct": _to_float(parts[6]),
                "retail_net_inflow_pct": _to_float(parts[7]),
                "medium_net_inflow_pct": _to_float(parts[8]),
                "large_net_inflow_pct": _to_float(parts[9]),
                "extra_large_net_inflow_pct": _to_float(parts[10]),
                "close": _to_float(parts[11]),
                "change_pct": _to_float(parts[12]),
            }
        )

    items.sort(key=lambda item: str(item.get("trade_date") or ""), reverse=True)
    return items[:limit]


def fetch_stock_long_tiger(stock_code: str, *, limit: int = 8, lookback_days: int = 3650) -> list[dict[str, Any]]:
    security_code = _normalize_stock_security_code(stock_code)
    if not security_code:
        return []

    today = date.today()
    begin_date = (today - timedelta(days=max(30, lookback_days))).isoformat()
    response = _SESSION.get(
        "https://datacenter-web.eastmoney.com/api/data/v1/get",
        params={
            "sortColumns": "TRADE_DATE,SECURITY_CODE",
            "sortTypes": "-1,1",
            "pageSize": str(max(1, min(limit, 20))),
            "pageNumber": "1",
            "reportName": "RPT_DAILYBILLBOARD_DETAILSNEW",
            "columns": (
                "SECURITY_CODE,SECUCODE,SECURITY_NAME_ABBR,TRADE_DATE,EXPLAIN,CLOSE_PRICE,"
                "CHANGE_RATE,BILLBOARD_NET_AMT,BILLBOARD_BUY_AMT,BILLBOARD_SELL_AMT,"
                "BILLBOARD_DEAL_AMT,ACCUM_AMOUNT,DEAL_NET_RATIO,DEAL_AMOUNT_RATIO,"
                "TURNOVERRATE,FREE_MARKET_CAP,EXPLANATION,D1_CLOSE_ADJCHRATE,"
                "D2_CLOSE_ADJCHRATE,D5_CLOSE_ADJCHRATE,D10_CLOSE_ADJCHRATE,SECURITY_TYPE_CODE"
            ),
            "source": "WEB",
            "client": "WEB",
            "filter": (
                f'(SECUCODE="{security_code}")'
                f"(TRADE_DATE<='{today.isoformat()}')"
                f"(TRADE_DATE>='{begin_date}')"
            ),
        },
        headers={
            "Host": "datacenter-web.eastmoney.com",
            "Referer": "https://data.eastmoney.com/stock/tradedetail.html",
        },
        timeout=15,
    )
    response.raise_for_status()
    rows = ((response.json().get("result") or {}).get("data")) or []
    items: list[dict[str, Any]] = []
    for row in rows[:limit]:
        items.append(
            {
                "trade_date": row.get("TRADE_DATE"),
                "close_price": _to_float(row.get("CLOSE_PRICE")),
                "change_pct": _to_float(row.get("CHANGE_RATE")),
                "net_amount": _to_float(row.get("BILLBOARD_NET_AMT")),
                "buy_amount": _to_float(row.get("BILLBOARD_BUY_AMT")),
                "sell_amount": _to_float(row.get("BILLBOARD_SELL_AMT")),
                "deal_amount": _to_float(row.get("BILLBOARD_DEAL_AMT")),
                "deal_net_ratio": _to_float(row.get("DEAL_NET_RATIO")),
                "deal_amount_ratio": _to_float(row.get("DEAL_AMOUNT_RATIO")),
                "turnover_ratio": _to_float(row.get("TURNOVERRATE")),
                "free_market_cap": _to_float(row.get("FREE_MARKET_CAP")),
                "explanation": _strip_html(row.get("EXPLANATION")),
                "explain": _strip_html(row.get("EXPLAIN")),
                "next_1d_pct": _to_float(row.get("D1_CLOSE_ADJCHRATE")),
                "next_2d_pct": _to_float(row.get("D2_CLOSE_ADJCHRATE")),
                "next_5d_pct": _to_float(row.get("D5_CLOSE_ADJCHRATE")),
                "next_10d_pct": _to_float(row.get("D10_CLOSE_ADJCHRATE")),
            }
        )
    return items


def fetch_stock_concepts(stock_code: str, *, limit: int = 12) -> list[dict[str, Any]]:
    security_code = _normalize_stock_security_code(stock_code)
    if not security_code:
        return []

    response = _SESSION.get(
        "https://datacenter.eastmoney.com/securities/api/data/v1/get",
        params={
            "reportName": "RPT_F10_CORETHEME_BOARDTYPE",
            "columns": (
                "SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,NEW_BOARD_CODE,"
                "BOARD_NAME,SELECTED_BOARD_REASON,IS_PRECISE,BOARD_RANK,BOARD_YIELD,DERIVE_BOARD_CODE"
            ),
            "quoteColumns": "f3~05~NEW_BOARD_CODE~BOARD_YIELD",
            "filter": f'(SECUCODE="{security_code}")(IS_PRECISE="1")',
            "pageNumber": "1",
            "pageSize": str(max(1, min(limit, 30))),
            "sortTypes": "1",
            "sortColumns": "BOARD_RANK",
            "source": "HSF10",
            "client": "PC",
        },
        headers={
            "Host": "datacenter.eastmoney.com",
            "Referer": "https://emweb.securities.eastmoney.com/",
            "Origin": "https://emweb.securities.eastmoney.com",
        },
        timeout=15,
    )
    response.raise_for_status()
    rows = ((response.json().get("result") or {}).get("data")) or []
    items: list[dict[str, Any]] = []
    for row in rows[:limit]:
        items.append(
            {
                "board_code": row.get("NEW_BOARD_CODE") or row.get("BOARD_CODE"),
                "board_name": row.get("BOARD_NAME"),
                "selected_reason": _strip_html(row.get("SELECTED_BOARD_REASON")),
                "board_rank": _to_float(row.get("BOARD_RANK")),
                "board_yield": _to_float(row.get("BOARD_YIELD")),
            }
        )
    return items


def fetch_stock_financial_reports(stock_code: str, *, limit: int = 4) -> list[dict[str, Any]]:
    security_code = _normalize_stock_security_code(stock_code)
    if not security_code:
        return []

    response = _SESSION.get(
        "https://datacenter.eastmoney.com/securities/api/data/v1/get",
        params={
            "reportName": "RPT_F10_FINANCE_DUPONT",
            "columns": (
                "SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,REPORT_DATE,REPORT_TYPE,REPORT_DATE_NAME,"
                "NOTICE_DATE,NETPROFIT,TOTAL_OPERATE_INCOME,TOTAL_ASSETS,TOTAL_LIABILITIES,"
                "PARENT_NETPROFIT,ROE,DEBT_ASSET_RATIO"
            ),
            "filter": f'(SECUCODE="{security_code}")',
            "pageNumber": "1",
            "pageSize": str(max(1, min(limit, 12))),
            "sortTypes": "-1",
            "sortColumns": "REPORT_DATE",
            "source": "HSF10",
            "client": "PC",
        },
        headers={
            "Host": "datacenter.eastmoney.com",
            "Referer": "https://emweb.securities.eastmoney.com/",
            "Origin": "https://emweb.securities.eastmoney.com",
        },
        timeout=15,
    )
    response.raise_for_status()
    rows = ((response.json().get("result") or {}).get("data")) or []
    items: list[dict[str, Any]] = []
    for row in rows[:limit]:
        items.append(
            {
                "report_date": row.get("REPORT_DATE"),
                "report_type": row.get("REPORT_TYPE") or row.get("REPORT_DATE_NAME"),
                "notice_date": row.get("NOTICE_DATE"),
                "net_profit": _to_float(row.get("NETPROFIT")),
                "parent_net_profit": _to_float(row.get("PARENT_NETPROFIT")),
                "total_operate_income": _to_float(row.get("TOTAL_OPERATE_INCOME")),
                "total_assets": _to_float(row.get("TOTAL_ASSETS")),
                "total_liabilities": _to_float(row.get("TOTAL_LIABILITIES")),
                "roe": _to_float(row.get("ROE")),
                "debt_asset_ratio": _to_float(row.get("DEBT_ASSET_RATIO")),
            }
        )
    return items


def fetch_stock_holder_numbers(stock_code: str, *, limit: int = 8) -> list[dict[str, Any]]:
    security_code = _normalize_stock_security_code(stock_code)
    if not security_code:
        return []

    response = _SESSION.get(
        "https://datacenter.eastmoney.com/securities/api/data/v1/get",
        params={
            "reportName": "RPT_F10_EH_HOLDERNUM",
            "columns": (
                "SECUCODE,SECURITY_CODE,END_DATE,HOLDER_TOTAL_NUM,TOTAL_NUM_RATIO,"
                "AVG_FREE_SHARES,AVG_FREESHARES_RATIO,HOLD_FOCUS,PRICE,AVG_HOLD_AMT,"
                "HOLD_RATIO_TOTAL,FREEHOLD_RATIO_TOTAL"
            ),
            "filter": f'(SECUCODE="{security_code}")',
            "pageNumber": "1",
            "pageSize": str(max(1, min(limit, 12))),
            "sortTypes": "-1",
            "sortColumns": "END_DATE",
            "source": "HSF10",
            "client": "PC",
        },
        headers={
            "Host": "datacenter.eastmoney.com",
            "Referer": "https://emweb.securities.eastmoney.com/",
            "Origin": "https://emweb.securities.eastmoney.com",
        },
        timeout=15,
    )
    response.raise_for_status()
    rows = ((response.json().get("result") or {}).get("data")) or []
    items: list[dict[str, Any]] = []
    for row in rows[:limit]:
        items.append(
            {
                "end_date": row.get("END_DATE"),
                "holder_total_num": _to_float(row.get("HOLDER_TOTAL_NUM")),
                "total_num_ratio": _to_float(row.get("TOTAL_NUM_RATIO")),
                "avg_free_shares": _to_float(row.get("AVG_FREE_SHARES")),
                "avg_free_shares_ratio": _to_float(row.get("AVG_FREESHARES_RATIO")),
                "hold_focus": _to_float(row.get("HOLD_FOCUS")),
                "price": _to_float(row.get("PRICE")),
                "avg_hold_amt": _to_float(row.get("AVG_HOLD_AMT")),
                "hold_ratio_total": _to_float(row.get("HOLD_RATIO_TOTAL")),
                "freehold_ratio_total": _to_float(row.get("FREEHOLD_RATIO_TOTAL")),
            }
        )
    return items


def load_stock_event_feeds(stock_code: str, stock_name: str | None = None) -> dict[str, list[dict[str, Any]]]:
    news_keyword = (stock_name or "").strip() or _normalize_stock_code(stock_code)

    try:
        telegraphs = fetch_cls_stock_news(news_keyword)
    except Exception:
        telegraphs = []

    try:
        notices = fetch_stock_notices(stock_code)
    except Exception:
        notices = []

    try:
        reports = fetch_stock_research_reports(stock_code)
    except Exception:
        reports = []

    try:
        capital_flows = fetch_stock_capital_flows(stock_code)
    except Exception:
        capital_flows = []

    try:
        long_tiger = fetch_stock_long_tiger(stock_code)
    except Exception:
        long_tiger = []

    try:
        concepts = fetch_stock_concepts(stock_code)
    except Exception:
        concepts = []

    try:
        financial_reports = fetch_stock_financial_reports(stock_code)
    except Exception:
        financial_reports = []

    try:
        holder_numbers = fetch_stock_holder_numbers(stock_code)
    except Exception:
        holder_numbers = []

    return {
        "telegraphs": telegraphs,
        "notices": notices,
        "research_reports": reports,
        "capital_flows": capital_flows,
        "long_tiger": long_tiger,
        "concepts": concepts,
        "financial_reports": financial_reports,
        "holder_numbers": holder_numbers,
    }
