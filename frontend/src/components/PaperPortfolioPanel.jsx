import { Alert, Badge, Button, Card, Progress, Space, Table, Tag, Typography } from "antd";

import PaperSummaryCards from "./PaperSummaryCards";
import CompactEmpty from "./CompactEmpty";
import MarketStatusNotice from "./MarketStatusNotice";
import RecommendationPerformancePanel from "./RecommendationPerformancePanel";
import StrategyStabilityPanel from "./StrategyStabilityPanel";
import { capText, colorStyle, numberText, percentText } from "../lib/formatters";

const { Text } = Typography;

export default function PaperPortfolioPanel({
  portfolio,
  loading,
  recommendations = [],
  recommendationSummary,
  recommendationLoading,
  recommendationPerformance,
  performanceLoading,
  strategyStability,
  strategyStabilityLoading,
  strategyPrevalidation,
  onSelectCode,
  onOpenReview,
  onQuickTrade,
  onRefreshRecommendations,
  onRefreshPerformance,
  onRunStrategyStability,
}) {
  const positions = portfolio?.positions ?? [];
  const trades = portfolio?.trades ?? [];
  const marketContext = recommendationSummary?.market_context ?? {};
  const tradeGate = marketContext.trade_gate ?? {};
  const recommendationAccount = recommendationSummary?.account ?? {};
  const strategyContext = recommendationSummary?.strategy_context ?? {};
  const strategyCandidateActions = strategyContext.candidate_actions ?? {};
  const prevalidation = strategyPrevalidation ?? strategyContext.prevalidation ?? {};
  const marketStatus = portfolio?.market_status ?? {};
  const riskDiagnosis = portfolio?.risk_diagnosis ?? {};
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
      render: (_, record) => record.action === "buy" ? (
        <Space size={8} className="dense-cell-line">
          <Text>{record.recommended_quantity}股</Text>
          <Text type="secondary">约¥{numberText(record.estimated_cash)}</Text>
          <Text type="secondary">区间 {numberText(record.entry_zone_low)}-{numberText(record.entry_zone_high)}</Text>
          <Text type="secondary">损 {numberText(record.stop_loss_price)} / 盈 {numberText(record.take_profit_price)}</Text>
        </Space>
      ) : (
        <Space size={8} className="dense-cell-line">
          <Tag bordered={false}>仅观察</Tag>
          <Text type="secondary">等待滚动验证与当前行情同时通过</Text>
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
          <Tag
            bordered={false}
            color={record.strategy_evidence?.action === "support" ? "green" : record.strategy_evidence?.action === "caution" ? "gold" : "default"}
          >
            {record.strategy_evidence?.label ?? "策略未验证"}
          </Tag>
          {(record.reasons ?? []).slice(0, 2).map((item, index) => (
            <Text key={`${record.stock_code}-reason-${index}`} type="secondary">
              {item}
            </Text>
          ))}
          <Space size={10} wrap className="signal-badge-row">
            <Badge color={record.confidence === "高" ? "#007aff" : "#8e8e93"} text={`置信 ${record.confidence}`} />
            <Badge color={record.risk_level === "高" ? "#ff9f0a" : "#8e8e93"} text={`风险 ${record.risk_level}`} />
          </Space>
        </Space>
      ),
    },
    {
      title: "操作",
      key: "actions",
      render: (_, record) => (
        <Space direction="vertical" size={6}>
          {record.action === "buy" ? (
            <Button
              size="small"
              type="primary"
              disabled={!marketOpen || tradeGate.allow_new_positions === false}
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
          ) : (
            <Button size="small" disabled>观察</Button>
          )}
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
            <Badge
              color={record.review_rating === "good" ? "#34c759" : record.review_rating === "bad" ? "#ff3b30" : "#8e8e93"}
              text={record.review_rating === "good" ? "做得好" : record.review_rating === "bad" ? "做得差" : "一般"}
            />
          ) : (
            <Badge status="default" text={record.plan_status === "closed" ? "待复盘" : "未结束"} />
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
      <MarketStatusNotice marketStatus={marketStatus} />
      <PaperSummaryCards portfolio={portfolio} />
      {riskDiagnosis.label ? (
        <Alert
          showIcon
          type={riskDiagnosis.level === "high" ? "error" : riskDiagnosis.level === "medium" ? "warning" : "success"}
          message={`系统结论：${riskDiagnosis.label}`}
          description={(
            <Space direction="vertical" size={2}>
              <Text>{riskDiagnosis.summary}</Text>
              {(riskDiagnosis.flags ?? []).slice(0, 3).map((flag) => (
                <Text type="secondary" key={flag}>· {flag}</Text>
              ))}
              {(riskDiagnosis.position_actions ?? []).slice(0, 3).map((item) => (
                <Text type="secondary" key={`${item.stock_code}-${item.action}`}>
                  · {item.stock_name}：{item.label}
                </Text>
              ))}
            </Space>
          )}
        />
      ) : null}
      <Card
        variant="borderless"
        className="table-card trade-recommendation-card"
        title="训练推荐与观察"
        loading={recommendationLoading}
        extra={
          <Button size="small" onClick={onRefreshRecommendations} loading={recommendationLoading}>
            刷新
          </Button>
        }
      >
        <div className="trade-recommendation-summary">
          <Space wrap>
            <Badge
              color={marketContext.regime === "偏强" ? "#ff3b30" : marketContext.regime === "偏弱" ? "#34c759" : "#8e8e93"}
              text={marketContext.regime ?? "观察"}
            />
            <Text type="secondary">上涨占比 {numberText(marketContext.rising_ratio)}%</Text>
            <Text type="secondary">涨停 {marketContext.limit_up_count ?? 0}</Text>
            <Text type="secondary">跌停 {marketContext.limit_down_count ?? 0}</Text>
            <Text type="secondary">当前仓位 {numberText(recommendationAccount.current_position_pct)}%</Text>
            <Text type="secondary">新增计划 {numberText(recommendationAccount.planned_position_pct)}%</Text>
          </Space>
          <Text type="secondary">{marketContext.strategy ?? "先确认市场强弱，再做小仓训练。"}</Text>
        </div>
        {tradeGate.status ? (
          <Alert
            showIcon
            type={tradeGate.status === "blocked" ? "error" : tradeGate.status === "limited" ? "warning" : "info"}
            message={`${tradeGate.label} · 总仓位上限 ${numberText(tradeGate.max_total_position_pct)}%`}
            description={(tradeGate.reasons ?? []).join("；")}
            style={{ marginBottom: 12 }}
          />
        ) : null}
        {strategyContext.run_id ? (
          <Alert
            showIcon
            type={(strategyCandidateActions.block ?? 0) > 0 ? "warning" : "info"}
            message={`策略证据已接入 · 当前映射为${strategyContext.mapped_historical_regime ?? "未知"}行情`}
            description={`稳定性记录 #${strategyContext.run_id}：加分 ${strategyCandidateActions.support ?? 0}，降权 ${strategyCandidateActions.caution ?? 0}，阻断 ${strategyCandidateActions.block ?? 0}，未验证 ${strategyCandidateActions.untested ?? 0}。`}
            style={{ marginBottom: 12 }}
          />
        ) : null}
        {prevalidation.job_id ? (
          <Alert
            showIcon
            type={prevalidation.status === "completed_with_errors" ? "warning" : prevalidation.status === "completed" ? "success" : "info"}
            message={prevalidation.status === "running"
              ? `候选策略后台验证中 · ${prevalidation.completed ?? 0}/${prevalidation.total ?? 0}`
              : prevalidation.status === "completed_with_errors"
                ? "候选策略预验证已结束，部分标的失败"
                : "候选策略预验证已完成"}
            description={(
              <Space direction="vertical" size={3} style={{ width: "100%" }}>
                <Progress percent={Math.round(prevalidation.progress_pct ?? 0)} size="small" status={prevalidation.status === "completed_with_errors" ? "exception" : undefined} />
                <Text type="secondary">
                  {prevalidation.status === "running" && prevalidation.current_stock_code
                    ? `正在验证 ${prevalidation.current_stock_code}；验证前只能观察。`
                    : `24 小时缓存已有 ${prevalidation.cached_count ?? 0} 只；只有稳定且匹配当前行情的候选可买入。`}
                </Text>
              </Space>
            )}
            style={{ marginBottom: 12 }}
          />
        ) : null}
        <Table
          rowKey="stock_code"
          size="small"
          columns={recommendationColumns}
          dataSource={recommendations}
          pagination={false}
          locale={{ emptyText: <CompactEmpty description="当前没有满足风险条件的买入或观察候选" /> }}
          onRow={(record) => ({ onClick: () => onSelectCode(record.stock_code) })}
        />
      </Card>
      <StrategyStabilityPanel
        stability={strategyStability}
        loading={strategyStabilityLoading}
        onRun={onRunStrategyStability}
        onSelectCode={onSelectCode}
      />
      <RecommendationPerformancePanel
        performance={recommendationPerformance}
        loading={performanceLoading}
        onRefresh={onRefreshPerformance}
      />
      <Card variant="borderless" className="table-card" title="当前持仓" loading={loading}>
        <Table
          rowKey="stock_code"
          size="small"
          columns={positionColumns}
          dataSource={positions}
          pagination={false}
          locale={{ emptyText: <CompactEmpty description="当前没有持仓，可从股票详情发起模拟买入" /> }}
          onRow={(record) => ({ onClick: () => onSelectCode(record.stock_code) })}
        />
      </Card>
      <Card variant="borderless" className="table-card" title="最近成交" loading={loading}>
        <Table
          rowKey="id"
          size="small"
          columns={tradeColumns}
          dataSource={trades}
          pagination={{ pageSize: 8, hideOnSinglePage: true }}
          locale={{ emptyText: <CompactEmpty description="还没有交易记录" /> }}
          onRow={(record) => ({ onClick: () => onSelectCode(record.stock_code) })}
        />
      </Card>
    </Space>
  );
}
