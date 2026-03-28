import { Button, Card, Input, InputNumber, Segmented, Space, Typography } from "antd";

const { Text } = Typography;

export default function ScreeningControls({
  screeningPreset,
  setScreeningPreset,
  screeningFilters,
  updateScreeningField,
  onRun,
  onReset,
  screeningLoading,
}) {
  return (
    <Card bordered={false} className="screening-controls-card">
      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        <div className="screening-control-row">
          <div className="screening-control-main">
            <Text type="secondary">策略预设</Text>
            <Segmented
              value={screeningPreset}
              onChange={setScreeningPreset}
              options={[
                { label: "强势动量", value: "momentum" },
                { label: "放量回升", value: "rebound" },
              ]}
            />
          </div>
          <div className="screening-control-main">
            <Text type="secondary">筛选范围</Text>
            <Segmented
              value={screeningFilters.scope}
              onChange={(value) => updateScreeningField("scope", value)}
              options={[
                { label: "全市场", value: "all" },
                { label: "我的自选", value: "watchlist" },
              ]}
            />
          </div>
        </div>

        <div className="screening-query-box">
          <Text type="secondary">条件描述</Text>
          <Input.TextArea
            rows={2}
            value={screeningFilters.query}
            onChange={(event) => updateScreeningField("query", event.target.value)}
            placeholder="例如：放量上涨、价格不高、换手率高一点、优先看低估值股票"
          />
        </div>

        <div className="screening-filter-grid">
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
          <div>
            <Text type="secondary">最高 PE</Text>
            <InputNumber
              min={0}
              step={1}
              value={screeningFilters.max_pe_ratio}
              onChange={(value) => updateScreeningField("max_pe_ratio", value)}
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
        </div>

        <Space wrap>
          <Button type="primary" onClick={onRun} loading={screeningLoading}>
            开始筛选
          </Button>
          <Button onClick={onReset}>重置条件</Button>
        </Space>
      </Space>
    </Card>
  );
}
