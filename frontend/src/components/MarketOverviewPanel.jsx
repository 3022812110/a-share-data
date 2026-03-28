import { Card, Space, Typography } from "antd";

import { capText, colorStyle, numberText, percentText, trillionText } from "../lib/formatters";

const { Text } = Typography;

export default function MarketOverviewPanel({ summary }) {
  const indices = summary.major_indices ?? [];
  const exchangeOverview = summary.exchange_overview ?? {};
  const exchangeItems = [
    { label: "沪市公司", value: exchangeOverview?.sse?.listed_companies ?? "--" },
    { label: "沪市总市值", value: trillionText(exchangeOverview?.sse?.total_market_value) },
    { label: "沪市流通", value: trillionText(exchangeOverview?.sse?.circulating_market_value) },
    { label: "深市数量", value: exchangeOverview?.szse?.stock_count ?? "--" },
    { label: "深市总市值", value: trillionText(exchangeOverview?.szse?.total_market_value) },
    { label: "深市成交", value: trillionText(exchangeOverview?.szse?.trading_amount) },
  ];

  return (
    <div className="market-overview-grid">
      <Card bordered={false} className="market-panel-card compact-panel-card" title="A股大盘">
        <Space direction="vertical" size={10} style={{ width: "100%" }}>
          <div className="market-summary-header">
            <Text type="secondary">最新时间 {summary.latest_trade_time ?? "--"}</Text>
            <Text type="secondary">成交额 {capText(summary.total_turnover_yi)}</Text>
          </div>
          <div className="market-index-grid">
            {indices.map((item) => (
              <Card key={item.index_code} size="small" className="compact-index-card">
                <div className="compact-index-row">
                  <Text type="secondary">{item.index_name}</Text>
                  <Text strong>{numberText(item.price, 2)}</Text>
                  <Text style={colorStyle(item.change_pct)}>{percentText(item.change_pct)}</Text>
                </div>
              </Card>
            ))}
          </div>
        </Space>
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
  );
}
