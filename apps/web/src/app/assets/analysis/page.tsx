"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, Info, WalletCards } from "lucide-react";
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
import { assetTypeKey } from "../_lib/asset-options";
import { AssetAllocation } from "../_components/asset-allocation";
import { AssetHistoryChart } from "../_components/asset-history-chart";
import { AssetSectionTabs } from "../_components/asset-section-tabs";

export default function AssetAnalysisPage() {
  const { t } = useT();
  const { formatCurrency, formatDate, formatPercent } = useFormatters();
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
  const points = historyQuery.isError ? [] : (historyQuery.data?.points ?? []);
  const incompleteValues =
    Boolean(overview?.unconverted_count || overview?.missing_valuation_count) ||
    points.some((point) => point.unconverted_count > 0);
  const rangeChange =
    points.length > 1 &&
    !points[0].unconverted_count &&
    !points.at(-1)?.unconverted_count
      ? Number(points.at(-1)?.amount_pln ?? 0) -
        Number(points[0]?.amount_pln ?? 0)
      : null;
  const total = Number(overview?.total_pln ?? 0);
  const byCurrency = new Map<string, number>();
  for (const account of accounts) {
    if (account.tracking_mode === "aggregate") {
      if (account.unconverted_count || account.missing_valuation_count)
        continue;
      const currency = account.native_currency ?? account.default_currency;
      byCurrency.set(
        currency,
        (byCurrency.get(currency) ?? 0) + Number(account.amount_pln),
      );
    } else {
      for (const item of account.items) {
        const value = item.current_value;
        if (value.amount_pln == null || value.unconverted) continue;
        byCurrency.set(
          item.currency,
          (byCurrency.get(item.currency) ?? 0) + Number(value.amount_pln),
        );
      }
    }
  }
  const currencyAllocation = [...byCurrency].map(([currency, amount]) => ({
    key: currency,
    label: currency,
    value: amount,
    share: total > 0 ? amount / total : 0,
  }));

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
          <section className="flex flex-col gap-5 border-b pb-5 pt-1 sm:flex-row sm:flex-wrap sm:items-center sm:gap-8">
            <div>
              <HelpTooltip content={t("assets.estimateBasis")}>
                <p className="w-fit text-sm text-muted-foreground">
                  {t("assets.totalAssetsValue")}
                </p>
              </HelpTooltip>
              <p className="mt-1 text-3xl font-semibold tracking-tight tabular-nums">
                {formatCurrency(total, "PLN")}
              </p>
            </div>
            <div className="border-t pt-4 sm:border-l sm:border-t-0 sm:pl-8 sm:pt-0">
              <HelpTooltip content={t("assets.changeInRangeHint")}>
                <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                  {t("assets.changeInRange")} ({t(`assets.range.${range}`)})
                  <Info className="h-3.5 w-3.5" aria-hidden="true" />
                </span>
              </HelpTooltip>
              {historyQuery.isLoading ? (
                <Skeleton className="mt-2 h-7 w-36" />
              ) : (
                <p
                  className={cn(
                    "mt-1 text-2xl font-semibold tabular-nums",
                    rangeChange && rangeChange > 0
                      ? "text-positive"
                      : rangeChange && rangeChange < 0
                        ? "text-negative"
                        : "text-foreground",
                  )}
                >
                  {rangeChange == null
                    ? "—"
                    : `${rangeChange > 0 ? "+" : ""}${formatCurrency(rangeChange, "PLN")}`}
                </p>
              )}
              {points.length ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  {formatDate(points[0].date)}{" "}
                  <span className="px-1" aria-hidden="true">
                    –
                  </span>{" "}
                  {formatDate(points[points.length - 1].date)}
                </p>
              ) : null}
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

          <Card>
            <CardHeader className="flex-col gap-4 space-y-0 pb-4 sm:flex-row sm:items-center sm:justify-between">
              <CardTitle className="text-base font-semibold text-foreground">
                {t("assets.valueHistory")}
              </CardTitle>
              <div className="inline-flex h-9 w-fit shrink-0 items-stretch divide-x divide-border/60 overflow-hidden rounded-md border border-input bg-card">
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
              {historyQuery.isLoading ? (
                <Skeleton className="h-[280px] w-full" />
              ) : null}
              {historyQuery.isError ? (
                <ErrorState
                  title={t("assets.historyError")}
                  onRetry={() => void historyQuery.refetch()}
                />
              ) : null}
              {!historyQuery.isLoading &&
              !historyQuery.isError &&
              points.length === 0 ? (
                <EmptyState
                  title={t("assets.noHistory")}
                  className="h-[280px] border-0 py-8"
                />
              ) : null}
              {!historyQuery.isLoading &&
              !historyQuery.isError &&
              points.length ? (
                <AssetHistoryChart key={range} data={points} />
              ) : null}
            </CardContent>
          </Card>
          <div className="grid gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader className="pb-4">
                <CardTitle>{t("assets.allocation")}</CardTitle>
                <p className="text-xs text-muted-foreground">
                  {t("assets.typeAllocationHint")}
                </p>
              </CardHeader>
              <CardContent>
                <AssetAllocation
                  data={overview.breakdown.map((row) => ({
                    key: row.asset_type,
                    label: t(assetTypeKey(row.asset_type)),
                    value: Number(row.amount_pln),
                    share: Number(row.share),
                  }))}
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-4">
                <CardTitle>{t("assets.currencyAllocation")}</CardTitle>
                <p className="text-xs text-muted-foreground">
                  {t("assets.currencyAllocationHint")}
                </p>
              </CardHeader>
              <CardContent>
                <AssetAllocation data={currencyAllocation} />
              </CardContent>
            </Card>
          </div>
          <Card>
            <CardHeader className="flex-col gap-3 space-y-0 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-1.5">
                <CardTitle>{t("assets.largestPositions")}</CardTitle>
                <p className="text-xs text-muted-foreground">
                  {t("assets.largestPositionsHint")}
                </p>
              </div>
              <Button asChild variant="ghost" size="sm" className="w-fit">
                <Link href="/assets">{t("assets.fullList")}</Link>
              </Button>
            </CardHeader>
            <CardContent className="divide-y">
              {[...accounts]
                .sort(
                  (left, right) =>
                    Number(right.amount_pln) - Number(left.amount_pln),
                )
                .slice(0, 5)
                .map((account) => {
                  const amount = Number(account.amount_pln);
                  const partial =
                    account.unconverted_count > 0 ||
                    account.missing_valuation_count > 0;
                  const unknown =
                    account.tracking_mode === "aggregate" && partial;
                  const share = total > 0 && !unknown ? amount / total : null;
                  return (
                    <div
                      key={account.id}
                      className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 py-4 first:pt-0 last:pb-0"
                    >
                      <div className="min-w-0">
                        <p className="break-words text-sm font-medium [overflow-wrap:anywhere]">
                          {account.name}
                        </p>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          {account.tracking_mode === "aggregate"
                            ? t(
                                assetTypeKey(
                                  account.aggregate_asset_type ?? "other",
                                ),
                              )
                            : t("assets.summaryPortfolios")}
                        </p>
                      </div>
                      <div className="flex items-center justify-end gap-2 text-right text-sm font-semibold tabular-nums">
                        {unknown ? "—" : formatCurrency(amount, "PLN")}
                        {partial ? (
                          <HelpTooltip content={t("assets.partialGroupTotal")}>
                            <AlertTriangle
                              className="h-3.5 w-3.5 text-warning"
                              aria-label={t("assets.partialGroupTotal")}
                            />
                          </HelpTooltip>
                        ) : null}
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                        <div
                          className="h-full rounded-full bg-primary/70"
                          style={{
                            width: `${Math.max(0, Math.min(100, (share ?? 0) * 100))}%`,
                          }}
                        />
                      </div>
                      <span className="text-right text-xs tabular-nums text-muted-foreground">
                        {share == null ? "—" : formatPercent(share)}
                      </span>
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

function AnalysisSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-96 w-full" />
      <div className="grid gap-6 xl:grid-cols-2">
        <Skeleton className="h-80 w-full" />
        <Skeleton className="h-80 w-full" />
      </div>
      <Skeleton className="h-48 w-full" />
    </div>
  );
}
