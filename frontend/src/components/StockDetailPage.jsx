import React from "react";
import { Button, Card, Space, Tag, Typography } from "antd";
import { ArrowLeftOutlined, ReloadOutlined } from "@ant-design/icons";

import DetailPanel from "./DetailPanel";
import { colorStyle, numberText, percentText } from "../lib/formatters";

const { Text } = Typography;

export default function StockDetailPage({
  activeMenu,
  detail,
  loading,
  onBack,
  onRefresh,
  refreshing,
  ...detailPanelProps
}) {
  const snapshot = detail?.snapshot;
  const research = detail?.research ?? {};
  const signals = research.signals ?? {};
  const aiView = research.ai_view ?? {};
  const heroMetrics = snapshot
    ? [
        { label: "现价", value: numberText(snapshot.price, 2), tone: snapshot.change_pct },
        { label: "涨跌幅", value: percentText(snapshot.change_pct), tone: snapshot.change_pct },
        { label: "换手率", value: percentText(snapshot.turnover_ratio), tone: snapshot.turnover_ratio },
        { label: "量比", value: numberText(snapshot.volume_ratio, 2), tone: snapshot.volume_ratio >= 1 ? 1 : -1 },
        { label: "总市值", value: `${numberText(snapshot.total_market_value, 2)} 亿` },
        { label: "20日收益", value: percentText(signals.return_20d_pct), tone: signals.return_20d_pct },
      ]
    : [];

  return (
    <div className="detail-page-shell">
      <Card bordered={false} className="detail-page-header detail-hero-card">
        <div className="detail-page-header-row">
          <Space size={10}>
            <Button icon={<ArrowLeftOutlined />} onClick={onBack}>
              返回列表
            </Button>
            <div>
              <div className="detail-page-title-row">
                <Typography.Title level={4} style={{ margin: 0 }}>
                  {snapshot?.stock_name ?? snapshot?.display_name ?? snapshot?.stock_code ?? "单股详情"}
                </Typography.Title>
                {snapshot ? (
                  <Tag color={Number(snapshot.change_pct) >= 0 ? "red" : "green"}>
                    {percentText(snapshot.change_pct)}
                  </Tag>
                ) : null}
                {snapshot?.in_watchlist ? <Tag color="gold">自选</Tag> : null}
                {aiView?.verdict ? <Tag color="blue">{aiView.verdict}</Tag> : null}
              </div>
              <Text type="secondary">
                {snapshot
                  ? `${snapshot.stock_code} · ${snapshot.market}${research?.profile?.industry ? ` · ${research.profile.industry}` : ""}`
                  : "单股研究与模拟交易"}
              </Text>
            </div>
          </Space>
          <Button icon={<ReloadOutlined />} onClick={onRefresh} loading={refreshing}>
            刷新快照
          </Button>
        </div>

        {snapshot ? (
          <>
            <div className="detail-hero-metrics">
              {heroMetrics.map((item) => (
                <div key={item.label} className="detail-hero-metric">
                  <Text type="secondary">{item.label}</Text>
                  <Text strong style={item.tone !== undefined ? colorStyle(item.tone) : undefined}>
                    {item.value}
                  </Text>
                </div>
              ))}
            </div>

            <div className="detail-hero-subgrid">
              <div className="detail-hero-band">
                <Text type="secondary">交易位</Text>
                <div className="detail-hero-band-values">
                  <span>买入 {numberText(snapshot.buy_price, 2)}</span>
                  <span>止盈 {numberText(snapshot.take_profit_price, 2)}</span>
                  <span>止损 {numberText(snapshot.stop_loss_price, 2)}</span>
                  <span>默认 {snapshot.default_trade_quantity || 100} 股</span>
                </div>
              </div>
              <div className="detail-hero-band">
                <Text type="secondary">研究信号</Text>
                <div className="detail-hero-band-values">
                  <span>MA20 {numberText(signals.ma20, 2)}</span>
                  <span>MA60 {numberText(signals.ma60, 2)}</span>
                  <span>支撑 {numberText(signals.support_price, 2)}</span>
                  <span>阻力 {numberText(signals.resistance_price, 2)}</span>
                </div>
              </div>
            </div>
          </>
        ) : null}
      </Card>

      <DetailPanel activeMenu={activeMenu} detail={detail} loading={loading} {...detailPanelProps} />
    </div>
  );
}
