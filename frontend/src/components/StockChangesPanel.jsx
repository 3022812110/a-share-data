import React from "react";
import {
  Alert,
  Button,
  Card,
  Input,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
} from "antd";
import { ReloadOutlined } from "@ant-design/icons";

import { request } from "../lib/api";
import { colorStyle, numberText, percentText } from "../lib/formatters";

const { Text } = Typography;

const REFRESH_OPTIONS = [
  { value: 10, label: "10秒" },
  { value: 30, label: "30秒" },
  { value: 60, label: "60秒" },
];

const DIRECTION_OPTIONS = [
  { value: "all", label: "全部方向" },
  { value: "bullish", label: "上涨异动" },
  { value: "bearish", label: "下跌异动" },
  { value: "neutral", label: "中性异动" },
];

function compactNumber(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric === 0) return "--";
  if (Math.abs(numeric) >= 100000000) return `${(numeric / 100000000).toFixed(2)}亿`;
  if (Math.abs(numeric) >= 10000) return `${(numeric / 10000).toFixed(2)}万`;
  return numberText(numeric, 0);
}

function directionLabel(direction) {
  if (direction === "bullish") return "上涨";
  if (direction === "bearish") return "下跌";
  return "中性";
}

function directionColor(direction) {
  if (direction === "bullish") return "red";
  if (direction === "bearish") return "green";
  return "blue";
}

function buildQuery(params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    query.set(key, String(value));
  });
  return query.toString();
}

export default function StockChangesPanel({ onSelectCode }) {
  const [typePayload, setTypePayload] = React.useState({ all: [], bullish: [], bearish: [] });
  const [selectedTypes, setSelectedTypes] = React.useState([]);
  const [liveRows, setLiveRows] = React.useState([]);
  const [liveMeta, setLiveMeta] = React.useState({});
  const [liveLoading, setLiveLoading] = React.useState(false);
  const [historyRows, setHistoryRows] = React.useState([]);
  const [historyMeta, setHistoryMeta] = React.useState({ total: 0, page: 1, page_size: 80, summary: {} });
  const [historyLoading, setHistoryLoading] = React.useState(false);
  const [historyPage, setHistoryPage] = React.useState(1);
  const [historyPageSize, setHistoryPageSize] = React.useState(80);
  const [keyword, setKeyword] = React.useState("");
  const [direction, setDirection] = React.useState("all");
  const [autoRefresh, setAutoRefresh] = React.useState(true);
  const [refreshSeconds, setRefreshSeconds] = React.useState(30);

  React.useEffect(() => {
    let cancelled = false;
    request("/api/stock-changes/types")
      .then((data) => {
        if (cancelled) return;
        setTypePayload(data);
        setSelectedTypes((data.all ?? []).map((item) => item.value));
      })
      .catch(() => {
        if (!cancelled) setTypePayload({ all: [], bullish: [], bearish: [] });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedTypeText = selectedTypes.join(",");

  const loadLive = React.useCallback(async () => {
    setLiveLoading(true);
    try {
      const query = buildQuery({
        page: 1,
        page_size: 120,
        change_types: selectedTypeText,
        persist: true,
      });
      const data = await request(`/api/stock-changes?${query}`);
      setLiveRows(data.items ?? []);
      setLiveMeta(data);
    } finally {
      setLiveLoading(false);
    }
  }, [selectedTypeText]);

  const loadHistory = React.useCallback(async () => {
    setHistoryLoading(true);
    try {
      const query = buildQuery({
        page: historyPage,
        page_size: historyPageSize,
        keyword,
        direction,
        change_types: selectedTypeText,
      });
      const data = await request(`/api/stock-changes/history?${query}`);
      setHistoryRows(data.items ?? []);
      setHistoryMeta(data);
    } finally {
      setHistoryLoading(false);
    }
  }, [direction, historyPage, historyPageSize, keyword, selectedTypeText]);

  React.useEffect(() => {
    if (!selectedTypes.length) return;
    loadLive().catch(() => {});
  }, [loadLive, selectedTypes.length]);

  React.useEffect(() => {
    if (!selectedTypes.length) return;
    loadHistory().catch(() => {});
  }, [loadHistory, selectedTypes.length]);

  React.useEffect(() => {
    if (!autoRefresh || !selectedTypes.length) return undefined;
    const timer = window.setInterval(() => {
      loadLive().catch(() => {});
    }, refreshSeconds * 1000);
    return () => window.clearInterval(timer);
  }, [autoRefresh, loadLive, refreshSeconds, selectedTypes.length]);

  const typeOptions = (typePayload.all ?? []).map((item) => ({
    value: item.value,
    label: item.label,
  }));

  const summary = historyMeta.summary ?? {};
  const liveBullish = liveRows.filter((item) => item.direction === "bullish").length;
  const liveBearish = liveRows.filter((item) => item.direction === "bearish").length;

  const columns = [
    {
      title: "时间",
      key: "time",
      width: 130,
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text strong>{record.event_time ?? "--"}</Text>
          <Text type="secondary">{record.trade_date ?? liveMeta.trade_date ?? "--"}</Text>
        </Space>
      ),
    },
    {
      title: "股票",
      key: "stock",
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text strong>{record.stock_name || record.stock_code}</Text>
          <Space size={6}>
            <Text code>{record.stock_code}</Text>
            {record.market ? <Text type="secondary">{record.market}</Text> : null}
          </Space>
        </Space>
      ),
    },
    {
      title: "异动",
      key: "change",
      render: (_, record) => (
        <Space direction="vertical" size={4}>
          <Space size={6} wrap>
            <Tag color={directionColor(record.direction)}>{record.type_name}</Tag>
            <Tag bordered={false}>{directionLabel(record.direction)}</Tag>
          </Space>
          <Text type="secondary">类型 {record.change_type}</Text>
        </Space>
      ),
    },
    {
      title: "价格",
      key: "price",
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text strong>{numberText(record.price, 2)}</Text>
          <Text style={colorStyle(record.change_pct)}>{percentText(record.change_pct)}</Text>
        </Space>
      ),
    },
    {
      title: "量额",
      key: "volume",
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text>量 {compactNumber(record.volume)}</Text>
          <Text type="secondary">额 {compactNumber(record.amount)}</Text>
        </Space>
      ),
    },
    {
      title: "操作",
      key: "action",
      width: 96,
      render: (_, record) => (
        <Button
          size="small"
          onClick={(event) => {
            event.stopPropagation();
            onSelectCode?.(record.stock_code);
          }}
        >
          详情
        </Button>
      ),
    },
  ];

  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      <Card bordered={false} className="stock-changes-hero">
        <div className="stock-changes-head">
          <div>
            <Text className="stock-changes-eyebrow">INTRADAY SIGNALS</Text>
            <Typography.Title level={4} style={{ margin: "2px 0 0" }}>
              盘中异动雷达
            </Typography.Title>
            <Text type="secondary">
              实时抓取东方财富盘中异动，并写入本地历史表，后续用于预警、复盘和 AI 研究。
            </Text>
          </div>
          <Space wrap>
            <Tag color="red">上涨 {liveBullish}</Tag>
            <Tag color="green">下跌 {liveBearish}</Tag>
            <Tag>本次入库 {liveMeta.saved_count ?? 0}</Tag>
            <Tag>{liveMeta.fetched_at ?? "--"}</Tag>
          </Space>
        </div>
      </Card>

      <Card bordered={false} className="table-card" title="实时监控">
        <Space direction="vertical" size={10} style={{ width: "100%" }}>
          <div className="stock-changes-toolbar">
            <Space wrap>
              <Select
                mode="multiple"
                allowClear
                maxTagCount="responsive"
                value={selectedTypes}
                options={typeOptions}
                onChange={setSelectedTypes}
                placeholder="选择异动类型"
                style={{ minWidth: 320 }}
              />
              <Button onClick={() => setSelectedTypes((typePayload.all ?? []).map((item) => item.value))}>
                全部
              </Button>
              <Button onClick={() => setSelectedTypes((typePayload.bullish ?? []).map((item) => item.value))}>
                上涨型
              </Button>
              <Button onClick={() => setSelectedTypes((typePayload.bearish ?? []).map((item) => item.value))}>
                下跌型
              </Button>
            </Space>
            <Space wrap>
              <Text type="secondary">自动刷新</Text>
              <Switch checked={autoRefresh} onChange={setAutoRefresh} />
              <Select
                value={refreshSeconds}
                options={REFRESH_OPTIONS}
                onChange={setRefreshSeconds}
                style={{ width: 90 }}
              />
              <Button icon={<ReloadOutlined />} onClick={() => loadLive().catch(() => {})} loading={liveLoading}>
                刷新
              </Button>
            </Space>
          </div>
          {!selectedTypes.length ? (
            <Alert showIcon type="warning" message="至少选择一个异动类型。" />
          ) : null}
          <Table
            rowKey={(record) => record.event_key ?? `${record.trade_date}-${record.event_time}-${record.stock_code}-${record.change_type}`}
            columns={columns}
            dataSource={liveRows}
            loading={liveLoading}
            size="small"
            scroll={{ y: 420 }}
            pagination={false}
            onRow={(record) => ({ onClick: () => onSelectCode?.(record.stock_code) })}
          />
        </Space>
      </Card>

      <Card
        bordered={false}
        className="table-card"
        title="异动历史"
        extra={
          <Space wrap>
            <Tag color="red">上涨 {summary.bullish ?? 0}</Tag>
            <Tag color="green">下跌 {summary.bearish ?? 0}</Tag>
            <Tag>总计 {historyMeta.total ?? 0}</Tag>
          </Space>
        }
      >
        <Space direction="vertical" size={10} style={{ width: "100%" }}>
          <div className="stock-changes-toolbar">
            <Space wrap>
              <Input.Search
                allowClear
                placeholder="搜索代码、名称或异动类型"
                style={{ width: 260 }}
                onSearch={(value) => {
                  setHistoryPage(1);
                  setKeyword(value);
                }}
              />
              <Select
                value={direction}
                options={DIRECTION_OPTIONS}
                onChange={(value) => {
                  setHistoryPage(1);
                  setDirection(value);
                }}
                style={{ width: 120 }}
              />
            </Space>
            <Button onClick={() => loadHistory().catch(() => {})} loading={historyLoading}>
              查询
            </Button>
          </div>
          <Table
            rowKey="id"
            columns={columns}
            dataSource={historyRows}
            loading={historyLoading}
            size="small"
            scroll={{ y: 520 }}
            onRow={(record) => ({ onClick: () => onSelectCode?.(record.stock_code) })}
            pagination={{
              current: historyPage,
              pageSize: historyPageSize,
              total: historyMeta.total ?? 0,
              showSizeChanger: true,
              pageSizeOptions: [50, 80, 120, 200],
              onChange: (nextPage, nextSize) => {
                setHistoryPage(nextPage);
                setHistoryPageSize(nextSize);
              },
            }}
          />
        </Space>
      </Card>
    </Space>
  );
}
