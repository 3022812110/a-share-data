import { Alert, Button, Card, Space, Table, Tag, Typography } from "antd";

import CompactEmpty from "./CompactEmpty";
import { colorStyle, numberText, percentText } from "../lib/formatters";


const { Text } = Typography;


export default function RecommendationPerformancePanel({ performance, loading, onRefresh }) {
  const calibration = performance?.calibration ?? {};
  const horizons = performance?.horizons ?? {};
  const items = performance?.items ?? [];
  const statusType = calibration.status === "stable"
    ? "success"
    : calibration.status === "tighten"
      ? "error"
      : "info";
  const summaryHorizons = [1, 5, 10, 20];

  const columns = [
    {
      title: "历史建议",
      key: "stock",
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text strong>{record.stock_name}</Text>
          <Text type="secondary">{record.stock_code} · {record.recommendation_date}</Text>
        </Space>
      ),
    },
    {
      title: "当时环境",
      dataIndex: "market_regime",
      render: (value) => <Tag bordered={false}>{value ?? "未知"}</Tag>,
    },
    {
      title: "1日结果",
      key: "return1",
      render: (_, record) => {
        const value = record.metrics?.["1"]?.return_pct;
        return <Text style={colorStyle(value)}>{percentText(value)}</Text>;
      },
    },
    {
      title: "5日结果",
      key: "return5",
      render: (_, record) => {
        const value = record.metrics?.["5"]?.return_pct;
        return <Text strong style={colorStyle(value)}>{percentText(value)}</Text>;
      },
    },
    {
      title: "状态",
      key: "status",
      render: (_, record) => (
        <Text type="secondary">
          {record.evaluated_trade_days >= 5 ? "已完成5日验证" : `已跟踪 ${record.evaluated_trade_days ?? 0} 日`}
        </Text>
      ),
    },
  ];

  return (
    <Card
      variant="borderless"
      className="table-card"
      title="建议是否靠谱"
      loading={loading}
      extra={<Button size="small" onClick={onRefresh} loading={loading}>重新核算</Button>}
    >
      <Alert
        showIcon
        type={statusType}
        message={calibration.label ?? "可信度积累中"}
        description={calibration.summary ?? "系统会自动检查每次建议后续的真实涨跌。"}
        style={{ marginBottom: 12 }}
      />
      <div className="paper-stat-grid compact-strip" style={{ marginBottom: 12 }}>
        {summaryHorizons.map((horizon) => {
          const metric = horizons[String(horizon)] ?? {};
          return (
            <Card variant="borderless" key={horizon} className="compact-metric-card">
              <div className="compact-metric-row">
                <Text type="secondary">{horizon}日</Text>
                <Text strong>{metric.sample_count ?? 0}例</Text>
              </div>
              <div className="compact-metric-row">
                <Text type="secondary">胜率 {metric.win_rate_pct == null ? "--" : `${numberText(metric.win_rate_pct)}%`}</Text>
                <Text style={colorStyle(metric.avg_return_pct)}>{percentText(metric.avg_return_pct)}</Text>
              </div>
            </Card>
          );
        })}
      </div>
      <Table
        rowKey="id"
        size="small"
        columns={columns}
        dataSource={items.slice(0, 12)}
        pagination={false}
        locale={{ emptyText: <CompactEmpty description="当前没有买入建议样本；系统开放买入并给出建议后会自动开始验证" /> }}
      />
    </Card>
  );
}
