import React from "react";
import {
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Space,
  Statistic,
  Tabs,
  Tag,
  Typography,
} from "antd";

import PaperTradeCard from "./PaperTradeCard";
import { colorStyle, numberText, percentText, trillionText } from "../lib/formatters";

const { Title, Text, Paragraph } = Typography;

export default function DetailPanel({
  activeMenu,
  detail,
  loading,
  form,
  onSave,
  onRemove,
  saving,
  onRunBacktest,
  backtest,
  backtesting,
  paperForm,
  onPaperOrder,
  onSavePlan,
  onQuickTrade,
  paperOrdering,
  planSaving,
  portfolio,
}) {
  const snapshot = detail?.snapshot;
  const recentBars = detail?.daily_bars?.slice(0, 8) ?? [];
  const research = detail?.research ?? {};
  const aiView = research.ai_view ?? {};
  const signals = research.signals ?? {};
  const profile = research.profile ?? {};
  const defaultTradeQuantity = Math.max(100, Number(snapshot?.default_trade_quantity) || 100);
  const [activeTab, setActiveTab] = React.useState(activeMenu === "watch" || activeMenu === "paper" ? "trade" : "research");

  React.useEffect(() => {
    setActiveTab(activeMenu === "watch" || activeMenu === "paper" ? "trade" : "research");
  }, [activeMenu, snapshot?.stock_code]);

  const tradeCard = (
    <PaperTradeCard
      key="trade"
      snapshot={snapshot}
      portfolio={portfolio}
      paperForm={paperForm}
      onPaperOrder={onPaperOrder}
      onSavePlan={onSavePlan}
      onQuickTrade={onQuickTrade}
      paperOrdering={paperOrdering}
      planSaving={planSaving}
    />
  );

  const watchlistCard = (
    <Card key="watchlist" size="small" title="自选设置">
      <Form form={form} layout="vertical">
        <Form.Item label="显示名称" name="display_name">
          <Input placeholder="可选" />
        </Form.Item>
        <Form.Item label="备注" name="notes">
          <Input.TextArea rows={3} placeholder="记录逻辑、催化剂、风险点" />
        </Form.Item>
        <div className="target-grid">
          <Form.Item label="买入价" name="buy_price">
            <Input type="number" placeholder="买入价" />
          </Form.Item>
          <Form.Item label="止盈价" name="take_profit_price">
            <Input type="number" placeholder="止盈价" />
          </Form.Item>
          <Form.Item label="止损价" name="stop_loss_price">
            <Input type="number" placeholder="止损价" />
          </Form.Item>
        </div>
        <Form.Item label="默认交易股数" name="default_trade_quantity">
          <InputNumber min={100} step={100} style={{ width: "100%" }} placeholder="100 / 200 / 500" />
        </Form.Item>
        <Space>
          <Button onClick={onRemove} loading={saving} disabled={!snapshot?.in_watchlist}>
            移除自选
          </Button>
          <Button type="primary" onClick={onSave} loading={saving}>
            保存到自选
          </Button>
        </Space>
      </Form>
    </Card>
  );

  const barsCard = (
    <Card key="bars" size="small" title="最近日线">
      <Space direction="vertical" style={{ width: "100%" }} size={10}>
        {recentBars.length ? (
          recentBars.map((bar) => (
            <div key={bar.trade_date} className="bar-row">
              <div>
                <Text strong>{bar.trade_date}</Text>
                <div>
                  <Text type="secondary">收盘 {numberText(bar.close)}</Text>
                </div>
              </div>
              <Text style={colorStyle(bar.change_pct)}>{percentText(bar.change_pct)}</Text>
            </div>
          ))
        ) : (
          <Text type="secondary">当前还没有这只股票的日线历史。</Text>
        )}
      </Space>
    </Card>
  );

  const researchCard = (
    <Card key="research" size="small" title="单股研究卡">
      <Space direction="vertical" size={14} style={{ width: "100%" }}>
        <div className="research-ai-head">
          <div>
            <Text type="secondary">AI结论</Text>
            <Title level={5} style={{ margin: "4px 0 0" }}>
              {aiView.verdict ?? "--"}
            </Title>
          </div>
          <Space wrap>
            <Tag color="blue">{aiView.style ?? "--"}</Tag>
            <Tag>{aiView.confidence ?? "--"} 置信度</Tag>
          </Space>
        </div>

        <Paragraph style={{ margin: 0 }}>{aiView.summary ?? "还没有生成研究结论。"}</Paragraph>

        <div className="research-section">
          <Text type="secondary">正向信号</Text>
          <Space wrap>
            {(aiView.bull_points ?? []).map((item) => (
              <Tag color="green" key={item}>
                {item}
              </Tag>
            ))}
          </Space>
        </div>

        <div className="research-section">
          <Text type="secondary">风险提示</Text>
          <Space wrap>
            {(aiView.risk_points ?? []).map((item) => (
              <Tag color="red" key={item}>
                {item}
              </Tag>
            ))}
          </Space>
        </div>

        <Descriptions size="small" column={1} colon={false}>
          <Descriptions.Item label="20日均线">{numberText(signals.ma20)}</Descriptions.Item>
          <Descriptions.Item label="60日均线">{numberText(signals.ma60)}</Descriptions.Item>
          <Descriptions.Item label="5日收益">{percentText(signals.return_5d_pct)}</Descriptions.Item>
          <Descriptions.Item label="20日收益">{percentText(signals.return_20d_pct)}</Descriptions.Item>
          <Descriptions.Item label="20日波动">{percentText(signals.volatility_20d)}</Descriptions.Item>
          <Descriptions.Item label="支撑 / 阻力">
            {numberText(signals.support_price)} / {numberText(signals.resistance_price)}
          </Descriptions.Item>
        </Descriptions>
      </Space>
    </Card>
  );

  const profileCard = (
    <Card key="profile" size="small" title="个股资料">
      <Descriptions size="small" column={1} colon={false}>
        <Descriptions.Item label="行业">{profile.industry ?? "--"}</Descriptions.Item>
        <Descriptions.Item label="上市时间">{profile.listing_date ?? "--"}</Descriptions.Item>
        <Descriptions.Item label="总股本">
          {profile.total_share_capital ? `${Number(profile.total_share_capital).toLocaleString()}` : "--"}
        </Descriptions.Item>
        <Descriptions.Item label="流通股">
          {profile.circulating_share_capital ? `${Number(profile.circulating_share_capital).toLocaleString()}` : "--"}
        </Descriptions.Item>
        <Descriptions.Item label="总市值">
          {profile.total_market_value ? trillionText(profile.total_market_value / 100000000) : "--"}
        </Descriptions.Item>
        <Descriptions.Item label="流通市值">
          {profile.circulating_market_value ? trillionText(profile.circulating_market_value / 100000000) : "--"}
        </Descriptions.Item>
      </Descriptions>
    </Card>
  );

  const backtestCard = (
    <Card
      key="backtest"
      size="small"
      title="Backtrader 回测"
      extra={
        <Button size="small" onClick={onRunBacktest} loading={backtesting}>
          运行 SMA 5/20
        </Button>
      }
    >
      {backtest?.status === "ok" ? (
        <Descriptions size="small" column={1} colon={false}>
          <Descriptions.Item label="回测区间">
            {backtest.data_start_date} 至 {backtest.data_end_date}
          </Descriptions.Item>
          <Descriptions.Item label="策略收益">{percentText(backtest.strategy_return_pct)}</Descriptions.Item>
          <Descriptions.Item label="基准收益">{percentText(backtest.benchmark_return_pct)}</Descriptions.Item>
          <Descriptions.Item label="最大回撤">{percentText(-Math.abs(backtest.max_drawdown_pct ?? 0))}</Descriptions.Item>
          <Descriptions.Item label="平仓次数">{backtest.closed_trades ?? 0}</Descriptions.Item>
          <Descriptions.Item label="胜率">{percentText(backtest.win_rate_pct)}</Descriptions.Item>
        </Descriptions>
      ) : (
        <Text type="secondary">点击右上角按钮，用本地日线数据跑一版稳妥的 SMA 5/20 研究回测。</Text>
      )}
    </Card>
  );

  const sectionMap = {
    all: [
      { key: "research", label: "研究卡", children: researchCard },
      { key: "watchlist", label: "自选设置", children: watchlistCard },
      { key: "bars", label: "最近日线", children: barsCard },
      { key: "backtest", label: "回测", children: backtestCard },
      { key: "profile", label: "资料", children: profileCard },
      { key: "trade", label: `交易 ${defaultTradeQuantity}股`, children: tradeCard },
    ],
    watch: [
      { key: "trade", label: `交易 ${defaultTradeQuantity}股`, children: tradeCard },
      { key: "watchlist", label: "自选设置", children: watchlistCard },
      { key: "research", label: "研究卡", children: researchCard },
      { key: "backtest", label: "回测", children: backtestCard },
      { key: "bars", label: "最近日线", children: barsCard },
      { key: "profile", label: "资料", children: profileCard },
    ],
    analysis: [
      { key: "research", label: "研究卡", children: researchCard },
      { key: "trade", label: `交易 ${defaultTradeQuantity}股`, children: tradeCard },
      { key: "backtest", label: "回测", children: backtestCard },
      { key: "watchlist", label: "自选设置", children: watchlistCard },
      { key: "profile", label: "资料", children: profileCard },
      { key: "bars", label: "最近日线", children: barsCard },
    ],
    paper: [
      { key: "trade", label: `交易 ${defaultTradeQuantity}股`, children: tradeCard },
      { key: "research", label: "研究卡", children: researchCard },
      { key: "backtest", label: "回测", children: backtestCard },
      { key: "watchlist", label: "自选设置", children: watchlistCard },
      { key: "profile", label: "资料", children: profileCard },
      { key: "bars", label: "最近日线", children: barsCard },
    ],
  };

  return (
    <Card bordered={false} className="detail-card" loading={loading}>
      {!snapshot ? (
        <div className="detail-placeholder">选择一只股票查看详情</div>
      ) : (
        <Space direction="vertical" size={18} style={{ width: "100%" }}>
          <div className="detail-head">
            <div>
              <Title level={4} style={{ margin: 0 }}>
                {snapshot.stock_name}
              </Title>
              <Text type="secondary">
                {snapshot.stock_code} · {snapshot.market}
              </Text>
            </div>
            <Tag color={Number(snapshot.change_pct) >= 0 ? "red" : "green"}>
              {percentText(snapshot.change_pct)}
            </Tag>
          </div>

          <div className="detail-metric-grid">
            <Card size="small">
              <Statistic title="现价" value={snapshot.price} precision={2} />
            </Card>
            <Card size="small">
              <Statistic title="换手率" value={snapshot.turnover_ratio} precision={2} suffix="%" />
            </Card>
            <Card size="small">
              <Statistic title="量比" value={snapshot.volume_ratio} precision={2} />
            </Card>
            <Card size="small">
              <Statistic title="总市值" value={snapshot.total_market_value} precision={2} suffix="亿" />
            </Card>
          </div>

          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={sectionMap[activeMenu] ?? []}
            size="small"
            className="detail-tabs"
          />
        </Space>
      )}
    </Card>
  );
}
