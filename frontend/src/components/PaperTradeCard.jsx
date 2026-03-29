import { Button, Card, Form, Input, InputNumber, Space, Typography } from "antd";

import { numberText } from "../lib/formatters";

const { Text } = Typography;

export default function PaperTradeCard({
  snapshot,
  portfolio,
  paperForm,
  onPaperOrder,
  onSavePlan,
  onQuickTrade,
  paperOrdering,
  planSaving,
}) {
  const account = portfolio?.account ?? {};
  const quickTradeQuantity = Math.max(100, Number(snapshot.default_trade_quantity) || 100);

  return (
    <Card size="small" title="AI交易">
      <Space direction="vertical" size={14} style={{ width: "100%" }}>
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
