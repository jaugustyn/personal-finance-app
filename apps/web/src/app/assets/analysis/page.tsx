"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, WalletCards } from "lucide-react";
import { api, type AssetHistoryRange } from "@/lib/api";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { HelpTooltip } from "@/components/help-tooltip";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useFormatters, useT } from "@/lib/i18n";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import { AssetAllocation } from "../_components/asset-allocation";
import { AssetHistoryChart } from "../_components/asset-history-chart";
import { AssetSectionTabs } from "../_components/asset-section-tabs";

export default function AssetAnalysisPage() {
  const { t } = useT();
  const { formatCurrency } = useFormatters();
  const [range, setRange] = useState<AssetHistoryRange>("1y");
  const overviewQuery = useQuery({
    queryKey: queryKeys.assets.overview,
    queryFn: api.assetOverview,
  });
  const accountsQuery = useQuery({
    queryKey: queryKeys.assets.accounts(false),
    queryFn: () => api.assetAccounts(false),
  });
  const historyQuery = useQuery({
    queryKey: queryKeys.assets.history(range),
    queryFn: () => api.assetHistory(range),
  });

  const loading = overviewQuery.isLoading || accountsQuery.isLoading;
  const failed = overviewQuery.isError || accountsQuery.isError;
  const overview = overviewQuery.data;
  const accounts = accountsQuery.data ?? [];
  const points = historyQuery.data?.points ?? [];
  const incompleteValues =
    Boolean(overview?.unconverted_count) ||
    points.some((point) => point.unconverted_count > 0);
  const rangeChange = points.length
    ? Number(points.at(-1)?.amount_pln ?? 0) - Number(points[0]?.amount_pln ?? 0)
    : null;
  const maxAccountValue = Math.max(
    0,
    ...accounts.map((account) => Number(account.amount_pln)),
  );

  return (
    <div className="space-y-6">
      <PageHeader title={t("assets.title")} />
      <AssetSectionTabs />

      {failed ? (
        <ErrorState
          title={t("assets.loadError")}
          onRetry={() => {
            void overviewQuery.refetch();
            void accountsQuery.refetch();
          }}
        />
      ) : loading ? (
        <AnalysisSkeleton />
      ) : !overview || accounts.length === 0 ? (
        <EmptyState
          icon={WalletCards}
          title={t("assets.analyticsEmpty")}
          description={t("assets.analyticsEmptyDescription")}
          action={
            <Button asChild variant="outline">
              <Link href="/assets">
                <ArrowLeft className="h-4 w-4" />
                {t("assets.backToPortfolio")}
              </Link>
            </Button>
          }
        />
      ) : (
        <>
          <section className="rounded-lg border bg-card px-5 py-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <AnalysisMetric
                label={t("assets.totalAssetsValue")}
                value={formatCurrency(Number(overview.total_pln), "PLN")}
              />
              <AnalysisMetric
                label={t("assets.changeInRange")}
                hint={t("assets.changeInRangeHint")}
                value={
                  rangeChange == null
                    ? "—"
                    : formatCurrency(rangeChange, "PLN")
                }
                tone={rangeChange == null ? "neutral" : rangeChange >= 0 ? "positive" : "negative"}
              />
              <AnalysisMetric
                label={t("assets.accountCount")}
                value={String(overview.account_count)}
              />
            </div>
          </section>

          {incompleteValues ? (
            <section className="flex items-start gap-3 rounded-lg border border-warning/35 bg-warning/5 p-4">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
              <p className="text-sm text-foreground">
                {t("assets.analyticsIncompleteValues")}
              </p>
            </section>
          ) : null}

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.7fr)_minmax(18rem,0.8fr)]">
            <Card>
              <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-base font-semibold text-foreground">
                  {t("assets.valueHistory")}
                </CardTitle>
                <div className="inline-flex h-9 items-stretch divide-x divide-border/60 overflow-hidden rounded-md border border-input bg-card">
                  {(["3m", "1y", "all"] as const).map((option) => (
                    <button
                      key={option}
                      type="button"
                      aria-pressed={range === option}
                      className={cn(
                        "relative flex h-full items-center whitespace-nowrap px-3 text-xs font-medium leading-none transition-colors focus-visible:z-10 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                        range === option
                          ? "bg-accent-soft text-accent-soft-foreground"
                          : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                      )}
                      onClick={() => setRange(option)}
                    >
                      {t(`assets.range.${option}`)}
                    </button>
                  ))}
                </div>
              </CardHeader>
              <CardContent>
                {historyQuery.isLoading ? <Skeleton className="h-[280px] w-full" /> : null}
                {historyQuery.isError ? (
                  <ErrorState
                    title={t("assets.historyError")}
                    onRetry={() => void historyQuery.refetch()}
                  />
                ) : null}
                {!historyQuery.isLoading && !historyQuery.isError && points.length === 0 ? (
                  <EmptyState title={t("assets.noHistory")} className="h-[280px] border-0 py-8" />
                ) : null}
                {points.length ? <AssetHistoryChart data={points} /> : null}
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-4">
                <CardTitle className="text-base font-semibold text-foreground">
                  {t("assets.allocation")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <AssetAllocation data={overview.breakdown} />
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="pb-4">
              <CardTitle className="text-base font-semibold text-foreground">
                {t("assets.byAccount")}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {[...accounts]
                .sort((left, right) => Number(right.amount_pln) - Number(left.amount_pln))
                .map((account) => {
                  const amount = Number(account.amount_pln);
                  const width = maxAccountValue > 0 ? (amount / maxAccountValue) * 100 : 0;
                  return (
                    <div key={account.id} className="space-y-2">
                      <div className="flex items-baseline justify-between gap-4 text-sm">
                        <span className="truncate font-medium">{account.name}</span>
                        <span className="shrink-0 tabular-nums">
                          {formatCurrency(amount, "PLN")}
                        </span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                        <div
                          className="h-full rounded-full bg-primary/70"
                          style={{ width: `${Math.max(amount > 0 ? 2 : 0, Math.min(100, width))}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function AnalysisMetric({
  label,
  hint,
  value,
  tone = "neutral",
}: {
  label: string;
  hint?: string;
  value: string;
  tone?: "neutral" | "positive" | "negative";
}) {
  const toneClass =
    tone === "positive"
      ? "text-positive"
      : tone === "negative"
        ? "text-negative"
        : "text-foreground";
  return (
    <div>
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {hint ? (
          <HelpTooltip content={hint}>
            <span>{label}</span>
          </HelpTooltip>
        ) : (
          <span>{label}</span>
        )}
      </div>
      <p className={`mt-1 text-lg font-semibold tabular-nums ${toneClass}`}>{value}</p>
    </div>
  );
}

function AnalysisSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-28 w-full" />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.7fr)_minmax(18rem,0.8fr)]">
        <Skeleton className="h-80 w-full" />
        <Skeleton className="h-80 w-full" />
      </div>
      <Skeleton className="h-48 w-full" />
    </div>
  );
}
