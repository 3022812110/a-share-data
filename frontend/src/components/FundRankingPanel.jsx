import React from "react";
import { Alert, Badge, Button, Card, Input, Segmented, Select, Space, Table, Tooltip, Typography } from "antd";
import { ReloadOutlined, StarFilled, StarOutlined } from "@ant-design/icons";

import { request } from "../lib/api";
import { colorStyle, numberText, percentText } from "../lib/formatters";
import CompactEmpty from "./CompactEmpty";

const { Text } = Typography;

const PERIODS = [
  { value: "1d", label: "1日多空" },
  { value: "3d", label: "3日多空" },
  { value: "13d", label: "13日趋势" },
];

const SORT_OPTIONS = [
  { value: "net_inflow_yi", label: "多空资金" },
  { value: "change_pct", label: "涨幅" },
  { value: "opening_pct", label: "开幅" },
  { value: "turnover_ratio", label: "换手率" },
  { value: "price", label: "最新价" },
];

function fundText(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "--";
  return `${numeric > 0 ? "+" : ""}${numeric.toFixed(2)}亿`;
}

export default function FundRankingPanel({ onSelectCode, onToggleWatchlist }) {
  const [period, setPeriod] = React.useState("1d");
  const [payload, setPayload] = React.useState({ items: [] });
  const [loading, setLoading] = React.useState(false);
  const [keyword, setKeyword] = React.useState("");
  const [sortBy, setSortBy] = React.useState("net_inflow_yi");
  const [sortOrder, setSortOrder] = React.useState("desc");

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await request(`/api/fund-ranking?period=${period}&limit=300`);
      setPayload(data);
    } finally {
      setLoading(false);
    }
  }, [period]);

  React.useEffect(() => {
    load().catch(() => setPayload({ items: [] }));
  }, [load]);

  const rows = React.useMemo(() => {
    const query = keyword.trim().toLowerCase();
    const filtered = (payload.items ?? []).filter((item) => (
      !query
      || String(item.stock_code ?? "").toLowerCase().includes(query)
      || String(item.stock_name ?? "").toLowerCase().includes(query)
    ));
    return [...filtered].sort((left, right) => {
      const a = Number(left?.[sortBy]);
      const b = Number(right?.[sortBy]);
      const leftValue = Number.isFinite(a) ? a : Number.NEGATIVE_INFINITY;
      const rightValue = Number.isFinite(b) ? b : Number.NEGATIVE_INFINITY;
      return sortOrder === "asc" ? leftValue - rightValue : rightValue - leftValue;
    });
  }, [keyword, payload.items, sortBy, sortOrder]);

  const columns = [
    {
      title: "排名",
      dataIndex: "rank",
      width: 56,
      align: "center",
      render: (value) => <Text type="secondary" className="fund-rank-number">{value}</Text>,
    },
    {
      title: "股票",
      key: "stock",
      width: 190,
      render: (_, record) => (
        <div className="fund-stock-cell">
          <Text strong>{record.stock_name}</Text>
          <Text type="secondary">{record.stock_code} · {record.market}</Text>
        </div>
      ),
    },
    {
      title: "最新价",
      dataIndex: "price",
      width: 100,
      align: "right",
      render: (value) => <Text strong className="market-numeric">{numberText(value)}</Text>,
    },
    {
      title: "开幅",
      dataIndex: "opening_pct",
      width: 100,
      align: "right",
      render: (value) => <Text strong style={colorStyle(value)}>{percentText(value)}</Text>,
    },
    {
      title: "涨幅",
      dataIndex: "change_pct",
      width: 100,
      align: "right",
      render: (value) => <Text strong style={colorStyle(value)}>{percentText(value)}</Text>,
    },
    {
      title: payload.label ?? "多空资金",
      dataIndex: "net_inflow_yi",
      width: 160,
      align: "right",
      render: (value, record) => (
        <Space size={7}>
          <Badge color={record.direction === "long" ? "#ff3b30" : "#34c759"} />
          <Text strong className="market-numeric" style={colorStyle(value)}>{fundText(value)}</Text>
        </Space>
      ),
    },
    {
      title: "资金占比",
      dataIndex: "net_inflow_pct",
      width: 108,
      align: "right",
      render: (value) => <Text style={colorStyle(value)}>{percentText(value)}</Text>,
    },
    {
      title: "换手率",
      dataIndex: "turnover_ratio",
      width: 96,
      align: "right",
      render: (value) => <Text>{percentText(value)}</Text>,
    },
    {
      title: "操作",
      key: "action",
      width: 112,
      fixed: "right",
      render: (_, record) => (
        <Tooltip title={record.in_watchlist ? "点击移出自选" : "点击加入自选"}>
          <Button
            size="small"
            type="text"
            className={record.in_watchlist ? "fund-watch-button active" : "fund-watch-button"}
            icon={record.in_watchlist ? <StarFilled /> : <StarOutlined />}
            onClick={async (event) => {
              event.stopPropagation();
              await onToggleWatchlist(record);
              await load();
            }}
          >
            {record.in_watchlist ? "已自选" : "加自选"}
          </Button>
        </Tooltip>
      ),
    },
  ];

  return (
    <section className="fund-ranking-shell">
      <Card variant="borderless" className="fund-ranking-card">
        <div className="fund-ranking-header">
          <div>
            <Typography.Title level={4}>资金榜</Typography.Title>
            <Text type="secondary">观察多空资金持续性，同时对比价格开幅与涨幅</Text>
          </div>
          <Space size={7} wrap>
            <Segmented value={period} options={PERIODS} onChange={setPeriod} />
            <Input.Search allowClear placeholder="代码或名称" value={keyword} onChange={(event) => setKeyword(event.target.value)} />
            <Select value={sortBy} options={SORT_OPTIONS} onChange={setSortBy} />
            <Select
              value={sortOrder}
              options={[{ value: "desc", label: "从高到低" }, { value: "asc", label: "从低到高" }]}
              onChange={setSortOrder}
            />
            <Button icon={<ReloadOutlined />} onClick={() => load().catch(() => {})} loading={loading}>刷新</Button>
          </Space>
        </div>

        {payload.note ? (
          <Alert
            type="info"
            showIcon={payload.is_proxy}
            className="fund-ranking-note"
            message={payload.note}
            action={<Text type="secondary">更新 {String(payload.fetched_at ?? "--").replace("T", " ")}</Text>}
          />
        ) : null}

        <Table
          rowKey="stock_code"
          className="fund-ranking-table"
          columns={columns}
          dataSource={rows}
          loading={loading}
          size="small"
          sticky
          scroll={{ x: 1080, y: "calc(100vh - 250px)" }}
          pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: [30, 50, 100] }}
          locale={{ emptyText: <CompactEmpty description="当前资金榜暂无可用数据" /> }}
          onRow={(record) => ({ onClick: () => onSelectCode(record.stock_code) })}
        />
      </Card>
    </section>
  );
}
