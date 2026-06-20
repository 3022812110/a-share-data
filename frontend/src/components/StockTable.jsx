import { Button, Card, InputNumber, Space, Table, Tag, Typography } from "antd";

import { capText, colorStyle, numberText, percentText } from "../lib/formatters";

const { Text } = Typography;

export default function StockTable({
  title,
  items,
  total,
  loading,
  page,
  pageSize,
  onPageChange,
  selectedCode,
  onSelectCode,
  onToggleWatchlist,
  onQuickTrade,
  tradeQuantities,
  onTradeQuantityChange,
  showTradeActions,
  marketStatus,
  controls,
}) {
  const marketOpen = marketStatus?.is_open === true;
  const columns = [
    {
      title: "股票",
      key: "stock",
      render: (_, record) => (
        <Space size={5} className="dense-cell-line">
          <Text strong>{record.stock_name}</Text>
          <Text code>{record.stock_code}</Text>
          <Text type="secondary">{record.market}</Text>
        </Space>
      ),
    },
    {
      title: "行情",
      key: "quote",
      render: (_, record) => (
        <Space size={6} className="dense-cell-line">
          <Text strong>{numberText(record.price)}</Text>
          <Text style={colorStyle(record.change_pct)}>{percentText(record.change_pct)}</Text>
        </Space>
      ),
    },
    {
      title: "活跃度",
      key: "activity",
      render: (_, record) => (
        <Space size={7} className="dense-cell-line">
          <Text>换手 {percentText(record.turnover_ratio)}</Text>
          <Text type="secondary">量比 {numberText(record.volume_ratio)}</Text>
        </Space>
      ),
    },
    {
      title: "交易计划",
      key: "plan",
      render: (_, record) => (
        <Space size={7} className="dense-cell-line">
          <Text>买入 {numberText(record.buy_price)}</Text>
          <Text type="secondary">盈 {numberText(record.take_profit_price)}</Text>
          <Text type="secondary">损 {numberText(record.stop_loss_price)}</Text>
        </Space>
      ),
    },
    {
      title: "估值与市值",
      key: "valuation",
      render: (_, record) => (
        <Space size={7} className="dense-cell-line">
          <Text>PE {numberText(record.pe_ratio)}</Text>
          <Text>PB {numberText(record.pb_ratio)}</Text>
          <Text type="secondary">{capText(record.total_market_value)}</Text>
        </Space>
      ),
    },
    {
      title: "状态 / 操作",
      key: "status",
      render: (_, record) => (
        <div className="table-status-cell">
          <div className="table-status-head">
            {record.in_watchlist ? <Tag color="gold">自选</Tag> : <Tag>市场</Tag>}
            <Text style={colorStyle(record.buy_distance_pct)}>{percentText(record.buy_distance_pct)}</Text>
          </div>
          <Space wrap className="table-action-group">
            {showTradeActions ? (
              <>
                <Button
                  size="small"
                  type="primary"
                  disabled={!marketOpen}
                  onClick={(event) => {
                    event.stopPropagation();
                    const quantity = tradeQuantities?.[record.stock_code] ?? record.default_trade_quantity ?? 100;
                    onQuickTrade(record.stock_code, "buy", quantity, record.in_watchlist ? `一键买入自选 ${quantity} 股` : `一键买入 ${quantity} 股`);
                  }}
                >
                  买入
                </Button>
                <Button
                  size="small"
                  disabled={!marketOpen}
                  onClick={(event) => {
                    event.stopPropagation();
                    const quantity = tradeQuantities?.[record.stock_code] ?? record.default_trade_quantity ?? 100;
                    onQuickTrade(record.stock_code, "sell", quantity, `一键卖出 ${quantity} 股`);
                  }}
                >
                  卖出
                </Button>
                <InputNumber
                  size="small"
                  min={100}
                  step={100}
                  style={{ width: 96 }}
                  value={tradeQuantities?.[record.stock_code] ?? record.default_trade_quantity ?? 100}
                  onClick={(event) => event.stopPropagation()}
                  onChange={(value) => onTradeQuantityChange(record.stock_code, value)}
                />
              </>
            ) : null}
            <Button
              size="small"
              type={record.in_watchlist ? "default" : "link"}
              onClick={(event) => {
                event.stopPropagation();
                onToggleWatchlist(record);
              }}
            >
              {record.in_watchlist ? "移除" : "加入"}
            </Button>
          </Space>
        </div>
      ),
    },
  ];

  return (
    <Card bordered={false} className="table-card" title={title} extra={controls}>
      <Table
        rowKey="stock_code"
        columns={columns}
        dataSource={items}
        loading={loading}
        size="small"
        scroll={{ y: 700 }}
        locale={{ emptyText: title === "我的自选" ? "你还没有加入任何自选股" : "暂无数据" }}
        rowClassName={(record) => (record.stock_code === selectedCode ? "ant-table-row-selected-custom" : "")}
        onRow={(record) => ({ onClick: () => onSelectCode(record.stock_code) })}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          pageSizeOptions: [20, 50, 100],
          onChange: onPageChange,
        }}
      />
    </Card>
  );
}
