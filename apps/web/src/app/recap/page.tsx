"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { CardGridSkeleton } from "@/components/ui/skeleton";
import { useT, tCategory } from "@/lib/i18n";
import { formatCurrency, formatDate, cn } from "@/lib/utils";
import {
  CalendarRange,
  TrendingUp,
  Store,
  AlertTriangle,
} from "lucide-react";

import { Input } from "@/components/ui/input";
import { useLocalStorageState } from "@/hooks/use-local-storage-state";
import { transactionsHref } from "@/lib/transaction-links";

type Period = "week" | "month" | "custom";
type CategoryChangeRow = {
  category: string;
  current: number;
  previous: number;
  delta: number;
};
type TopMerchantRow = {
  merchant: string;
  merchant_display?: string | null;
  merchant_canonical_key?: string | null;
  amount: number;
  count: number;
};

/** Tone for spending deltas: more spending is negative (red), less is green. */
function deltaTone(delta: number): string {
  if (delta > 0) return "text-negative"; // more spending = negative
  if (delta < 0) return "text-positive";
  return "text-muted-foreground";
}

/** Tone for income/net deltas: more is good (green), less is bad (red). */
function gainTone(delta: number): string {
  if (delta > 0) return "text-positive";
  if (delta < 0) return "text-negative";
  return "text-muted-foreground";
}

function previousValue(current: number, delta: number): number {
  return current - delta;
}

export default function RecapPage() {
  const { t } = useT();
  const [period, setPeriod] = useLocalStorageState<Period>(
    "finance.recap.period",
    "month",
  );
  const [dateFrom, setDateFrom] = useLocalStorageState(
    "finance.recap.dateFrom",
    "",
  );
  const [dateTo, setDateTo] = useLocalStorageState(
    "finance.recap.dateTo",
    "",
  );

  const isCustomReady =
    period === "custom" && !!dateFrom && !!dateTo && dateFrom <= dateTo;

  const query = useQuery({
    queryKey: ["recap", period, dateFrom, dateTo],
    queryFn: () =>
      period === "custom"
        ? api.recap("month", dateFrom, dateTo)
        : api.recap(period),
    enabled: period !== "custom" || isCustomReady,
  });
  const categoryChangeColumns: DataTableColumn<CategoryChangeRow>[] = [
    {
      id: "category",
      header: t("transactions.column.category"),
      sortValue: (row) => tCategory(t, row.category),
      cell: (row) => tCategory(t, row.category),
    },
    {
      id: "previous",
      header: t("recap.previous"),
      align: "right",
      className: "tabular-nums text-muted-foreground",
      sortValue: (row) => row.previous,
      cell: (row) => formatCurrency(row.previous),
    },
    {
      id: "current",
      header: t("recap.current"),
      align: "right",
      className: "tabular-nums",
      sortValue: (row) => row.current,
      cell: (row) => formatCurrency(row.current),
    },
    {
      id: "delta",
      header: t("recap.delta"),
      align: "right",
      className: "tabular-nums",
      sortValue: (row) => row.delta,
      cell: (row) => (
        <span className={cn(deltaTone(row.delta))}>
          {row.delta > 0 ? "+" : ""}
          {formatCurrency(row.delta)}
        </span>
      ),
    },
  ];
  const merchantColumns: DataTableColumn<TopMerchantRow>[] = [
    {
      id: "merchant",
      header: t("transactions.column.merchant"),
      sortValue: (row) => row.merchant_display || row.merchant,
      className: "font-medium",
      cell: (row) => (
        <Link
          href={transactionsHref({
            search: row.merchant,
            direction: "debit",
            date_from: query.data?.current_from,
            date_to: query.data?.current_to,
          })}
          className="text-primary underline-offset-4 hover:underline"
        >
          {row.merchant_display || row.merchant}
        </Link>
      ),
    },
    {
      id: "count",
      header: t("recap.count"),
      align: "right",
      className: "tabular-nums text-muted-foreground",
      sortValue: (row) => row.count,
      cell: (row) => row.count,
    },
    {
      id: "amount",
      header: t("transactions.column.amount"),
      align: "right",
      className: "tabular-nums",
      sortValue: (row) => row.amount,
      cell: (row) => formatCurrency(row.amount),
    },
  ];
  return (
    <div className="space-y-6">
      <PageHeader title={t("recap.title")} description={t("recap.subtitle")} />

      <div className="flex flex-wrap items-center gap-3">
        <div className="inline-flex rounded-lg border border-border p-1">
          {(["week", "month", "custom"] as Period[]).map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setPeriod(p)}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm transition-colors",
                period === p
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t(`recap.period.${p}`)}
            </button>
          ))}
        </div>
        {period === "custom" && (
          <div className="flex items-center gap-2">
            <label className="text-xs text-muted-foreground">
              {t("recap.dateFrom")}
            </label>
            <Input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="h-8 w-36 text-xs"
            />
            <span className="text-xs text-muted-foreground">–</span>
            <label className="text-xs text-muted-foreground">
              {t("recap.dateTo")}
            </label>
            <Input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="h-8 w-36 text-xs"
            />
          </div>
        )}
      </div>
      {period !== "custom" ? (
        <p className="text-xs text-muted-foreground">
          {period === "week"
            ? t("recap.periodHelp.week")
            : t("recap.periodHelp.month")}
        </p>
      ) : null}

      {query.isLoading ? (
        <CardGridSkeleton />
      ) : query.isError ? (
        <ErrorState onRetry={() => query.refetch()} />
      ) : !query.data ? (
        <EmptyState title={t("common.empty")} icon={CalendarRange} />
      ) : (
        <div className="space-y-6">
          <div className="rounded-md border bg-muted/20 p-3 text-sm text-muted-foreground">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="inline-flex items-center gap-1.5">
                <CalendarRange className="h-4 w-4" />
                {t("recap.currentRange", {
                  from: formatDate(query.data.current_from),
                  to: formatDate(query.data.current_to),
                })}
              </span>
              <span>
                {t("recap.previousRange", {
                  from: formatDate(query.data.previous_from),
                  to: formatDate(query.data.previous_to),
                })}
              </span>
            </div>
          </div>

          {query.data.cashflow.income === 0 &&
          query.data.cashflow.expenses === 0 ? (
            <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{t("recap.currentEmpty")}</span>
            </div>
          ) : null}

          <div className="grid gap-3 sm:grid-cols-3">
            {(
              [
                [
                  "income",
                  query.data.cashflow.income,
                  query.data.cashflow.income_delta,
                ],
                [
                  "expenses",
                  query.data.cashflow.expenses,
                  query.data.cashflow.expenses_delta,
                ],
                ["net", query.data.cashflow.net, query.data.cashflow.net_delta],
              ] as const
            ).map(([key, value, delta]) => (
              <Card key={key}>
                <CardContent className="space-y-1 p-4">
                  <div className="text-xs text-muted-foreground">
                    {t(`recap.${key}`)}
                  </div>
                  <div className="text-2xl font-semibold tabular-nums">
                    {formatCurrency(value)}
                  </div>
                  <div className="flex flex-wrap gap-x-2 gap-y-0.5 text-xs">
                    <span className="text-muted-foreground">
                      {t("recap.previousShort", {
                        value: formatCurrency(previousValue(value, delta)),
                      })}
                    </span>
                    <span
                      className={cn(
                        "tabular-nums",
                        key === "expenses" ? deltaTone(delta) : gainTone(delta),
                      )}
                    >
                      {t("recap.deltaShort", {
                        value: `${delta >= 0 ? "+" : ""}${formatCurrency(delta)}`,
                      })}
                    </span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base text-foreground">
                  <TrendingUp className="h-4 w-4 text-muted-foreground" />
                  {t("recap.changes.title")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <DataTable
                  columns={categoryChangeColumns}
                  data={query.data.category_changes}
                  rowKey={(row) => row.category}
                  emptyTitle={t("recap.changes.empty")}
                  initialSort={{ id: "delta", dir: "desc" }}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base text-foreground">
                  <Store className="h-4 w-4 text-muted-foreground" />
                  {t("recap.merchants.title")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <DataTable
                  columns={merchantColumns}
                  data={query.data.top_merchants}
                  rowKey={(row) => row.merchant_canonical_key || row.merchant}
                  emptyTitle={t("recap.merchants.empty")}
                  initialSort={{ id: "amount", dir: "desc" }}
                />
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
