import { Alert, Button, Card, Space, Table, Tag, Typography } from "antd";

import PaperSummaryCards from "./PaperSummaryCards";
import { capText, colorStyle, numberText, percentText } from "../lib/formatters";

const { Text } = Typography;

export default function PaperPortfolioPanel({
  portfolio,
  loading,
  recommendations = [],
  recommendationSummary,
  recommendationLoading,
  onSelectCode,
  onOpenReview,
  onQuickTrade,
  onRefreshRecommendations,
}) {
  const positions = portfolio?.positions ?? [];
  const trades = portfolio?.trades ?? [];
  const marketContext = recommendationSummary?.market_context ?? {};
  const recommendationAccount = recommendationSummary?.account ?? {};
  const marketStatus = portfolio?.market_status ?? {};
  const marketOpen = marketStatus.is_open === true;

  const recommendationColumns = [
    {
      title: "标的",
      key: "stock",
      render: (_, record) => (
        <Space direction="vertical" size={4}>
          <Text strong>{record.stock_name}</Text>
          <Space size={6} wrap>
            <Text code>{record.stock_code}</Text>
            <Text type="secondary">{record.market}</Text>
            {(record.theme_tags ?? []).slice(0, 2).map((tag) => (
              <Tag key={`${record.stock_code}-${tag}`} bordered={false}>
                {tag}
              </Tag>
            ))}
          </Space>
        </Space>
      ),
    },
    {
      title: "现价",
      dataIndex: "price",
      render: (value) => <Text>{numberText(value)}</Text>,
    },
    {
      title: "买入计划",
      key: "plan",
      render: (_, record) => (
        <Space size={8} className="dense-cell-line">
          <Text>{record.recommended_quantity}股</Text>
          <Text type="secondary">约¥{numberText(record.estimated_cash)}</Text>
          <Text type="secondary">区间 {numberText(record.entry_zone_low)}-{numberText(record.entry_zone_high)}</Text>
          <Text type="secondary">损 {numberText(record.stop_loss_price)} / 盈 {numberText(record.take_profit_price)}</Text>
        </Space>
      ),
    },
    {
      title: "盘面",
      key: "market",
      render: (_, record) => (
        <Space size={8} className="dense-cell-line">
          <Text style={colorStyle(record.change_pct)}>{percentText(record.change_pct)}</Text>
          <Text type="secondary">换 {numberText(record.turnover_ratio)}%</Text>
          <Text type="secondary">量 {numberText(record.volume_ratio)}</Text>
          <Text type="secondary">成交 {capText(record.amount_yi)}</Text>
        </Space>
      ),
    },
    {
      title: "依据",
      key: "reason",
      render: (_, record) => (
        <Space direction="vertical" size={2}>
          {(record.reasons ?? []).slice(0, 2).map((item, index) => (
            <Text key={`${record.stock_code}-reason-${index}`} type="secondary">
              {item}
            </Text>
          ))}
          <Space size={4} wrap>
            <Tag color={record.confidence === "高" ? "red" : "blue"}>置信 {record.confidence}</Tag>
            <Tag color={record.risk_level === "高" ? "orange" : "green"}>风险 {record.risk_level}</Tag>
          </Space>
        </Space>
      ),
    },
    {
      title: "操作",
      key: "actions",
      render: (_, record) => (
        <Space direction="vertical" size={6}>
          <Button
            size="small"
            type="primary"
            disabled={!marketOpen}
            onClick={(event) => {
              event.stopPropagation();
              onQuickTrade?.(
                record.stock_code,
                "buy",
                record.recommended_quantity,
                `训练推荐买入 ${record.recommended_quantity} 股：${record.entry_reason}`,
              );
            }}
          >
            买入
          </Button>
          <Button
            size="small"
            onClick={(event) => {
              event.stopPropagation();
              onSelectCode(record.stock_code);
            }}
          >
            详情
          </Button>
        </Space>
      ),
    },
  ];

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
      title: "持仓数量",
      key: "position",
      render: (_, record) => <Text>{record.quantity} 股</Text>,
    },
    {
      title: "买入价",
      dataIndex: "avg_cost",
      key: "avg_cost",
      render: (value) => <Text strong>{numberText(value)}</Text>,
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
      title: "现价 / 持仓盈亏",
      key: "pnl",
      render: (_, record) => (
        <Space size={8} className="dense-cell-line">
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
      <Alert
        showIcon
        type={marketOpen ? "success" : "warning"}
        message={marketOpen ? "A股交易中，模拟盘可买卖" : marketStatus.reason ?? "正在确认 A 股交易状态"}
        description={
          marketStatus.next_open
            ? `北京时间 ${marketStatus.current_time ?? "--"}，下次开市 ${marketStatus.next_open}`
            : `北京时间 ${marketStatus.current_time ?? "--"}`
        }
      />
      <PaperSummaryCards portfolio={portfolio} />
      <Card
        bordered={false}
        className="table-card trade-recommendation-card"
        title="训练推荐"
        loading={recommendationLoading}
        extra={
          <Button size="small" onClick={onRefreshRecommendations} loading={recommendationLoading}>
            刷新
          </Button>
        }
      >
        <div className="trade-recommendation-summary">
          <Space wrap>
            <Tag color={marketContext.regime === "偏强" ? "red" : marketContext.regime === "偏弱" ? "green" : "blue"}>
              {marketContext.regime ?? "观察"}
            </Tag>
            <Text type="secondary">上涨占比 {numberText(marketContext.rising_ratio)}%</Text>
            <Text type="secondary">涨停 {marketContext.limit_up_count ?? 0}</Text>
            <Text type="secondary">跌停 {marketContext.limit_down_count ?? 0}</Text>
            <Text type="secondary">计划仓位 {numberText(recommendationAccount.planned_position_pct)}%</Text>
          </Space>
          <Text type="secondary">{marketContext.strategy ?? "先确认市场强弱，再做小仓训练。"}</Text>
        </div>
        <Table
          rowKey="stock_code"
          size="small"
          columns={recommendationColumns}
          dataSource={recommendations}
          pagination={false}
          locale={{ emptyText: "当前没有满足仓位和风险条件的训练标的。" }}
          onRow={(record) => ({ onClick: () => onSelectCode(record.stock_code) })}
        />
      </Card>
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
