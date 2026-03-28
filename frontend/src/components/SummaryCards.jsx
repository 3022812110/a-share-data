import { Card, Typography } from "antd";

const { Text } = Typography;

export default function SummaryCards({ summary }) {
  const metrics = [
    { label: "全市场", value: summary.stock_count ?? 0 },
    { label: "上涨", value: summary.rising_count ?? 0, style: { color: "#cf1322" } },
    { label: "下跌", value: summary.falling_count ?? 0, style: { color: "#389e0d" } },
    { label: "涨停", value: summary.limit_up_count ?? 0, style: { color: "#cf1322" } },
    { label: "跌停", value: summary.limit_down_count ?? 0, style: { color: "#389e0d" } },
    { label: "自选", value: summary.watchlist_count ?? 0 },
  ];

  return (
    <div className="stat-grid compact-strip">
      {metrics.map((item) => (
        <Card bordered={false} key={item.label} className="compact-metric-card">
          <div className="compact-metric-row">
            <Text type="secondary">{item.label}</Text>
            <Text strong style={item.style}>
              {item.value}
            </Text>
          </div>
        </Card>
      ))}
    </div>
  );
}
