"use client";

import Link from "next/link";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, CalendarRange, Loader2 } from "lucide-react";

import { DataTable, type DataTableColumn } from "@/components/data-table";
import { DateRangePicker } from "@/components/date-range-picker";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { SegmentedControl } from "@/components/segmented-control";
import { Card, CardContent } from "@/components/ui/card";
import { CardGridSkeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  storedValueOneOf,
  useLocalStorageState,
} from "@/hooks/use-local-storage-state";
import { api, type Recap } from "@/lib/api";
import { useFormatters, useT } from "@/lib/i18n";
import type { Formatters } from "@/lib/formatters";
import { transactionsHref } from "@/lib/transaction-links";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import { CategoryChangeList } from "./_components/category-change-list";

type Period = "week" | "month" | "custom";
const isPeriod = storedValueOneOf<Period>(["week", "month", "custom"]);
type MerchantChangeRow = Recap["merchant_changes"][number];

export default function RecapPage() {
  const { t } = useT();
  const formatters = useFormatters();
  const { formatDate } = formatters;
  const [period, setPeriod] = useLocalStorageState<Period>(
    "finance.recap.period",
    "month",
    { validate: isPeriod },
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
    queryKey: queryKeys.recap.detail({
      period,
      dateFrom: period === "custom" ? dateFrom : null,
      dateTo: period === "custom" ? dateTo : null,
    }),
    queryFn: () =>
      period === "custom"
        ? api.recap("month", dateFrom, dateTo)
        : api.recap(period),
    enabled: period !== "custom" || isCustomReady,
    placeholderData: keepPreviousData,
  });

  const data = query.data;
  const currency = data?.base_currency ?? "PLN";
  const merchantColumns: DataTableColumn<MerchantChangeRow>[] = [
    {
      id: "merchant",
      header: t("transactions.column.merchant"),
      headerClassName: "w-[38%]",
      sortValue: (row) => row.merchant_display || row.merchant,
      cell: (row) => (
        <div className="min-w-0">
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
          <p
            className="mt-0.5 flex items-center gap-1.5 text-xs tabular-nums text-muted-foreground"
            aria-label={t("recap.operationsComparison", {
              previous: row.previous_count,
              current: row.current_count,
            })}
          >
            <span>{t("recap.operations")}</span>
            <span>{row.previous_count}</span>
            <ArrowRight className="h-3 w-3 shrink-0" aria-hidden />
            <span className="text-foreground/75">{row.current_count}</span>
          </p>
        </div>
      ),
    },
    amountColumn("current", t("recap.current"), currency, formatters),
    amountColumn("previous", t("recap.previous"), currency, formatters),
    changeColumn(t, currency, formatters),
  ];

  return (
    <div className="space-y-5">
      <PageHeader title={t("recap.title")} />

      <section className="-mx-4 border-y border-border/70 px-4 py-4 sm:-mx-6 sm:px-6">
        <div className="flex flex-wrap items-end gap-4">
          <div className="space-y-1">
            <div className="text-xs font-medium text-muted-foreground">
              {t("recap.analysisRange")}
            </div>
            <SegmentedControl
              value={period}
              options={(["week", "month", "custom"] as Period[]).map(
                (value) => ({
                  value,
                  label: t(`recap.period.${value}`),
                  tooltip: t(`recap.period.${value}Hint`),
                }),
              )}
              onValueChange={(value) => setPeriod(value as Period)}
              ariaLabel={t("recap.analysisRange")}
            />
          </div>
          {period === "custom" && (
            <div className="w-full max-w-[18rem]">
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
          <div className="mt-4 flex min-h-8 flex-wrap items-center gap-x-8 gap-y-2 text-sm leading-5">
            {period !== "custom" && (
              <PeriodRange
                label={t("recap.current")}
                value={`${formatDate(data.current_from)} – ${formatDate(data.current_to)}`}
              />
            )}
            <PeriodRange
              label={period === "custom" ? t("recap.comparedWith") : t("recap.previous")}
              value={`${formatDate(data.previous_from)} – ${formatDate(data.previous_to)}`}
            />
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
          merchantColumns={merchantColumns}
        />
      )}
    </div>
  );
}

function AnalysisContent({
  data,
  merchantColumns,
}: {
  data: Recap;
  merchantColumns: DataTableColumn<MerchantChangeRow>[];
}) {
  const { t } = useT();
  const { formatCurrency } = useFormatters();
  const currency = data.base_currency;

  return (
    <div className="space-y-5">
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

      <div className="grid gap-3 lg:grid-cols-3">
        <MetricCard
          title={t("recap.income")}
          current={data.cashflow.income}
          delta={data.cashflow.income_delta}
          currency={currency}
          positiveIncrease
          deltaWording="amount"
        />
        <MetricCard
          title={t("recap.expenses")}
          tooltip={t("recap.expensesHint")}
          current={data.cashflow.expenses}
          delta={data.cashflow.expenses_delta}
          currency={currency}
          deltaWording="amount"
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
          tooltip={t("recap.netHint")}
          current={data.cashflow.net}
          delta={data.cashflow.net_delta}
          currency={currency}
          positiveIncrease
          deltaWording="balance"
          details={[
            data.cashflow.debt_payments > 0
              ? t("recap.debtDetails", {
                  value: formatCurrency(data.cashflow.debt_payments, currency),
                })
              : null,
            data.cashflow.asset_allocations > 0
              ? t("recap.assetDetails", {
                  value: formatCurrency(data.cashflow.asset_allocations, currency),
                })
              : null,
          ]
            .filter(Boolean)
            .join(" · ")}
        />
      </div>

      <section className="space-y-3">
        <div className="flex min-h-9 items-center">
          <h2 className="text-base font-semibold">{t("recap.changes.title")}</h2>
        </div>
        <CategoryChangeList
          data={data.category_changes}
          currency={currency}
          currentFrom={data.current_from}
          currentTo={data.current_to}
          previousFrom={data.previous_from}
          previousTo={data.previous_to}
        />
      </section>

      <section className="space-y-3">
        <div className="flex min-h-9 items-center">
          <h2 className="text-base font-semibold">{t("recap.merchants.title")}</h2>
        </div>
        <DataTable
          columns={merchantColumns}
          data={data.merchant_changes}
          rowKey={(row) => row.merchant_canonical_key || row.merchant}
          emptyTitle={t("recap.merchants.empty")}
          initialSort={{ id: "delta", dir: "desc" }}
          tableClassName="min-w-[38rem]"
        />
      </section>
    </div>
  );
}

function PeriodRange({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <span className="font-medium tabular-nums text-foreground">{value}</span>
    </div>
  );
}

function MetricCard({
  title,
  tooltip,
  current,
  delta,
  currency,
  positiveIncrease = false,
  deltaWording,
  details,
}: {
  title: string;
  tooltip?: string;
  current: number;
  delta: number;
  currency: string;
  positiveIncrease?: boolean;
  deltaWording: "amount" | "balance";
  details?: string;
}) {
  const { t } = useT();
  const { formatCurrency } = useFormatters();
  const favorable = positiveIncrease ? delta >= 0 : delta <= 0;
  const deltaText =
    delta === 0
      ? t("recap.metric.unchanged")
      : t(
          deltaWording === "balance"
            ? delta > 0
              ? "recap.metric.higher"
              : "recap.metric.lower"
            : delta > 0
              ? "recap.metric.more"
              : "recap.metric.less",
          { value: formatCurrency(Math.abs(delta), currency) },
        );
  return (
    <Card>
      <CardContent className="p-4">
        {tooltip ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <span
                tabIndex={0}
                className="cursor-help text-sm font-medium text-muted-foreground outline-none focus-visible:text-foreground"
              >
                {title}
              </span>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs text-pretty leading-relaxed">
              {tooltip}
            </TooltipContent>
          </Tooltip>
        ) : (
          <div className="text-sm font-medium text-muted-foreground">{title}</div>
        )}
        <div className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">
          {formatCurrency(current, currency)}
        </div>
        <div className="mt-1.5 text-xs">
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
            {deltaText}
          </span>
        </div>
        {details ? <p className="mt-1.5 text-xs text-muted-foreground">{details}</p> : null}
      </CardContent>
    </Card>
  );
}

function amountColumn<T extends { previous: number; current: number }>(
  key: "previous" | "current",
  header: string,
  currency: string,
  formatters: Formatters,
): DataTableColumn<T> {
  return {
    id: key,
    header,
    align: "right",
    headerClassName: "text-right",
    className: cn("tabular-nums", key === "previous" && "text-muted-foreground"),
    sortValue: (row) => row[key],
    cell: (row) => formatters.formatCurrency(row[key], currency),
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
  formatters: Formatters,
): DataTableColumn<T> {
  return {
    id: "delta",
    header: t("recap.delta"),
    align: "right",
    headerClassName: "text-right",
    className: "tabular-nums",
    sortValue: (row) => Math.abs(row.delta),
    cell: (row) => (
      <div>
        <div className={cn("font-medium", deltaTone(row.delta))}>
          {signedCurrency(row.delta, currency, formatters.formatCurrency)}
        </div>
        <div className="text-xs text-muted-foreground">
          {changeDescription(row, t, formatters.formatNumber)}
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
  formatNumber: Formatters["formatNumber"],
): string {
  if (row.previous === 0 && row.current !== 0) return t("recap.changeNew");
  if (row.current === 0 && row.previous !== 0) return t("recap.changeAbsent");
  if (row.change_percent === null) return "—";
  const sign = row.change_percent > 0 ? "+" : "";
  return `${sign}${formatNumber(row.change_percent, 1)}%`;
}

function signedCurrency(
  value: number,
  currency: string,
  formatCurrency: Formatters["formatCurrency"],
): string {
  return `${value > 0 ? "+" : ""}${formatCurrency(value, currency)}`;
}

function deltaTone(delta: number): string {
  if (delta > 0) return "text-negative";
  if (delta < 0) return "text-positive";
  return "text-muted-foreground";
}
