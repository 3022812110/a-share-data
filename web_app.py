from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ashare_data.config import get_tushare_token
from ashare_data.db import DB_PATH, init_db
from ashare_data.queries import (
    load_analysis_table,
    load_daily_bars,
    load_overview,
    load_recent_trade_calendar,
    load_realtime_quotes,
    load_stock_codes,
    load_stock_options,
    load_watchlist,
    load_watchlist_snapshot,
)
from ashare_data.index_constituents import import_index_constituents
from ashare_data.sync import sync_daily_bars_for_codes
from ashare_data.sync import sync_realtime_quotes_for_codes
from ashare_data.watchlist import bulk_upsert_watchlist_items, delete_watchlist_item, upsert_watchlist_item


st.set_page_config(page_title="A-Share Data", page_icon=":chart_with_upwards_trend:", layout="wide")
init_db()


def render_overview() -> None:
    overview = load_overview()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("交易日历条数", f"{overview['trade_calendar_count']}")
    col2.metric("日线条数", f"{overview['daily_bars_count']}")
    col3.metric("股票数量", f"{overview['stock_count']}")
    col4.metric("最新交易日", overview["latest_trade_date"] or "暂无")

    st.caption(f"数据库: {DB_PATH}")
    st.caption(f"最近抓取时间: {overview['latest_fetch'] or '暂无'}")
    sources = overview.get("sources") or {}
    if sources:
        st.caption("日线来源分布: " + ", ".join(f"{key}={value}" for key, value in sources.items()))
    st.caption(f"Tushare Token: {'已配置' if get_tushare_token() else '未配置'}")


def render_trade_calendar() -> None:
    st.subheader("最近交易日历")
    calendar_frame = load_recent_trade_calendar(limit=10)
    if calendar_frame.empty:
        st.info("trade_calendar 目前为空。先运行抓取脚本。")
        return
    st.dataframe(calendar_frame, use_container_width=True, hide_index=True)


def render_daily_bars() -> None:
    st.subheader("股票日线")
    stock_options = load_stock_options()
    if not stock_options:
        st.warning("daily_bars 目前为空。先运行日线同步脚本。")
        st.code(
            "\n".join(
                [
                    "cd /Users/zhangmi/Desktop/Work/a-share-data",
                    "source .venv/bin/activate",
                    "python scripts/fetch_daily_bars.py --stock-codes 000001 600036 --start-date 2025-01-01 --end-date 2025-03-20",
                ]
            ),
            language="bash",
        )
        return

    selected_option = st.selectbox(
        "选择股票",
        options=stock_options,
        index=0,
        format_func=lambda item: f"{item['stock_code']} - {item['stock_name']}",
    )
    selected_code = selected_option["stock_code"]
    limit = st.slider("显示最近多少条", min_value=20, max_value=240, value=120, step=20)
    frame = load_daily_bars(selected_code, limit=limit)

    if frame.empty:
        st.info("该股票目前没有本地日线数据。")
        return

    chart_frame = frame.iloc[::-1].copy()
    chart_frame["trade_date"] = pd.to_datetime(chart_frame["trade_date"])
    chart_frame = chart_frame.set_index("trade_date")
    latest_turnover = chart_frame["turnover_ratio"].iloc[-1]
    turnover_text = "暂无" if pd.isna(latest_turnover) else f"{latest_turnover:.2f}%"

    metric1, metric2, metric3 = st.columns(3)
    metric1.metric("最近收盘价", f"{chart_frame['close'].iloc[-1]:.2f}")
    metric2.metric("最近涨跌幅", f"{chart_frame['change_pct'].iloc[-1]:.2f}%")
    metric3.metric("最近换手率", turnover_text)

    st.line_chart(chart_frame[["close"]], height=320)
    st.dataframe(frame, use_container_width=True, hide_index=True)


def render_watchlist_page() -> None:
    st.subheader("自选股")
    left_col, right_col = st.columns([1, 1.2])

    with left_col:
        with st.form("single_watchlist_form", clear_on_submit=True):
            stock_code = st.text_input("股票代码", placeholder="例如 000001")
            display_name = st.text_input("显示名称", placeholder="可选")
            notes = st.text_area("备注", placeholder="可选")
            submitted = st.form_submit_button("添加或更新")
            if submitted and stock_code.strip():
                saved_code = upsert_watchlist_item(stock_code, display_name, notes)
                st.success(f"已保存 {saved_code}")

        with st.form("bulk_watchlist_form", clear_on_submit=True):
            bulk_codes = st.text_area("批量添加股票代码", placeholder="用空格、逗号或换行分隔")
            bulk_submitted = st.form_submit_button("批量加入自选")
            if bulk_submitted and bulk_codes.strip():
                parts = bulk_codes.replace(",", " ").split()
                inserted = bulk_upsert_watchlist_items(parts)
                st.success(f"已加入 {len(inserted)} 只股票")

    with right_col:
        watchlist = load_watchlist()
        if watchlist.empty:
            st.info("当前还没有自选股。")
        else:
            remove_code = st.selectbox("删除自选股", options=watchlist["stock_code"].tolist())
            if st.button("删除所选股票", type="secondary"):
                delete_watchlist_item(remove_code)
                st.success(f"已删除 {remove_code}")
            st.dataframe(watchlist, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("一键导入成分股")
    import_col1, import_col2, import_col3 = st.columns([1, 1, 2])
    with import_col1:
        import_date = st.date_input("成分股日期", value=pd.Timestamp("2025-03-20"), key="import_date")
    with import_col2:
        index_name = st.selectbox("指数", options=["沪深300", "中证500"])
    with import_col3:
        st.write("")
        st.write("")
        if st.button("导入指数成分股", type="primary"):
            result = import_index_constituents(index_name=index_name, query_date=import_date.strftime("%Y-%m-%d"))
            st.success(f"已导入 {result['index_name']} 成分股 {result['count']} 只")

    st.divider()
    st.subheader("批量同步")
    watchlist_snapshot = load_watchlist_snapshot()
    if watchlist_snapshot.empty:
        st.warning("请先添加自选股。")
        return

    sync_col1, sync_col2, sync_col3 = st.columns([1, 1, 2])
    with sync_col1:
        start_date = st.date_input("开始日期", value=pd.Timestamp("2025-01-01"))
    with sync_col2:
        end_date = st.date_input("结束日期", value=pd.Timestamp("2025-03-20"))
    with sync_col3:
        selected_codes = st.multiselect(
            "选择要同步的股票",
            options=watchlist_snapshot["stock_code"].tolist(),
            default=watchlist_snapshot["stock_code"].tolist(),
        )

    if st.button("同步所选股票日线", type="primary"):
        results = sync_daily_bars_for_codes(
            stock_codes=selected_codes,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
        )
        st.success("同步完成")
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)

    st.subheader("实时行情")
    if st.button("刷新自选股实时行情"):
        quote_rows = sync_realtime_quotes_for_codes(selected_codes)
        st.success(f"已刷新 {len(quote_rows)} 条实时行情")
    realtime_frame = load_realtime_quotes()
    if realtime_frame.empty:
        st.info("还没有实时行情数据。点击上面的按钮刷新。")
    else:
        st.dataframe(realtime_frame, use_container_width=True, hide_index=True)

    st.subheader("自选股最新快照")
    st.dataframe(load_watchlist_snapshot(), use_container_width=True, hide_index=True)


def render_analysis_page() -> None:
    st.subheader("简单分析")
    watchlist = load_watchlist()
    stock_codes = watchlist["stock_code"].tolist() if not watchlist.empty else load_stock_codes()
    if not stock_codes:
        st.info("还没有可分析的股票数据。")
        return

    analysis_frame = load_analysis_table(stock_codes)
    if analysis_frame.empty:
        st.info("当前数据不足以生成分析结果。")
        return

    leader = analysis_frame.iloc[0]
    col1, col2, col3 = st.columns(3)
    col1.metric("20日最强", str(leader["stock_code"]))
    col2.metric("20日收益", "暂无" if pd.isna(leader["return_20d_pct"]) else f"{leader['return_20d_pct']:.2f}%")
    col3.metric("是否站上MA20", "是" if bool(leader["above_ma20"]) else "否")

    selected_code = st.selectbox("分析单只股票", options=analysis_frame["stock_code"].tolist())
    selected_row = analysis_frame.loc[analysis_frame["stock_code"] == selected_code].iloc[0]
    detail_col1, detail_col2, detail_col3, detail_col4 = st.columns(4)
    detail_col1.metric("最新收盘价", f"{selected_row['latest_close']:.2f}")
    detail_col2.metric("MA5", "暂无" if pd.isna(selected_row["ma5"]) else f"{selected_row['ma5']:.2f}")
    detail_col3.metric("MA20", "暂无" if pd.isna(selected_row["ma20"]) else f"{selected_row['ma20']:.2f}")
    detail_col4.metric(
        "20日波动",
        "暂无" if pd.isna(selected_row["volatility_20d"]) else f"{selected_row['volatility_20d']:.2f}",
    )

    st.dataframe(analysis_frame, use_container_width=True, hide_index=True)


def main() -> None:
    st.title("A-Share Data Dashboard")
    st.write("本地 SQLite 数据看板。先验证数据采集链路，再逐步加分析能力。")
    tab_overview, tab_watchlist, tab_analysis = st.tabs(["概览", "自选股", "简单分析"])
    with tab_overview:
        render_overview()
        st.divider()
        render_trade_calendar()
        st.divider()
        render_daily_bars()
    with tab_watchlist:
        render_watchlist_page()
    with tab_analysis:
        render_analysis_page()


if __name__ == "__main__":
    main()
