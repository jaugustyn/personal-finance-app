"use client";

import { useQuery } from "@tanstack/react-query";

import { EmptyState } from "@/components/empty-state";
import {
  CashflowChart,
  CategoryMoMChart,
  CategoryTrendChart,
  NetWorthChart,
} from "@/components/charts";
import { PageHeader } from "@/components/page-header";
import { api, type CashflowPoint } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { useLocalStorageState } from "@/hooks/use-local-storage-state";
import { AttentionPanel } from "./_components/dashboard-operational";
import { MerchantRankingCard } from "./_components/dashboard-merchant-ranking";
import { FinancialSnapshot } from "./_components/dashboard-snapshot";
import { SpendingBreakdownCard } from "./_components/dashboard-category-panel";
import {
  ChartCard,
  ChartSkeleton,
  DashboardSection,
} from "./_components/dashboard-section";
import { DashboardToolbar } from "./_components/dashboard-toolbar";
import {
  RANGE_MONTHS,
  type DashboardLimit,
  type DashboardRange,
} from "./_lib/dashboard-types";

export default function DashboardPage() {
  const { t } = useT();
  const [range, setRange] = useLocalStorageState<DashboardRange>(
    "finance.dashboard.v2.range",
    "1m",
  );
  const [includeTransfers, setIncludeTransfers] = useLocalStorageState(
    "finance.dashboard.v2.includeTransfers",
    false,
  );
  const [chartLimit, setChartLimit] = useLocalStorageState<DashboardLimit>(
    "finance.dashboard.v2.chartLimit",
    8,
  );

  const allData = range === "all";
  const months = RANGE_MONTHS[range];
  const trendMonths = months;
  const comparisonMonths = allData ? months : Math.max(months, 2);
  const periodComparison = range !== "1m";

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
      includeTransfers,
      chartLimit,
    ],
    queryFn: () =>
      api.byCategory(
        months,
        chartLimit,
        allData,
        "debit",
        includeTransfers,
      ),
  });
  const transactionTypeBreakdown = useQuery({
    queryKey: [
      "dashboard",
      "transactionTypeBreakdown",
      months,
      allData,
      includeTransfers,
      chartLimit,
    ],
    queryFn: () =>
      api.byTransactionType(
        months,
        chartLimit,
        allData,
        "credit",
        includeTransfers,
      ),
  });
  const categoryTrend = useQuery({
    queryKey: [
      "dashboard",
      "categoryTrend",
      trendMonths,
      allData,
      includeTransfers,
      chartLimit,
    ],
    queryFn: () =>
      api.categoryTrend(
        trendMonths,
        chartLimit,
        allData,
        "debit",
        includeTransfers,
      ),
  });
  const categoryDeltaTrend = useQuery({
    queryKey: [
      "dashboard",
      "categoryDeltaTrend",
      comparisonMonths,
      allData,
      includeTransfers,
      chartLimit,
    ],
    queryFn: () =>
      api.categoryTrend(
        comparisonMonths,
        chartLimit,
        allData,
        "debit",
        includeTransfers,
      ),
  });
  const networth = useQuery({
    queryKey: ["dashboard", "networth", trendMonths, allData, includeTransfers],
    queryFn: () => api.networth(trendMonths, allData, includeTransfers),
  });
  const topMerchants = useQuery({
    queryKey: [
      "dashboard",
      "topMerchants",
      months,
      allData,
      includeTransfers,
      chartLimit,
    ],
    queryFn: () =>
      api.topMerchants(
        months,
        chartLimit,
        "amount",
        allData,
        "debit",
        includeTransfers,
      ),
  });
  const incomeSources = useQuery({
    queryKey: [
      "dashboard",
      "incomeSources",
      months,
      allData,
      includeTransfers,
      chartLimit,
    ],
    queryFn: () =>
      api.topMerchants(
        months,
        chartLimit,
        "amount",
        allData,
        "credit",
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

  const overviewData = overview.data;
  const baseCurrency = overviewData?.base_currency ?? "PLN";
  const totalIncome = overviewData ? Number(overviewData.total_income) : 0;
  const totalExpenses = overviewData ? Number(overviewData.total_expenses) : 0;
  const netCashflow = overviewData ? Number(overviewData.net_cashflow) : 0;
  const savingsRate = overviewData ? Number(overviewData.savings_rate) : 0;
  const cashflowData = normalizeCashflowMonths(cashflow.data ?? [], range, months);

  return (
    <div>
      <PageHeader title={t("nav.dashboard")} className="mb-3" />

      <DashboardToolbar
        range={range}
        includeTransfers={includeTransfers}
        chartLimit={chartLimit}
        onRangeChange={setRange}
        onIncludeTransfersChange={setIncludeTransfers}
        onChartLimitChange={setChartLimit}
      />

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <main className="min-w-0 space-y-7">
          <DashboardSection
            title={t("dashboard.overviewSectionTitle")}
            description={t("dashboard.overviewSectionDescription")}
          >
            <FinancialSnapshot
              income={totalIncome}
              expenses={totalExpenses}
              net={netCashflow}
              savingsRate={savingsRate}
              currency={baseCurrency}
              isLoading={overview.isLoading}
              isFetching={overview.isFetching}
            />

            <ChartCard title={t("dashboard.cashflowTitle")}>
              {cashflow.isLoading ? (
                <ChartSkeleton />
              ) : cashflowData.length > 0 ? (
                <CashflowChart data={cashflowData} currency={baseCurrency} />
              ) : (
                <EmptyState title={t("common.empty")} />
              )}
            </ChartCard>

            <div className="grid gap-4 2xl:grid-cols-2">
              <SpendingBreakdownCard
                data={categoryBreakdown.data}
                isLoading={categoryBreakdown.isLoading}
                currency={baseCurrency}
                direction="debit"
              />
              <MerchantRankingCard
                data={topMerchants.data}
                isLoading={topMerchants.isLoading}
                currency={baseCurrency}
                direction="debit"
              />
            </div>
          </DashboardSection>

          <DashboardSection
            title={t("dashboard.incomeSectionTitle")}
            description={t("dashboard.incomeSectionDescription")}
            separated
          >
            <div className="grid gap-4 2xl:grid-cols-2">
              <SpendingBreakdownCard
                data={transactionTypeBreakdown.data}
                isLoading={transactionTypeBreakdown.isLoading}
                currency={baseCurrency}
                direction="credit"
              />
              <MerchantRankingCard
                data={incomeSources.data}
                isLoading={incomeSources.isLoading}
                currency={baseCurrency}
                direction="credit"
              />
            </div>
          </DashboardSection>

          <div className="xl:hidden">
            <AttentionPanel
              reviewRows={reviewQueue.data}
              anomalies={anomalies.data}
              subscriptions={subscriptionsOverview.data}
              baseCurrency={baseCurrency}
              reviewLoading={reviewQueue.isLoading}
              anomaliesLoading={anomalies.isLoading}
              subscriptionsLoading={subscriptionsOverview.isLoading}
            />
          </div>

          <DashboardSection
            title={t("dashboard.trends.title")}
            description={t("dashboard.trends.description")}
            separated
          >
            <div className="grid gap-4 2xl:grid-cols-2">
              <ChartCard
                title={
                  periodComparison
                    ? t("dashboard.periodDeltaTitle")
                    : t("dashboard.momTitle")
                }
              >
                {categoryDeltaTrend.isLoading ? (
                  <ChartSkeleton />
                ) : categoryDeltaTrend.data && categoryDeltaTrend.data.length > 0 ? (
                  <CategoryMoMChart
                    data={categoryDeltaTrend.data}
                    currency={baseCurrency}
                    comparisonMode={periodComparison ? "period" : "latest"}
                  />
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
            </div>
            <ChartCard title={t("dashboard.networthTitle")}>
              {networth.isLoading ? (
                <ChartSkeleton />
              ) : networth.data && networth.data.length > 0 ? (
                <NetWorthChart data={networth.data} currency={baseCurrency} />
              ) : (
                <EmptyState title={t("common.empty")} />
              )}
            </ChartCard>
          </DashboardSection>
        </main>

        <aside className="hidden min-w-0 xl:block">
          <div className="sticky top-[4.5rem]">
            <AttentionPanel
              reviewRows={reviewQueue.data}
              anomalies={anomalies.data}
              subscriptions={subscriptionsOverview.data}
              baseCurrency={baseCurrency}
              reviewLoading={reviewQueue.isLoading}
              anomaliesLoading={anomalies.isLoading}
              subscriptionsLoading={subscriptionsOverview.isLoading}
              layout="rail"
            />
          </div>
        </aside>
      </div>
    </div>
  );
}

function normalizeCashflowMonths(
  data: CashflowPoint[],
  range: DashboardRange,
  months: number,
): CashflowPoint[] {
  if (range === "all") return data;

  const byMonth = new Map(data.map((point) => [monthKey(point.month), point]));
  const currentMonth = new Date();
  currentMonth.setDate(1);

  return Array.from({ length: months }, (_, index) => {
    const offset = months - index - 1;
    const key = monthKey(
      new Date(currentMonth.getFullYear(), currentMonth.getMonth() - offset, 1),
    );
    const point = byMonth.get(key);
    return point
      ? { ...point, month: key }
      : {
          month: key,
          income: 0,
          expenses: 0,
          refunds: 0,
          debt_payments: 0,
          asset_allocations: 0,
          net: 0,
        };
  });
}

function monthKey(value: string | Date): string {
  if (value instanceof Date) {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, "0");
    return `${year}-${month}`;
  }
  return value.slice(0, 7);
}
