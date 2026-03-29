import React from "react";
import { Card, Empty, Segmented, Space, Spin, Tag, Typography } from "antd";
import { createChart, CandlestickSeries, HistogramSeries, LineSeries, LineStyle } from "lightweight-charts";

import { request } from "../lib/api";
import { colorStyle, numberText, percentText } from "../lib/formatters";

const { Text } = Typography;

const INTERVAL_OPTIONS = [
  { label: "日K", value: "day", limit: 240 },
  { label: "60分", value: "60m", limit: 240 },
  { label: "30分", value: "30m", limit: 240 },
  { label: "15分", value: "15m", limit: 240 },
];

function toUnixSeconds(value) {
  if (!value) return null;
  const text = String(value).trim();
  const iso = text.includes(" ")
    ? `${text.replace(" ", "T")}:00+08:00`
    : `${text}T00:00:00+08:00`;
  const timestamp = Date.parse(iso);
  if (Number.isNaN(timestamp)) return null;
  return Math.floor(timestamp / 1000);
}

function sma(items, period) {
  const result = [];
  let sum = 0;
  for (let index = 0; index < items.length; index += 1) {
    const close = Number(items[index]?.close ?? 0);
    sum += close;
    if (index >= period) {
      sum -= Number(items[index - period]?.close ?? 0);
    }
    if (index >= period - 1) {
      result.push({
        time: toUnixSeconds(items[index].time),
        value: Number((sum / period).toFixed(2)),
      });
    }
  }
  return result;
}

function buildPriceLines(series, snapshot) {
  if (!series || !snapshot) return [];
  const configs = [
    { price: snapshot.buy_price, color: "#1677ff", title: "买入" },
    { price: snapshot.take_profit_price, color: "#ef5350", title: "止盈" },
    { price: snapshot.stop_loss_price, color: "#26a69a", title: "止损" },
    { price: snapshot.paper_avg_cost, color: "#722ed1", title: "持仓成本" },
  ];
  return configs
    .filter((item) => Number(item.price) > 0)
    .map((item) =>
      series.createPriceLine({
        price: Number(item.price),
        color: item.color,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: item.title,
      })
    );
}

export default function StockKLinePanel({ stockCode, snapshot }) {
  const [interval, setInterval] = React.useState("day");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [payload, setPayload] = React.useState(null);
  const containerRef = React.useRef(null);

  React.useEffect(() => {
    setInterval("day");
  }, [stockCode]);

  React.useEffect(() => {
    if (!stockCode) {
      setPayload(null);
      return;
    }
    const option = INTERVAL_OPTIONS.find((item) => item.value === interval) ?? INTERVAL_OPTIONS[0];
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");
      try {
        const data = await request(
          `/api/stocks/${stockCode}/kline?interval=${option.value}&adjust=qfq&limit=${option.limit}`
        );
        if (!cancelled) {
          setPayload(data);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError.message || "K线加载失败");
          setPayload(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [interval, stockCode]);

  React.useEffect(() => {
    const node = containerRef.current;
    const items = payload?.items ?? [];
    if (!node || !items.length) return undefined;

    const chart = createChart(node, {
      width: node.clientWidth || 320,
      height: 320,
      layout: {
        background: { color: "#ffffff" },
        textColor: "#475569",
      },
      grid: {
        vertLines: { color: "#eef2f7" },
        horzLines: { color: "#eef2f7" },
      },
      rightPriceScale: {
        borderColor: "#e2e8f0",
      },
      timeScale: {
        borderColor: "#e2e8f0",
        timeVisible: interval !== "day",
        secondsVisible: false,
      },
      crosshair: {
        vertLine: { color: "#94a3b8" },
        horzLine: { color: "#94a3b8" },
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#ef5350",
      downColor: "#26a69a",
      borderUpColor: "#ef5350",
      borderDownColor: "#26a69a",
      wickUpColor: "#ef5350",
      wickDownColor: "#26a69a",
      priceLineVisible: false,
    });
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceScaleId: "volume",
      priceFormat: { type: "volume" },
      lastValueVisible: false,
      priceLineVisible: false,
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.72, bottom: 0 },
      borderVisible: false,
    });

    const ma5Series = chart.addSeries(LineSeries, { color: "#1677ff", lineWidth: 1, priceLineVisible: false });
    const ma10Series = chart.addSeries(LineSeries, { color: "#722ed1", lineWidth: 1, priceLineVisible: false });
    const ma20Series = chart.addSeries(LineSeries, { color: "#fa8c16", lineWidth: 1, priceLineVisible: false });

    const candles = items
      .map((item) => ({
        time: toUnixSeconds(item.time),
        open: Number(item.open),
        high: Number(item.high),
        low: Number(item.low),
        close: Number(item.close),
      }))
      .filter((item) => item.time && Number.isFinite(item.open) && Number.isFinite(item.close));

    const volumes = items
      .map((item) => ({
        time: toUnixSeconds(item.time),
        value: Number(item.volume ?? 0),
        color: Number(item.close) >= Number(item.open) ? "rgba(239,83,80,0.35)" : "rgba(38,166,154,0.35)",
      }))
      .filter((item) => item.time);

    candleSeries.setData(candles);
    volumeSeries.setData(volumes);
    ma5Series.setData(sma(items, 5));
    ma10Series.setData(sma(items, 10));
    ma20Series.setData(sma(items, 20));
    const priceLines = buildPriceLines(candleSeries, snapshot);

    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect?.width ?? node.clientWidth;
      chart.applyOptions({ width });
      chart.timeScale().fitContent();
    });
    resizeObserver.observe(node);

    return () => {
      priceLines.forEach((line) => {
        try {
          candleSeries.removePriceLine(line);
        } catch {
          // ignore cleanup race
        }
      });
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [interval, payload, snapshot]);

  const latest = payload?.latest;
  const activeInterval = INTERVAL_OPTIONS.find((item) => item.value === interval)?.label ?? "日K";
  const levelItems = [
    { label: "买入位", value: snapshot?.buy_price, tone: "buy" },
    { label: "止盈位", value: snapshot?.take_profit_price, tone: "sell" },
    { label: "止损位", value: snapshot?.stop_loss_price, tone: "risk" },
    { label: "持仓成本", value: snapshot?.paper_avg_cost, tone: "hold" },
  ].filter((item) => Number(item.value) > 0);
  const quickSignalItems = [
    { label: "现价", value: numberText(snapshot?.price, 2), tone: snapshot?.change_pct },
    { label: "涨跌幅", value: percentText(snapshot?.change_pct), tone: snapshot?.change_pct },
    { label: "换手率", value: percentText(snapshot?.turnover_ratio), tone: snapshot?.turnover_ratio },
    { label: "量比", value: numberText(snapshot?.volume_ratio, 2), tone: Number(snapshot?.volume_ratio ?? 0) >= 1 ? 1 : -1 },
  ];

  return (
    <Card
      size="small"
      title="K线终端"
      extra={
        <Space size={6} wrap>
          <Tag color="blue">{activeInterval}</Tag>
          <Tag>前复权</Tag>
          <Tag>{payload?.stock_name ?? snapshot?.stock_name ?? "--"}</Tag>
        </Space>
      }
    >
      <div className="kline-panel">
        <div className="kline-toolbar">
          <Segmented
            size="small"
            options={INTERVAL_OPTIONS.map((item) => ({ label: item.label, value: item.value }))}
            value={interval}
            onChange={setInterval}
          />
          <div className="kline-legend-strip">
            <span className="kline-legend-item kline-legend-item-ma5">MA5</span>
            <span className="kline-legend-item kline-legend-item-ma10">MA10</span>
            <span className="kline-legend-item kline-legend-item-ma20">MA20</span>
          </div>
        </div>

        <div className="kline-workspace">
          <div className="kline-main-stage">
            {latest ? (
              <div className="kline-meta-strip">
                <span>
                  <Text type="secondary">时间</Text> {latest.time}
                </span>
                <span>
                  <Text type="secondary">开</Text> {numberText(latest.open)}
                </span>
                <span>
                  <Text type="secondary">高</Text> {numberText(latest.high)}
                </span>
                <span>
                  <Text type="secondary">低</Text> {numberText(latest.low)}
                </span>
                <span>
                  <Text type="secondary">收</Text> {numberText(latest.close)}
                </span>
                <span style={colorStyle(latest.change_pct)}>
                  <Text type="secondary">涨跌</Text> {percentText(latest.change_pct)}
                </span>
                <span>
                  <Text type="secondary">换手</Text> {percentText(latest.turnover_ratio)}
                </span>
              </div>
            ) : null}

            <Spin spinning={loading}>
              {error ? (
                <div className="detail-placeholder">{error}</div>
              ) : payload?.items?.length ? (
                <div ref={containerRef} className="kline-chart-canvas" />
              ) : (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无K线数据" />
              )}
            </Spin>
          </div>

          <aside className="kline-side-panel">
            <div className="kline-side-section">
              <div className="kline-side-head">
                <Text strong>快速信号</Text>
                <Tag color={Number(snapshot?.change_pct) >= 0 ? "red" : "green"}>
                  {percentText(snapshot?.change_pct)}
                </Tag>
              </div>
              <div className="kline-side-grid">
                {quickSignalItems.map((item) => (
                  <div key={item.label} className="kline-side-metric">
                    <Text type="secondary">{item.label}</Text>
                    <Text strong style={colorStyle(item.tone)}>
                      {item.value}
                    </Text>
                  </div>
                ))}
              </div>
            </div>

            <div className="kline-side-section">
              <div className="kline-side-head">
                <Text strong>交易位</Text>
                <Text type="secondary">{snapshot?.default_trade_quantity || 100} 股</Text>
              </div>
              {levelItems.length ? (
                <div className="kline-level-list">
                  {levelItems.map((item) => (
                    <div key={item.label} className={`kline-level-row kline-level-row-${item.tone}`}>
                      <Text>{item.label}</Text>
                      <Text strong>{numberText(item.value, 2)}</Text>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="kline-empty-note">还没有设置买入、止盈、止损或持仓成本。</div>
              )}
            </div>

            <div className="kline-side-section">
              <div className="kline-side-head">
                <Text strong>最新K线摘要</Text>
                <Text type="secondary">{activeInterval}</Text>
              </div>
              {latest ? (
                <div className="kline-summary-list">
                  <div className="kline-summary-row">
                    <span>成交量</span>
                    <strong>{numberText(latest.volume, 0)}</strong>
                  </div>
                  <div className="kline-summary-row">
                    <span>成交额</span>
                    <strong>{numberText(latest.amount, 0)}</strong>
                  </div>
                  <div className="kline-summary-row">
                    <span>振幅</span>
                    <strong>{percentText(latest.amplitude_pct)}</strong>
                  </div>
                  <div className="kline-summary-row">
                    <span>涨跌额</span>
                    <strong style={colorStyle(latest.change_amount)}>{numberText(latest.change_amount, 2)}</strong>
                  </div>
                </div>
              ) : (
                <div className="kline-empty-note">暂无摘要数据。</div>
              )}
            </div>
          </aside>
        </div>
      </div>
    </Card>
  );
}
