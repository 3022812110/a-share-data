import { Alert, Space, Tag, Typography } from "antd";
import { CheckCircleOutlined, ClockCircleOutlined } from "@ant-design/icons";

const { Text } = Typography;

function compactDateTime(value) {
  const text = String(value ?? "").trim();
  if (!text) return "--";
  return text.replace("T", " ").replace("Z", "").slice(0, 16);
}

export default function MarketStatusNotice({ marketStatus, compact = false }) {
  const marketOpen = marketStatus?.is_open === true;
  const title = marketOpen ? "A 股交易中" : marketStatus?.reason ?? "正在确认交易状态";
  const detail = marketOpen
    ? "模拟盘已开放"
    : marketStatus?.next_open
      ? `下次开市 ${compactDateTime(marketStatus.next_open)}`
      : `北京时间 ${compactDateTime(marketStatus?.current_time)}`;

  return (
    <Alert
      className={compact ? "market-status-notice compact" : "market-status-notice"}
      type="info"
      showIcon
      icon={marketOpen ? <CheckCircleOutlined /> : <ClockCircleOutlined />}
      message={
        <Space size={8} wrap={false}>
          <Text strong>{title}</Text>
          <Text type="secondary">{detail}</Text>
        </Space>
      }
      action={
        <Tag bordered={false} className={marketOpen ? "market-status-chip open" : "market-status-chip"}>
          {marketOpen ? "可交易" : "模拟盘暂停"}
        </Tag>
      }
    />
  );
}
