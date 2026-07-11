import { Tag, Typography } from "antd";
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  FireOutlined,
  FundOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";

import { capText, colorStyle, numberText, percentText } from "../lib/formatters";

const { Text } = Typography;

function numeric(value, fallback = 0) {
  const result = Number(value);
  return Number.isFinite(result) ? result : fallback;
}

function compactName(value, length = 7) {
  const text = String(value || "--");
  return text.length > length ? `${text.slice(0, length)}…` : text;
}

export default function MarketOverviewPanel({ summary, onSelectCode }) {
  const indices = summary.major_indices ?? [];
  const insights = summary.market_insights ?? {};
  const sentiment = insights.sentiment ?? {};
  const industryRanks = insights.sector_rankings?.industry ?? [];
  const conceptRanks = insights.sector_rankings?.concept ?? [];
  const stockMoneyRanks = insights.stock_money_rankings ?? [];
  const hotTopics = insights.hot_topics ?? [];
  const hotWords = insights.hot_words ?? [];
  const rising = numeric(summary.rising_count);
  const falling = numeric(summary.falling_count);
  const breadthTotal = Math.max(1, rising + falling);
  const risingRatio = Math.round((rising / breadthTotal) * 100);

  return (
    <section className="market-workbench" aria-label="市场总览">
      <div className="market-ticker-ribbon">
        <div className="market-ticker-label">
          <span className="market-live-dot" />
          <div>
            <Text strong>市场总览</Text>
            <Text type="secondary">{summary.latest_trade_time ?? "--"}</Text>
          </div>
        </div>

        <div className="market-index-ticker-list">
          {indices.map((item) => (
            <div className="market-index-ticker" key={item.index_code}>
              <Text type="secondary">{item.index_name}</Text>
              <Text strong className="market-numeric market-index-price" style={colorStyle(item.change_pct)}>
                {numberText(item.price, 2)}
              </Text>
              <Text className="market-index-change" style={colorStyle(item.change_pct)}>
                {numeric(item.change_pct) >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                {percentText(item.change_pct)}
              </Text>
            </div>
          ))}
        </div>

        <div className="market-ticker-meta">
          <div>
            <Text type="secondary">全市场</Text>
            <Text strong className="market-numeric">{summary.stock_count ?? 0}</Text>
          </div>
          <div>
            <Text type="secondary">成交额</Text>
            <Text strong className="market-numeric">{capText(summary.total_turnover_yi)}</Text>
          </div>
        </div>
      </div>

      <div className="market-signal-deck">
        <section className="market-signal-panel market-breadth-panel">
          <div className="market-panel-heading">
            <span><ThunderboltOutlined /> 市场宽度</span>
            <Tag bordered={false} color={risingRatio >= 55 ? "red" : risingRatio <= 45 ? "green" : "default"}>
              {risingRatio >= 55 ? "偏强" : risingRatio <= 45 ? "偏弱" : "均衡"}
            </Tag>
          </div>
          <div className="market-breadth-meter" title={`上涨 ${risingRatio}%`}>
            <span className="market-breadth-up" style={{ width: `${risingRatio}%` }} />
          </div>
          <div className="market-breadth-numbers">
            <span className="market-up"><b>{rising}</b> 上涨</span>
            <span><b>{summary.limit_up_count ?? 0}</b> 涨停</span>
            <span><b>{summary.limit_down_count ?? 0}</b> 跌停</span>
            <span className="market-down"><b>{falling}</b> 下跌</span>
          </div>
          <div className="market-sentiment-line">
            <Text type="secondary">情绪</Text>
            <Text strong>{sentiment.label ?? "中性"} · {numberText(sentiment.score ?? 50, 0)}</Text>
            <Text type="secondary" ellipsis={{ tooltip: sentiment.description }}>
              {sentiment.description ?? "等待更多市场样本"}
            </Text>
          </div>
        </section>

        <section className="market-signal-panel market-sector-panel">
          <div className="market-panel-heading">
            <span><FundOutlined /> 资金主线</span>
            <Text type="secondary">净流入 Top 4</Text>
          </div>
          <div className="market-sector-columns">
            <div>
              <Text type="secondary" className="market-column-label">行业</Text>
              {industryRanks.slice(0, 4).map((item, index) => (
                <div className="market-ranked-row" key={item.category_code ?? item.name}>
                  <span className="market-row-rank">{index + 1}</span>
                  <Text>{compactName(item.name)}</Text>
                  <Text strong style={colorStyle(item.net_inflow_yi)}>{capText(item.net_inflow_yi)}</Text>
                </div>
              ))}
            </div>
            <div>
              <Text type="secondary" className="market-column-label">概念</Text>
              {conceptRanks.slice(0, 4).map((item, index) => (
                <div className="market-ranked-row" key={item.category_code ?? item.name}>
                  <span className="market-row-rank">{index + 1}</span>
                  <Text>{compactName(item.name)}</Text>
                  <Text strong style={colorStyle(item.net_inflow_yi)}>{capText(item.net_inflow_yi)}</Text>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="market-signal-panel market-capital-panel">
          <div className="market-panel-heading">
            <span><FundOutlined /> 个股资金</span>
            <Text type="secondary">主力净流入</Text>
          </div>
          <div className="market-capital-list">
            {stockMoneyRanks.slice(0, 5).map((item, index) => (
              <button
                type="button"
                className="market-capital-row"
                key={item.stock_code}
                onClick={() => onSelectCode?.(item.stock_code)}
              >
                <span className="market-row-rank">{index + 1}</span>
                <span className="market-capital-stock">
                  <strong>{item.stock_name}</strong>
                  <small>{item.stock_code}</small>
                </span>
                <span className="market-capital-value">
                  <strong>{capText(item.main_net_inflow_yi)}</strong>
                  <small style={colorStyle(item.change_pct)}>{percentText(item.change_pct)}</small>
                </span>
              </button>
            ))}
          </div>
        </section>

        <section className="market-signal-panel market-focus-panel">
          <div className="market-panel-heading">
            <span><FireOutlined /> 今日焦点</span>
            <Text type="secondary">热点 / 事件</Text>
          </div>
          <div className="market-focus-list">
            {hotTopics.slice(0, 3).map((item, index) => (
              <a className="market-focus-row" href={item.url || "#"} target="_blank" rel="noreferrer" key={item.topic_id ?? index}>
                <span className="market-row-rank">{index + 1}</span>
                <span>{compactName(item.title, 17)}</span>
                <small>{numberText(item.post_count, 0)}</small>
              </a>
            ))}
          </div>
          <div className="market-hotword-strip">
            {hotWords.slice(0, 5).map((item) => (
              <Tag bordered={false} key={item.word}>{item.word}</Tag>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}
