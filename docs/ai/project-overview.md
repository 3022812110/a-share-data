# 项目概览

## 项目定位

本项目是面向个人使用的本地 A 股研究与模拟交易工作台，整合行情同步、市场总览、条件选股、个股研究、交易计划、模拟交易和复盘。当前边界是辅助研究与训练可验证的交易规则，不连接真实券商自动下单。

## 技术栈

- 后端：Python 3、FastAPI、SQLite、Uvicorn。
- 数据：AKShare、baostock、adata、东方财富/腾讯公开行情接口，可选 Tushare。
- 分析：pandas、Backtrader，以及项目内实现的技术指标、风控和推荐评估逻辑。
- 前端：React 18、Vite 5、Ant Design、Ant Design Plots、Lightweight Charts。

## 目录结构

```text
src/ashare_data/     核心后端、数据访问、研究和交易逻辑
scripts/             数据初始化、同步、查询和 API 启动脚本
frontend/            React 工作台
tests/               Python unittest 测试
data/                本地 SQLite 运行数据，不提交
shared-state/        跨设备使用的 SQLite 安全快照
docs/ai/             AI 项目概览、当前状态、工作日志与交接模板
web_app.py           早期 Streamlit 入口
```

## 关键后端模块

- `src/ashare_data/api_app.py`：FastAPI 入口和 HTTP 接口。
- `src/ashare_data/db.py`：SQLite 连接、schema 初始化和兼容迁移。
- `src/ashare_data/stock_market.py`：市场总览、全市场股票视图和行情聚合。
- `src/ashare_data/market_refresh_service.py`：行情新鲜度检查与后台补刷。
- `src/ashare_data/screening_ai.py`：自然语言条件选股解释与筛选。
- `src/ashare_data/ai_trade.py`：AI 交易决策、推荐列表和决策证据保存。
- `src/ashare_data/trade_risk.py`：市场硬风控、仓位限制和组合风险诊断。
- `src/ashare_data/recommendation_performance.py`：推荐后 1/3/5/10/20 个交易日表现、MFE/MAE 和策略校准。
- `src/ashare_data/paper_trading.py`：模拟账户、持仓批次、成交、T+1、费用、计划和账户快照。
- `src/ashare_data/backtesting.py`：个股基础回测。
- `src/ashare_data/strategy_lab.py`：趋势跟随、放量突破、超跌修复的参数比较、成交模拟、单股时间切分与多股票滚动样本外验证。
- `src/ashare_data/strategy_prevalidation.py`：推荐候选的后台滚动预验证、24 小时 SQLite 缓存、补位队列和运行进度。
- `src/ashare_data/market_regime.py`：上证指数历史日线缓存、无未来数据的上涨/震荡/下跌分类和实时市场状态映射。
- `src/ashare_data/data_health.py`：数据完整度与新鲜度诊断。

## 关键前端入口

- `frontend/src/StockWorkspace.jsx`：主工作台、功能区路由和数据装配。
- `frontend/src/components/MarketOverviewPanel.jsx`：市场概况。
- `frontend/src/components/ScreeningChatPanel.jsx`：AI 条件选股交互。
- `frontend/src/components/PaperPortfolioPanel.jsx`：模拟账户、风险提示和交易计划。
- `frontend/src/components/RecommendationPerformancePanel.jsx`：AI 推荐表现和策略校准。
- `frontend/src/components/StockDetailPage.jsx`：个股详情、K 线、研究与回测入口。

## 重要数据约定

- SQLite 主库默认是 `data/market.db`，运行中的数据库不提交到 Git。
- 跨设备同步通过 `shared-state/market.snapshot` 完成；它是 SQLite 备份生成的快照，不是运行中的数据库文件。
- `stock_market_snapshot.amount` 按腾讯行情源原始语义保存为“万元”；同步到 `daily_bars.amount` 时必须乘以 `10,000` 转成“元”。
- 行情时间和交易日判断统一按 `Asia/Shanghai` 语义处理。
- 推荐表现按后续交易日收盘价计算，不能把自然日直接当作交易日。
- AI 推荐、决策上下文和组合快照需要持久化，后续评价不得只依赖当前页面状态。
- 策略实验记录保存在 `strategy_experiment_runs`；结果包含数据区间、样本切分、成交假设、候选参数和样本内外指标。
- 多股票稳定性记录保存在 `strategy_stability_runs`；默认股票池按当前持仓、自选、最近推荐和高流动性补充的优先级构建。
- 推荐候选的独立预验证结果保存在 `strategy_candidate_validations`；观察项不会写入 `ai_recommendation_items` 的买入表现样本。
- 上证指数历史日线保存在 `market_index_daily_bars`；推荐批次的策略门控上下文保存在 `ai_recommendation_runs.strategy_context_json`。

## 交易与风险约定

- 市场处于极端风险、核心行情过期或数据不足时，新增买入必须被后端硬阻断；仅靠前端提示不算风控。
- 买入检查必须基于当前账户权益、总仓位和单票仓位，而不是固定金额。
- 模拟交易遵守 A 股 T+1 可卖规则，并计入佣金、印花税和过户费等项目已有费用模型。
- 策略实验使用收盘信号、下一交易日开盘成交，按 100 股整手模拟，并计入滑点、费用和涨跌停阻断。
- 策略参数只能在前 70% 时间样本中选择，后 30% 样本只用于验证；不能根据样本外结果反向调参后仍称其为样本外表现。
- 滚动验证每个窗口只使用此前 180 根日线选参，并在随后 40 根日线上验证；当前最多保留最近 3 个互不重叠的样本外窗口。
- 历史市场状态必须使用样本外窗口开始前的指数数据分类；不能用窗口结束后的指数涨跌反向标注窗口开始时的市场状态。
- AI 推荐中，只有滚动验证稳定且当前市场状态匹配的候选可以生成买入计划；观察、样本不足和未验证候选只能展示为观察，明确失效或状态不匹配必须阻断。
- 风险诊断至少覆盖止损触发、单票集中度、账户回撤和行情新鲜度。
- 推荐评估区分“刚产生、尚无成熟样本”和“样本表现差”，不能把缺少样本解释成策略有效或无效。

## 常用命令

```bash
# 启动后端
PYTHONPATH=src .venv/bin/python scripts/run_api.py

# 启动前端
cd frontend && npm run dev

# 后端测试
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v

# 前端生产构建
cd frontend && npm run build
```
