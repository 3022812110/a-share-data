import { Button, Card, Space, Table, Tag, Typography } from "antd";

import { colorStyle, numberText, percentText } from "../lib/formatters";

const { Text } = Typography;

export default function ScreeningTable({ data, loading, onPick, onToggleWatchlist }) {
  const columns = [
    {
      title: "股票",
      key: "stock",
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text strong>{record.stock_name}</Text>
          <Space size={6}>
            <Text code>{record.stock_code}</Text>
            <Text type="secondary">{record.market}</Text>
          </Space>
        </Space>
      ),
    },
    {
      title: "AI评分",
      dataIndex: "ai_score",
      render: (value) => <Text strong>{numberText(value)}</Text>,
    },
    {
      title: "现价",
      dataIndex: "price",
      render: (value) => numberText(value),
    },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      render: (value) => <Text style={colorStyle(value)}>{percentText(value)}</Text>,
    },
    {
      title: "量比 / 换手",
      key: "activity",
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text>量比 {numberText(record.volume_ratio)}</Text>
          <Text type="secondary">换手 {percentText(record.turnover_ratio)}</Text>
        </Space>
      ),
    },
    {
      title: "入选理由",
      dataIndex: "reasons",
      render: (value) => (
        <Space wrap>
          {(value || []).map((reason) => (
            <Tag key={reason}>{reason}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: "操作",
      key: "action",
      render: (_, record) => (
        <Space size={6} wrap className="table-action-group">
          <Button
            type="link"
            onClick={(event) => {
              event.stopPropagation();
              onPick(record.stock_code);
            }}
          >
            查看
          </Button>
          <Button
            size="small"
            onClick={(event) => {
              event.stopPropagation();
              onToggleWatchlist(record);
            }}
          >
            {record.in_watchlist ? "移除自选" : "加入自选"}
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <Card bordered={false} className="table-card" title="AI分析候选池">
      <Table
        rowKey="stock_code"
        columns={columns}
        dataSource={data}
        loading={loading}
        size="small"
        scroll={{ y: 700 }}
        pagination={{ pageSize: 20 }}
        onRow={(record) => ({ onClick: () => onPick(record.stock_code) })}
      />
    </Card>
  );
}
