import { Bar, Pie } from "@ant-design/plots";
import { Card, Tabs, Tag, Typography } from "antd";
import {
  FireOutlined,
  FundOutlined,
  NotificationOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";

import { capText, colorStyle, numberText, percentText, trillionText } from "../lib/formatters";

const { Text } = Typography;

function clampNumber(value, fallback = 0) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

function shortText(value, max = 10) {
  if (!value) return "--";
  return value.length > max ? `${value.slice(0, max)}…` : value;
}

function heatText(value) {
  const numeric = clampNumber(value);
  if (!numeric) return "--";
  if (numeric >= 100000000) return `${(numeric / 100000000).toFixed(1)}亿`;
  if (numeric >= 10000) return `${(numeric / 10000).toFixed(1)}万`;
  return numberText(numeric, 0);
}

function sentimentTone(score) {
  const numeric = clampNumber(score, 50);
  if (numeric >= 65) return "bull";
  if (numeric <= 35) return "bear";
  return "neutral";
}

function buildPlotTheme() {
  return {
    type: "classic",
    view: {
      viewFill: "transparent",
    },
    axis: {
      labelFill: "#6b7280",
      lineStroke: "rgba(148,163,184,0.22)",
      tickStroke: "rgba(148,163,184,0.22)",
      titleFill: "#94a3b8",
      gridStroke: "rgba(148,163,184,0.14)",
    },
    legend: {
      itemNameFill: "#475569",
      itemValueFill: "#64748b",
    },
  };
}

export default function MarketOverviewPanel({ summary }) {
  const indices = summary.major_indices ?? [];
  const exchangeOverview = summary.exchange_overview ?? {};
  const insights = summary.market_insights ?? {};
  const sentiment = insights.sentiment ?? {};
  const hotWords = insights.hot_words ?? [];
  const hotTopics = insights.hot_topics ?? [];
  const telegraphSample = insights.telegraph_sample ?? [];
  const sectorRankings = insights.sector_rankings ?? {};
  const industryRanks = sectorRankings.industry ?? [];
  const conceptRanks = sectorRankings.concept ?? [];

  const exchangeItems = [
    { label: "沪市公司", value: exchangeOverview?.sse?.listed_companies ?? "--" },
    { label: "沪市总市值", value: trillionText(exchangeOverview?.sse?.total_market_value) },
    { label: "沪市流通", value: trillionText(exchangeOverview?.sse?.circulating_market_value) },
    { label: "深市数量", value: exchangeOverview?.szse?.stock_count ?? "--" },
    { label: "深市总市值", value: trillionText(exchangeOverview?.szse?.total_market_value) },
    { label: "深市成交", value: trillionText(exchangeOverview?.szse?.trading_amount) },
  ];

  const breadthItems = [
    { label: "上涨", value: summary.rising_count ?? 0, tone: "up" },
    { label: "下跌", value: summary.falling_count ?? 0, tone: "down" },
    { label: "涨停", value: summary.limit_up_count ?? 0, tone: "hot" },
    { label: "跌停", value: summary.limit_down_count ?? 0, tone: "cold" },
  ];

  const cockpitMetrics = [
    { label: "全市场", value: summary.stock_count ?? 0, tone: "neutral" },
    { label: "上涨家数", value: summary.rising_count ?? 0, tone: "up" },
    { label: "下跌家数", value: summary.falling_count ?? 0, tone: "down" },
    { label: "涨停", value: summary.limit_up_count ?? 0, tone: "hot" },
    { label: "跌停", value: summary.limit_down_count ?? 0, tone: "cold" },
    { label: "自选", value: summary.watchlist_count ?? 0, tone: "neutral" },
  ];

  const sentimentScore = clampNumber(sentiment.score, 50);
  const totalSentimentCount = Math.max(
    1,
    clampNumber(sentiment.bullish_count) +
      clampNumber(sentiment.neutral_count) +
      clampNumber(sentiment.bearish_count),
  );

  const sentimentChartData = [
    { type: "偏多", value: clampNumber(sentiment.bullish_count), color: "#e2686d" },
    { type: "中性", value: clampNumber(sentiment.neutral_count), color: "#7b8ba1" },
    { type: "偏空", value: clampNumber(sentiment.bearish_count), color: "#4fa177" },
  ].filter((item) => item.value > 0);

  const industryChartData = industryRanks.slice(0, 6).map((item, index) => ({
    rank: index + 1,
    name: shortText(item.name, 8),
    fullName: item.name,
    value: clampNumber(item.net_inflow_yi),
    leader: item.leading_stock_name || "--",
    leaderChange: item.leading_stock_change_pct,
  }));

  const conceptChartData = conceptRanks.slice(0, 6).map((item, index) => ({
    rank: index + 1,
    name: shortText(item.name, 8),
    fullName: item.name,
    value: clampNumber(item.net_inflow_yi),
    leader: item.leading_stock_name || "--",
    leaderChange: item.leading_stock_change_pct,
  }));

  const topicChartData = hotTopics.slice(0, 6).map((item, index) => ({
    rank: index + 1,
    name: shortText(item.title, 8),
    fullName: item.title,
    value: clampNumber(item.heat),
    discussions: clampNumber(item.post_count),
    url: item.url,
  }));

  const plotTheme = buildPlotTheme();

  const sentimentPieConfig = {
    data: sentimentChartData.length
      ? sentimentChartData
      : [
          { type: "偏多", value: 1, color: "#e2686d" },
          { type: "中性", value: 1, color: "#7b8ba1" },
          { type: "偏空", value: 1, color: "#4fa177" },
        ],
    angleField: "value",
    colorField: "type",
    height: 208,
    radius: 0.98,
    innerRadius: 0.72,
    padding: 0,
    autoFit: true,
    theme: plotTheme,
    legend: false,
    tooltip: false,
    color: ({ color }) => color,
    label: false,
    annotations: [
      {
        type: "text",
        style: {
          x: "50%",
          y: "46%",
          text: numberText(sentimentScore, 0),
          textAlign: "center",
          fontSize: 28,
          fontWeight: 700,
          fill: "#111827",
        },
      },
      {
        type: "text",
        style: {
          x: "50%",
          y: "58%",
          text: sentiment.label ?? "中性",
          textAlign: "center",
          fontSize: 11,
          fill: "#64748b",
        },
      },
    ],
  };

  const industryBarConfig = {
    data: industryChartData,
    xField: "name",
    yField: "value",
    height: 228,
    padding: [10, 10, 26, 10],
    autoFit: true,
    theme: plotTheme,
    legend: false,
    tooltip: {
      title: (datum) => datum.fullName,
    },
    axis: {
      y: {
        labelFormatter: (value) => `${value}亿`,
      },
      x: {
        labelAutoRotate: false,
      },
    },
    style: {
      radiusTopLeft: 8,
      radiusTopRight: 8,
      fill: "#68b390",
      fillOpacity: 0.86,
    },
  };

  const conceptBarConfig = {
    data: conceptChartData,
    xField: "name",
    yField: "value",
    height: 228,
    padding: [10, 10, 26, 10],
    autoFit: true,
    theme: plotTheme,
    legend: false,
    tooltip: {
      title: (datum) => datum.fullName,
    },
    axis: {
      y: {
        labelFormatter: (value) => `${value}亿`,
      },
      x: {
        labelAutoRotate: false,
      },
    },
    style: {
      radiusTopLeft: 8,
      radiusTopRight: 8,
      fill: "#5e8de0",
      fillOpacity: 0.9,
    },
  };

  const topicBarConfig = {
    data: topicChartData,
    xField: "value",
    yField: "name",
    seriesField: "name",
    height: 250,
    padding: [8, 12, 8, 4],
    autoFit: true,
    theme: plotTheme,
    legend: false,
    axis: {
      x: {
        labelFormatter: (value) => heatText(value),
      },
      y: {
        labelAutoHide: false,
      },
    },
    tooltip: {
      title: (datum) => datum.fullName,
    },
    style: {
      radiusTopRight: 8,
      radiusBottomRight: 8,
      fill: "#6a8fd8",
      fillOpacity: 0.88,
    },
  };

  const fundsPanel = (
    <div className="market-chart-grid market-chart-grid-double">
      <div className="market-chart-card">
        <div className="market-chart-card-head">
          <Text strong>行业净流入</Text>
          <Text type="secondary">Top 6</Text>
        </div>
        <Bar {...industryBarConfig} />
        <div className="market-chart-footnotes">
          {industryChartData.slice(0, 3).map((item) => (
            <div key={`industry-${item.rank}`} className="market-footnote-row">
              <Text>{item.fullName}</Text>
              <Text type="secondary">
                龙头 {item.leader} {percentText(item.leaderChange)}
              </Text>
            </div>
          ))}
        </div>
      </div>
      <div className="market-chart-card">
        <div className="market-chart-card-head">
          <Text strong>概念净流入</Text>
          <Text type="secondary">Top 6</Text>
        </div>
        <Bar {...conceptBarConfig} />
        <div className="market-chart-footnotes">
          {conceptChartData.slice(0, 3).map((item) => (
            <div key={`concept-${item.rank}`} className="market-footnote-row">
              <Text>{item.fullName}</Text>
              <Text type="secondary">
                龙头 {item.leader} {percentText(item.leaderChange)}
              </Text>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const topicsPanel = (
    <div className="market-chart-stack">
      <div className="market-chart-card">
        <div className="market-chart-card-head">
          <Text strong>热门话题热度</Text>
          <Text type="secondary">最近 24 小时</Text>
        </div>
        <Bar {...topicBarConfig} />
      </div>
      <div className="market-topic-table">
        {hotTopics.slice(0, 6).map((item, index) => (
          <a
            key={item.topic_id ?? `${item.title}-${index}`}
            href={item.url || "#"}
            target="_blank"
            rel="noreferrer"
            className={`market-topic-table-row ${item.url ? "market-topic-table-row-link" : ""}`}
          >
            <div className="market-topic-table-rank">{index + 1}</div>
            <div className="market-topic-table-main">
              <Text strong>{item.title}</Text>
              <Text type="secondary">{item.description || "暂无摘要"}</Text>
            </div>
            <div className="market-topic-table-meta">
              <Text strong>{heatText(item.heat)}</Text>
              <Text type="secondary">{numberText(item.post_count, 0)} 条讨论</Text>
            </div>
          </a>
        ))}
      </div>
    </div>
  );

  const pulsePanel = (
    <div className="market-pulse-table">
      {telegraphSample.slice(0, 8).map((item, index) => (
        <div key={`${item.title}-${index}`} className="market-pulse-row">
          <div className="market-pulse-time">
            <Text type="secondary">{item.published_at || "--"}</Text>
          </div>
          <div className="market-pulse-main">
            <Text strong>{item.title}</Text>
            <div className="market-pulse-tags">
              {(item.subject_names || []).slice(0, 3).map((name) => (
                <Tag key={`${item.title}-${name}`} bordered={false} className="market-pulse-tag">
                  {name}
                </Tag>
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  );

  return (
    <div className="market-overview-stack">
      <Card bordered={false} className="market-panel-card market-cockpit-card">
        <div className="market-cockpit-head">
          <div className="market-cockpit-copy">
            <Text className="market-cockpit-eyebrow">MARKET COCKPIT</Text>
            <Text strong className="market-cockpit-title">
              今日市场驾驶舱
            </Text>
            <Text type="secondary" className="market-cockpit-subtitle">
              以指数、市场宽度、热点和快讯脉冲快速判断当前盘面环境。
            </Text>
          </div>
          <div className="market-cockpit-meta">
            <div className="market-cockpit-meta-item">
              <Text type="secondary">最新交易时间</Text>
              <Text strong>{summary.latest_trade_time ?? "--"}</Text>
            </div>
            <div className="market-cockpit-meta-item">
              <Text type="secondary">全市场成交额</Text>
              <Text strong>{capText(summary.total_turnover_yi)}</Text>
            </div>
          </div>
        </div>
        <div className="market-cockpit-grid">
          {cockpitMetrics.map((item) => (
            <div key={item.label} className={`market-cockpit-metric market-cockpit-metric-${item.tone}`}>
              <Text type="secondary">{item.label}</Text>
              <Text strong>{item.value}</Text>
            </div>
          ))}
        </div>
      </Card>

      <div className="market-overview-grid">
        <Card bordered={false} className="market-panel-card compact-panel-card" title="A股大盘">
          <div className="market-summary-header">
            <Text type="secondary">最新时间 {summary.latest_trade_time ?? "--"}</Text>
            <Text type="secondary">成交额 {capText(summary.total_turnover_yi)}</Text>
          </div>
          <div className="market-index-grid">
            {indices.map((item) => (
              <Card
                key={item.index_code}
                size="small"
                className={`compact-index-card ${
                  clampNumber(item.change_pct) > 0
                    ? "compact-index-card-up"
                    : clampNumber(item.change_pct) < 0
                      ? "compact-index-card-down"
                      : "compact-index-card-flat"
                }`}
              >
                <div className="compact-index-row">
                  <Text type="secondary">{item.index_name}</Text>
                  <Text strong>{numberText(item.price, 2)}</Text>
                  <Text style={colorStyle(item.change_pct)}>{percentText(item.change_pct)}</Text>
                </div>
              </Card>
            ))}
          </div>
          <div className="market-breadth-strip">
            {breadthItems.map((item) => (
              <div key={item.label} className={`market-breadth-pill market-breadth-pill-${item.tone}`}>
                <Text>{item.label}</Text>
                <Text strong>{item.value}</Text>
              </div>
            ))}
          </div>
        </Card>

        <Card bordered={false} className="market-panel-card compact-panel-card" title="交易所总数据">
          <div className="exchange-inline-grid">
            {exchangeItems.map((item) => (
              <div key={item.label} className="exchange-inline-item">
                <Text type="secondary">{item.label}</Text>
                <Text strong>{item.value}</Text>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="market-insights-grid">
        <Card
          bordered={false}
          className="market-panel-card compact-panel-card market-card-sentiment"
          title={
            <span className="market-card-title">
              <ThunderboltOutlined />
              市场情绪
            </span>
          }
        >
          <div className="market-sentiment-pro">
            <div className="market-sentiment-plot">
              <Pie {...sentimentPieConfig} />
            </div>
            <div className="market-sentiment-side">
              <div className="market-sentiment-side-head">
                <Tag bordered={false} className={`market-sentiment-status-pill market-sentiment-status-pill-${sentimentTone(sentimentScore)}`}>
                  {sentiment.label ?? "中性"}
                </Tag>
                <Text type="secondary">{sentiment.description ?? "市场环境正在观察中。"}</Text>
              </div>
              <div className="market-sentiment-stat-list">
                {[
                  { label: "偏多样本", value: sentiment.bullish_count ?? 0, tone: "bull" },
                  { label: "中性样本", value: sentiment.neutral_count ?? 0, tone: "neutral" },
                  { label: "偏空样本", value: sentiment.bearish_count ?? 0, tone: "bear" },
                ].map((item) => (
                  <div key={item.label} className="market-sentiment-stat-row">
                    <div className="market-sentiment-stat-copy">
                      <span className={`market-sentiment-dot market-sentiment-dot-${item.tone}`} />
                      <Text type="secondary">{item.label}</Text>
                    </div>
                    <div className="market-sentiment-stat-values">
                      <Text strong>{item.value}</Text>
                      <Text type="secondary">
                        {Math.round((clampNumber(item.value) / totalSentimentCount) * 100)}%
                      </Text>
                    </div>
                  </div>
                ))}
              </div>
              <div className="market-word-inline market-word-inline-compact">
                {hotWords.slice(0, 8).map((item) => (
                  <Tag key={item.word} className="market-word-chip" bordered={false}>
                    {item.word} · {numberText(item.count, 0)}
                  </Tag>
                ))}
              </div>
            </div>
          </div>
        </Card>

        <Card
          bordered={false}
          className="market-panel-card compact-panel-card market-insight-panel"
          title={
            <span className="market-card-title">
              <FundOutlined />
              市场洞察
            </span>
          }
        >
          <Tabs
            defaultActiveKey="funds"
            size="small"
            className="market-insight-tabs"
            items={[
              {
                key: "funds",
                label: (
                  <span className="market-tab-label">
                    <FundOutlined />
                    板块资金
                  </span>
                ),
                children: fundsPanel,
              },
              {
                key: "topics",
                label: (
                  <span className="market-tab-label">
                    <FireOutlined />
                    热门话题
                  </span>
                ),
                children: topicsPanel,
              },
              {
                key: "pulse",
                label: (
                  <span className="market-tab-label">
                    <NotificationOutlined />
                    市场脉冲
                  </span>
                ),
                children: pulsePanel,
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
