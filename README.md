# A 股研究工作台

一个面向个人使用的本地 A 股研究与模拟交易系统，目标是把行情同步、条件选股、研究分析、模拟交易、交易计划和复盘整合到同一个工作台里，逐步训练出可验证的交易规则，而不是直接做自动下单。

## 当前能力

- 全市场股票快照与市场总览
- 数据健康检查、过期提示与后台自动补刷
- 我的自选与自定义交易股数
- AI 条件选股
- 多周期 K 线、MA / RSI / MACD / BOLL 指标、单股研究卡与多策略样本外验证
- 持仓、自选与候选股票的滚动样本外验证和策略稳定性排行榜
- 基于上证指数历史状态的上涨/震荡/下跌分层，以及策略证据对 AI 推荐的加分、降权和阻断
- 推荐候选后台预验证、24 小时结果缓存和补位式队列；未验证或证据不足的候选只展示为观察
- 模拟交易账户、持仓、成交记录
- 交易计划与卖后复盘

## 技术栈

- 后端：Python、FastAPI、SQLite
- 数据：AKShare、baostock、adata、可选 Tushare
- 前端：React、Vite、Ant Design
- 回测：Backtrader、项目内策略实验室

## 目录结构

```text
src/ashare_data/     核心后端逻辑
scripts/             启动与数据同步脚本
frontend/            React 前端
data/                本地 SQLite 数据库（不提交）
shared-state/        可提交的个人数据安全快照
docs/ai/             AI 项目概览、当前状态、工作日志与交接模板
web_app.py           早期 Streamlit 入口
```

## AI 项目日志

本仓库使用 `docs/ai/` 保存面向 AI 编程助手的项目知识和持续工作记录。新设备或新会话先阅读 [AI 项目日志](docs/ai/README.md)，可以快速了解架构、当前状态、已知风险和最近验证结果。仓库根目录的 `AGENTS.md` 规定了 AI 的协作与维护规则。

## 本地启动

### 1. 安装后端依赖

```bash
cd /path/to/a-share-data
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置可选数据源

如需启用 Tushare，在项目根目录新建 `.env.local`：

```bash
TUSHARE_TOKEN=your_token_here
```

### 3. 启动 API

```bash
cd /path/to/a-share-data
source .venv/bin/activate
PYTHONPATH=src python scripts/run_api.py
```
默认监听：`http://127.0.0.1:8001`

API 启动后会每 3 分钟检查核心行情新鲜度；只有发现全市场快照或主要指数过期时才会自动补刷。可通过 `DISABLE_MARKET_AUTO_REFRESH=1` 关闭。

### 4. 启动前端

```bash
cd /path/to/a-share-data/frontend
npm install
npm run dev
```

默认地址：`http://127.0.0.1:5173`

## 说明

- `data/market.db` 是本地研究数据库，不应直接提交到仓库。
- `shared-state/market.snapshot` 是通过 SQLite 备份生成的个人数据快照，可随代码提交到私有仓库并在另一台电脑恢复；不要直接提交运行中的 `data/market.db`。
- `.env.local` 仅用于本机保存私密 token，不应提交到仓库。
- 现阶段系统定位是“研究与模拟训练”，不是自动交易系统。
