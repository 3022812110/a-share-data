import { Card, Typography } from "antd";

import { colorStyle, numberText } from "../lib/formatters";

const { Text } = Typography;

export default function PaperSummaryCards({ portfolio }) {
  const account = portfolio?.account ?? {};
  const metrics = [
    { label: "初始", value: `¥${numberText(account.initial_cash)}` },
    { label: "可用", value: `¥${numberText(account.cash_balance)}` },
    { label: "持仓", value: `¥${numberText(account.market_value)}` },
    { label: "总资产", value: `¥${numberText(account.total_assets)}` },
    { label: "浮盈亏", value: `¥${numberText(account.unrealized_pnl)}`, style: colorStyle(account.unrealized_pnl) },
    { label: "已实现", value: `¥${numberText(account.realized_pnl)}`, style: colorStyle(account.realized_pnl) },
  ];

  return (
    <div className="paper-stat-grid compact-strip">
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
