import { Card, Space, Tag, Typography } from "antd";

const { Title, Text } = Typography;

export default function ScreeningSummaryCard({ summary }) {
  if (!summary) return null;

  return (
    <Card bordered={false} className="screening-summary-card">
      <div className="screening-summary-grid">
        <div className="screening-summary-metric">
          <Text type="secondary">筛选策略</Text>
          <Title level={5} style={{ margin: "2px 0 0" }}>
            {summary.preset_label}
          </Title>
        </div>
        <div className="screening-summary-metric">
          <Text type="secondary">候选数量</Text>
          <Title level={5} style={{ margin: "2px 0 0" }}>
            {summary.candidate_count}
          </Title>
        </div>
        <div className="screening-summary-metric">
          <Text type="secondary">展示数量</Text>
          <Title level={5} style={{ margin: "2px 0 0" }}>
            {summary.returned_count}
          </Title>
        </div>
        <div className="screening-summary-tags">
          <Text type="secondary">已应用条件</Text>
          <Space wrap>
            {(summary.applied_conditions ?? []).map((item) => (
              <Tag key={item}>{item}</Tag>
            ))}
          </Space>
        </div>
      </div>
    </Card>
  );
}
