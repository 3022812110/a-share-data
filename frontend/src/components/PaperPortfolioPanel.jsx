import { Button, Card, Space, Table, Tag, Typography } from "antd";

import PaperSummaryCards from "./PaperSummaryCards";
import { colorStyle, numberText } from "../lib/formatters";

const { Text } = Typography;

export default function PaperPortfolioPanel({ portfolio, loading, onSelectCode, onOpenReview }) {
  const positions = portfolio?.positions ?? [];
  const trades = portfolio?.trades ?? [];

  const positionColumns = [
    {
      title: "持仓",
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
      title: "仓位",
      key: "position",
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text>{record.quantity} 股</Text>
          <Text type="secondary">成本 {numberText(record.avg_cost)}</Text>
        </Space>
      ),
    },
    {
      title: "计划",
      key: "plan",
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text>{record.entry_reason ?? "未填写计划"}</Text>
          <Text type="secondary">
            {record.planned_holding_days ? `${record.planned_holding_days} 天` : "周期未定"}
            {record.stop_loss_price ? ` / 止损 ${numberText(record.stop_loss_price)}` : ""}
          </Text>
        </Space>
      ),
    },
    {
      title: "现价 / 盈亏",
      key: "pnl",
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text>{numberText(record.current_price)}</Text>
          <Text style={colorStyle(record.unrealized_pnl)}>¥{numberText(record.unrealized_pnl)}</Text>
        </Space>
      ),
    },
  ];

  const tradeColumns = [
    {
      title: "时间",
      dataIndex: "trade_time",
      render: (value) => value ?? "--",
    },
    {
      title: "成交",
      key: "trade",
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text strong>{record.stock_name}</Text>
          <Text type="secondary">
            {record.side === "buy" ? "买入" : "卖出"} {record.quantity} 股 @ {numberText(record.price)}
          </Text>
        </Space>
      ),
    },
    {
      title: "金额 / 已实现",
      key: "amount",
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text>¥{numberText(record.amount)}</Text>
          <Text style={colorStyle(record.realized_pnl)}>¥{numberText(record.realized_pnl)}</Text>
        </Space>
      ),
    },
    {
      title: "复盘",
      key: "review",
      render: (_, record) => (
        <Space direction="vertical" size={4}>
          {record.review_rating ? (
            <Tag color={record.review_rating === "good" ? "green" : record.review_rating === "bad" ? "red" : "blue"}>
              {record.review_rating === "good" ? "做得好" : record.review_rating === "bad" ? "做得差" : "一般"}
            </Tag>
          ) : (
            <Tag>{record.plan_status === "closed" ? "待复盘" : "未结束"}</Tag>
          )}
          {record.plan_id && record.plan_status === "closed" ? (
            <Button
              size="small"
              type="link"
              onClick={(event) => {
                event.stopPropagation();
                onOpenReview(record);
              }}
            >
              {record.review_summary ? "查看复盘" : "写复盘"}
            </Button>
          ) : null}
        </Space>
      ),
    },
  ];

  return (
    <Space direction="vertical" size={10} style={{ width: "100%" }}>
      <PaperSummaryCards portfolio={portfolio} />
      <Card bordered={false} className="table-card" title="当前持仓" loading={loading}>
        <Table
          rowKey="stock_code"
          size="small"
          columns={positionColumns}
          dataSource={positions}
          pagination={false}
          locale={{ emptyText: "当前没有持仓，先从右侧详情里试一笔模拟买入。" }}
          onRow={(record) => ({ onClick: () => onSelectCode(record.stock_code) })}
        />
      </Card>
      <Card bordered={false} className="table-card" title="最近成交" loading={loading}>
        <Table
          rowKey="id"
          size="small"
          columns={tradeColumns}
          dataSource={trades}
          pagination={{ pageSize: 8, hideOnSinglePage: true }}
          locale={{ emptyText: "还没有交易记录。" }}
          onRow={(record) => ({ onClick: () => onSelectCode(record.stock_code) })}
        />
      </Card>
    </Space>
  );
}
