import { StarFilled, StarOutlined } from "@ant-design/icons";
import { Button, Card, Empty, Input, InputNumber, Segmented, Space, Tag, Typography } from "antd";

import { colorStyle, numberText, percentText } from "../lib/formatters";

const { Title, Text } = Typography;

export default function AnalysisSidebar({
  screeningPreset,
  setScreeningPreset,
  screeningFilters,
  updateScreeningField,
  onRun,
  onReset,
  screeningLoading,
  summary,
  data,
  onPick,
  onToggleWatchlist,
}) {
  return (
    <div className="analysis-side-stack">
      <Card bordered={false} className="analysis-side-card">
        <div className="analysis-side-head">
          <div className="analysis-side-head-copy">
            <Text type="secondary">分析范围</Text>
            <Title level={5} style={{ margin: 0 }}>
              先决定要看哪些股票，再交给 AI 分析
            </Title>
          </div>
          <Button size="small" onClick={onReset}>
            重置
          </Button>
        </div>

        <div className="analysis-side-section">
          <Text type="secondary">分析策略</Text>
          <Segmented
            block
            value={screeningPreset}
            onChange={setScreeningPreset}
            options={[
              { label: "强势动量", value: "momentum" },
              { label: "放量回升", value: "rebound" },
            ]}
          />
        </div>

        <div className="analysis-side-section">
          <Text type="secondary">分析范围</Text>
          <Segmented
            block
            value={screeningFilters.scope}
            onChange={(value) => updateScreeningField("scope", value)}
            options={[
              { label: "全市场", value: "all" },
              { label: "我的自选", value: "watchlist" },
            ]}
          />
        </div>

        <div className="analysis-side-section">
          <Text type="secondary">条件描述</Text>
          <Input.TextArea
            autoSize={{ minRows: 2, maxRows: 4 }}
            value={screeningFilters.query}
            onChange={(event) => updateScreeningField("query", event.target.value)}
            placeholder="例如：放量上涨、价格不高、优先看换手率高一点的股票"
          />
        </div>

        <div className="analysis-settings-grid">
          <div>
            <Text type="secondary">最小涨幅</Text>
            <InputNumber
              min={0}
              step={0.1}
              value={screeningFilters.min_change_pct}
              onChange={(value) => updateScreeningField("min_change_pct", value)}
              placeholder="%"
              style={{ width: "100%" }}
            />
          </div>
          <div>
            <Text type="secondary">最小换手率</Text>
            <InputNumber
              min={0}
              step={0.1}
              value={screeningFilters.min_turnover_ratio}
              onChange={(value) => updateScreeningField("min_turnover_ratio", value)}
              placeholder="%"
              style={{ width: "100%" }}
            />
          </div>
          <div>
            <Text type="secondary">最小量比</Text>
            <InputNumber
              min={0}
              step={0.1}
              value={screeningFilters.min_volume_ratio}
              onChange={(value) => updateScreeningField("min_volume_ratio", value)}
              style={{ width: "100%" }}
            />
          </div>
          <div>
            <Text type="secondary">返回数量</Text>
            <InputNumber
              min={10}
              max={200}
              step={10}
              value={screeningFilters.limit}
              onChange={(value) => updateScreeningField("limit", value ?? 80)}
              style={{ width: "100%" }}
            />
          </div>
          <div>
            <Text type="secondary">最低价格</Text>
            <InputNumber
              min={0}
              step={0.1}
              value={screeningFilters.min_price}
              onChange={(value) => updateScreeningField("min_price", value)}
              placeholder="元"
              style={{ width: "100%" }}
            />
          </div>
          <div>
            <Text type="secondary">最高价格</Text>
            <InputNumber
              min={0}
              step={0.1}
              value={screeningFilters.max_price}
              onChange={(value) => updateScreeningField("max_price", value)}
              placeholder="元"
              style={{ width: "100%" }}
            />
          </div>
          <div className="analysis-settings-span-2">
            <Text type="secondary">最高 PE</Text>
            <InputNumber
              min={0}
              step={1}
              value={screeningFilters.max_pe_ratio}
              onChange={(value) => updateScreeningField("max_pe_ratio", value)}
              style={{ width: "100%" }}
            />
          </div>
        </div>

        <Space wrap className="analysis-action-row">
          <Button type="primary" onClick={onRun} loading={screeningLoading}>
            更新候选池
          </Button>
          <Text type="secondary">
            {summary?.returned_count ?? data.length} / {summary?.candidate_count ?? data.length} 只
          </Text>
        </Space>
      </Card>

      <Card bordered={false} className="analysis-side-card">
        <div className="analysis-side-head">
          <div className="analysis-side-head-copy">
            <Text type="secondary">候选池概览</Text>
            <Title level={5} style={{ margin: 0 }}>
              当前候选池
            </Title>
          </div>
        </div>

        <div className="analysis-summary-grid">
          <div className="analysis-summary-metric">
            <Text type="secondary">策略</Text>
            <Text strong>{summary?.preset_label ?? "未设置"}</Text>
          </div>
          <div className="analysis-summary-metric">
            <Text type="secondary">候选</Text>
            <Text strong>{summary?.candidate_count ?? data.length}</Text>
          </div>
          <div className="analysis-summary-metric">
            <Text type="secondary">展示</Text>
            <Text strong>{summary?.returned_count ?? data.length}</Text>
          </div>
        </div>

        {(summary?.applied_conditions ?? []).length ? (
          <div className="analysis-summary-tags">
            <Text type="secondary">已应用条件</Text>
            <Space wrap>
              {(summary?.applied_conditions ?? []).map((item) => (
                <Tag key={item}>{item}</Tag>
              ))}
            </Space>
          </div>
        ) : null}

        {data.length ? (
          <div className="analysis-candidate-list">
            {data.slice(0, 8).map((item) => (
              <div key={item.stock_code} className="analysis-candidate-item">
                <div className="analysis-candidate-header">
                  <div>
                    <Button
                      type="link"
                      className="analysis-candidate-link"
                      onClick={() => onPick(item.stock_code)}
                    >
                      {item.stock_name}（{item.stock_code}）
                    </Button>
                    <Text className="analysis-candidate-meta">
                      评分 {numberText(item.ai_score)} · 现价 {numberText(item.price)} ·{" "}
                      <span style={colorStyle(item.change_pct)}>{percentText(item.change_pct)}</span>
                    </Text>
                  </div>
                  <Tag color="blue">AI {numberText(item.ai_score)}</Tag>
                </div>

                <Space wrap>
                  {(item.reasons ?? []).slice(0, 3).map((reason) => (
                    <Tag key={`${item.stock_code}-${reason}`}>{reason}</Tag>
                  ))}
                </Space>

                <div className="analysis-candidate-actions">
                  <Text type="secondary">
                    量比 {numberText(item.volume_ratio)} · 换手 {percentText(item.turnover_ratio)}
                  </Text>
                  <Button
                    size="small"
                    icon={item.in_watchlist ? <StarFilled /> : <StarOutlined />}
                    onClick={() => onToggleWatchlist(item)}
                  >
                    {item.in_watchlist ? "已在自选" : "加入自选"}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="先更新一次候选池" />
        )}
      </Card>
    </div>
  );
}
