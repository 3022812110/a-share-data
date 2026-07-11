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

function emaValues(values, period) {
  if (!values.length) return [];
  const multiplier = 2 / (period + 1);
  const result = [values[0]];
  for (let index = 1; index < values.length; index += 1) {
    result.push(values[index] * multiplier + result[index - 1] * (1 - multiplier));
  }
  return result;
}

function calculateTechnicalSignals(items) {
  const closes = items.map((item) => Number(item.close)).filter(Number.isFinite);
  if (closes.length < 26) return null;

  const ema12 = emaValues(closes, 12);
  const ema26 = emaValues(closes, 26);
  const macdSeries = closes.map((_, index) => ema12[index] - ema26[index]);
  const signalSeries = emaValues(macdSeries, 9);
  const macd = macdSeries.at(-1);
  const signal = signalSeries.at(-1);
  const histogram = (macd - signal) * 2;

  let gains = 0;
  let losses = 0;
  const rsiWindow = closes.slice(-15);
  for (let index = 1; index < rsiWindow.length; index += 1) {
    const change = rsiWindow[index] - rsiWindow[index - 1];
    if (change >= 0) gains += change;
    else losses += Math.abs(change);
  }
  const averageGain = gains / 14;
  const averageLoss = losses / 14;
  const rsi = averageLoss === 0 ? 100 : 100 - 100 / (1 + averageGain / averageLoss);

  const bollWindow = closes.slice(-20);
  const middle = bollWindow.reduce((sum, value) => sum + value, 0) / bollWindow.length;
  const variance = bollWindow.reduce((sum, value) => sum + (value - middle) ** 2, 0) / bollWindow.length;
  const deviation = Math.sqrt(variance);
  const upper = middle + deviation * 2;
  const lower = middle - deviation * 2;
  const latestClose = closes.at(-1);

  const positiveSignals = [macd > signal, latestClose > middle, rsi >= 45 && rsi <= 70].filter(Boolean).length;
  const verdict = positiveSignals >= 3 ? "偏强" : positiveSignals <= 1 ? "偏弱" : "震荡";
  const tone = verdict === "偏强" ? "red" : verdict === "偏弱" ? "green" : "gold";

  return {
    rsi,
    macd,
    signal,
    histogram,
    middle,
    upper,
    lower,
    latestClose,
    verdict,
    tone,
  };
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
  const technicalSignals = React.useMemo(
    () => calculateTechnicalSignals(payload?.items ?? []),
    [payload]
  );
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
                <Text strong style={colorStyle(snapshot?.change_pct)}>
                  {percentText(snapshot?.change_pct)}
                </Text>
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
                <Text strong>技术指标雷达</Text>
                {technicalSignals ? <Tag color={technicalSignals.tone}>{technicalSignals.verdict}</Tag> : null}
              </div>
              {technicalSignals ? (
                <div className="technical-signal-list">
                  <div className="kline-summary-row">
                    <span>RSI 14</span>
                    <strong style={colorStyle(technicalSignals.rsi > 70 ? -1 : technicalSignals.rsi < 30 ? 1 : 0)}>
                      {numberText(technicalSignals.rsi, 1)}
                    </strong>
                  </div>
                  <div className="kline-summary-row">
                    <span>MACD</span>
                    <strong style={colorStyle(technicalSignals.histogram)}>
                      {numberText(technicalSignals.macd, 3)}
                    </strong>
                  </div>
                  <div className="kline-summary-row">
                    <span>信号线</span>
                    <strong>{numberText(technicalSignals.signal, 3)}</strong>
                  </div>
                  <div className="kline-summary-row">
                    <span>BOLL 中轨</span>
                    <strong>{numberText(technicalSignals.middle, 2)}</strong>
                  </div>
                  <div className="technical-boll-band">
                    <Text type="secondary">下 {numberText(technicalSignals.lower, 2)}</Text>
                    <span className="technical-boll-track">
                      <span
                        className="technical-boll-marker"
                        style={{
                          left: `${Math.max(
                            0,
                            Math.min(
                              100,
                              ((technicalSignals.latestClose - technicalSignals.lower) /
                                Math.max(technicalSignals.upper - technicalSignals.lower, 0.01)) *
                                100
                            )
                          )}%`,
                        }}
                      />
                    </span>
                    <Text type="secondary">上 {numberText(technicalSignals.upper, 2)}</Text>
                  </div>
                </div>
              ) : (
                <div className="kline-empty-note">至少需要 26 根 K 线才能计算指标。</div>
              )}
            </div>
          </aside>
        </div>
      </div>
    </Card>
  );
}
