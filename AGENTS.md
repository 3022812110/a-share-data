# AI 协作说明

本文件约束所有在本仓库工作的 AI 编程助手。目标是让不同设备、不同会话能够基于同一组事实继续工作，并留下可追溯的项目记录。

## 开始工作前

执行实质性修改前，按顺序阅读：

1. `README.md`
2. `docs/ai/README.md`
3. `docs/ai/project-overview.md`
4. `docs/ai/system-status.md`
5. `docs/ai/worklog.md` 中最近的记录

代码、测试和数据库结构是最终事实来源；文档与代码冲突时，以当前代码为准并修正文档。

## 工作与记录规则

- 完成一项有实际影响的功能、修复或重构后，更新 `docs/ai/system-status.md`。
- 在 `docs/ai/worklog.md` 追加日期、变更事实、影响范围和验证结果。
- 只记录可以从代码、命令结果或明确需求中验证的事实，不记录推测和聊天流水。
- 不在文档中写入 API Token、Cookie、账户密钥、真实券商信息、个人持仓明细或其他隐私数据。
- `data/market.db` 是本地运行数据，不提交；跨设备数据使用项目已有的 `shared-state/market.snapshot` 机制。
- 新增交易建议或执行能力时，默认保持“研究与模拟训练”边界，不接入真实券商自动下单。
- 涉及交易逻辑时，必须考虑行情新鲜度、市场风险、仓位限制、A 股 T+1、涨跌停和费用。

## 开发环境

用户在中国。GitHub、git、curl、npm、yarn、pnpm、pip、brew 等访问国外网络的命令优先设置：

```bash
HTTP_PROXY=http://127.0.0.1:6789
HTTPS_PROXY=http://127.0.0.1:6789
ALL_PROXY=http://127.0.0.1:6789
```

需要查询技术文档时，优先使用 Context7（如果当前会话可用）。未明确要求时，不做移动端模拟器、打包或测试。

## 最低验证要求

按变更范围执行相关检查；提交前通常至少运行：

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
cd frontend && npm run build
git diff --check
```

若某项检查因环境限制无法运行，必须在 `docs/ai/worklog.md` 和交付说明中明确写出原因。
