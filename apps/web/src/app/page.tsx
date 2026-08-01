"use client";

import { useQuery } from "@tanstack/react-query";
import { CircleAlert } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import {
  CashflowChart,
  CategoryMoMChart,
  CategoryTrendChart,
  CumulativeCashflowChart,
} from "@/components/charts";
import { PageHeader } from "@/components/page-header";
import { api, type CashflowPoint } from "@/lib/api";
import { useT } from "@/lib/i18n";
import {
  storedValueOneOf,
  useLocalStorageState,
} from "@/hooks/use-local-storage-state";
import { queryKeys } from "@/lib/query-keys";
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
import { DashboardAssetsSummary } from "./_components/dashboard-assets-summary";
import {
  RANGE_MONTHS,
  RANGE_OPTIONS,
  LIMIT_OPTIONS,
  type DashboardLimit,
  type DashboardRange,
} from "./_lib/dashboard-types";

const isDashboardRange = storedValueOneOf(RANGE_OPTIONS);
const isDashboardLimit = storedValueOneOf(LIMIT_OPTIONS);

export default function DashboardPage() {
  const { t } = useT();
  const [range, setRange] = useLocalStorageState<DashboardRange>(
    "finance.dashboard.v2.range",
    "1m",
    { validate: isDashboardRange },
  );
  const [includeTransfers, setIncludeTransfers] = useLocalStorageState(
    "finance.dashboard.v2.includeTransfers",
    false,
  );
  const [chartLimit, setChartLimit] = useLocalStorageState<DashboardLimit>(
    "finance.dashboard.v2.chartLimit",
    8,
    { validate: isDashboardLimit },
  );

  const allData = range === "all";
  const months = RANGE_MONTHS[range];
  const trendMonths = months;
  const comparisonMonths = allData ? months : Math.max(months, 2);
  const periodComparison = range !== "1m";
  const rangeKey = { months, allData, includeTransfers };
  const trendRangeKey = { months: trendMonths, allData, includeTransfers };
  const rankingKey = { ...rangeKey, limit: chartLimit };

  const overview = useQuery({
    queryKey: queryKeys.dashboard.overview(rangeKey),
    queryFn: () => api.overview(months, allData, includeTransfers),
  });
  const currencyStatus = useQuery({
    queryKey: queryKeys.dashboard.currencyStatus,
    queryFn: api.currencyStatus,
  });
  const assetsOverview = useQuery({
    queryKey: queryKeys.assets.overview,
    queryFn: api.assetOverview,
  });
  const reviewQueue = useQuery({
    queryKey: queryKeys.dashboard.reviewQueue(8),
    queryFn: () => api.reviewQueue(8),
  });
  const anomalies = useQuery({
    queryKey: queryKeys.dashboard.anomalies({
      direction: "all",
      reviewState: "pending",
      limit: 5,
    }),
    queryFn: () =>
      api.anomalies({
        direction: "all",
        review_state: "pending",
        limit: 5,
      }),
  });
  const subscriptionsOverview = useQuery({
    queryKey: queryKeys.dashboard.subscriptionsOverview,
    queryFn: () => api.subscriptionsOverview(),
  });
  const cashflow = useQuery({
    queryKey: queryKeys.dashboard.cashflow(rangeKey),
    queryFn: () => api.cashflow(months, allData, includeTransfers),
  });
  const categoryBreakdown = useQuery({
    queryKey: queryKeys.dashboard.categoryBreakdown(rankingKey),
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
    queryKey: queryKeys.dashboard.transactionTypeBreakdown(rankingKey),
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
    queryKey: queryKeys.dashboard.categoryTrend({
      ...trendRangeKey,
      limit: chartLimit,
    }),
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
    queryKey: queryKeys.dashboard.categoryDeltaTrend({
      months: comparisonMonths,
      allData,
      includeTransfers,
      limit: chartLimit,
    }),
    queryFn: () =>
      api.categoryTrend(
        comparisonMonths,
        chartLimit,
        allData,
        "debit",
        includeTransfers,
      ),
  });
  const cumulativeCashflow = useQuery({
    queryKey: queryKeys.dashboard.cumulativeCashflow(trendRangeKey),
    queryFn: () =>
      api.cumulativeCashflow(trendMonths, allData, includeTransfers),
  });
  const topMerchants = useQuery({
    queryKey: queryKeys.dashboard.topMerchants(rankingKey),
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
    queryKey: queryKeys.dashboard.incomeSources(rankingKey),
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
  const overviewData = overview.data;
  const baseCurrency = overviewData?.base_currency ?? "PLN";
  const totalIncome = overviewData ? Number(overviewData.total_income) : 0;
  const totalExpenses = overviewData ? Number(overviewData.total_expenses) : 0;
  const netCashflow = overviewData ? Number(overviewData.net_cashflow) : 0;
  const savingsRate = overviewData ? Number(overviewData.savings_rate) : 0;
  const unconvertedCount = currencyStatus.data?.missing_rate_count ?? 0;
  const cashflowData = normalizeCashflowMonths(cashflow.data ?? [], range, months);
  const categoryTrendsEmpty =
    !categoryDeltaTrend.isLoading &&
    !categoryDeltaTrend.isError &&
    !categoryTrend.isLoading &&
    !categoryTrend.isError &&
    (categoryDeltaTrend.data?.length ?? 0) === 0 &&
    (categoryTrend.data?.length ?? 0) === 0;

  return (
    <div className="space-y-5">
      <PageHeader title={t("nav.dashboard")} />

      <DashboardToolbar
        range={range}
        includeTransfers={includeTransfers}
        chartLimit={chartLimit}
        onRangeChange={setRange}
        onIncludeTransfersChange={setIncludeTransfers}
        onChartLimitChange={setChartLimit}
      />

      {currencyStatus.isError ? (
        <ErrorState
          variant="compact"
          onRetry={() => void currencyStatus.refetch()}
        />
      ) : null}

      {unconvertedCount > 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-300/70 bg-amber-50/60 px-3 py-2 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/25 dark:text-amber-200">
          <CircleAlert className="h-4 w-4 shrink-0" />
          <span>
            {t("dashboard.unconvertedWarning", {
              count: unconvertedCount,
            })}
          </span>
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-6">
          <DashboardSection
            title={t("dashboard.overviewSectionTitle")}
            description={t("dashboard.overviewSectionDescription")}
          >
            {overview.isError ? (
              <ErrorState
                variant="compact"
                onRetry={() => void overview.refetch()}
              />
            ) : (
              <FinancialSnapshot
                income={totalIncome}
                expenses={totalExpenses}
                net={netCashflow}
                savingsRate={savingsRate}
                currency={baseCurrency}
                isLoading={overview.isLoading}
                isFetching={overview.isFetching}
              />
            )}

            <DashboardAssetsSummary
              data={assetsOverview.data}
              isLoading={assetsOverview.isLoading}
              isError={assetsOverview.isError}
              onRetry={() => void assetsOverview.refetch()}
            />

            <ChartCard title={t("dashboard.cashflowTitle")}>
              {cashflow.isLoading ? (
                <ChartSkeleton />
              ) : cashflow.isError ? (
                <ErrorState
                  variant="compact"
                  onRetry={() => void cashflow.refetch()}
                />
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
                isError={categoryBreakdown.isError}
                onRetry={() => void categoryBreakdown.refetch()}
                currency={baseCurrency}
                direction="debit"
              />
              <MerchantRankingCard
                data={topMerchants.data}
                isLoading={topMerchants.isLoading}
                isError={topMerchants.isError}
                onRetry={() => void topMerchants.refetch()}
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
                isError={transactionTypeBreakdown.isError}
                onRetry={() => void transactionTypeBreakdown.refetch()}
                currency={baseCurrency}
                direction="credit"
              />
              <MerchantRankingCard
                data={incomeSources.data}
                isLoading={incomeSources.isLoading}
                isError={incomeSources.isError}
                onRetry={() => void incomeSources.refetch()}
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
              reviewLoading={reviewQueue.isLoading}
              anomaliesLoading={anomalies.isLoading}
              subscriptionsLoading={subscriptionsOverview.isLoading}
              reviewError={reviewQueue.isError}
              anomaliesError={anomalies.isError}
              subscriptionsError={subscriptionsOverview.isError}
              onReviewRetry={() => void reviewQueue.refetch()}
              onAnomaliesRetry={() => void anomalies.refetch()}
              onSubscriptionsRetry={() => void subscriptionsOverview.refetch()}
            />
          </div>

          <DashboardSection
            title={t("dashboard.trends.title")}
            description={t("dashboard.trends.description")}
            separated
          >
            {categoryTrendsEmpty ? (
              <EmptyState
                title={t("dashboard.categoryTrendsEmptyTitle")}
                description={t("dashboard.categoryTrendsEmptyDescription")}
              />
            ) : (
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
                  ) : categoryDeltaTrend.isError ? (
                    <ErrorState
                      variant="compact"
                      onRetry={() => void categoryDeltaTrend.refetch()}
                    />
                  ) : categoryDeltaTrend.data && categoryDeltaTrend.data.length > 0 ? (
                    <CategoryMoMChart
                      data={categoryDeltaTrend.data}
                      currency={baseCurrency}
                      comparisonMode={periodComparison ? "period" : "latest"}
                    />
                  ) : (
                    <EmptyState
                      title={t("dashboard.categoryTrendsEmptyTitle")}
                      description={t("dashboard.categoryTrendsEmptyDescription")}
                    />
                  )}
                </ChartCard>
                <ChartCard title={t("dashboard.categoryTrendTitle")}>
                  {categoryTrend.isLoading ? (
                    <ChartSkeleton />
                  ) : categoryTrend.isError ? (
                    <ErrorState
                      variant="compact"
                      onRetry={() => void categoryTrend.refetch()}
                    />
                  ) : categoryTrend.data && categoryTrend.data.length > 0 ? (
                    <CategoryTrendChart
                      data={categoryTrend.data}
                      currency={baseCurrency}
                    />
                  ) : (
                    <EmptyState
                      title={t("dashboard.categoryTrendsEmptyTitle")}
                      description={t("dashboard.categoryTrendsEmptyDescription")}
                    />
                  )}
                </ChartCard>
              </div>
            )}
            <ChartCard title={t("dashboard.cumulativeCashflowTitle")}>
              {cumulativeCashflow.isLoading ? (
                <ChartSkeleton />
              ) : cumulativeCashflow.isError ? (
                <ErrorState
                  variant="compact"
                  onRetry={() => void cumulativeCashflow.refetch()}
                />
              ) : cumulativeCashflow.data &&
                cumulativeCashflow.data.length > 0 ? (
                <CumulativeCashflowChart
                  data={cumulativeCashflow.data}
                  currency={baseCurrency}
                />
              ) : (
                <EmptyState title={t("common.empty")} />
              )}
            </ChartCard>
          </DashboardSection>
        </div>

        <aside className="hidden min-w-0 xl:block">
          <div className="sticky top-[4.5rem]">
            <AttentionPanel
              reviewRows={reviewQueue.data}
              anomalies={anomalies.data}
              subscriptions={subscriptionsOverview.data}
              reviewLoading={reviewQueue.isLoading}
              anomaliesLoading={anomalies.isLoading}
              subscriptionsLoading={subscriptionsOverview.isLoading}
              reviewError={reviewQueue.isError}
              anomaliesError={anomalies.isError}
              subscriptionsError={subscriptionsOverview.isError}
              onReviewRetry={() => void reviewQueue.refetch()}
              onAnomaliesRetry={() => void anomalies.refetch()}
              onSubscriptionsRetry={() => void subscriptionsOverview.refetch()}
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
