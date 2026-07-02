"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import {
  ArrowDownCircle,
  ArrowUpCircle,
  PiggyBank,
  RotateCcw,
  Wallet,
} from "lucide-react";
import { api } from "@/lib/api";
import { KpiCard } from "@/components/kpi-card";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  CashflowChart,
  CategoryMoMChart,
  CategoryTrendChart,
  FrequentMerchantsBar,
  NetWorthChart,
  TopMerchantsBar,
} from "@/components/charts";
import { cn, formatCurrency, formatPercent } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { useLocalStorageState } from "@/hooks/use-local-storage-state";
import { CategoryPanel } from "./_components/dashboard-category-panel";
import { InsightStrip } from "./_components/dashboard-insights";
import {
  OperationalHeader,
  OperationalPanels,
} from "./_components/dashboard-operational";
import {
  ChartCard,
  ChartSkeleton,
  ContextRow,
  SectionIntro,
} from "./_components/dashboard-section";
import {
  FilterChip,
  ToolbarButton,
  ToolbarGroup,
} from "./_components/dashboard-toolbar";
import {
  LIMIT_OPTIONS,
  RANGE_MONTHS,
  RANGE_OPTIONS,
  type DashboardDirection,
  type DashboardLimit,
  type DashboardRange,
  type DashboardTab,
} from "./_lib/dashboard-types";

export default function DashboardPage() {
  const { t } = useT();
  const [range, setRange] = useLocalStorageState<DashboardRange>(
    "finance.dashboard.range",
    "12m",
  );
  const [analysisDirection, setAnalysisDirection] =
    useLocalStorageState<DashboardDirection>(
      "finance.dashboard.analysisDirection",
      "debit",
    );
  const [includeTransfers, setIncludeTransfers] = useLocalStorageState(
    "finance.dashboard.includeTransfers",
    false,
  );
  const [chartLimit, setChartLimit] = useLocalStorageState<DashboardLimit>(
    "finance.dashboard.chartLimit",
    8,
  );
  const [activeTab, setActiveTab] = useLocalStorageState<DashboardTab>(
    "finance.dashboard.tab",
    "overview",
  );

  const allData = range === "all";
  const months = RANGE_MONTHS[range];

  const overview = useQuery({
    queryKey: ["dashboard", "overview", months, allData, includeTransfers],
    queryFn: () => api.overview(months, allData, includeTransfers),
  });
  const cashflow = useQuery({
    queryKey: ["dashboard", "cashflow", months, allData, includeTransfers],
    queryFn: () => api.cashflow(months, allData, includeTransfers),
  });
  const categoryBreakdown = useQuery({
    queryKey: [
      "dashboard",
      "categoryBreakdown",
      months,
      allData,
      analysisDirection,
      includeTransfers,
      chartLimit,
    ],
    queryFn: () =>
      api.byCategory(
        months,
        chartLimit,
        allData,
        analysisDirection,
        includeTransfers,
      ),
  });
  const categoryTrend = useQuery({
    queryKey: [
      "dashboard",
      "categoryTrend",
      months,
      allData,
      analysisDirection,
      includeTransfers,
      chartLimit,
    ],
    queryFn: () =>
      api.categoryTrend(
        months,
        chartLimit,
        allData,
        analysisDirection,
        includeTransfers,
      ),
  });
  const networth = useQuery({
    queryKey: ["dashboard", "networth", months, allData, includeTransfers],
    queryFn: () => api.networth(months, allData, includeTransfers),
  });
  const topMerchants = useQuery({
    queryKey: [
      "dashboard",
      "topMerchants",
      months,
      allData,
      analysisDirection,
      includeTransfers,
      chartLimit,
    ],
    queryFn: () =>
      api.topMerchants(
        months,
        chartLimit,
        "amount",
        allData,
        analysisDirection,
        includeTransfers,
      ),
  });
  const frequentMerchants = useQuery({
    queryKey: [
      "dashboard",
      "frequentMerchants",
      months,
      allData,
      analysisDirection,
      includeTransfers,
      chartLimit,
    ],
    queryFn: () =>
      api.topMerchants(
        months,
        chartLimit,
        "count",
        allData,
        analysisDirection,
        includeTransfers,
      ),
  });
  const reviewQueue = useQuery({
    queryKey: ["dashboard", "reviewQueue"],
    queryFn: () => api.reviewQueue(8),
  });
  const anomalies = useQuery({
    queryKey: ["dashboard", "anomalies"],
    queryFn: () => api.anomalies({ direction: "debit", mode: "review", limit: 5 }),
  });
  const subscriptionsOverview = useQuery({
    queryKey: ["dashboard", "subscriptionsOverview"],
    queryFn: () => api.subscriptionsOverview(),
  });
  const recent = useQuery({
    queryKey: ["dashboard", "recent"],
    queryFn: () => api.transactions({ limit: 6 }),
  });

  const o = overview.data;
  const totalIncome = o ? Number(o.total_income) : 0;
  const totalExpenses = o ? Number(o.total_expenses) : 0;
  const netCashflow = o ? Number(o.net_cashflow) : 0;
  const baseCurrency = o?.base_currency ?? "PLN";
  const averageMonths = allData
    ? Math.max(cashflow.data?.length ?? 0, 1)
    : months;
  const monthlyAvg = o && averageMonths > 0 ? netCashflow / averageMonths : null;
  const topCategory = categoryBreakdown.data?.[0] ?? null;
  const topMerchant = topMerchants.data?.[0] ?? null;
  const reviewCount = reviewQueue.data?.length ?? 0;
  const anomalyCount = anomalies.data?.length ?? 0;
  const defaultFilters =
    range === "12m" &&
    analysisDirection === "debit" &&
    !includeTransfers &&
    chartLimit === 8;

  const sparklines = useMemo(() => {
    const data = cashflow.data ?? [];
    return {
      income: data.map((d) => Number(d.income)),
      expenses: data.map((d) => Number(d.expenses)),
      net: data.map((d) => Number(d.net)),
    };
  }, [cashflow.data]);

  const rangeLabels: Record<DashboardRange, string> = {
    "1m": t("dashboard.range.1m"),
    "3m": t("dashboard.range.3m"),
    "6m": t("dashboard.range.6m"),
    "12m": t("dashboard.range.12m"),
    all: t("dashboard.range.all"),
  };
  const directionLabels: Record<DashboardDirection, string> = {
    debit: t("dashboard.analysis.expenses"),
    credit: t("dashboard.analysis.income"),
  };

  const resetFilters = () => {
    setRange("12m");
    setAnalysisDirection("debit");
    setIncludeTransfers(false);
    setChartLimit(8);
  };

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("nav.dashboard")}
        description={t("dashboard.subtitle")}
      />

      <section
        className={cn(
          "sticky top-3 z-30 rounded-lg border bg-card/95 p-3 shadow-sm backdrop-blur",
          "supports-[backdrop-filter]:bg-card/85",
        )}
      >
        <div className="flex flex-wrap items-end gap-3">
          <ToolbarGroup label={t("dashboard.toolbar.period")}>
            {RANGE_OPTIONS.map((value) => (
              <ToolbarButton
                key={value}
                active={range === value}
                onClick={() => setRange(value)}
              >
                {rangeLabels[value]}
              </ToolbarButton>
            ))}
          </ToolbarGroup>
          <ToolbarGroup label={t("dashboard.toolbar.analysis")}>
            <ToolbarButton
              active={analysisDirection === "debit"}
              onClick={() => setAnalysisDirection("debit")}
            >
              {t("dashboard.analysis.expenses")}
            </ToolbarButton>
            <ToolbarButton
              active={analysisDirection === "credit"}
              onClick={() => setAnalysisDirection("credit")}
            >
              {t("dashboard.analysis.income")}
            </ToolbarButton>
          </ToolbarGroup>
          <ToolbarGroup label={t("dashboard.toolbar.transfers")}>
            <ToolbarButton
              active={!includeTransfers}
              onClick={() => setIncludeTransfers(false)}
            >
              {t("dashboard.transfers.omitted")}
            </ToolbarButton>
            <ToolbarButton
              active={includeTransfers}
              onClick={() => setIncludeTransfers(true)}
            >
              {t("dashboard.transfers.included")}
            </ToolbarButton>
          </ToolbarGroup>
          <ToolbarGroup label={t("dashboard.toolbar.top")}>
            {LIMIT_OPTIONS.map((value) => (
              <ToolbarButton
                key={value}
                active={chartLimit === value}
                onClick={() => setChartLimit(value)}
              >
                {value}
              </ToolbarButton>
            ))}
          </ToolbarGroup>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2 border-t pt-3 text-xs">
          <FilterChip label={rangeLabels[range]} />
          <FilterChip label={directionLabels[analysisDirection]} />
          <FilterChip
            label={
              includeTransfers
                ? t("dashboard.transfers.included")
                : t("dashboard.transfers.omitted")
            }
          />
          <FilterChip label={t("dashboard.filter.top", { n: chartLimit })} />
          <FilterChip
            label={t("dashboard.filter.currency", { currency: baseCurrency })}
          />
          {!defaultFilters && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={resetFilters}
              className="h-7 px-2"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              {t("dashboard.filters.clear")}
            </Button>
          )}
        </div>
      </section>

      <Tabs
        value={activeTab}
        onValueChange={(value) => setActiveTab(value as DashboardTab)}
        className="space-y-4"
      >
        <TabsList className="h-auto flex-wrap justify-start">
          <TabsTrigger value="overview">{t("dashboard.tabs.overview")}</TabsTrigger>
          <TabsTrigger value="review">{t("dashboard.tabs.review")}</TabsTrigger>
          <TabsTrigger value="explore">{t("dashboard.tabs.explore")}</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
            <div className="min-w-0 space-y-4">
              <SectionIntro
                title={t("dashboard.section.analysis")}
                description={t("dashboard.section.analysisHint")}
                badge={
                  defaultFilters
                    ? t("dashboard.filters.default")
                    : t("dashboard.filters.active")
                }
              />

              <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
                <KpiCard
                  label={t("dashboard.kpi.income")}
                  value={o ? formatCurrency(totalIncome, baseCurrency) : "—"}
                  hint={o ? t("dashboard.kpi.txCount", { n: o.tx_count }) : undefined}
                  trend="up"
                  icon={ArrowUpCircle}
                  sparkline={sparklines.income}
                />
                <KpiCard
                  label={t("dashboard.kpi.expenses")}
                  value={o ? formatCurrency(totalExpenses, baseCurrency) : "—"}
                  trend="down"
                  icon={ArrowDownCircle}
                  sparkline={sparklines.expenses}
                />
                <KpiCard
                  label={t("dashboard.kpi.net")}
                  value={o ? formatCurrency(netCashflow, baseCurrency) : "—"}
                  hint={
                    o
                      ? t("dashboard.kpi.savingsHint", {
                          value: formatPercent(Number(o.savings_rate)),
                        })
                      : undefined
                  }
                  trend={o && netCashflow >= 0 ? "up" : "down"}
                  icon={PiggyBank}
                  sparkline={sparklines.net}
                />
                <KpiCard
                  label={t("dashboard.kpi.monthlyAvg")}
                  value={
                    monthlyAvg != null
                      ? formatCurrency(monthlyAvg, baseCurrency)
                      : "—"
                  }
                  icon={Wallet}
                />
              </div>

              <InsightStrip
                topCategory={topCategory}
                topMerchant={topMerchant}
                transactionCount={o?.tx_count ?? 0}
                reviewCount={reviewCount}
                anomalyCount={anomalyCount}
                baseCurrency={baseCurrency}
              />

              <div className="grid gap-4 xl:grid-cols-5">
                <ChartCard
                  title={t("dashboard.cashflowTitle")}
                  className="xl:col-span-3"
                >
                  {cashflow.isLoading ? (
                    <ChartSkeleton />
                  ) : cashflow.data && cashflow.data.length > 0 ? (
                    <CashflowChart data={cashflow.data} currency={baseCurrency} />
                  ) : (
                    <EmptyState title={t("common.empty")} />
                  )}
                </ChartCard>
                <ChartCard
                  title={t("dashboard.momTitle")}
                  className="xl:col-span-2"
                >
                  {categoryTrend.isLoading ? (
                    <ChartSkeleton />
                  ) : categoryTrend.data && categoryTrend.data.length > 0 ? (
                    <CategoryMoMChart
                      data={categoryTrend.data}
                      currency={baseCurrency}
                    />
                  ) : (
                    <EmptyState title={t("common.empty")} />
                  )}
                </ChartCard>
              </div>

              <div className="grid gap-4 xl:grid-cols-2">
                <CategoryPanel
                  data={categoryBreakdown.data}
                  isLoading={categoryBreakdown.isLoading}
                  currency={baseCurrency}
                />
                <ChartCard title={t("dashboard.topMerchantsTitle")}>
                  {topMerchants.isLoading ? (
                    <ChartSkeleton />
                  ) : topMerchants.data && topMerchants.data.length > 0 ? (
                    <TopMerchantsBar
                      data={topMerchants.data}
                      currency={baseCurrency}
                    />
                  ) : (
                    <EmptyState title={t("common.empty")} />
                  )}
                </ChartCard>
              </div>

              <div className="xl:hidden">
                <OperationalHeader />
                <OperationalPanels
                  reviewRows={reviewQueue.data}
                  anomalies={anomalies.data}
                  subscriptions={subscriptionsOverview.data}
                  recent={recent.data}
                  baseCurrency={baseCurrency}
                  reviewLoading={reviewQueue.isLoading}
                  anomaliesLoading={anomalies.isLoading}
                  subscriptionsLoading={subscriptionsOverview.isLoading}
                  recentLoading={recent.isLoading}
                  layout="grid"
                />
              </div>
            </div>

            <aside className="hidden min-w-0 xl:block">
              <div className="sticky top-32 space-y-3">
                <OperationalHeader />
                <OperationalPanels
                  reviewRows={reviewQueue.data}
                  anomalies={anomalies.data}
                  subscriptions={subscriptionsOverview.data}
                  recent={recent.data}
                  baseCurrency={baseCurrency}
                  reviewLoading={reviewQueue.isLoading}
                  anomaliesLoading={anomalies.isLoading}
                  subscriptionsLoading={subscriptionsOverview.isLoading}
                  recentLoading={recent.isLoading}
                  layout="rail"
                />
              </div>
            </aside>
          </div>
        </TabsContent>

        <TabsContent value="review" className="space-y-4">
          <SectionIntro
            title={t("dashboard.section.operational")}
            description={t("dashboard.section.operationalHint")}
            badge={t("dashboard.filters.independent")}
          />
          <OperationalPanels
            reviewRows={reviewQueue.data}
            anomalies={anomalies.data}
            subscriptions={subscriptionsOverview.data}
            recent={recent.data}
            baseCurrency={baseCurrency}
            reviewLoading={reviewQueue.isLoading}
            anomaliesLoading={anomalies.isLoading}
            subscriptionsLoading={subscriptionsOverview.isLoading}
            recentLoading={recent.isLoading}
            layout="grid"
          />
        </TabsContent>

        <TabsContent value="explore" className="space-y-4">
          <SectionIntro
            title={t("dashboard.section.explore")}
            description={t("dashboard.section.exploreHint")}
            badge={directionLabels[analysisDirection]}
          />
          <div className="grid gap-4 xl:grid-cols-2">
            <ChartCard title={t("dashboard.networthTitle")}>
              {networth.isLoading ? (
                <ChartSkeleton />
              ) : networth.data && networth.data.length > 0 ? (
                <NetWorthChart data={networth.data} currency={baseCurrency} />
              ) : (
                <EmptyState title={t("common.empty")} />
              )}
            </ChartCard>
            <ChartCard title={t("dashboard.categoryTrendTitle")}>
              {categoryTrend.isLoading ? (
                <ChartSkeleton />
              ) : categoryTrend.data && categoryTrend.data.length > 0 ? (
                <CategoryTrendChart
                  data={categoryTrend.data}
                  currency={baseCurrency}
                />
              ) : (
                <EmptyState title={t("common.empty")} />
              )}
            </ChartCard>
            <ChartCard title={t("dashboard.frequentTitle")}>
              {frequentMerchants.isLoading ? (
                <ChartSkeleton />
              ) : frequentMerchants.data && frequentMerchants.data.length > 0 ? (
                <FrequentMerchantsBar data={frequentMerchants.data} />
              ) : (
                <EmptyState title={t("common.empty")} />
              )}
            </ChartCard>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  {t("dashboard.explore.contextTitle")}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <ContextRow
                  label={t("dashboard.toolbar.period")}
                  value={rangeLabels[range]}
                />
                <ContextRow
                  label={t("dashboard.toolbar.analysis")}
                  value={directionLabels[analysisDirection]}
                />
                <ContextRow
                  label={t("dashboard.toolbar.transfers")}
                  value={
                    includeTransfers
                      ? t("dashboard.transfers.included")
                      : t("dashboard.transfers.omitted")
                  }
                />
                <ContextRow
                  label={t("dashboard.filter.currencyLabel")}
                  value={baseCurrency}
                />
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
