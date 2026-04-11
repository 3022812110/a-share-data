import { Button, Card, Form, Input, InputNumber, Space, Tag, Typography } from "antd";

import { numberText } from "../lib/formatters";
import { resolveModelLabel, resolveProviderLabel } from "../lib/aiModelSettings";

const { Text } = Typography;
const ACTION_LABELS = {
  buy: "买入",
  watch: "观察",
  hold: "持有",
  reduce: "减仓",
  sell: "卖出",
  avoid: "回避",
};
const ACTION_COLORS = {
  buy: "red",
  watch: "blue",
  hold: "gold",
  reduce: "orange",
  sell: "green",
  avoid: "default",
};
const STATUS_LABELS = {
  generated: "已生成",
  applied: "已套用",
  executed: "已执行",
  reviewed: "已复盘",
};
const STATUS_COLORS = {
  generated: "blue",
  applied: "purple",
  executed: "cyan",
  reviewed: "success",
};

function formatDecisionTime(value) {
  const text = String(value ?? "").trim();
  if (!text) return "--";
  return text.replace("T", " ").replace("Z", "").slice(0, 16);
}

function canExecuteDecision(decision) {
  return ["buy", "sell", "reduce"].includes(decision?.action) && Number(decision?.quantity) > 0;
}

export default function PaperTradeCard({
  snapshot,
  portfolio,
  paperForm,
  onPaperOrder,
  onSavePlan,
  onQuickTrade,
  paperOrdering,
  planSaving,
  modelSettings,
  onOpenModelSettings,
  aiTradeDecisions,
  aiTradeLoading,
  aiTradeGenerating,
  aiTradeActing,
  onGenerateAiTradeDecision,
  onApplyAiTradeDecision,
  onExecuteAiTradeDecision,
}) {
  const account = portfolio?.account ?? {};
  const quickTradeQuantity = Math.max(100, Number(snapshot.default_trade_quantity) || 100);
  const modelSummary = `${resolveProviderLabel(modelSettings.provider)} · ${resolveModelLabel(
    modelSettings.provider,
    modelSettings.model
  )}`;
  const recentDecisions = Array.isArray(aiTradeDecisions) ? aiTradeDecisions.slice(0, 3) : [];

  return (
    <Card size="small" title="AI交易">
      <Space direction="vertical" size={14} style={{ width: "100%" }}>
        <div className="trade-ai-toolbar">
          <div className="trade-ai-toolbar-copy">
            <Text type="secondary">共享模型</Text>
            <Text strong>{modelSummary}</Text>
          </div>
          <Space wrap>
            <Button onClick={onOpenModelSettings}>模型设置</Button>
            <Button type="primary" onClick={onGenerateAiTradeDecision} loading={aiTradeGenerating}>
              AI给建议
            </Button>
          </Space>
        </div>

        <div className="trade-ai-decision-section">
          <div className="trade-ai-decision-headline">
            <Text strong>最近AI建议</Text>
            <Text type="secondary">会自动读取当前持仓、历史成交和复盘结果继续判断</Text>
          </div>
          {aiTradeLoading ? (
            <Text type="secondary">正在加载 AI 建议...</Text>
          ) : recentDecisions.length ? (
            <div className="trade-ai-decision-list">
              {recentDecisions.map((decision) => {
                const canApply = !["applied", "executed", "reviewed"].includes(decision.status);
                const canExecute = canExecuteDecision(decision) && !["executed", "reviewed"].includes(decision.status);
                return (
                  <div className="trade-ai-decision-card" key={decision.id}>
                    <div className="trade-ai-decision-top">
                      <Space wrap size={6}>
                        <Tag color={ACTION_COLORS[decision.action] ?? "default"}>
                          {ACTION_LABELS[decision.action] ?? decision.action}
                        </Tag>
                        <Tag color={STATUS_COLORS[decision.status] ?? "default"}>
                          {STATUS_LABELS[decision.status] ?? decision.status}
                        </Tag>
                        <Tag>数量 {decision.quantity || 0} 股</Tag>
                        <Tag>置信度 {decision.confidence ?? "--"}</Tag>
                        <Tag>风险 {decision.risk_level ?? "--"}</Tag>
                      </Space>
                      <Text type="secondary">{formatDecisionTime(decision.created_at)}</Text>
                    </div>

                    <Text strong>{decision.summary ?? "暂无结论"}</Text>

                    <div className="trade-ai-chip-wrap">
                      {decision.stop_loss_price ? <Tag>止损 {numberText(decision.stop_loss_price, 2)}</Tag> : null}
                      {decision.take_profit_price ? <Tag>止盈 {numberText(decision.take_profit_price, 2)}</Tag> : null}
                      {decision.planned_holding_days ? <Tag>持有 {decision.planned_holding_days} 天</Tag> : null}
                    </div>

                    {decision.reasoning?.length ? (
                      <div className="trade-ai-reasoning">
                        {decision.reasoning.map((item, index) => (
                          <Text key={`${decision.id}-reason-${index}`}>{`${index + 1}. ${item}`}</Text>
                        ))}
                      </div>
                    ) : null}

                    {decision.review_summary || decision.lessons_learned ? (
                      <div className="trade-ai-review-box">
                        {decision.review_rating ? <Tag color="gold">复盘 {decision.review_rating}</Tag> : null}
                        {decision.exit_reason ? <Text type="secondary">卖出原因：{decision.exit_reason}</Text> : null}
                        {decision.review_summary ? <Text>复盘结论：{decision.review_summary}</Text> : null}
                        {decision.lessons_learned ? <Text type="secondary">下次改进：{decision.lessons_learned}</Text> : null}
                      </div>
                    ) : null}

                    <Space wrap>
                      <Button
                        onClick={() => onApplyAiTradeDecision(decision.id)}
                        loading={aiTradeActing === `apply-${decision.id}`}
                        disabled={!canApply}
                      >
                        套用到计划
                      </Button>
                      <Button
                        type="primary"
                        onClick={() => onExecuteAiTradeDecision(decision.id)}
                        loading={aiTradeActing === `execute-${decision.id}`}
                        disabled={!canExecute}
                      >
                        执行到模拟盘
                      </Button>
                    </Space>
                  </div>
                );
              })}
            </div>
          ) : (
            <Text type="secondary">还没有 AI 建议。点一次“AI给建议”，我会先读你的这只股票、持仓和最近交易，再给出操作建议。</Text>
          )}
        </div>

        <div className="trade-account-strip">
          <div className="trade-account-pill">
            <Text type="secondary">模拟账户</Text>
            <Text strong>{account.account_name ?? "AI 模拟账户"}</Text>
          </div>
          <div className="trade-account-pill">
            <Text type="secondary">可用现金</Text>
            <Text strong>¥{numberText(account.cash_balance)}</Text>
          </div>
          <div className="trade-account-pill">
            <Text type="secondary">当前持仓</Text>
            <Text strong>
              {snapshot.paper_quantity ? `${snapshot.paper_quantity} 股 / 成本 ${numberText(snapshot.paper_avg_cost)}` : "暂无持仓"}
            </Text>
          </div>
        </div>

        <Space wrap className="trade-shortcuts">
          <Button
            type="primary"
            onClick={() =>
              onQuickTrade(
                snapshot.stock_code,
                "buy",
                quickTradeQuantity,
                snapshot.in_watchlist ? `一键买入自选 ${quickTradeQuantity} 股` : `一键买入 ${quickTradeQuantity} 股`,
              )
            }
            loading={paperOrdering}
          >
            {snapshot.in_watchlist ? `一键买入自选 ${quickTradeQuantity} 股` : `一键买入 ${quickTradeQuantity} 股`}
          </Button>
          <Button
            onClick={() => onQuickTrade(snapshot.stock_code, "sell", quickTradeQuantity, `一键卖出 ${quickTradeQuantity} 股`)}
            loading={paperOrdering}
          >
            一键卖出 {quickTradeQuantity} 股
          </Button>
        </Space>

        <Form form={paperForm} layout="vertical" initialValues={{ quantity: 100, note: "" }}>
          <div className="trade-form-grid">
            <Form.Item label="交易数量" name="quantity" rules={[{ required: true, message: "请输入数量" }]}>
              <InputNumber min={100} step={100} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item label="备注" name="note">
              <Input.TextArea autoSize={{ minRows: 1, maxRows: 2 }} placeholder="这次模拟交易想验证什么" />
            </Form.Item>
          </div>
          <div className="trade-plan-grid">
            <Form.Item label="买入理由" name="entry_reason">
              <Input placeholder="例如：放量突破、回调企稳" />
            </Form.Item>
            <Form.Item label="计划持有天数" name="planned_holding_days">
              <InputNumber min={1} max={120} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item label="计划止损" name="plan_stop_loss_price">
              <InputNumber min={0} step={0.01} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item label="计划止盈" name="plan_take_profit_price">
              <InputNumber min={0} step={0.01} style={{ width: "100%" }} />
            </Form.Item>
          </div>
          <Form.Item label="失效条件" name="invalidation_condition">
            <Input placeholder="例如：跌破止损位、量能明显走弱" />
          </Form.Item>
          <Form.Item label="计划备注" name="plan_note">
            <Input.TextArea autoSize={{ minRows: 1, maxRows: 2 }} placeholder="补充交易计划、观察点和风险项" />
          </Form.Item>
          <Space wrap>
            <Button type="primary" onClick={() => onPaperOrder("buy")} loading={paperOrdering}>
              按填写数量买入
            </Button>
            <Button onClick={() => onPaperOrder("sell")} loading={paperOrdering}>
              按填写数量卖出
            </Button>
            <Button onClick={onSavePlan} loading={planSaving}>
              {snapshot.paper_plan_id ? "更新计划" : "保存计划"}
            </Button>
          </Space>
        </Form>
      </Space>
    </Card>
  );
}
