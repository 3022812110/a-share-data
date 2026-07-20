import { Alert, Button, Card, Space, Table, Tag, Typography } from "antd";

import CompactEmpty from "./CompactEmpty";
import { colorStyle, numberText, percentText } from "../lib/formatters";


const { Text } = Typography;


export default function StrategyStabilityPanel({ stability, loading, onRun, onSelectCode }) {
  const ranking = stability?.ranking ?? [];
  const conclusion = stability?.conclusion ?? {};
  const conclusionType = conclusion.status === "evidence_available"
    ? "success"
    : conclusion.status === "observe_only"
      ? "warning"
      : "info";

  const columns = [
    {
      title: "标的",
      key: "stock",
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Button type="link" size="small" style={{ padding: 0 }} onClick={() => onSelectCode?.(record.stock_code)}>
            {record.stock_name}
          </Button>
          <Space size={6}>
            <Text type="secondary">{record.stock_code}</Text>
            <Tag bordered={false}>{record.source}</Tag>
          </Space>
        </Space>
      ),
    },
    {
      title: "最稳策略",
      key: "strategy",
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text strong>{record.best_strategy_name}</Text>
          <Text type="secondary">{record.window_count} 个窗口 / {record.aggregate?.total_trades ?? 0} 笔</Text>
          <Text type="secondary">历史适用：{record.aggregate?.best_market_regime ?? "未知"}</Text>
        </Space>
      ),
    },
    {
      title: "平均样本外",
      key: "return",
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text strong style={colorStyle(record.aggregate?.average_return_pct)}>
            {percentText(record.aggregate?.average_return_pct)}
          </Text>
          <Text type="secondary" style={colorStyle(record.aggregate?.average_excess_return_pct)}>
            超额 {percentText(record.aggregate?.average_excess_return_pct)}
          </Text>
        </Space>
      ),
    },
    {
      title: "一致性",
      key: "consistency",
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text>正收益 {numberText(record.aggregate?.positive_window_pct)}%</Text>
          <Text type="secondary">跑赢基准 {numberText(record.aggregate?.beat_benchmark_pct)}%</Text>
        </Space>
      ),
    },
    {
      title: "最差回撤",
      key: "drawdown",
      render: (_, record) => (
        <Text style={colorStyle(record.aggregate?.worst_drawdown_pct)}>
          {percentText(record.aggregate?.worst_drawdown_pct)}
        </Text>
      ),
    },
    {
      title: "结论",
      key: "status",
      render: (_, record) => {
        const status = record.robustness?.status;
        const color = status === "stable" ? "green" : status === "observe" ? "gold" : status === "reject" ? "red" : "default";
        return <Tag color={color}>{record.robustness?.label ?? "样本不足"}</Tag>;
      },
    },
  ];

  return (
    <Card
      variant="borderless"
      className="table-card"
      title="策略稳定性排行榜"
      loading={loading}
      extra={<Button size="small" onClick={onRun} loading={loading}>运行滚动验证</Button>}
    >
      {stability ? (
        <>
          <Alert
            showIcon
            type={conclusionType}
            message={conclusion.label}
            description={conclusion.summary}
            style={{ marginBottom: 12 }}
          />
          <div className="paper-stat-grid compact-strip" style={{ marginBottom: 12 }}>
            <Card variant="borderless" className="compact-metric-card">
              <div className="compact-metric-row"><Text type="secondary">股票池</Text><Text strong>{stability.universe_size ?? 0} 只</Text></div>
            </Card>
            <Card variant="borderless" className="compact-metric-card">
              <div className="compact-metric-row"><Text type="secondary">跨窗口稳定</Text><Text strong>{stability.stable_count ?? 0} 只</Text></div>
            </Card>
            <Card variant="borderless" className="compact-metric-card">
              <div className="compact-metric-row"><Text type="secondary">仅观察</Text><Text strong>{stability.observe_count ?? 0} 只</Text></div>
            </Card>
            <Card variant="borderless" className="compact-metric-card">
              <div className="compact-metric-row"><Text type="secondary">失效 / 不足</Text><Text strong>{(stability.reject_count ?? 0) + (stability.insufficient_count ?? 0)} 只</Text></div>
            </Card>
          </div>
          <Table
            rowKey="stock_code"
            size="small"
            columns={columns}
            dataSource={ranking}
            pagination={false}
            scroll={{ x: 820 }}
            locale={{ emptyText: <CompactEmpty description="本轮没有股票具备足够的滚动验证数据" /> }}
          />
          <Text type="secondary">
            默认按持仓、自选和最近推荐组建股票池；稳定标签只代表多个历史样本外窗口结果更一致，不构成买入指令。
          </Text>
        </>
      ) : (
        <CompactEmpty description="点击运行后，系统会比较多只股票在多个独立样本外窗口中的表现" />
      )}
    </Card>
  );
}
