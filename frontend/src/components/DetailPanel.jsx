import React from "react";
import { Alert, Button, Card, Descriptions, Form, Input, InputNumber, Space, Tabs, Tag, Typography } from "antd";

import PaperTradeCard from "./PaperTradeCard";
import StockKLinePanel from "./StockKLinePanel";
import { capText, colorStyle, numberText, percentText, trillionText } from "../lib/formatters";

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
  function yuanToYiText(value) {
    return value === null || value === undefined || Number.isNaN(Number(value))
      ? "--"
      : capText(Number(value) / 100000000);
  }

  function wanText(value) {
    return value === null || value === undefined || Number.isNaN(Number(value))
      ? "--"
      : `${(Number(value) / 10000).toFixed(2)}万`;
  }

  const snapshot = detail?.snapshot;
  const research = detail?.research ?? {};
  const feeds = detail?.feeds ?? {};
  const aiView = research.ai_view ?? {};
  const signals = research.signals ?? {};
  const profile = research.profile ?? {};
  const capitalFlows = feeds.capital_flows ?? [];
  const longTigerRows = feeds.long_tiger ?? [];
  const concepts = feeds.concepts ?? [];
  const financialReports = feeds.financial_reports ?? [];
  const holderNumbers = feeds.holder_numbers ?? [];
  const latestCapitalFlow = capitalFlows[0] ?? null;
  const latestFinancial = financialReports[0] ?? null;
  const latestHolder = holderNumbers[0] ?? null;
  const defaultTradeQuantity = Math.max(100, Number(snapshot?.default_trade_quantity) || 100);
  const [activeTab, setActiveTab] = React.useState("chart");
  const verdictTone =
    aiView.verdict?.includes("回避") || aiView.verdict?.includes("谨慎")
      ? "risk"
      : aiView.verdict?.includes("观察")
        ? "watch"
        : "bull";
  const catalystItems = [
    concepts.length ? `题材聚焦：${concepts.slice(0, 3).map((item) => item.board_name).join(" / ")}` : null,
    feeds.notices?.[0]?.title
      ? `最新公告：${feeds.notices[0].notice_date ?? "--"} ${feeds.notices[0].title}`
      : null,
    feeds.research_reports?.[0]?.title
      ? `研报跟踪：${feeds.research_reports[0].publish_date ?? "--"} ${feeds.research_reports[0].title}`
      : null,
    latestCapitalFlow && Number(latestCapitalFlow.main_net_inflow) > 0
      ? `主力净流入 ${yuanToYiText(latestCapitalFlow.main_net_inflow)}，净占比 ${percentText(
          latestCapitalFlow.main_net_inflow_pct
        )}`
      : null,
  ]
    .filter(Boolean)
    .slice(0, 4);
  const invalidationItems = [
    Number(signals.support_price) > 0 ? `跌破支撑位 ${numberText(signals.support_price, 2)}` : null,
    Number(snapshot?.stop_loss_price) > 0 ? `跌破自设止损 ${numberText(snapshot.stop_loss_price, 2)}` : null,
    Number(signals.volatility_20d) > 0 ? `20日波动扩大到 ${percentText(signals.volatility_20d)}` : null,
    latestCapitalFlow && Number(latestCapitalFlow.main_net_inflow) < 0
      ? `主力转为净流出 ${yuanToYiText(latestCapitalFlow.main_net_inflow)}`
      : "主力转为持续净流出且量能衰减",
  ]
    .filter(Boolean)
    .slice(0, 4);
  const researchMetrics = [
    { label: "20日均线", value: numberText(signals.ma20) },
    { label: "60日均线", value: numberText(signals.ma60) },
    { label: "5日收益", value: percentText(signals.return_5d_pct), tone: signals.return_5d_pct },
    { label: "20日收益", value: percentText(signals.return_20d_pct), tone: signals.return_20d_pct },
    { label: "20日波动", value: percentText(signals.volatility_20d) },
    {
      label: "支撑 / 阻力",
      value: `${numberText(signals.support_price)} / ${numberText(signals.resistance_price)}`,
    },
  ];

  React.useEffect(() => {
    setActiveTab("chart");
  }, [snapshot?.stock_code]);

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

  const chartCard = <StockKLinePanel key="chart" stockCode={snapshot?.stock_code} snapshot={snapshot} />;

  const researchCard = (
    <Card key="research" size="small" title="单股研究卡">
      <div className="research-workspace">
        <div className={`research-hero research-hero-${verdictTone}`}>
          <div className="research-hero-copy">
            <Text type="secondary">AI结论</Text>
            <Title level={4} style={{ margin: "2px 0 0" }}>
              {aiView.verdict ?? "--"}
            </Title>
            <Paragraph style={{ margin: 0 }}>{aiView.summary ?? "还没有生成研究结论。"}</Paragraph>
          </div>
          <div className="research-hero-side">
            <Tag color="blue">{aiView.style ?? "--"}</Tag>
            <Tag>{aiView.confidence ?? "--"} 置信度</Tag>
          </div>
        </div>

        <div className="research-signal-grid">
          <div className="research-signal-card">
            <Text strong>正向信号</Text>
            <div className="research-chip-wrap">
              {(aiView.bull_points ?? []).length ? (
                (aiView.bull_points ?? []).map((item) => (
                  <Tag color="green" key={item}>
                    {item}
                  </Tag>
                ))
              ) : (
                <Text type="secondary">暂无明显强化信号。</Text>
              )}
            </div>
          </div>

          <div className="research-signal-card">
            <Text strong>风险提示</Text>
            <div className="research-chip-wrap">
              {(aiView.risk_points ?? []).length ? (
                (aiView.risk_points ?? []).map((item) => (
                  <Tag color="red" key={item}>
                    {item}
                  </Tag>
                ))
              ) : (
                <Text type="secondary">暂无明显风险提示。</Text>
              )}
            </div>
          </div>
        </div>

        <div className="research-decision-grid">
          <div className="research-decision-card">
            <Text strong>催化剂</Text>
            <div className="research-bullet-list">
              {catalystItems.length ? (
                catalystItems.map((item) => (
                  <div key={item} className="research-bullet-row">
                    <span className="research-bullet-dot" />
                    <Text>{item}</Text>
                  </div>
                ))
              ) : (
                <Text type="secondary">当前没有明确的事件催化。</Text>
              )}
            </div>
          </div>

          <div className="research-decision-card">
            <Text strong>失效条件</Text>
            <div className="research-bullet-list">
              {invalidationItems.map((item) => (
                <div key={item} className="research-bullet-row">
                  <span className="research-bullet-dot research-bullet-dot-risk" />
                  <Text>{item}</Text>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="research-metric-grid">
          {researchMetrics.map((item) => (
            <div key={item.label} className="research-metric-card">
              <Text type="secondary">{item.label}</Text>
              <Text strong style={item.tone !== undefined ? colorStyle(item.tone) : undefined}>
                {item.value}
              </Text>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );

  const feedsCard = (
    <Card key="feeds" size="small" title="事件 / 公告 / 研报">
      <Space direction="vertical" size={14} style={{ width: "100%" }}>
        <div className="feed-section">
          <div className="feed-section-head">
            <Text strong>财联社快讯</Text>
            <Tag>{(feeds.telegraphs ?? []).length} 条</Tag>
          </div>
          {(feeds.telegraphs ?? []).length ? (
            <div className="feed-list">
              {feeds.telegraphs.map((item) => (
                <div className="feed-item" key={`telegraph-${item.id ?? item.title}`}>
                  <div className="feed-item-head">
                    <Text strong>{item.title}</Text>
                    <Text type="secondary">{item.published_at ?? "--"}</Text>
                  </div>
                  {item.content ? <Paragraph className="feed-item-content">{item.content}</Paragraph> : null}
                </div>
              ))}
            </div>
          ) : (
            <Alert type="info" showIcon message="暂未检索到与该股票相关的财联社快讯。" />
          )}
        </div>

        <div className="feed-grid">
          <div className="feed-section">
            <div className="feed-section-head">
              <Text strong>公司公告</Text>
              <Tag>{(feeds.notices ?? []).length} 条</Tag>
            </div>
            {(feeds.notices ?? []).length ? (
              <div className="feed-list compact">
                {feeds.notices.map((item) => (
                  <div className="feed-item compact" key={`notice-${item.art_code ?? item.title}`}>
                    <div className="feed-item-head">
                      <Text strong>{item.title}</Text>
                      <Text type="secondary">{item.notice_date ?? "--"}</Text>
                    </div>
                    <Space wrap size={6}>
                      {item.notice_type ? <Tag color="blue">{item.notice_type}</Tag> : null}
                      {item.url ? (
                        <a href={item.url} target="_blank" rel="noreferrer">
                          原文
                        </a>
                      ) : null}
                    </Space>
                  </div>
                ))}
              </div>
            ) : (
              <Alert type="info" showIcon message="暂未获取到公告。" />
            )}
          </div>

          <div className="feed-section">
            <div className="feed-section-head">
              <Text strong>研报跟踪</Text>
              <Tag>{(feeds.research_reports ?? []).length} 条</Tag>
            </div>
            {(feeds.research_reports ?? []).length ? (
              <div className="feed-list compact">
                {feeds.research_reports.map((item) => (
                  <div className="feed-item compact" key={`report-${item.info_code ?? item.title}`}>
                    <div className="feed-item-head">
                      <Text strong>{item.title}</Text>
                      <Text type="secondary">{item.publish_date ?? "--"}</Text>
                    </div>
                    <Space wrap size={6}>
                      {item.org_name ? <Tag color="purple">{item.org_name}</Tag> : null}
                      {item.rating ? <Tag color="gold">{item.rating}</Tag> : null}
                      {item.url ? (
                        <a href={item.url} target="_blank" rel="noreferrer">
                          原文
                        </a>
                      ) : null}
                    </Space>
                  </div>
                ))}
              </div>
            ) : (
              <Alert type="info" showIcon message="暂未获取到研报。" />
            )}
          </div>
        </div>
      </Space>
    </Card>
  );

  const moneyCard = (
    <Card key="money" size="small" title="资金流 / 龙虎榜">
      <Space direction="vertical" size={14} style={{ width: "100%" }}>
        <div className="feed-section">
          <div className="feed-section-head">
            <Text strong>个股资金流</Text>
            <Tag>{capitalFlows.length} 日</Tag>
          </div>
          {latestCapitalFlow ? (
            <>
              <div className="money-flow-grid">
                <div className="bar-row">
                  <Text type="secondary">最近交易日</Text>
                  <Text strong>{latestCapitalFlow.trade_date ?? "--"}</Text>
                </div>
                <div className="bar-row">
                  <Text type="secondary">主力净流入</Text>
                  <Text strong style={colorStyle(latestCapitalFlow.main_net_inflow)}>
                    {yuanToYiText(latestCapitalFlow.main_net_inflow)}
                  </Text>
                </div>
                <div className="bar-row">
                  <Text type="secondary">主力净占比</Text>
                  <Text strong style={colorStyle(latestCapitalFlow.main_net_inflow_pct)}>
                    {percentText(latestCapitalFlow.main_net_inflow_pct)}
                  </Text>
                </div>
                <div className="bar-row">
                  <Text type="secondary">收盘 / 涨跌幅</Text>
                  <Text strong>
                    {numberText(latestCapitalFlow.close)} /{" "}
                    <span style={colorStyle(latestCapitalFlow.change_pct)}>
                      {percentText(latestCapitalFlow.change_pct)}
                    </span>
                  </Text>
                </div>
              </div>

              <div className="feed-list compact">
                {capitalFlows.slice(0, 8).map((item) => (
                  <div className="feed-item compact" key={`flow-${item.trade_date}`}>
                    <div className="feed-item-head">
                      <Text strong>{item.trade_date}</Text>
                      <Text style={colorStyle(item.main_net_inflow)}>{yuanToYiText(item.main_net_inflow)}</Text>
                    </div>
                    <Space wrap size={6}>
                      <Tag color={Number(item.main_net_inflow_pct) >= 0 ? "red" : "green"}>
                        主力 {percentText(item.main_net_inflow_pct)}
                      </Tag>
                      <Tag color={Number(item.large_net_inflow_pct) >= 0 ? "red" : "green"}>
                        大单 {percentText(item.large_net_inflow_pct)}
                      </Tag>
                      <Tag color={Number(item.extra_large_net_inflow_pct) >= 0 ? "red" : "green"}>
                        超大单 {percentText(item.extra_large_net_inflow_pct)}
                      </Tag>
                    </Space>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <Alert type="info" showIcon message="暂未获取到个股资金流数据。" />
          )}
        </div>

        <div className="feed-section">
          <div className="feed-section-head">
            <Text strong>龙虎榜</Text>
            <Tag>{longTigerRows.length} 次</Tag>
          </div>
          {longTigerRows.length ? (
            <div className="feed-list">
              {longTigerRows.map((item, index) => (
                <div className="feed-item" key={`lhb-${item.trade_date}-${index}`}>
                  <div className="feed-item-head">
                    <Text strong>{item.trade_date?.slice(0, 10) ?? "--"}</Text>
                    <Text style={colorStyle(item.net_amount)}>{yuanToYiText(item.net_amount)}</Text>
                  </div>
                  <Paragraph className="feed-item-content">{item.explanation ?? item.explain ?? "龙虎榜上榜"}</Paragraph>
                  <Space wrap size={6}>
                    {item.explain ? <Tag color="blue">{item.explain}</Tag> : null}
                    <Tag color={Number(item.change_pct) >= 0 ? "red" : "green"}>
                      当日 {percentText(item.change_pct)}
                    </Tag>
                    <Tag color={Number(item.deal_net_ratio) >= 0 ? "red" : "green"}>
                      净买额占比 {percentText(item.deal_net_ratio)}
                    </Tag>
                    <Tag>成交额占比 {percentText(item.deal_amount_ratio)}</Tag>
                    <Tag>换手 {percentText(item.turnover_ratio)}</Tag>
                    {item.next_1d_pct !== null && item.next_1d_pct !== undefined ? (
                      <Tag color={Number(item.next_1d_pct) >= 0 ? "red" : "green"}>
                        次日 {percentText(item.next_1d_pct)}
                      </Tag>
                    ) : null}
                    {item.next_5d_pct !== null && item.next_5d_pct !== undefined ? (
                      <Tag color={Number(item.next_5d_pct) >= 0 ? "red" : "green"}>
                        5日 {percentText(item.next_5d_pct)}
                      </Tag>
                    ) : null}
                  </Space>
                </div>
              ))}
            </div>
          ) : (
            <Alert type="info" showIcon message="近年内暂未检索到该股票龙虎榜记录。" />
          )}
        </div>
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

  const fundamentalsCard = (
    <Card key="fundamentals" size="small" title="题材 / 财务 / 股东">
      <Space direction="vertical" size={14} style={{ width: "100%" }}>
        <div className="feed-section">
          <div className="feed-section-head">
            <Text strong>概念题材</Text>
            <Tag>{concepts.length} 个</Tag>
          </div>
          {concepts.length ? (
            <>
              <Space wrap>
                {concepts.map((item) => (
                  <Tag key={`${item.board_code}-${item.board_name}`} color="blue">
                    {item.board_name}
                  </Tag>
                ))}
              </Space>
              <div className="feed-list compact">
                {concepts.slice(0, 4).map((item) => (
                  <div className="feed-item compact" key={`concept-${item.board_code}`}>
                    <div className="feed-item-head">
                      <Text strong>{item.board_name}</Text>
                      <Text type="secondary">板块排名 {numberText(item.board_rank, 0)}</Text>
                    </div>
                    {item.selected_reason ? <Paragraph className="feed-item-content">{item.selected_reason}</Paragraph> : null}
                  </div>
                ))}
              </div>
            </>
          ) : (
            <Alert type="info" showIcon message="暂未获取到概念题材信息。" />
          )}
        </div>

        <div className="feed-grid">
          <div className="feed-section">
            <div className="feed-section-head">
              <Text strong>财务摘要</Text>
              <Tag>{financialReports.length} 期</Tag>
            </div>
            {latestFinancial ? (
              <>
                <div className="money-flow-grid">
                  <div className="bar-row">
                    <Text type="secondary">最新报告期</Text>
                    <Text strong>{latestFinancial.report_type ?? latestFinancial.report_date?.slice(0, 10) ?? "--"}</Text>
                  </div>
                  <div className="bar-row">
                    <Text type="secondary">营业收入</Text>
                    <Text strong>{yuanToYiText(latestFinancial.total_operate_income)}</Text>
                  </div>
                  <div className="bar-row">
                    <Text type="secondary">归母净利润</Text>
                    <Text strong>{yuanToYiText(latestFinancial.parent_net_profit)}</Text>
                  </div>
                  <div className="bar-row">
                    <Text type="secondary">ROE</Text>
                    <Text strong>{percentText(latestFinancial.roe)}</Text>
                  </div>
                  <div className="bar-row">
                    <Text type="secondary">总资产</Text>
                    <Text strong>{yuanToYiText(latestFinancial.total_assets)}</Text>
                  </div>
                  <div className="bar-row">
                    <Text type="secondary">资产负债率</Text>
                    <Text strong>{percentText(latestFinancial.debt_asset_ratio)}</Text>
                  </div>
                </div>

                <div className="feed-list compact">
                  {financialReports.slice(0, 4).map((item) => (
                    <div className="feed-item compact" key={`finance-${item.report_date}`}>
                      <div className="feed-item-head">
                        <Text strong>{item.report_type ?? item.report_date?.slice(0, 10)}</Text>
                        <Text type="secondary">{item.notice_date?.slice(0, 10) ?? "--"}</Text>
                      </div>
                      <Space wrap size={6}>
                        <Tag>营收 {yuanToYiText(item.total_operate_income)}</Tag>
                        <Tag>归母 {yuanToYiText(item.parent_net_profit)}</Tag>
                        <Tag>ROE {percentText(item.roe)}</Tag>
                      </Space>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <Alert type="info" showIcon message="暂未获取到财务摘要。" />
            )}
          </div>

          <div className="feed-section">
            <div className="feed-section-head">
              <Text strong>股东人数</Text>
              <Tag>{holderNumbers.length} 期</Tag>
            </div>
            {latestHolder ? (
              <>
                <div className="money-flow-grid">
                  <div className="bar-row">
                    <Text type="secondary">最新期末</Text>
                    <Text strong>{latestHolder.end_date?.slice(0, 10) ?? "--"}</Text>
                  </div>
                  <div className="bar-row">
                    <Text type="secondary">股东总数</Text>
                    <Text strong>{numberText(latestHolder.holder_total_num, 0)}</Text>
                  </div>
                  <div className="bar-row">
                    <Text type="secondary">较上期变化</Text>
                    <Text strong style={colorStyle(latestHolder.total_num_ratio)}>
                      {percentText(latestHolder.total_num_ratio)}
                    </Text>
                  </div>
                  <div className="bar-row">
                    <Text type="secondary">户均持股</Text>
                    <Text strong>{wanText(latestHolder.avg_free_shares)}</Text>
                  </div>
                  <div className="bar-row">
                    <Text type="secondary">户均持股市值</Text>
                    <Text strong>{yuanToYiText(latestHolder.avg_hold_amt)}</Text>
                  </div>
                  <div className="bar-row">
                    <Text type="secondary">筹码集中度</Text>
                    <Text strong>{numberText(latestHolder.hold_focus)}</Text>
                  </div>
                </div>

                <div className="feed-list compact">
                  {holderNumbers.slice(0, 5).map((item) => (
                    <div className="feed-item compact" key={`holder-${item.end_date}`}>
                      <div className="feed-item-head">
                        <Text strong>{item.end_date?.slice(0, 10)}</Text>
                        <Text style={colorStyle(item.total_num_ratio)}>{percentText(item.total_num_ratio)}</Text>
                      </div>
                      <Space wrap size={6}>
                        <Tag>股东 {numberText(item.holder_total_num, 0)}</Tag>
                        <Tag>户均持股 {wanText(item.avg_free_shares)}</Tag>
                        <Tag>户均市值 {yuanToYiText(item.avg_hold_amt)}</Tag>
                      </Space>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <Alert type="info" showIcon message="暂未获取到股东人数信息。" />
            )}
          </div>
        </div>
      </Space>
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
      { key: "chart", label: "K线", children: chartCard },
      { key: "money", label: "资金", children: moneyCard },
      { key: "fundamentals", label: "题材/财务", children: fundamentalsCard },
      { key: "feeds", label: "资讯", children: feedsCard },
      { key: "research", label: "研究卡", children: researchCard },
      { key: "watchlist", label: "自选设置", children: watchlistCard },
      { key: "backtest", label: "回测", children: backtestCard },
      { key: "profile", label: "资料", children: profileCard },
      { key: "trade", label: `交易 ${defaultTradeQuantity}股`, children: tradeCard },
    ],
    watch: [
      { key: "trade", label: `交易 ${defaultTradeQuantity}股`, children: tradeCard },
      { key: "chart", label: "K线", children: chartCard },
      { key: "money", label: "资金", children: moneyCard },
      { key: "fundamentals", label: "题材/财务", children: fundamentalsCard },
      { key: "feeds", label: "资讯", children: feedsCard },
      { key: "watchlist", label: "自选设置", children: watchlistCard },
      { key: "research", label: "研究卡", children: researchCard },
      { key: "backtest", label: "回测", children: backtestCard },
      { key: "profile", label: "资料", children: profileCard },
    ],
    analysis: [
      { key: "chart", label: "K线", children: chartCard },
      { key: "money", label: "资金", children: moneyCard },
      { key: "fundamentals", label: "题材/财务", children: fundamentalsCard },
      { key: "feeds", label: "资讯", children: feedsCard },
      { key: "research", label: "研究卡", children: researchCard },
      { key: "trade", label: `交易 ${defaultTradeQuantity}股`, children: tradeCard },
      { key: "backtest", label: "回测", children: backtestCard },
      { key: "watchlist", label: "自选设置", children: watchlistCard },
      { key: "profile", label: "资料", children: profileCard },
    ],
    paper: [
      { key: "trade", label: `交易 ${defaultTradeQuantity}股`, children: tradeCard },
      { key: "chart", label: "K线", children: chartCard },
      { key: "money", label: "资金", children: moneyCard },
      { key: "fundamentals", label: "题材/财务", children: fundamentalsCard },
      { key: "feeds", label: "资讯", children: feedsCard },
      { key: "research", label: "研究卡", children: researchCard },
      { key: "backtest", label: "回测", children: backtestCard },
      { key: "watchlist", label: "自选设置", children: watchlistCard },
      { key: "profile", label: "资料", children: profileCard },
    ],
  };

  return (
    <Card bordered={false} className="detail-card" loading={loading}>
      {!snapshot ? (
        <div className="detail-placeholder">选择一只股票查看详情</div>
      ) : (
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={sectionMap[activeMenu] ?? []}
          size="small"
          className="detail-tabs detail-workspace-tabs"
        />
      )}
    </Card>
  );
}
