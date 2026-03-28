import React from "react";
import { App as AntApp, Button, Form, Input, InputNumber, Layout, Menu, Modal, Select, Space, Switch, Typography } from "antd";
import {
  BarChartOutlined,
  BankOutlined,
  FundProjectionScreenOutlined,
  ReloadOutlined,
  StarOutlined,
} from "@ant-design/icons";

import { request } from "./lib/api";
import SummaryCards from "./components/SummaryCards";
import MarketOverviewPanel from "./components/MarketOverviewPanel";
import PaperPortfolioPanel from "./components/PaperPortfolioPanel";
import DetailPanel from "./components/DetailPanel";
import StockTable from "./components/StockTable";
import ScreeningTable from "./components/ScreeningTable";
import ScreeningControls from "./components/ScreeningControls";
import ScreeningSummaryCard from "./components/ScreeningSummaryCard";

const { Header, Sider, Content } = Layout;
const { Title, Text } = Typography;

const sortOptions = [
  { value: "change_pct", label: "涨跌幅" },
  { value: "turnover_ratio", label: "换手率" },
  { value: "volume_ratio", label: "量比" },
  { value: "total_market_value", label: "总市值" },
  { value: "buy_distance_pct", label: "距离买入价" },
];

const menuItems = [
  { key: "all", icon: <FundProjectionScreenOutlined />, label: "所有股票" },
  { key: "watch", icon: <StarOutlined />, label: "我的自选" },
  { key: "analysis", icon: <BarChartOutlined />, label: "AI条件选股" },
  { key: "paper", icon: <BankOutlined />, label: "模拟交易" },
];

const screeningDefaults = {
  query: "",
  scope: "all",
  min_change_pct: undefined,
  min_turnover_ratio: undefined,
  min_volume_ratio: undefined,
  min_price: undefined,
  max_price: undefined,
  max_pe_ratio: undefined,
  limit: 80,
};

export default function StockWorkspace() {
  const { message } = AntApp.useApp();
  const [activeMenu, setActiveMenu] = React.useState("all");
  const [summary, setSummary] = React.useState({});
  const [items, setItems] = React.useState([]);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(50);
  const [search, setSearch] = React.useState("");
  const [sortBy, setSortBy] = React.useState("change_pct");
  const [sortOrder, setSortOrder] = React.useState("desc");
  const [watchlistOnly, setWatchlistOnly] = React.useState(false);
  const [selectedCode, setSelectedCode] = React.useState("");
  const [detail, setDetail] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [detailLoading, setDetailLoading] = React.useState(false);
  const [refreshing, setRefreshing] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [screeningPreset, setScreeningPreset] = React.useState("momentum");
  const [screeningFilters, setScreeningFilters] = React.useState(() => ({ ...screeningDefaults }));
  const [screeningData, setScreeningData] = React.useState([]);
  const [screeningSummary, setScreeningSummary] = React.useState(null);
  const [screeningLoading, setScreeningLoading] = React.useState(false);
  const [backtest, setBacktest] = React.useState(null);
  const [backtesting, setBacktesting] = React.useState(false);
  const [paperPortfolio, setPaperPortfolio] = React.useState({ account: {}, positions: [], trades: [] });
  const [paperLoading, setPaperLoading] = React.useState(false);
  const [paperOrdering, setPaperOrdering] = React.useState(false);
  const [planSaving, setPlanSaving] = React.useState(false);
  const [reviewTarget, setReviewTarget] = React.useState(null);
  const [reviewSaving, setReviewSaving] = React.useState(false);
  const [tradeQuantities, setTradeQuantities] = React.useState({});
  const [form] = Form.useForm();
  const [paperForm] = Form.useForm();
  const [reviewForm] = Form.useForm();

  const endpoint = activeMenu === "watch" ? "/api/watchlist" : "/api/stocks";

  const loadSummary = React.useCallback(async () => {
    const data = await request("/api/summary");
    setSummary(data);
  }, []);

  const loadList = React.useCallback(async () => {
    if (activeMenu === "analysis" || activeMenu === "paper") return;
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
        search,
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      if (activeMenu === "all") {
        params.set("watchlist_only", String(watchlistOnly));
      }
      const data = await request(`${endpoint}?${params.toString()}`);
      setItems(data.items ?? []);
      setTotal(data.total ?? 0);
      setTradeQuantities((current) => {
        const next = { ...current };
        for (const item of data.items ?? []) {
          if (next[item.stock_code] === undefined) {
            next[item.stock_code] = item.default_trade_quantity ?? 100;
          }
        }
        return next;
      });
      setSelectedCode((current) => {
        if (current && data.items?.some((item) => item.stock_code === current)) return current;
        return data.items?.[0]?.stock_code ?? "";
      });
    } catch (error) {
      message.error(error.message || "加载列表失败");
    } finally {
      setLoading(false);
    }
  }, [activeMenu, endpoint, message, page, pageSize, search, sortBy, sortOrder, watchlistOnly]);

  const loadPaperPortfolio = React.useCallback(async () => {
    setPaperLoading(true);
    try {
      const data = await request("/api/paper/portfolio");
      setPaperPortfolio(data);
      if (activeMenu === "paper") {
        setSelectedCode((current) => {
          if (current && data.positions?.some((item) => item.stock_code === current)) return current;
          return data.positions?.[0]?.stock_code ?? data.trades?.[0]?.stock_code ?? current;
        });
      }
    } catch (error) {
      message.error(error.message || "加载模拟账户失败");
    } finally {
      setPaperLoading(false);
    }
  }, [activeMenu, message]);

  const loadDetail = React.useCallback(async () => {
    if (!selectedCode) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    try {
      const data = await request(`/api/stocks/${selectedCode}`);
      setDetail(data);
      form.setFieldsValue({
        display_name: data.snapshot?.display_name ?? "",
        notes: data.snapshot?.notes ?? "",
        buy_price: data.snapshot?.buy_price ?? undefined,
        take_profit_price: data.snapshot?.take_profit_price ?? undefined,
        stop_loss_price: data.snapshot?.stop_loss_price ?? undefined,
        default_trade_quantity: data.snapshot?.default_trade_quantity ?? 100,
      });
      paperForm.setFieldsValue({
        quantity: data.snapshot?.default_trade_quantity ?? 100,
        note: "",
        entry_reason: data.snapshot?.paper_entry_reason ?? data.snapshot?.notes ?? "",
        planned_holding_days: data.snapshot?.paper_planned_holding_days ?? undefined,
        plan_stop_loss_price: data.snapshot?.paper_stop_loss_price ?? data.snapshot?.stop_loss_price ?? undefined,
        plan_take_profit_price: data.snapshot?.paper_take_profit_price ?? data.snapshot?.take_profit_price ?? undefined,
        invalidation_condition: data.snapshot?.paper_invalidation_condition ?? "",
        plan_note: data.snapshot?.paper_plan_note ?? "",
      });
    } catch (error) {
      message.error(error.message || "加载股票详情失败");
    } finally {
      setDetailLoading(false);
    }
  }, [form, message, paperForm, selectedCode]);

  const loadScreening = React.useCallback(async () => {
    if (activeMenu !== "analysis") return;
    setScreeningLoading(true);
    try {
      const params = new URLSearchParams({
        preset: screeningPreset,
        scope: screeningFilters.scope,
        limit: String(screeningFilters.limit ?? 80),
      });
      if (screeningFilters.query?.trim()) params.set("query", screeningFilters.query.trim());
      [
        "min_change_pct",
        "min_turnover_ratio",
        "min_volume_ratio",
        "min_price",
        "max_price",
        "max_pe_ratio",
      ].forEach((key) => {
        const value = screeningFilters[key];
        if (value !== undefined && value !== null && value !== "") {
          params.set(key, String(value));
        }
      });
      const data = await request(`/api/screening?${params.toString()}`);
      setScreeningData(data.items ?? []);
      setTradeQuantities((current) => {
        const next = { ...current };
        for (const item of data.items ?? []) {
          if (next[item.stock_code] === undefined) {
            next[item.stock_code] = item.default_trade_quantity ?? 100;
          }
        }
        return next;
      });
      setScreeningSummary(data.summary ?? null);
      setSelectedCode(data.items?.[0]?.stock_code ?? "");
    } catch (error) {
      message.error(error.message || "加载条件选股失败");
    } finally {
      setScreeningLoading(false);
    }
  }, [activeMenu, message, screeningFilters, screeningPreset]);

  React.useEffect(() => {
    loadSummary().catch(() => {});
    loadPaperPortfolio().catch(() => {});
  }, [loadPaperPortfolio, loadSummary]);

  React.useEffect(() => {
    setPage(1);
    setSearch("");
    setSelectedCode("");
  }, [activeMenu]);

  React.useEffect(() => {
    if (activeMenu === "analysis") {
      loadScreening().catch(() => {});
    } else if (activeMenu === "paper") {
      loadPaperPortfolio().catch(() => {});
    } else {
      loadList().catch(() => {});
    }
  }, [activeMenu, loadList, loadPaperPortfolio, loadScreening]);

  React.useEffect(() => {
    loadDetail().catch(() => {});
  }, [loadDetail]);

  React.useEffect(() => {
    setBacktest(null);
  }, [selectedCode]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await request("/api/stocks/refresh", {
        method: "POST",
        body: JSON.stringify({}),
      });
      await Promise.all([loadSummary(), loadList(), loadDetail(), loadScreening()]);
      message.success("全市场快照已刷新");
    } catch (error) {
      message.error(error.message || "刷新失败");
    } finally {
      setRefreshing(false);
    }
  };

  const handleSave = async () => {
    if (!selectedCode) return;
    setSaving(true);
    try {
      const values = await form.validateFields();
      await request(`/api/watchlist/${selectedCode}`, {
        method: "PUT",
        body: JSON.stringify(values),
      });
      await Promise.all([loadSummary(), loadList(), loadDetail(), loadScreening()]);
      message.success("已保存到自选");
    } catch (error) {
      if (!error?.errorFields) {
        message.error(error.message || "保存失败");
      }
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async () => {
    if (!selectedCode) return;
    setSaving(true);
    try {
      await request(`/api/watchlist/${selectedCode}`, { method: "DELETE" });
      await Promise.all([loadSummary(), loadList(), loadDetail(), loadScreening()]);
      message.success("已移除自选");
    } catch (error) {
      message.error(error.message || "删除失败");
    } finally {
      setSaving(false);
    }
  };

  const handleToggleWatchlist = async (record) => {
    try {
      if (record.in_watchlist) {
        await request(`/api/watchlist/${record.stock_code}`, { method: "DELETE" });
        message.success("已移除自选");
      } else {
        await request(`/api/watchlist/${record.stock_code}`, {
          method: "PUT",
          body: JSON.stringify({
            display_name: record.display_name ?? record.stock_name,
            notes: record.notes ?? "",
            buy_price: record.buy_price,
            take_profit_price: record.take_profit_price,
            stop_loss_price: record.stop_loss_price,
            default_trade_quantity: tradeQuantities[record.stock_code] ?? record.default_trade_quantity ?? 100,
          }),
        });
        message.success("已加入自选");
      }
      await Promise.all([loadSummary(), loadList(), loadDetail(), loadScreening()]);
    } catch (error) {
      message.error(error.message || "更新自选失败");
    }
  };

  const handlePaperOrder = async (side) => {
    if (!selectedCode) return;
    setPaperOrdering(true);
    try {
      const values = await paperForm.validateFields();
      const payload = {
        stock_code: selectedCode,
        side,
        quantity: values.quantity,
        note: values.note ?? "",
      };
      if (side === "buy") {
        payload.plan = {
          entry_reason: values.entry_reason,
          planned_holding_days: values.planned_holding_days,
          stop_loss_price: values.plan_stop_loss_price,
          take_profit_price: values.plan_take_profit_price,
          invalidation_condition: values.invalidation_condition,
          plan_note: values.plan_note,
        };
      }
      await request("/api/paper/orders", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await Promise.all([loadPaperPortfolio(), loadDetail()]);
      message.success(side === "buy" ? "模拟买入已记录" : "模拟卖出已记录");
    } catch (error) {
      if (!error?.errorFields) {
        message.error(error.message || "模拟交易失败");
      }
    } finally {
      setPaperOrdering(false);
    }
  };

  const handleQuickTrade = async (stockCode, side, quantity = 100, note = "") => {
    if (!stockCode) return;
    setPaperOrdering(true);
    try {
      const normalizedQuantity = Math.max(100, Number(quantity) || 100);
      const record =
        (detail?.snapshot?.stock_code === stockCode ? detail.snapshot : null)
        ?? items.find((item) => item.stock_code === stockCode)
        ?? screeningData.find((item) => item.stock_code === stockCode)
        ?? paperPortfolio.positions.find((item) => item.stock_code === stockCode)
        ?? paperPortfolio.trades.find((item) => item.stock_code === stockCode);
      const payload = {
        stock_code: stockCode,
        side,
        quantity: normalizedQuantity,
        note,
      };
      if (side === "buy") {
        payload.plan = {
          entry_reason: record?.notes || record?.entry_reason || "快速买入观察",
          planned_holding_days: record?.planned_holding_days || 3,
          stop_loss_price: record?.stop_loss_price,
          take_profit_price: record?.take_profit_price,
          invalidation_condition: record?.invalidation_condition || "跌破止损位、承接走弱或逻辑失效",
          plan_note: note || record?.plan_note || record?.notes || "",
        };
      }
      await request("/api/paper/orders", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setSelectedCode(stockCode);
      await Promise.all([
        loadPaperPortfolio(),
        loadSummary(),
        loadList(),
        loadScreening(),
        selectedCode === stockCode ? loadDetail() : Promise.resolve(),
      ]);
      message.success(side === "buy" ? "模拟买入已记录" : "模拟卖出已记录");
    } catch (error) {
      message.error(error.message || "模拟交易失败");
    } finally {
      setPaperOrdering(false);
    }
  };

  const handleRunBacktest = async () => {
    if (!selectedCode) return;
    setBacktesting(true);
    try {
      const data = await request(`/api/backtest/${selectedCode}`);
      setBacktest(data);
      message.success("回测完成");
    } catch (error) {
      message.error(error.message || "回测失败");
    } finally {
      setBacktesting(false);
    }
  };

  const handleTradeQuantityChange = (stockCode, value) => {
    const normalized = Math.max(100, Number(value) || 100);
    setTradeQuantities((current) => ({
      ...current,
      [stockCode]: normalized,
    }));
  };

  const handleOpenReview = (trade) => {
    setReviewTarget(trade);
    reviewForm.setFieldsValue({
      exit_reason: trade.exit_reason ?? "",
      review_rating: trade.review_rating ?? undefined,
      review_summary: trade.review_summary ?? "",
      lessons_learned: trade.lessons_learned ?? "",
    });
  };

  const handleSaveReview = async () => {
    if (!reviewTarget?.plan_id) return;
    setReviewSaving(true);
    try {
      const values = await reviewForm.validateFields();
      await request(`/api/paper/plans/${reviewTarget.plan_id}/review`, {
        method: "PUT",
        body: JSON.stringify(values),
      });
      await Promise.all([loadPaperPortfolio(), loadDetail()]);
      setReviewTarget(null);
      reviewForm.resetFields();
      message.success("复盘已保存");
    } catch (error) {
      if (!error?.errorFields) {
        message.error(error.message || "保存复盘失败");
      }
    } finally {
      setReviewSaving(false);
    }
  };

  const handleSavePlan = async () => {
    if (!selectedCode) return;
    setPlanSaving(true);
    try {
      const values = await paperForm.validateFields([
        "entry_reason",
        "planned_holding_days",
        "plan_stop_loss_price",
        "plan_take_profit_price",
        "invalidation_condition",
        "plan_note",
      ]);
      await request(`/api/paper/plans/${selectedCode}`, {
        method: "PUT",
        body: JSON.stringify({
          entry_reason: values.entry_reason,
          planned_holding_days: values.planned_holding_days,
          stop_loss_price: values.plan_stop_loss_price,
          take_profit_price: values.plan_take_profit_price,
          invalidation_condition: values.invalidation_condition,
          plan_note: values.plan_note,
        }),
      });
      await Promise.all([loadPaperPortfolio(), loadDetail()]);
      message.success("交易计划已保存");
    } catch (error) {
      if (!error?.errorFields) {
        message.error(error.message || "保存计划失败");
      }
    } finally {
      setPlanSaving(false);
    }
  };

  const updateScreeningField = (field, value) => {
    setScreeningFilters((current) => ({
      ...current,
      [field]: value,
    }));
  };

  const renderToolbar = () => (
    <Space wrap>
      <Input.Search
        allowClear
        placeholder="搜索代码或名称"
        onSearch={(value) => {
          setPage(1);
          setSearch(value);
        }}
        style={{ width: 220 }}
      />
      <Select value={sortBy} options={sortOptions} onChange={setSortBy} style={{ width: 140 }} />
      <Select
        value={sortOrder}
        options={[
          { value: "desc", label: "降序" },
          { value: "asc", label: "升序" },
        ]}
        onChange={setSortOrder}
        style={{ width: 110 }}
      />
      {activeMenu === "all" ? (
        <Space>
          <Text type="secondary">仅看自选</Text>
          <Switch
            checked={watchlistOnly}
            onChange={(checked) => {
              setPage(1);
              setWatchlistOnly(checked);
            }}
          />
        </Space>
      ) : null}
      {activeMenu === "watch" ? (
        <>
          <Button
            type="primary"
            disabled={!selectedCode}
            onClick={() =>
              handleQuickTrade(
                selectedCode,
                "buy",
                tradeQuantities[selectedCode] ?? detail?.snapshot?.default_trade_quantity ?? 100,
                "一键买入当前自选",
              )
            }
            loading={paperOrdering}
          >
            一键买入当前自选
          </Button>
          <Button
            disabled={!selectedCode}
            onClick={() =>
              handleQuickTrade(
                selectedCode,
                "sell",
                tradeQuantities[selectedCode] ?? detail?.snapshot?.default_trade_quantity ?? 100,
                "一键卖出当前自选",
              )
            }
            loading={paperOrdering}
          >
            卖出当前自选
          </Button>
        </>
      ) : null}
    </Space>
  );

  const pageTitle =
    activeMenu === "watch"
      ? "我的自选"
      : activeMenu === "analysis"
        ? "AI条件选股"
        : activeMenu === "paper"
          ? "模拟交易"
          : "所有股票";
  const pageSubtitle =
    activeMenu === "watch"
      ? "这里只显示你主动加入的自选股"
      : activeMenu === "analysis"
        ? "按第一版规则评分筛选强势候选股"
        : activeMenu === "paper"
          ? "默认 20000 元虚拟资金，用来训练你的交易纪律和我的研究能力"
          : "全市场实时快照与个股工作台";

  return (
    <Layout className="app-shell">
      <Sider width={208} breakpoint="lg" collapsedWidth={0} className="app-sider">
        <div className="brand-box">
          <div className="brand-icon">股</div>
          <div>
            <Title level={5} style={{ margin: 0, color: "#0f172a" }}>
              A-Share Data
            </Title>
            <Text type="secondary">股票选股控制台</Text>
          </div>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[activeMenu]}
          items={menuItems}
          className="side-menu"
          onClick={({ key }) => setActiveMenu(key)}
        />
      </Sider>

      <Layout>
        <Header className="top-header">
          <div>
            <Title level={4} style={{ margin: 0 }}>
              {pageTitle}
            </Title>
            <Text type="secondary">{pageSubtitle}</Text>
          </div>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={handleRefresh} loading={refreshing}>
              同步全市场
            </Button>
          </Space>
        </Header>

        <Content className="page-content">
          {activeMenu === "all" ? (
            <>
              <SummaryCards summary={summary} />
              <MarketOverviewPanel summary={summary} />
            </>
          ) : null}

          {activeMenu === "analysis" ? <ScreeningSummaryCard summary={screeningSummary} /> : null}
          {activeMenu === "analysis" ? (
            <ScreeningControls
              screeningPreset={screeningPreset}
              setScreeningPreset={setScreeningPreset}
              screeningFilters={screeningFilters}
              updateScreeningField={updateScreeningField}
              onRun={() => loadScreening()}
              onReset={() => {
                setScreeningPreset("momentum");
                setScreeningFilters({ ...screeningDefaults });
              }}
              screeningLoading={screeningLoading}
            />
          ) : null}

          <div className={`main-grid ${activeMenu !== "all" ? "main-grid-compact" : ""}`}>
            {activeMenu === "analysis" ? (
              <ScreeningTable
                data={screeningData}
                loading={screeningLoading}
                onPick={setSelectedCode}
                onToggleWatchlist={handleToggleWatchlist}
              />
            ) : activeMenu === "paper" ? (
              <PaperPortfolioPanel
                portfolio={paperPortfolio}
                loading={paperLoading}
                onSelectCode={setSelectedCode}
                onOpenReview={handleOpenReview}
              />
            ) : (
              <StockTable
                title={pageTitle}
                items={items}
                total={total}
                loading={loading}
                page={page}
                pageSize={pageSize}
                onPageChange={(nextPage, nextSize) => {
                  setPage(nextPage);
                  setPageSize(nextSize);
                }}
                selectedCode={selectedCode}
                onSelectCode={setSelectedCode}
                onToggleWatchlist={handleToggleWatchlist}
                onQuickTrade={handleQuickTrade}
                tradeQuantities={tradeQuantities}
                onTradeQuantityChange={handleTradeQuantityChange}
                showTradeActions={activeMenu === "watch"}
                controls={renderToolbar()}
              />
            )}

            <div className="detail-column">
              <DetailPanel
                activeMenu={activeMenu}
                detail={detail}
                loading={detailLoading}
                form={form}
                onSave={handleSave}
                onRemove={handleRemove}
                saving={saving}
                onRunBacktest={handleRunBacktest}
                backtest={backtest}
                backtesting={backtesting}
                paperForm={paperForm}
                onPaperOrder={handlePaperOrder}
                onSavePlan={handleSavePlan}
                onQuickTrade={handleQuickTrade}
                paperOrdering={paperOrdering}
                planSaving={planSaving}
                portfolio={paperPortfolio}
              />
            </div>
          </div>
        </Content>
      </Layout>
      <Modal
        title={reviewTarget ? `${reviewTarget.stock_name} 交易复盘` : "交易复盘"}
        open={Boolean(reviewTarget)}
        onCancel={() => {
          setReviewTarget(null);
          reviewForm.resetFields();
        }}
        onOk={handleSaveReview}
        okText="保存复盘"
        cancelText="取消"
        confirmLoading={reviewSaving}
        destroyOnClose
      >
        <Form form={reviewForm} layout="vertical">
          <Form.Item label="卖出原因" name="exit_reason">
            <Input placeholder="例如：到达止盈、趋势转弱、主动止损" />
          </Form.Item>
          <Form.Item label="这笔交易评价" name="review_rating">
            <Select
              allowClear
              options={[
                { value: "good", label: "做得好" },
                { value: "ok", label: "一般" },
                { value: "bad", label: "做得差" },
              ]}
            />
          </Form.Item>
          <Form.Item label="复盘结论" name="review_summary">
            <Input.TextArea rows={3} placeholder="这笔交易的结果和关键判断是否成立" />
          </Form.Item>
          <Form.Item label="下次改进" name="lessons_learned">
            <Input.TextArea rows={3} placeholder="下次遇到同类走势时要注意什么" />
          </Form.Item>
        </Form>
      </Modal>
    </Layout>
  );
}
