export const MODEL_STORAGE_KEY = "a-share-data.ai-model-settings";

export const PROVIDER_OPTIONS = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "google", label: "Google Gemini" },
  { value: "deepseek", label: "DeepSeek" },
  { value: "ollama", label: "Ollama" },
  { value: "custom", label: "自定义兼容接口" },
];

export const MODEL_OPTIONS = {
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

export const DEFAULT_MODEL_SETTINGS = {
  provider: "openai",
  model: "gpt-5.4",
  apiKey: "",
  baseUrl: "",
  systemPrompt: "你是A股研究助手，优先解释当前候选池的机会、风险和观察重点。",
  temperature: 0.3,
  maxTokens: 4000,
};

export function loadModelSettings() {
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

export function persistModelSettings(settings) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(MODEL_STORAGE_KEY, JSON.stringify(settings));
}

export function resolveProviderLabel(provider) {
  return PROVIDER_OPTIONS.find((item) => item.value === provider)?.label ?? provider;
}

export function resolveModelLabel(provider, model) {
  return MODEL_OPTIONS[provider]?.find((item) => item.value === model)?.label ?? model;
}
