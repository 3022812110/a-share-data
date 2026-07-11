import { Button, Popover, Progress, Tag, Typography } from "antd";
import {
  CheckCircleFilled,
  ClockCircleOutlined,
  ReloadOutlined,
  WarningFilled,
} from "@ant-design/icons";

const { Text } = Typography;

const STATUS_META = {
  healthy: { label: "数据正常", color: "success", icon: <CheckCircleFilled /> },
  warning: { label: "部分待更新", color: "warning", icon: <WarningFilled /> },
  stale: { label: "核心数据过期", color: "error", icon: <WarningFilled /> },
};

export default function DataHealthBar({ health, refreshing, onRefresh }) {
  const current = STATUS_META[health?.status] ?? STATUS_META.warning;
  const datasets = health?.datasets ?? [];
  const critical = datasets.filter((item) => ["market_snapshot", "stock_catalog", "major_indices"].includes(item.key));

  const details = (
    <div className="data-health-popover apple-data-popover">
      <div className="data-health-popover-head">
        <div>
          <Text strong>数据完整性</Text>
          <Text type="secondary">目标交易日 {health?.expected_trade_date ?? "--"}</Text>
        </div>
        <Tag color={current.color}>{current.label}</Tag>
      </div>
      <div className="data-health-list">
        {datasets.map((item) => (
          <div className="data-health-row" key={item.key}>
            <div className="data-health-row-main">
              <Text strong>{item.label}</Text>
              <Text type="secondary">{item.detail}</Text>
            </div>
            <div className="data-health-row-side">
              {item.coverage !== null && item.coverage !== undefined ? (
                <Progress percent={Math.round(Number(item.coverage) * 100)} size="small" showInfo={false} />
              ) : null}
              <Text type="secondary">{item.latest ?? "--"}</Text>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className={`apple-data-status apple-data-status-${health?.status ?? "warning"}`}>
      <span className="apple-data-status-icon">{current.icon}</span>
      <Text strong>{current.label}</Text>
      <Text type="secondary">交易日 {health?.expected_trade_date ?? "--"}</Text>
      <span className="apple-data-divider" />
      {critical.map((item) => (
        <span className="apple-data-metric" key={item.key}>
          {item.label} <b>{Math.round(Number(item.coverage ?? 0) * 100)}%</b>
        </span>
      ))}
      <span className="apple-data-spacer" />
      <Popover content={details} title={null} trigger="click" placement="bottomRight">
        <Button size="small" type="text" icon={<ClockCircleOutlined />}>明细</Button>
      </Popover>
      <Button size="small" icon={<ReloadOutlined />} onClick={onRefresh} loading={refreshing}>同步</Button>
    </div>
  );
}
