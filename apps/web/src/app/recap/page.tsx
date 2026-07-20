"use client";

import Link from "next/link";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CalendarRange,
  CircleDollarSign,
  Loader2,
  Scale,
  Store,
  Tags,
} from "lucide-react";

import { DataTable, type DataTableColumn } from "@/components/data-table";
import { DateRangePicker } from "@/components/date-range-picker";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CardGridSkeleton } from "@/components/ui/skeleton";
import { useLocalStorageState } from "@/hooks/use-local-storage-state";
import { api, type Recap } from "@/lib/api";
import { useT, tCategory } from "@/lib/i18n";
import { transactionsHref } from "@/lib/transaction-links";
import { cn, formatCurrency, formatDate, formatNumber } from "@/lib/utils";

type Period = "week" | "month" | "custom";
type CategoryChangeRow = Recap["category_changes"][number];
type MerchantChangeRow = Recap["merchant_changes"][number];

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
    period === "custom" && Boolean(dateFrom && dateTo && dateFrom <= dateTo);

  const query = useQuery({
    queryKey: [
      "recap",
      period,
      period === "custom" ? dateFrom : null,
      period === "custom" ? dateTo : null,
    ],
    queryFn: () =>
      period === "custom"
        ? api.recap("month", dateFrom, dateTo)
        : api.recap(period),
    enabled: period !== "custom" || isCustomReady,
    placeholderData: keepPreviousData,
  });

  const data = query.data;
  const currency = data?.base_currency ?? "PLN";
  const categoryColumns: DataTableColumn<CategoryChangeRow>[] = [
    {
      id: "category",
      header: t("transactions.column.category"),
      sortValue: (row) => tCategory(t, row.category),
      cell: (row) => (
        <Link
          href={transactionsHref({
            category: row.category,
            date_from:
              row.current_count > 0 ? data?.current_from : data?.previous_from,
            date_to: row.current_count > 0 ? data?.current_to : data?.previous_to,
          })}
          className="font-medium text-primary underline-offset-4 hover:underline"
        >
          {tCategory(t, row.category)}
        </Link>
      ),
    },
    amountColumn("previous", t("recap.previous"), currency),
    amountColumn("current", t("recap.current"), currency),
    {
      id: "count",
      header: t("recap.transactionsChange"),
      align: "right",
      className: "tabular-nums text-muted-foreground",
      sortValue: (row) => row.current_count - row.previous_count,
      cell: (row) => `${row.previous_count} → ${row.current_count}`,
    },
    changeColumn(t, currency),
  ];
  const merchantColumns: DataTableColumn<MerchantChangeRow>[] = [
    {
      id: "merchant",
      header: t("transactions.column.merchant"),
      sortValue: (row) => row.merchant_display || row.merchant,
      cell: (row) => (
        <Link
          href={transactionsHref({
            search: row.merchant,
            date_from:
              row.current_count > 0 ? data?.current_from : data?.previous_from,
            date_to: row.current_count > 0 ? data?.current_to : data?.previous_to,
          })}
          className="font-medium text-primary underline-offset-4 hover:underline"
        >
          {row.merchant_display || row.merchant}
        </Link>
      ),
    },
    amountColumn("previous", t("recap.previous"), currency),
    amountColumn("current", t("recap.current"), currency),
    {
      id: "count",
      header: t("recap.transactionsChange"),
      align: "right",
      className: "tabular-nums text-muted-foreground",
      sortValue: (row) => row.current_count - row.previous_count,
      cell: (row) => `${row.previous_count} → ${row.current_count}`,
    },
    changeColumn(t, currency),
  ];

  return (
    <div className="space-y-6">
      <PageHeader title={t("recap.title")} description={t("recap.subtitle")} />

      <section className="rounded-lg border bg-card px-4 py-3">
        <div className="flex flex-wrap items-end gap-4">
          <div className="space-y-1">
            <div className="text-xs font-medium text-muted-foreground">
              {t("recap.analysisRange")}
            </div>
            <div className="inline-flex h-9 items-stretch divide-x divide-border/60 overflow-hidden rounded-md border border-input bg-card">
              {(["week", "month", "custom"] as Period[]).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setPeriod(value)}
                  className={cn(
                    "px-3 text-xs font-medium transition-colors",
                    period === value
                      ? "bg-accent-soft text-accent-soft-foreground"
                      : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                  )}
                >
                  {t(`recap.period.${value}`)}
                </button>
              ))}
            </div>
          </div>
          {period === "custom" && (
            <div className="w-full max-w-sm space-y-1">
              <div className="text-xs font-medium text-muted-foreground">
                {t("recap.customRange")}
              </div>
              <DateRangePicker
                from={dateFrom}
                to={dateTo}
                onFromChange={setDateFrom}
                onToChange={setDateTo}
                onClear={() => {
                  setDateFrom("");
                  setDateTo("");
                }}
                ariaLabel={t("recap.customRange")}
              />
            </div>
          )}
        </div>

        {data && (period !== "custom" || isCustomReady) && (
          <div className="mt-3 flex min-h-8 flex-wrap items-center gap-x-2 gap-y-1 border-t pt-3 text-sm leading-5">
            <CalendarRange className="h-4 w-4 shrink-0 self-center text-muted-foreground" />
            <span className="font-medium tabular-nums text-foreground">
              {formatDate(data.current_from)} – {formatDate(data.current_to)}
            </span>
            <span className="text-muted-foreground" aria-hidden>
              ·
            </span>
            <span className="tabular-nums text-muted-foreground">
              {t("recap.comparedWith")} {formatDate(data.previous_from)} –{" "}
              {formatDate(data.previous_to)}
            </span>
            {query.isFetching && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          </div>
        )}
      </section>

      {period === "custom" && !isCustomReady ? (
        <EmptyState
          title={t("recap.selectRange")}
          description={t("recap.selectRangeHelp")}
          icon={CalendarRange}
        />
      ) : query.isLoading && !data ? (
        <CardGridSkeleton />
      ) : query.isError && !data ? (
        <ErrorState onRetry={() => query.refetch()} />
      ) : !data ? (
        <EmptyState title={t("common.empty")} icon={CalendarRange} />
      ) : (
        <AnalysisContent
          data={data}
          categoryColumns={categoryColumns}
          merchantColumns={merchantColumns}
        />
      )}
    </div>
  );
}

function AnalysisContent({
  data,
  categoryColumns,
  merchantColumns,
}: {
  data: Recap;
  categoryColumns: DataTableColumn<CategoryChangeRow>[];
  merchantColumns: DataTableColumn<MerchantChangeRow>[];
}) {
  const { t } = useT();
  const currency = data.base_currency;
  const noActivity =
    data.cashflow.income === 0 &&
    data.cashflow.expenses === 0 &&
    data.cashflow.debt_payments === 0 &&
    data.cashflow.asset_allocations === 0;

  return (
    <div className="space-y-6">
      {data.unconverted_count > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-300/70 bg-amber-50 px-4 py-3 text-sm text-amber-950 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-100">
          <span className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            {t("recap.unconverted", { count: data.unconverted_count })}
          </span>
          <Link href="/currencies" className="font-medium underline underline-offset-4">
            {t("recap.openCurrencies")}
          </Link>
        </div>
      )}

      {noActivity && (
        <div className="flex items-start gap-2 rounded-lg border px-4 py-3 text-sm text-muted-foreground">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          {t("recap.currentEmpty")}
        </div>
      )}

      <div className="grid gap-3 lg:grid-cols-3">
        <MetricCard
          title={t("recap.income")}
          icon={CircleDollarSign}
          current={data.cashflow.income}
          delta={data.cashflow.income_delta}
          currency={currency}
          positiveIncrease
        />
        <MetricCard
          title={t("recap.expenses")}
          icon={Tags}
          current={data.cashflow.expenses}
          delta={data.cashflow.expenses_delta}
          currency={currency}
          details={
            data.cashflow.refunds > 0
              ? t("recap.expenseDetails", {
                  gross: formatCurrency(data.cashflow.gross_expenses, currency),
                  refunds: formatCurrency(data.cashflow.refunds, currency),
                })
              : undefined
          }
        />
        <MetricCard
          title={t("recap.net")}
          icon={Scale}
          current={data.cashflow.net}
          delta={data.cashflow.net_delta}
          currency={currency}
          positiveIncrease
          details={cashflowDetails(data, t)}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Tags className="h-4 w-4 text-muted-foreground" />
            {t("recap.changes.title")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable
            columns={categoryColumns}
            data={data.category_changes}
            rowKey={(row) => row.category}
            emptyTitle={t("recap.changes.empty")}
            initialSort={{ id: "delta", dir: "desc" }}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Store className="h-4 w-4 text-muted-foreground" />
            {t("recap.merchants.title")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable
            columns={merchantColumns}
            data={data.merchant_changes}
            rowKey={(row) => row.merchant_canonical_key || row.merchant}
            emptyTitle={t("recap.merchants.empty")}
            initialSort={{ id: "delta", dir: "desc" }}
          />
        </CardContent>
      </Card>
    </div>
  );
}

function MetricCard({
  title,
  icon: Icon,
  current,
  delta,
  currency,
  positiveIncrease = false,
  details,
}: {
  title: string;
  icon: typeof CircleDollarSign;
  current: number;
  delta: number;
  currency: string;
  positiveIncrease?: boolean;
  details?: string;
}) {
  const { t } = useT();
  const previous = current - delta;
  const favorable = positiveIncrease ? delta >= 0 : delta <= 0;
  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <Icon className="h-4 w-4" />
          {title}
        </div>
        <div className="text-2xl font-semibold tabular-nums">
          {formatCurrency(current, currency)}
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
          <span className="text-muted-foreground">
            {t("recap.previousShort", {
              value: formatCurrency(previous, currency),
            })}
          </span>
          <span
            className={cn(
              "font-medium tabular-nums",
              delta === 0
                ? "text-muted-foreground"
                : favorable
                  ? "text-positive"
                  : "text-negative",
            )}
          >
            {signedCurrency(delta, currency)}
          </span>
        </div>
        {details && <p className="text-xs text-muted-foreground">{details}</p>}
      </CardContent>
    </Card>
  );
}

function amountColumn<T extends { previous: number; current: number }>(
  key: "previous" | "current",
  header: string,
  currency: string,
): DataTableColumn<T> {
  return {
    id: key,
    header,
    align: "right",
    className: cn("tabular-nums", key === "previous" && "text-muted-foreground"),
    sortValue: (row) => row[key],
    cell: (row) => formatCurrency(row[key], currency),
  };
}

function changeColumn<T extends {
  current: number;
  previous: number;
  delta: number;
  change_percent: number | null;
}>(
  t: ReturnType<typeof useT>["t"],
  currency: string,
): DataTableColumn<T> {
  return {
    id: "delta",
    header: t("recap.delta"),
    align: "right",
    className: "tabular-nums",
    sortValue: (row) => Math.abs(row.delta),
    cell: (row) => (
      <div>
        <div className={cn("font-medium", deltaTone(row.delta))}>
          {signedCurrency(row.delta, currency)}
        </div>
        <div className="text-xs text-muted-foreground">
          {changeDescription(row, t)}
        </div>
      </div>
    ),
  };
}

function changeDescription(
  row: {
    current: number;
    previous: number;
    change_percent: number | null;
  },
  t: ReturnType<typeof useT>["t"],
): string {
  if (row.previous === 0 && row.current !== 0) return t("recap.changeNew");
  if (row.current === 0 && row.previous !== 0) return t("recap.changeAbsent");
  if (row.change_percent === null) return "—";
  const sign = row.change_percent > 0 ? "+" : "";
  return `${sign}${formatNumber(row.change_percent, 1)}%`;
}

function cashflowDetails(data: Recap, t: ReturnType<typeof useT>["t"]): string | undefined {
  const details: string[] = [];
  if (data.cashflow.debt_payments > 0) {
    details.push(
      t("recap.debtDetails", {
        value: formatCurrency(data.cashflow.debt_payments, data.base_currency),
      }),
    );
  }
  if (data.cashflow.asset_allocations > 0) {
    details.push(
      t("recap.assetDetails", {
        value: formatCurrency(data.cashflow.asset_allocations, data.base_currency),
      }),
    );
  }
  return details.length ? details.join(" · ") : undefined;
}

function signedCurrency(value: number, currency: string): string {
  return `${value > 0 ? "+" : ""}${formatCurrency(value, currency)}`;
}

function deltaTone(delta: number): string {
  if (delta > 0) return "text-negative";
  if (delta < 0) return "text-positive";
  return "text-muted-foreground";
}
