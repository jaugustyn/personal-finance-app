"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useMemo, type ComponentType, type ReactNode } from "react";
import {
  AlertTriangle,
  ArrowDownCircle,
  ArrowUpCircle,
  CalendarClock,
  ListChecks,
  Loader2,
  PieChart,
  PiggyBank,
  ReceiptText,
  RotateCcw,
  ShoppingBag,
  Wallet,
} from "lucide-react";
import {
  api,
  type Anomaly,
  type CategoryBreakdown,
  type Direction,
  type MerchantStat,
  type ReviewQueueItem,
  type SubscriptionOverview,
  type SubscriptionUpcomingPayment,
  type Transaction,
} from "@/lib/api";
import { KpiCard } from "@/components/kpi-card";
import { PageHeader } from "@/components/page-header";
import { Money } from "@/components/money";
import { EmptyState } from "@/components/empty-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  CashflowChart,
  CategoryDonut,
  CategoryMoMChart,
  CategoryTrendChart,
  FrequentMerchantsBar,
  NetWorthChart,
  TopMerchantsBar,
} from "@/components/charts";
import { cn, formatCurrency, formatDate, formatPercent } from "@/lib/utils";
import { useT, tCategory } from "@/lib/i18n";
import { useLocalStorageState } from "@/hooks/use-local-storage-state";
import { transactionsHref } from "@/lib/transaction-links";

type DashboardRange = "1m" | "3m" | "6m" | "12m" | "all";
type DashboardDirection = Exclude<Direction, "all">;
type DashboardLimit = 5 | 8 | 12;
type DashboardTab = "overview" | "review" | "explore";

const RANGE_MONTHS: Record<DashboardRange, number> = {
  "1m": 1,
  "3m": 3,
  "6m": 6,
  "12m": 12,
  all: 12,
};
const RANGE_OPTIONS: DashboardRange[] = ["1m", "3m", "6m", "12m", "all"];
const LIMIT_OPTIONS: DashboardLimit[] = [5, 8, 12];

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

function ToolbarGroup({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="min-w-0 space-y-1">
      <div className="px-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="inline-flex max-w-full flex-wrap rounded-lg border bg-background p-1">
        {children}
      </div>
    </div>
  );
}

function ToolbarButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "h-8 rounded-md px-3 text-xs font-medium transition-colors",
        active
          ? "bg-accent text-accent-foreground shadow-sm"
          : "text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

function FilterChip({ label }: { label: string }) {
  return (
    <span className="inline-flex h-7 items-center rounded-md border bg-background px-2.5 text-muted-foreground">
      {label}
    </span>
  );
}

function SectionIntro({
  title,
  description,
  badge,
}: {
  title: string;
  description: string;
  badge: string;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 rounded-lg border bg-muted/30 p-4">
      <div className="min-w-0">
        <h2 className="text-base font-semibold text-foreground">{title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      </div>
      <Badge variant="accent">{badge}</Badge>
    </div>
  );
}

function InsightStrip({
  topCategory,
  topMerchant,
  transactionCount,
  reviewCount,
  anomalyCount,
  baseCurrency,
}: {
  topCategory: CategoryBreakdown | null;
  topMerchant: MerchantStat | null;
  transactionCount: number;
  reviewCount: number;
  anomalyCount: number;
  baseCurrency: string;
}) {
  const { t } = useT();
  return (
    <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
      <InsightItem
        icon={PieChart}
        label={t("dashboard.insight.topCategory")}
        value={
          topCategory?.category
            ? tCategory(t, topCategory.category)
            : t("common.empty")
        }
        detail={
          topCategory
            ? `${formatCurrency(Number(topCategory.amount), baseCurrency)} · ${formatPercent(
                Number(topCategory.share),
              )}`
            : undefined
        }
      />
      <InsightItem
        icon={ShoppingBag}
        label={t("dashboard.insight.topMerchant")}
        value={topMerchant?.merchant ?? t("common.empty")}
        detail={
          topMerchant
            ? formatCurrency(Number(topMerchant.amount), baseCurrency)
            : undefined
        }
      />
      <InsightItem
        icon={ReceiptText}
        label={t("dashboard.insight.transactions")}
        value={String(transactionCount)}
        detail={t("dashboard.insight.transactionsHint")}
      />
      <InsightItem
        icon={ListChecks}
        label={t("dashboard.insight.review")}
        value={String(reviewCount)}
        detail={t("dashboard.insight.reviewHint")}
      />
      <InsightItem
        icon={AlertTriangle}
        label={t("dashboard.insight.alerts")}
        value={String(anomalyCount)}
        detail={t("dashboard.insight.alertsHint")}
      />
    </div>
  );
}

function InsightItem({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <div className="flex min-w-0 items-center gap-3 rounded-lg border bg-card p-3">
      <div
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-md",
          "bg-accent-soft text-accent-soft-foreground",
        )}
      >
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="truncate text-sm font-semibold text-foreground">{value}</div>
        {detail && (
          <div className="truncate text-xs text-muted-foreground">{detail}</div>
        )}
      </div>
    </div>
  );
}

function ChartCard({
  title,
  children,
  className,
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-base text-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function CategoryPanel({
  data,
  isLoading,
  currency,
}: {
  data: CategoryBreakdown[] | undefined;
  isLoading: boolean;
  currency: string;
}) {
  const { t } = useT();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base text-foreground">
          {t("dashboard.byCategoryTitle")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <ChartSkeleton />
        ) : data && data.length > 0 ? (
          <>
            <CategoryDonut data={data} />
            <div className="space-y-2">
              {data.slice(0, 5).map((row) => (
                <div
                  key={row.category ?? "none"}
                  className="flex items-center justify-between gap-3 text-sm"
                >
                  <div className="min-w-0 truncate font-medium">
                    {row.category ? tCategory(t, row.category) : t("common.unknown")}
                  </div>
                  <div className="shrink-0 text-right tabular-nums text-muted-foreground">
                    {formatCurrency(Number(row.amount), currency)}
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <EmptyState title={t("common.empty")} />
        )}
      </CardContent>
    </Card>
  );
}

function OperationalHeader() {
  const { t } = useT();
  return (
    <div className="mb-3 flex items-start justify-between gap-3 xl:mb-0">
      <div>
        <h2 className="text-base font-semibold text-foreground">
          {t("dashboard.section.operational")}
        </h2>
        <p className="text-sm text-muted-foreground">
          {t("dashboard.section.operationalShortHint")}
        </p>
      </div>
      <Badge variant="muted">{t("dashboard.filters.independent")}</Badge>
    </div>
  );
}

function OperationalPanels({
  reviewRows,
  anomalies,
  subscriptions,
  recent,
  baseCurrency,
  reviewLoading,
  anomaliesLoading,
  subscriptionsLoading,
  recentLoading,
  layout,
}: {
  reviewRows: ReviewQueueItem[] | undefined;
  anomalies: Anomaly[] | undefined;
  subscriptions: SubscriptionOverview | undefined;
  recent: Transaction[] | undefined;
  baseCurrency: string;
  reviewLoading: boolean;
  anomaliesLoading: boolean;
  subscriptionsLoading: boolean;
  recentLoading: boolean;
  layout: "rail" | "grid";
}) {
  return (
    <div
      className={cn(
        layout === "grid"
          ? "grid gap-4 md:grid-cols-2 xl:grid-cols-4"
          : "space-y-3",
      )}
    >
      <ReviewPanel rows={reviewRows} isLoading={reviewLoading} />
      <AnomaliesPanel
        rows={anomalies}
        isLoading={anomaliesLoading}
        currency={baseCurrency}
      />
      <UpcomingPanel
        overview={subscriptions}
        isLoading={subscriptionsLoading}
      />
      <RecentPanel rows={recent} isLoading={recentLoading} />
    </div>
  );
}

function ReviewPanel({
  rows,
  isLoading,
}: {
  rows: ReviewQueueItem[] | undefined;
  isLoading: boolean;
}) {
  const { t } = useT();
  return (
    <ListCard
      title={t("dashboard.operational.review")}
      icon={ListChecks}
      href="/review"
      footer={t("dashboard.operational.openReview")}
    >
      {isLoading ? (
        <ListLoading />
      ) : rows && rows.length > 0 ? (
        rows.slice(0, 5).map((row) => (
          <Link
            key={row.transaction_id}
            href={transactionsHref({ view: "review", search: row.merchant || row.title })}
            className="block rounded-md px-2 py-1.5 transition-colors hover:bg-muted"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">
                  {row.merchant || row.title}
                </div>
                <div className="truncate text-xs text-muted-foreground">
                  {row.predicted_category
                    ? tCategory(t, row.predicted_category)
                    : t("review.queue.reason.missing_prediction")}
                </div>
              </div>
              <Money
                amount={Number(row.amount)}
                currency={row.currency}
                direction={row.direction}
                className="shrink-0 text-xs"
              />
            </div>
          </Link>
        ))
      ) : (
        <ListEmpty />
      )}
    </ListCard>
  );
}

function AnomaliesPanel({
  rows,
  isLoading,
  currency,
}: {
  rows: Anomaly[] | undefined;
  isLoading: boolean;
  currency: string;
}) {
  const { t } = useT();
  return (
    <ListCard
      title={t("dashboard.operational.alerts")}
      icon={AlertTriangle}
      href="/anomalies"
      footer={t("dashboard.operational.openAnomalies")}
    >
      {isLoading ? (
        <ListLoading />
      ) : rows && rows.length > 0 ? (
        rows.slice(0, 3).map((row) => (
          <Link
            key={row.id}
            href={transactionsHref({ search: row.merchant || row.title })}
            className="block rounded-md px-2 py-1.5 transition-colors hover:bg-muted"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">
                  {row.merchant || row.title}
                </div>
                <div className="truncate text-xs text-muted-foreground">
                  {row.reasons[0] ?? row.anomaly_type}
                </div>
              </div>
              <div className="shrink-0 text-xs font-medium tabular-nums text-negative">
                {formatCurrency(Number(row.amount), currency)}
              </div>
            </div>
          </Link>
        ))
      ) : (
        <ListEmpty />
      )}
    </ListCard>
  );
}

function UpcomingPanel({
  overview,
  isLoading,
}: {
  overview: SubscriptionOverview | undefined;
  isLoading: boolean;
}) {
  const { t } = useT();
  const rows = overview?.upcoming ?? [];
  return (
    <ListCard
      title={t("dashboard.operational.payments")}
      icon={CalendarClock}
      href="/subscriptions"
      footer={t("dashboard.operational.openSubscriptions")}
    >
      {isLoading ? (
        <ListLoading />
      ) : rows.length > 0 ? (
        rows.slice(0, 3).map((row) => <UpcomingRow key={row.subscription_key} row={row} />)
      ) : (
        <ListEmpty />
      )}
    </ListCard>
  );
}

function UpcomingRow({ row }: { row: SubscriptionUpcomingPayment }) {
  return (
    <Link
      href="/subscriptions"
      className="block rounded-md px-2 py-1.5 transition-colors hover:bg-muted"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">{row.display_name}</div>
          <div className="text-xs text-muted-foreground">
            {formatDate(row.due_date)}
          </div>
        </div>
        <div className="shrink-0 text-xs font-medium tabular-nums">
          {formatCurrency(Number(row.amount_base), row.base_currency)}
        </div>
      </div>
    </Link>
  );
}

function RecentPanel({
  rows,
  isLoading,
}: {
  rows: Transaction[] | undefined;
  isLoading: boolean;
}) {
  const { t } = useT();
  return (
    <ListCard
      title={t("dashboard.recentTitle")}
      icon={ReceiptText}
      href="/transactions"
      footer={t("dashboard.operational.openTransactions")}
    >
      {isLoading ? (
        <ListLoading />
      ) : rows && rows.length > 0 ? (
        rows.slice(0, 5).map((row) => (
          <Link
            key={row.id}
            href={transactionsHref({ search: row.merchant || row.title })}
            className="block rounded-md px-2 py-1.5 transition-colors hover:bg-muted"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">
                  {row.merchant || row.title}
                </div>
                <div className="text-xs text-muted-foreground">
                  {formatDate(row.booking_date)}
                </div>
              </div>
              <Money
                amount={Number(row.amount)}
                currency={row.currency}
                direction={row.direction}
                className="shrink-0 text-xs"
              />
            </div>
          </Link>
        ))
      ) : (
        <ListEmpty />
      )}
    </ListCard>
  );
}

function ListCard({
  title,
  icon: Icon,
  href,
  footer,
  children,
}: {
  title: string;
  icon: ComponentType<{ className?: string }>;
  href: string;
  footer: string;
  children: ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm text-foreground">
          <Icon className="h-4 w-4 text-muted-foreground" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="space-y-1">{children}</div>
        <Button asChild variant="link" size="sm" className="h-auto px-0 text-xs">
          <Link href={href}>{footer}</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

function ContextRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border px-3 py-2">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

function ListLoading() {
  return (
    <div className="flex h-24 items-center justify-center text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />
    </div>
  );
}

function ListEmpty() {
  const { t } = useT();
  return (
    <div className="rounded-md border border-dashed px-3 py-6 text-center text-xs text-muted-foreground">
      {t("common.empty")}
    </div>
  );
}

function ChartSkeleton() {
  return (
    <div className="flex h-72 items-center justify-center text-muted-foreground">
      <Loader2 className="h-5 w-5 animate-spin" />
    </div>
  );
}
