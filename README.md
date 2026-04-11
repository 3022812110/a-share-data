# A 股研究工作台

一个面向个人使用的本地 A 股研究与模拟交易系统，目标是把行情同步、条件选股、研究分析、模拟交易、交易计划和复盘整合到同一个工作台里，逐步训练出可验证的交易规则，而不是直接做自动下单。

## 当前能力

- 全市场股票快照与市场总览
- 我的自选与自定义交易股数
- AI 条件选股
- 单股研究卡与基础回测
- 模拟交易账户、持仓、成交记录
- 交易计划与卖后复盘

## 技术栈

- 后端：Python、FastAPI、SQLite
- 数据：AKShare、baostock、adata、可选 Tushare
- 前端：React、Vite、Ant Design
- 回测：Backtrader

## 目录结构

```text
src/ashare_data/     核心后端逻辑
scripts/             启动与数据同步脚本
frontend/            React 前端
data/                本地 SQLite 数据库（不提交）
web_app.py           早期 Streamlit 入口
```

## 本地启动

### 1. 安装后端依赖

```bash
cd /Users/zhangmi/Desktop/Work/a-share-data
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
cd /Users/zhangmi/Desktop/Work/a-share-data
source .venv/bin/activate
PYTHONPATH=src python scripts/run_api.py
```
默认监听：`http://127.0.0.1:8001`

### 4. 启动前端

```bash
cd /Users/zhangmi/Desktop/Work/a-share-data/frontend
npm install
npm run dev
```

默认地址：`http://127.0.0.1:5173`

## 说明

- `data/market.db` 是本地研究数据库，不应直接提交到仓库。
- `.env.local` 仅用于本机保存私密 token，不应提交到仓库。
- 现阶段系统定位是“研究与模拟训练”，不是自动交易系统。
