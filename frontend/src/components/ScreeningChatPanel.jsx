import React from "react";
import {
  ApiOutlined,
  RobotOutlined,
  SettingOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Button, Card, Input, InputNumber, Modal, Select, Space, Tag, Typography } from "antd";

import { numberText, percentText } from "../lib/formatters";

const { Text, Paragraph, Title } = Typography;

const QUICK_PROMPTS = [
  "现在最强的3只股票是谁？",
  "这批候选股最大的风险是什么？",
  "帮我看看最适合买入观察的是哪几只。",
];

const MODEL_STORAGE_KEY = "a-share-data.ai-model-settings";

const PROVIDER_OPTIONS = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "google", label: "Google Gemini" },
  { value: "deepseek", label: "DeepSeek" },
  { value: "ollama", label: "Ollama" },
  { value: "custom", label: "自定义兼容接口" },
];

const MODEL_OPTIONS = {
  openai: [
    { value: "gpt-5.4", label: "GPT-5.4" },
    { value: "gpt-5.4-mini", label: "GPT-5.4 Mini" },
    { value: "gpt-4.1", label: "GPT-4.1" },
  ],
  anthropic: [
    { value: "claude-sonnet-4", label: "Claude Sonnet 4" },
    { value: "claude-opus-4", label: "Claude Opus 4" },
  ],
  google: [
    { value: "gemini-2.5-pro", label: "Gemini 2.5 Pro" },
    { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash" },
  ],
  deepseek: [
    { value: "deepseek-chat", label: "DeepSeek Chat" },
    { value: "deepseek-reasoner", label: "DeepSeek Reasoner" },
  ],
  ollama: [
    { value: "qwen3:8b", label: "qwen3:8b" },
    { value: "llama3.1:8b", label: "llama3.1:8b" },
  ],
  custom: [{ value: "custom-model", label: "自定义模型" }],
};

const DEFAULT_MODEL_SETTINGS = {
  provider: "openai",
  model: "gpt-5.4",
  apiKey: "",
  baseUrl: "",
  systemPrompt: "你是A股研究助手，优先解释当前候选池的机会、风险和观察重点。",
  temperature: 0.3,
  maxTokens: 4000,
};

function loadModelSettings() {
  if (typeof window === "undefined") {
    return DEFAULT_MODEL_SETTINGS;
  }
  try {
    const raw = window.localStorage.getItem(MODEL_STORAGE_KEY);
    if (!raw) return DEFAULT_MODEL_SETTINGS;
    const parsed = JSON.parse(raw);
    return { ...DEFAULT_MODEL_SETTINGS, ...parsed };
  } catch {
    return DEFAULT_MODEL_SETTINGS;
  }
}

function persistModelSettings(settings) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(MODEL_STORAGE_KEY, JSON.stringify(settings));
}

function resolveProviderLabel(provider) {
  return PROVIDER_OPTIONS.find((item) => item.value === provider)?.label ?? provider;
}

function resolveModelLabel(provider, model) {
  return MODEL_OPTIONS[provider]?.find((item) => item.value === model)?.label ?? model;
}

function findCandidate(prompt, data) {
  const codeMatch = prompt.match(/\b\d{6}\b/);
  if (codeMatch) {
    return data.find((item) => item.stock_code === codeMatch[0]) ?? null;
  }
  return (
    data.find((item) => prompt.includes(item.stock_name) || prompt.includes(item.stock_code)) ?? null
  );
}

function buildCandidateAnswer(item) {
  const risks = [];
  if (Number(item.change_pct) >= 8) risks.push("涨幅已经较大，次日分歧风险高");
  if (Number(item.volume_ratio) < 1.2) risks.push("量比不够强，持续性待确认");
  if (Number(item.pe_ratio) > 80) risks.push("估值偏高");
  if (!risks.length) risks.push("仍需结合板块强度和次日承接确认");

  return {
    text: [
      `${item.stock_name}（${item.stock_code}）当前 AI 评分 ${numberText(item.ai_score, 1)}。`,
      `现价 ${numberText(item.price)}，涨跌幅 ${percentText(item.change_pct)}，量比 ${numberText(item.volume_ratio)}，换手率 ${percentText(item.turnover_ratio)}。`,
      `入选原因：${(item.reasons ?? []).join("、") || "当前满足筛选条件"}。`,
      `主要风险：${risks.join("、")}。`,
    ].join("\n"),
    picks: [item],
  };
}

function buildRankingAnswer(data) {
  const picks = data.slice(0, 3);
  if (!picks.length) {
    return { text: "当前还没有候选股。先点击“开始筛选”再来问我。", picks: [] };
  }
  return {
    text: [
      "当前最强的 3 只候选股：",
      ...picks.map(
        (item, index) =>
          `${index + 1}. ${item.stock_name}（${item.stock_code}），评分 ${numberText(item.ai_score, 1)}，涨跌幅 ${percentText(item.change_pct)}，理由：${(item.reasons ?? []).slice(0, 2).join("、") || "满足当前策略"}`
      ),
      "它们更适合先加入观察，而不是直接视为买入信号。",
    ].join("\n"),
    picks,
  };
}

function buildRiskAnswer(data) {
  const top = data.slice(0, 8);
  if (!top.length) {
    return { text: "当前没有候选池，暂时没法分析风险。", picks: [] };
  }
  const overbought = top.filter((item) => Number(item.change_pct) >= 8).length;
  const weakVolume = top.filter((item) => Number(item.volume_ratio) < 1.2).length;
  const highPe = top.filter((item) => Number(item.pe_ratio) > 80).length;

  return {
    text: [
      "这批候选股里，我优先提醒这几个风险：",
      `1. 涨幅过大的有 ${overbought} 只，容易高开低走。`,
      `2. 量比偏弱的有 ${weakVolume} 只，说明并不是所有上涨都有足够成交支持。`,
      `3. 估值偏高的有 ${highPe} 只，高波动时回撤会更快。`,
      "所以这页更适合做候选池，不适合直接追高。",
    ].join("\n"),
    picks: top.slice(0, 3),
  };
}

function buildGenericAnswer(summary, data) {
  if (!data.length) {
    return { text: "当前没有可分析的候选股。先点一次“开始筛选”，我再按结果给你解释。", picks: [] };
  }

  const leader = data[0];
  return {
    text: [
      `这轮筛选策略是“${summary?.preset_label ?? "AI条件选股"}”，候选 ${summary?.candidate_count ?? data.length} 只，当前展示 ${summary?.returned_count ?? data.length} 只。`,
      `从结果看，${leader.stock_name}（${leader.stock_code}）暂时排在前面，评分 ${numberText(leader.ai_score, 1)}。`,
      "你可以继续问我：",
      "1. 现在最强的 3 只是谁",
      "2. 某只股票为什么入选",
      "3. 这批候选股最大的风险是什么",
    ].join("\n"),
    picks: [leader],
  };
}

function buildAnswer(prompt, summary, data) {
  const normalized = prompt.trim();
  if (!normalized) return { text: "请输入一个问题。", picks: [] };
  if (!data.length) return { text: "当前还没有筛选结果，先点“开始筛选”。", picks: [] };

  const candidate = findCandidate(normalized, data);
  if (candidate) return buildCandidateAnswer(candidate);

  if (/(最强|前.?3|top|推荐|哪几只|买什么)/i.test(normalized)) {
    return buildRankingAnswer(data);
  }
  if (/(风险|回避|不要买|避开|危险)/i.test(normalized)) {
    return buildRiskAnswer(data);
  }
  return buildGenericAnswer(summary, data);
}

export default function ScreeningChatPanel({ summary, data, loading, onPick }) {
  const [input, setInput] = React.useState("");
  const [settingsOpen, setSettingsOpen] = React.useState(false);
  const [modelSettings, setModelSettings] = React.useState(loadModelSettings);
  const [draftSettings, setDraftSettings] = React.useState(loadModelSettings);
  // Keep this analysis local until a real model endpoint is wired into the app.
  const [messages, setMessages] = React.useState([
    {
      role: "assistant",
      content: "我会先根据当前候选池、评分、价量和入选理由，帮你快速梳理机会、风险和观察重点。",
      picks: [],
    },
  ]);

  React.useEffect(() => {
    if (!settingsOpen) return;
    setDraftSettings(modelSettings);
  }, [modelSettings, settingsOpen]);

  React.useEffect(() => {
    setMessages((current) => {
      if (current.length > 1) return current;
      if (!data.length) return current;
      const intro = buildGenericAnswer(summary, data);
      return [...current, { role: "assistant", content: intro.text, picks: intro.picks }];
    });
  }, [data, summary]);

  const submitPrompt = (promptText) => {
    const prompt = promptText.trim();
    if (!prompt) return;
    const answer = buildAnswer(prompt, summary, data);
    setMessages((current) => [
      ...current,
      { role: "user", content: prompt, picks: [] },
      { role: "assistant", content: answer.text, picks: answer.picks ?? [] },
    ]);
    setInput("");
  };

  const handleProviderChange = (provider) => {
    const nextModel = MODEL_OPTIONS[provider]?.[0]?.value ?? DEFAULT_MODEL_SETTINGS.model;
    setDraftSettings((current) => ({
      ...current,
      provider,
      model: nextModel,
    }));
  };

  const handleSaveSettings = () => {
    const next = {
      ...draftSettings,
      temperature: Number(draftSettings.temperature ?? DEFAULT_MODEL_SETTINGS.temperature),
      maxTokens: Number(draftSettings.maxTokens ?? DEFAULT_MODEL_SETTINGS.maxTokens),
    };
    setModelSettings(next);
    persistModelSettings(next);
    setSettingsOpen(false);
  };

  const modelSummary = `${resolveProviderLabel(modelSettings.provider)} · ${resolveModelLabel(
    modelSettings.provider,
    modelSettings.model
  )}`;

  return (
    <>
      <Card bordered={false} className="screening-chat-card">
        <div className="screening-ai-shell">
          <div className="screening-ai-hero">
            <div className="screening-ai-hero-head">
              <div className="screening-ai-brand">
                <div className="screening-ai-icon">
                  <RobotOutlined />
                </div>
                <div className="screening-ai-copy">
                  <Space size={8} wrap>
                    <Tag color="blue">AI分析</Tag>
                    {loading ? <Tag color="processing">分析中</Tag> : null}
                  </Space>
                  <Title level={3} className="screening-ai-title">
                    您好，需要我帮您分析什么？
                  </Title>
                  <Text className="screening-ai-subtitle">
                    你可以直接提问候选股强弱、入选原因、风险点，或者让我先梳理当前最值得观察的标的。
                  </Text>
                </div>
              </div>

              <Button
                className="screening-ai-model-button"
                icon={<SettingOutlined />}
                onClick={() => setSettingsOpen(true)}
              >
                <span className="screening-ai-model-meta">
                  <span className="screening-ai-model-label">选择模型</span>
                  <span className="screening-ai-model-value">{modelSummary}</span>
                </span>
              </Button>
            </div>

            <div className="screening-ai-prompt-box">
              <Input.TextArea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                autoSize={{ minRows: 3, maxRows: 6 }}
                className="screening-ai-input"
                placeholder="例如：现在最强的3只股票是谁？300827 为什么入选？这批候选股最大的风险是什么？"
                onPressEnter={(event) => {
                  if (!event.shiftKey) {
                    event.preventDefault();
                    submitPrompt(input);
                  }
                }}
              />

              <div className="screening-ai-prompt-actions">
                <Space wrap className="screening-ai-quick-prompts">
                  {QUICK_PROMPTS.map((item) => (
                    <Button
                      key={item}
                      size="small"
                      className="screening-ai-prompt-chip"
                      onClick={() => submitPrompt(item)}
                    >
                      {item}
                    </Button>
                  ))}
                </Space>

                <Button
                  type="primary"
                  size="large"
                  icon={<ThunderboltOutlined />}
                  onClick={() => submitPrompt(input)}
                >
                  开始分析
                </Button>
              </div>
            </div>
          </div>

          <div className="screening-chat-log">
            {messages.map((message, index) => (
              <div key={`${message.role}-${index}`} className={`chat-bubble ${message.role}`}>
                <div className="chat-bubble-head">
                  <Space size={8}>
                    {message.role === "assistant" ? <RobotOutlined /> : <ApiOutlined />}
                    <Text strong>{message.role === "assistant" ? "AI分析" : "你"}</Text>
                  </Space>
                </div>
                <Paragraph className="chat-bubble-content">{message.content}</Paragraph>
                {message.picks?.length ? (
                  <Space wrap>
                    {message.picks.map((item) => (
                      <Button
                        key={item.stock_code}
                        size="small"
                        type="link"
                        onClick={() => onPick(item.stock_code)}
                      >
                        查看 {item.stock_name}（{item.stock_code}）
                      </Button>
                    ))}
                  </Space>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      </Card>

      <Modal
        title="选择模型"
        open={settingsOpen}
        onCancel={() => setSettingsOpen(false)}
        onOk={handleSaveSettings}
        okText="保存配置"
        cancelText="取消"
        destroyOnClose
      >
        <div className="model-settings-grid">
          <div>
            <Text type="secondary">服务商</Text>
            <Select
              value={draftSettings.provider}
              options={PROVIDER_OPTIONS}
              onChange={handleProviderChange}
            />
          </div>

          <div>
            <Text type="secondary">模型</Text>
            <Select
              value={draftSettings.model}
              options={MODEL_OPTIONS[draftSettings.provider] ?? []}
              onChange={(model) => setDraftSettings((current) => ({ ...current, model }))}
            />
          </div>

          <div className="model-settings-span-2">
            <Text type="secondary">API Key</Text>
            <Input.Password
              value={draftSettings.apiKey}
              placeholder="sk-..."
              onChange={(event) =>
                setDraftSettings((current) => ({ ...current, apiKey: event.target.value }))
              }
            />
          </div>

          <div className="model-settings-span-2">
            <Text type="secondary">Base URL</Text>
            <Input
              value={draftSettings.baseUrl}
              placeholder="https://api.openai.com/v1"
              onChange={(event) =>
                setDraftSettings((current) => ({ ...current, baseUrl: event.target.value }))
              }
            />
          </div>

          <div>
            <Text type="secondary">Temperature</Text>
            <InputNumber
              min={0}
              max={2}
              step={0.1}
              value={draftSettings.temperature}
              style={{ width: "100%" }}
              onChange={(value) =>
                setDraftSettings((current) => ({ ...current, temperature: value ?? 0 }))
              }
            />
          </div>

          <div>
            <Text type="secondary">Max Tokens</Text>
            <InputNumber
              min={256}
              step={256}
              value={draftSettings.maxTokens}
              style={{ width: "100%" }}
              onChange={(value) =>
                setDraftSettings((current) => ({ ...current, maxTokens: value ?? 1024 }))
              }
            />
          </div>

          <div className="model-settings-span-2">
            <Text type="secondary">系统提示词</Text>
            <Input.TextArea
              autoSize={{ minRows: 3, maxRows: 6 }}
              value={draftSettings.systemPrompt}
              placeholder="定义 AI 在这里的分析角色和输出风格"
              onChange={(event) =>
                setDraftSettings((current) => ({ ...current, systemPrompt: event.target.value }))
              }
            />
          </div>
        </div>
      </Modal>
    </>
  );
}
