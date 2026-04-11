import { Input, InputNumber, Modal, Select, Typography } from "antd";

import { DEFAULT_MODEL_SETTINGS, MODEL_OPTIONS, PROVIDER_OPTIONS } from "../lib/aiModelSettings";

const { Text } = Typography;

export default function AiModelSettingsModal({
  open,
  draftSettings,
  setDraftSettings,
  onCancel,
  onSave,
}) {
  const handleProviderChange = (provider) => {
    const nextModel = MODEL_OPTIONS[provider]?.[0]?.value ?? DEFAULT_MODEL_SETTINGS.model;
    setDraftSettings((current) => ({
      ...current,
      provider,
      model: nextModel,
    }));
  };

  return (
    <Modal
      title="共享模型设置"
      open={open}
      onCancel={onCancel}
      onOk={onSave}
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
  );
}
