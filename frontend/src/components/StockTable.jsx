import { Button, InputNumber, Space, Table, Tag, Tooltip, Typography } from "antd";
import { MinusOutlined, PlusOutlined, StarFilled, StarOutlined } from "@ant-design/icons";

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
      width: 168,
      fixed: "left",
      render: (_, record) => (
        <div className="stock-identity-cell">
          <Text strong ellipsis={{ tooltip: record.stock_name }}>{record.stock_name}</Text>
          <span className="stock-code-line">
            <span>{record.stock_code}</span>
            <span>{record.market}</span>
            {record.in_watchlist ? <StarFilled className="stock-star-active" /> : null}
          </span>
        </div>
      ),
    },
    {
      title: "最新价",
      dataIndex: "price",
      key: "price",
      width: 84,
      align: "right",
      render: (value) => <Text strong className="market-numeric">{numberText(value)}</Text>,
    },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      key: "change_pct",
      width: 86,
      align: "right",
      render: (value) => <Text strong className="market-numeric" style={colorStyle(value)}>{percentText(value)}</Text>,
    },
    {
      title: "活跃度",
      key: "activity",
      width: 142,
      render: (_, record) => (
        <div className="stock-dual-metric">
          <span><small>换手</small><b>{percentText(record.turnover_ratio)}</b></span>
          <span><small>量比</small><b>{numberText(record.volume_ratio)}</b></span>
        </div>
      ),
    },
    {
      title: "估值 / 市值",
      key: "valuation",
      width: 174,
      render: (_, record) => (
        <div className="stock-inline-metrics">
          <span>PE <b>{numberText(record.pe_ratio)}</b></span>
          <span>PB <b>{numberText(record.pb_ratio)}</b></span>
          <span className="stock-cap-value">{capText(record.total_market_value)}</span>
        </div>
      ),
    },
    {
      title: "交易计划",
      key: "plan",
      width: 188,
      render: (_, record) => (
        <div className="stock-plan-cell">
          <Tooltip title="计划买入价"><span>买 <b>{numberText(record.buy_price)}</b></span></Tooltip>
          <Tooltip title="止盈价"><span className="stock-plan-profit">盈 {numberText(record.take_profit_price)}</span></Tooltip>
          <Tooltip title="止损价"><span className="stock-plan-risk">损 {numberText(record.stop_loss_price)}</span></Tooltip>
        </div>
      ),
    },
    {
      title: "距离计划",
      dataIndex: "buy_distance_pct",
      key: "buy_distance_pct",
      width: 96,
      align: "right",
      render: (value) => <Text className="market-numeric" style={colorStyle(value)}>{percentText(value)}</Text>,
    },
    {
      title: "操作",
      key: "actions",
      width: showTradeActions ? 286 : 104,
      fixed: "right",
      render: (_, record) => {
        const quantity = tradeQuantities?.[record.stock_code] ?? record.default_trade_quantity ?? 100;
        return (
          <div className="stock-row-actions">
            {showTradeActions ? (
              <>
                <Button
                  size="small"
                  type="primary"
                  icon={<PlusOutlined />}
                  disabled={!marketOpen}
                  onClick={(event) => {
                    event.stopPropagation();
                    onQuickTrade(record.stock_code, "buy", quantity, `一键买入 ${quantity} 股`);
                  }}
                >买</Button>
                <Button
                  size="small"
                  icon={<MinusOutlined />}
                  disabled={!marketOpen}
                  onClick={(event) => {
                    event.stopPropagation();
                    onQuickTrade(record.stock_code, "sell", quantity, `一键卖出 ${quantity} 股`);
                  }}
                >卖</Button>
                <InputNumber
                  size="small"
                  min={100}
                  step={100}
                  controls={false}
                  value={quantity}
                  onClick={(event) => event.stopPropagation()}
                  onChange={(value) => onTradeQuantityChange(record.stock_code, value)}
                />
              </>
            ) : null}
            <Tooltip title={record.in_watchlist ? "点击移出自选" : "点击加入自选"}>
              <Button
                size="small"
                type="text"
                className={record.in_watchlist ? "stock-watch-button active" : "stock-watch-button"}
                icon={record.in_watchlist ? <StarFilled /> : <StarOutlined />}
                onClick={(event) => {
                  event.stopPropagation();
                  onToggleWatchlist(record);
                }}
              >
                {record.in_watchlist ? "已自选" : "加自选"}
              </Button>
            </Tooltip>
          </div>
        );
      },
    },
  ];

  return (
    <section className="stock-scanner-shell">
      <div className="stock-scanner-toolbar">
        <div className="stock-scanner-title">
          <Text strong>{title}</Text>
          <Tag bordered={false}>{total.toLocaleString()} 只</Tag>
        </div>
        <Space size={6} wrap={false} className="stock-scanner-controls">{controls}</Space>
      </div>
      <Table
        rowKey="stock_code"
        columns={columns}
        dataSource={items}
        loading={loading}
        size="small"
        sticky
        scroll={{ x: 1120, y: "calc(100vh - 420px)" }}
        locale={{ emptyText: title === "我的自选" ? "你还没有加入任何自选股" : "暂无数据" }}
        rowClassName={(record) => record.stock_code === selectedCode ? "stock-row-selected" : ""}
        onRow={(record) => ({ onClick: () => onSelectCode(record.stock_code) })}
        pagination={{
          current: page,
          pageSize,
          total,
          size: "small",
          showSizeChanger: true,
          showQuickJumper: false,
          showTotal: (value, range) => `${range[0]}–${range[1]} / ${value}`,
          pageSizeOptions: [20, 50, 100],
          onChange: onPageChange,
        }}
      />
    </section>
  );
}
