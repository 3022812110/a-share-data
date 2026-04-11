import React from "react";
import {
  AppstoreOutlined,
  RobotOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { Button, Card, Input, Space, Tag, Typography } from "antd";

import { request, requestStream } from "../lib/api";
import { resolveModelLabel, resolveProviderLabel } from "../lib/aiModelSettings";

const { Text, Paragraph, Title } = Typography;

const QUICK_PROMPTS = [
  "分析一下我最近的几笔交易。",
  "结合我当前持仓，告诉我现在最该处理哪只。",
  "帮我看看最适合买入观察的是哪几只。",
];

const CHAT_STORAGE_KEY = "a-share-data.ai-chat-history.v1";
const MAX_STORED_THREADS = 12;

function loadChatHistory() {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(CHAT_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function persistChatHistory(history) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(history));
}

function mapStockCodesToPicks(stockCodes, data) {
  if (!Array.isArray(stockCodes)) return [];
  const picks = [];
  for (const rawCode of stockCodes) {
    const stockCode = String(rawCode ?? "").trim();
    const match = data.find((item) => item.stock_code === stockCode);
    if (match && !picks.some((item) => item.stock_code === match.stock_code)) {
      picks.push(match);
    }
    if (picks.length >= 5) break;
  }
  return picks;
}

function buildStockUniverse(data, portfolio) {
  const universe = [];
  const seen = new Set();
  for (const item of data ?? []) {
    const stockCode = String(item?.stock_code ?? "").trim();
    if (!stockCode || seen.has(stockCode)) continue;
    seen.add(stockCode);
    universe.push(item);
  }
  for (const item of portfolio?.positions ?? []) {
    const stockCode = String(item?.stock_code ?? "").trim();
    if (!stockCode || seen.has(stockCode)) continue;
    seen.add(stockCode);
    universe.push(item);
  }
  for (const item of portfolio?.trades ?? []) {
    const stockCode = String(item?.stock_code ?? "").trim();
    if (!stockCode || seen.has(stockCode)) continue;
    seen.add(stockCode);
    universe.push(item);
  }
  return universe;
}

function buildChatContextKey(summary, data) {
  const candidateCodes = [...new Set((data ?? []).map((item) => String(item?.stock_code ?? "").trim()).filter(Boolean))]
    .sort()
    .slice(0, 120);
  return JSON.stringify({
    preset: summary?.preset ?? "",
    presetLabel: summary?.preset_label ?? "",
    query: summary?.query ?? "",
    scope: summary?.scope ?? "",
    candidateCodes,
  });
}

function serializeMessages(messages) {
  return messages
    .filter((message) => !message.pending && message.content?.trim())
    .map((message) => ({
      id: message.id,
      role: message.role,
      content: message.content,
      stockCodes: Array.isArray(message.picks)
        ? message.picks.map((item) => item.stock_code).filter(Boolean)
        : [],
    }));
}

function hydrateMessages(storedMessages, data) {
  if (!Array.isArray(storedMessages)) return [];
  return storedMessages
    .map((message, index) => ({
      id: message.id || `restored-${index}`,
      role: message.role === "user" ? "user" : "assistant",
      content: String(message.content || ""),
      picks: mapStockCodesToPicks(message.stockCodes, data),
    }))
    .filter((message) => message.content.trim());
}

export default function ScreeningChatPanel({
  summary,
  data,
  loading,
  modelSettings,
  portfolio,
  onPick,
  onOpenWorkspacePanel,
  onOpenSettings,
}) {
  const [input, setInput] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [messages, setMessages] = React.useState([]);
  const [historyReady, setHistoryReady] = React.useState(false);
  const threadRef = React.useRef(null);
  const shouldAutoScrollRef = React.useRef(true);
  const persistSignatureRef = React.useRef({ contextKey: "", digest: "" });
  const stockUniverse = React.useMemo(() => buildStockUniverse(data, portfolio), [data, portfolio]);
  const screeningKey = React.useMemo(() => buildChatContextKey(summary, data), [summary, data]);

  React.useEffect(() => {
    let cancelled = false;
    setHistoryReady(false);

    const loadHistory = async () => {
      try {
        const remote = await request(`/api/screening/chat/history?context_key=${encodeURIComponent(screeningKey)}`);
        const hydratedRemote = hydrateMessages(remote?.messages, stockUniverse);
        if (!cancelled && hydratedRemote.length) {
          setMessages(hydrateRemote);
          persistSignatureRef.current = {
            contextKey: screeningKey,
            digest: JSON.stringify(serializeMessages(hydrateRemote)),
          };
          shouldAutoScrollRef.current = true;
          setHistoryReady(true);
          return;
        }
      } catch {
        // Ignore and fall back to local cache below.
      }

      const history = loadChatHistory();
      const hydratedLocal = hydrateMessages(history[screeningKey]?.messages, stockUniverse);
      if (!cancelled) {
        setMessages(hydratedLocal);
        persistSignatureRef.current = {
          contextKey: screeningKey,
          digest: JSON.stringify(serializeMessages(hydratedLocal)),
        };
        shouldAutoScrollRef.current = true;
        setHistoryReady(true);
      }
    };

    loadHistory().catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [screeningKey, stockUniverse]);

  React.useEffect(() => {
    const container = threadRef.current;
    if (!container || !shouldAutoScrollRef.current) return;
    window.requestAnimationFrame(() => {
      container.scrollTop = container.scrollHeight;
    });
  }, [messages]);

  React.useEffect(() => {
    if (!historyReady) {
      return;
    }
    const history = loadChatHistory();
    const next = { ...history };
    const serialized = serializeMessages(messages);
    const digest = JSON.stringify(serialized);

    if (serialized.length) {
      next[screeningKey] = {
        updatedAt: Date.now(),
        messages: serialized,
      };
    } else {
      delete next[screeningKey];
    }

    const trimmedEntries = Object.entries(next)
      .sort(([, left], [, right]) => (right?.updatedAt ?? 0) - (left?.updatedAt ?? 0))
      .slice(0, MAX_STORED_THREADS);
    persistChatHistory(Object.fromEntries(trimmedEntries));

    if (
      persistSignatureRef.current.contextKey === screeningKey
      && persistSignatureRef.current.digest === digest
    ) {
      return;
    }

    persistSignatureRef.current = { contextKey: screeningKey, digest };
    const timer = window.setTimeout(() => {
      request("/api/screening/chat/history", {
        method: "PUT",
        body: JSON.stringify({
          contextKey: screeningKey,
          summary,
          messages: serialized,
        }),
      }).catch(() => {});
    }, 280);

    return () => window.clearTimeout(timer);
  }, [historyReady, messages, screeningKey, summary]);

  const handleThreadScroll = () => {
    const container = threadRef.current;
    if (!container) return;
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    shouldAutoScrollRef.current = distanceFromBottom <= 80;
  };

  const submitPrompt = async (promptText) => {
    const prompt = promptText.trim();
    if (!prompt || submitting) return;
    shouldAutoScrollRef.current = true;
    const messageKey = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const userMessage = { id: `user-${messageKey}`, role: "user", content: prompt, picks: [] };
    const pendingMessage = {
      id: `assistant-${messageKey}`,
      role: "assistant",
      content: "",
      picks: [],
      pending: true,
    };
    const chatMessages = [...messages, userMessage].map(({ role, content }) => ({
      role,
      content,
    }));

    setMessages((current) => [...current, userMessage, pendingMessage]);
    setInput("");
    setSubmitting(true);
    try {
      let resolved = false;
      const payload = JSON.stringify({
        summary,
        items: data,
        messages: chatMessages,
        settings: modelSettings,
      });

      const applyDoneMessage = (rawPayload) => {
        resolved = true;
        const content =
          typeof rawPayload?.content === "string" && rawPayload.content.trim()
            ? rawPayload.content.trim()
            : "模型没有返回有效分析。";
        const picks = mapStockCodesToPicks(rawPayload?.stock_codes, stockUniverse);
        setMessages((current) =>
          current.map((item) =>
            item.id === pendingMessage.id
              ? { ...item, content, picks, pending: false }
              : item
          )
        );
      };

      try {
        await requestStream("/api/screening/chat/stream", {
          method: "POST",
          body: payload,
          onEvent: ({ event, data: rawPayload }) => {
            if (event === "delta") {
              const chunk = typeof rawPayload?.content === "string" ? rawPayload.content : "";
              if (!chunk) return;
              setMessages((current) =>
                current.map((item) =>
                  item.id === pendingMessage.id
                    ? { ...item, content: `${item.content || ""}${chunk}` }
                    : item
                )
              );
              return;
            }

            if (event === "done") {
              applyDoneMessage(rawPayload);
              return;
            }

            if (event === "error") {
              resolved = true;
              const content =
                typeof rawPayload?.message === "string" && rawPayload.message.trim()
                  ? `分析失败：${rawPayload.message.trim()}`
                  : "分析失败，请检查模型配置或网络。";
              setMessages((current) =>
                current.map((item) =>
                  item.id === pendingMessage.id
                    ? { ...item, content, picks: [], pending: false }
                    : item
                )
              );
            }
          },
        });
      } catch (error) {
        if (error?.status === 404) {
          const fallback = await request("/api/screening/chat", {
            method: "POST",
            body: payload,
          });
          applyDoneMessage(fallback);
        } else {
          throw error;
        }
      }

      if (!resolved) {
        setMessages((current) =>
          current.map((item) =>
            item.id === pendingMessage.id
              ? {
                  ...item,
                  content: item.content?.trim() ? item.content : "模型没有返回有效分析。",
                  pending: false,
                }
              : item
          )
        );
      }
    } catch (error) {
      const content = error?.message ? `分析失败：${error.message}` : "分析失败，请检查模型配置或网络。";
      setMessages((current) =>
        current.map((item) =>
          item.id === pendingMessage.id
            ? { ...item, content, picks: [], pending: false }
            : item
        )
      );
    } finally {
      setSubmitting(false);
    }
  };

  const modelSummary = `${resolveProviderLabel(modelSettings.provider)} · ${resolveModelLabel(
    modelSettings.provider,
    modelSettings.model
  )}`;
  const hasConversation = messages.length > 0;
  const hasTradeContext = Boolean((portfolio?.positions ?? []).length || (portfolio?.trades ?? []).length);

  return (
    <>
      <Card bordered={false} className="screening-chat-card">
        <div className="screening-ai-shell">
          <div className="screening-chat-topbar">
            <div className="screening-chat-topbar-copy">
              <Space size={8} wrap>
                <Tag color="blue">AI分析</Tag>
                {loading || submitting ? <Tag color="processing">分析中</Tag> : null}
                {summary?.preset_label ? <Tag>{summary.preset_label}</Tag> : null}
                {summary?.returned_count ? <Tag>{summary.returned_count} 只候选</Tag> : null}
                {hasTradeContext ? <Tag color="gold">已接入持仓与成交</Tag> : null}
              </Space>
              {/* <Text className="screening-chat-topbar-hint">
                现在可以直接问候选股、当前持仓、最近交易和复盘，不用再单独去找交易页
              </Text> */}
            </div>

            <Space wrap>
              <Button
                className="screening-ai-model-button"
                icon={<AppstoreOutlined />}
                onClick={onOpenWorkspacePanel}
              >
                <span className="screening-ai-model-meta">
                  <span className="screening-ai-model-label">候选池与设置</span>
                  <span className="screening-ai-model-value">
                    {summary?.preset_label ?? "查看分析范围"}
                  </span>
                </span>
              </Button>
              <Button
                className="screening-ai-model-button"
                icon={<SettingOutlined />}
                onClick={onOpenSettings}
              >
                <span className="screening-ai-model-meta">
                  <span className="screening-ai-model-label">选择模型</span>
                  <span className="screening-ai-model-value">{modelSummary}</span>
                </span>
              </Button>
            </Space>
          </div>

          {!hasConversation ? (
            <div className="screening-chat-empty-state">
              <div className="screening-chat-empty-icon">
                <RobotOutlined />
              </div>
              <div className="screening-chat-empty-copy">
                <Title level={2} className="screening-chat-empty-title">
                  您好，需要我帮您分析什么？
                </Title>
                <Text className="screening-chat-empty-subtitle">
                  你可以直接问候选股强弱，也可以让我分析你的当前持仓、最近成交和该先处理哪一笔交易。
                </Text>
              </div>
              <Space wrap className="screening-chat-empty-prompts">
                {QUICK_PROMPTS.map((item) => (
                  <Button
                    key={item}
                    size="large"
                    className="screening-ai-prompt-chip"
                    disabled={submitting}
                    onClick={() => submitPrompt(item)}
                  >
                    {item}
                  </Button>
                ))}
              </Space>
            </div>
          ) : null}

          <div
            ref={threadRef}
            className="screening-chat-thread"
            onScroll={handleThreadScroll}
          >
            {messages.map((message, index) => (
              <div key={`${message.role}-${index}`} className={`screening-chat-row ${message.role}`}>
                <div className={`screening-chat-avatar ${message.role}`}>
                  {message.role === "assistant" ? <RobotOutlined /> : <UserOutlined />}
                </div>
                <div className={`screening-chat-bubble ${message.role}`}>
                  {message.role === "assistant" || message.pending ? (
                    <div className="screening-chat-bubble-head">
                      {message.role === "assistant" ? <Text strong>AI分析</Text> : null}
                      {message.pending ? <Text type="secondary">正在生成</Text> : null}
                    </div>
                  ) : null}
                  <Paragraph className="screening-chat-bubble-content">{message.content}</Paragraph>
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
              </div>
            ))}
          </div>

          <div className="screening-chat-composer">
            {!hasConversation ? (
              <Text className="screening-chat-composer-hint">
                会基于当前候选池、持仓、最近成交和复盘记录回答，不会脱离你这套本地数据乱发挥。
              </Text>
            ) : null}
            <div className="screening-chat-composer-box">
              <Input.TextArea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                autoSize={{ minRows: 2, maxRows: 6 }}
                className="screening-ai-input"
                placeholder="直接问：分析我最近几笔交易 / 当前持仓风险 / 哪只最该先处理"
                onPressEnter={(event) => {
                  if (!event.shiftKey) {
                    event.preventDefault();
                    submitPrompt(input);
                  }
                }}
              />
              <div className="screening-chat-composer-actions">
                <Space wrap className="screening-ai-quick-prompts">
                  {hasConversation
                    ? QUICK_PROMPTS.map((item) => (
                        <Button
                          key={item}
                          size="small"
                          className="screening-ai-prompt-chip"
                          disabled={submitting}
                          onClick={() => submitPrompt(item)}
                        >
                          {item}
                        </Button>
                      ))
                    : null}
                </Space>
                <Button
                  type="primary"
                  size="large"
                  className="screening-chat-send-button"
                  icon={<ThunderboltOutlined />}
                  loading={submitting}
                  onClick={() => submitPrompt(input)}
                >
                  {hasConversation ? "发送" : "开始分析"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </Card>
    </>
  );
}
