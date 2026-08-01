"use client";

import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertTriangle,
  Loader2,
  Plus,
  RefreshCw,
  Save,
} from "lucide-react";
import { api, type CurrencyStatus, type FxRate } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { CurrencyCombobox } from "@/components/currency-combobox";
import { DatePicker } from "@/components/date-range-picker";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton, TableSkeleton } from "@/components/ui/skeleton";
import { useFormatters, useT } from "@/lib/i18n";
import { invalidateCurrencyData, queryKeys } from "@/lib/query-keys";
import { showErrorToast } from "@/lib/toasts";

const EMPTY_MISSING_RATES: CurrencyStatus["missing_rates"] = [];

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function CurrenciesPage() {
  const { t } = useT();
  const { formatCurrency, formatDate, formatNumber } = useFormatters();
  const qc = useQueryClient();
  const [currency, setCurrency] = useState("USD");
  const [rateDate, setRateDate] = useState(todayIso());
  const [rate, setRate] = useState("");
  const [manualRateOpen, setManualRateOpen] = useState(false);
  const [affectedTransactions, setAffectedTransactions] = useState<number | null>(
    null,
  );

  const statusQuery = useQuery({
    queryKey: queryKeys.currencies.status,
    queryFn: api.currencyStatus,
  });
  const ratesQuery = useQuery({
    queryKey: queryKeys.currencies.rates,
    queryFn: api.fxRates,
  });

  const addRate = useMutation({
    mutationFn: api.addFxRate,
    onSuccess: () => {
      toast.success(t("currencies.rateSaved"));
      setRate("");
      setManualRateOpen(false);
      setAffectedTransactions(null);
      void invalidateCurrencyData(qc);
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });
  const recompute = useMutation({
    mutationFn: api.recomputeCurrencies,
    onSuccess: (result) => {
      toast.success(
        t("currencies.recomputed", {
          updated: result.updated,
          missing: result.missing,
        }),
      );
      void invalidateCurrencyData(qc);
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const baseCurrency = statusQuery.data?.base_currency ?? "PLN";
  const missing = statusQuery.data?.missing_rates ?? EMPTY_MISSING_RATES;
  const currencyTotals = statusQuery.data?.currencies ?? [];
  const missingByCurrency = useMemo(() => {
    const counts = new Map<string, number>();
    for (const row of missing) {
      counts.set(row.currency, (counts.get(row.currency) ?? 0) + row.count);
    }
    return counts;
  }, [missing]);

  const rateColumns = useMemo<DataTableColumn<FxRate>[]>(
    () => [
      {
        id: "pair",
        header: t("currencies.ratePair"),
        headerClassName: "w-[28%]",
        sortValue: (row) => `${row.currency}/${row.base_currency}`,
        cell: (row) => `${row.currency} → ${row.base_currency}`,
      },
      {
        id: "date",
        header: t("currencies.rateDate"),
        headerClassName: "w-[28%]",
        sortValue: (row) => row.rate_date,
        cell: (row) => formatDate(row.rate_date),
      },
      {
        id: "rate",
        header: t("currencies.rate"),
        headerClassName: "w-[22%]",
        align: "right",
        className: "tabular-nums",
        sortValue: (row) => Number(row.rate),
        cell: (row) => (
          <span>
            {formatNumber(Number(row.rate), 4)}
          </span>
        ),
      },
      {
        id: "source",
        header: t("currencies.source"),
        headerClassName: "w-[22%]",
        sortValue: (row) => row.source,
        cell: (row) => (
          <Badge variant="secondary">
            {row.source.toLowerCase() === "nbp"
              ? t("currencies.sourceNbp")
              : row.source.toLowerCase() === "manual"
                ? t("currencies.sourceManual")
                : row.source}
          </Badge>
        ),
      },
    ],
    [formatDate, formatNumber, t],
  );

  function submitRate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedCurrency = currency.trim().toUpperCase();
    const numericRate = Number(rate.trim().replace(",", "."));
    if (!/^[A-Z]{3}$/.test(normalizedCurrency)) {
      toast.error(t("currencies.invalidCurrency"));
      return;
    }
    if (!Number.isFinite(numericRate) || numericRate <= 0) {
      toast.error(t("currencies.invalidRate"));
      return;
    }
    addRate.mutate({
      currency: normalizedCurrency,
      rate_date: rateDate,
      rate: numericRate,
    });
  }

  function openManualRate(
    row?: CurrencyStatus["missing_rates"][number],
  ): void {
    const defaultCurrency =
      currencyTotals.find((item) => item.currency !== baseCurrency)?.currency ??
      "USD";
    setCurrency(row?.currency ?? defaultCurrency);
    setRateDate(row?.rate_date ?? todayIso());
    setRate("");
    setAffectedTransactions(row?.count ?? null);
    setManualRateOpen(true);
  }

  if (statusQuery.isError || ratesQuery.isError) {
    return (
      <div className="space-y-5">
        <PageHeader
          title={t("currencies.title")}
          description={t("currencies.subtitle")}
        />
        <ErrorState
          title={t("currencies.error")}
          onRetry={() => {
            void statusQuery.refetch();
            void ratesQuery.refetch();
          }}
        />
      </div>
    );
  }

  if (statusQuery.isLoading || ratesQuery.isLoading) {
    return (
      <div className="space-y-5">
        <PageHeader
          title={t("currencies.title")}
          description={t("currencies.subtitle")}
        />
        <CurrenciesPageSkeleton />
      </div>
    );
  }

  const missingTransactionCount = statusQuery.data?.missing_rate_count ?? 0;
  const normalizedCurrency = currency.trim().toUpperCase();
  const numericRate = Number(rate.trim().replace(",", "."));
  const canSaveRate =
    /^[A-Z]{3}$/.test(normalizedCurrency) &&
    Boolean(rateDate) &&
    Number.isFinite(numericRate) &&
    numericRate > 0;

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("currencies.title")}
        description={t("currencies.subtitle")}
      />

      {missing.length > 0 ? (
        <section className="rounded-lg border border-warning/35 bg-warning/5 p-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex min-w-0 gap-3">
              <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-warning/15 text-warning">
                <AlertTriangle className="h-4 w-4" />
              </div>
              <div className="space-y-1">
                <h2 className="font-medium">{t("currencies.missingTitle")}</h2>
                <p className="text-sm text-muted-foreground">
                  {t("currencies.missingSummary", {
                    transactions: formatNumber(missingTransactionCount),
                    rates: formatNumber(missing.length),
                  })}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t("currencies.recomputeHint")}
                </p>
              </div>
            </div>
            <Button
              type="button"
              size="sm"
              onClick={() => recompute.mutate()}
              disabled={recompute.isPending}
              className="shrink-0"
            >
              {recompute.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              {t("currencies.recompute")}
            </Button>
          </div>
          <div className="mt-4 max-h-56 divide-y overflow-auto rounded-md border bg-card">
            {missing.map((row) => (
              <button
                key={`${row.currency}-${row.base_currency}-${row.rate_date}`}
                type="button"
                onClick={() => openManualRate(row)}
                className="flex w-full items-center justify-between gap-4 px-3 py-2.5 text-left text-sm transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
              >
                <span className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-0.5">
                  <span className="font-medium">
                    {row.currency} → {row.base_currency}
                  </span>
                  <span className="text-muted-foreground">
                    {formatDate(row.rate_date)}
                  </span>
                </span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {t("currencies.transactionCount", {
                    count: formatNumber(row.count),
                  })}
                </span>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(20rem,2fr)_minmax(0,3fr)] xl:items-start">
        <section className="space-y-3">
          <div className="flex min-h-9 items-center gap-2">
            <h2 className="text-base font-semibold">
              {t("currencies.detectedCurrencies")}
            </h2>
            <Badge variant="secondary" className="tabular-nums">
              {formatNumber(currencyTotals.length)}
            </Badge>
          </div>
          {currencyTotals.length === 0 ? (
            <EmptyState title={t("currencies.noTransactions")} />
          ) : (
            <div className="divide-y rounded-lg border bg-card">
              {currencyTotals.map((row) => {
                const net = Number(row.net);
                const missingCount = missingByCurrency.get(row.currency) ?? 0;
                return (
                  <article key={row.currency} className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-semibold">{row.currency}</h3>
                        {row.currency === baseCurrency ? (
                          <Badge variant="outline">
                            {t("currencies.baseBadge")}
                          </Badge>
                        ) : null}
                      </div>
                      <div className="text-right">
                        <p className="text-xs text-muted-foreground">
                          {t("currencies.transactionCount", {
                            count: formatNumber(row.count),
                          })}
                        </p>
                        {missingCount > 0 ? (
                          <p className="mt-0.5 text-xs text-warning">
                            {t("currencies.unconvertedForCurrency", {
                              count: formatNumber(missingCount),
                            })}
                          </p>
                        ) : null}
                      </div>
                    </div>
                    <dl className="mt-3 grid gap-y-2 sm:grid-cols-3 sm:gap-y-0 sm:divide-x sm:divide-border/70">
                      <CurrencyAmount
                        label={t("currencies.income")}
                        value={`+${formatCurrency(Number(row.total_income), row.currency)}`}
                        tone="positive"
                      />
                      <CurrencyAmount
                        label={t("currencies.expenses")}
                        value={`−${formatCurrency(Number(row.total_expenses), row.currency)}`}
                        tone="negative"
                      />
                      <CurrencyAmount
                        label={t("currencies.net")}
                        value={`${net >= 0 ? "+" : "−"}${formatCurrency(Math.abs(net), row.currency)}`}
                        tone={net >= 0 ? "positive" : "negative"}
                      />
                    </dl>
                  </article>
                );
              })}
            </div>
          )}
        </section>

        <section className="space-y-3">
          <div className="flex min-h-9 items-center">
            <h2 className="text-base font-semibold">
              {t("currencies.savedRates")}
            </h2>
          </div>
          <DataTable
            data={ratesQuery.data}
            columns={rateColumns}
            rowKey={(row) => row.id}
            initialSort={{ id: "date", dir: "desc" }}
            pagination={{ mode: "client" }}
            emptyTitle={t("currencies.noRates")}
            tableClassName="min-w-[34rem]"
            toolbarPosition="bottom"
            toolbar={
              <button
                type="button"
                onClick={() => openManualRate()}
                className="-mx-3 -my-2 flex w-[calc(100%+1.5rem)] items-center gap-2 px-3 py-2.5 text-left text-sm font-medium text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
              >
                <Plus className="h-4 w-4" />
                {t("currencies.manualRate")}
              </button>
            }
          />
        </section>
      </div>

      <Dialog
        open={manualRateOpen}
        onOpenChange={(open) => {
          if (addRate.isPending) return;
          setManualRateOpen(open);
          if (!open) setAffectedTransactions(null);
        }}
      >
        <DialogContent className="max-w-sm">
          <form onSubmit={submitRate} className="space-y-5">
            <DialogHeader>
              <DialogTitle>{t("currencies.manualRate")}</DialogTitle>
              <DialogDescription className="sr-only">
                {t("currencies.manualRateDescription")}
              </DialogDescription>
            </DialogHeader>

            <div className="grid gap-4 sm:grid-cols-[7rem_minmax(0,1fr)]">
              <div className="grid gap-2 text-sm">
                <label htmlFor="manual-rate-currency" className="font-medium">
                  {t("currencies.currency")}
                </label>
                <CurrencyCombobox
                  id="manual-rate-currency"
                  value={currency}
                  onChange={setCurrency}
                  baseCurrency={baseCurrency}
                  autoFocus
                />
              </div>

              <div className="grid gap-2 text-sm">
                <label htmlFor="manual-rate-date" className="font-medium">
                  {t("currencies.rateDate")}
                </label>
                <DatePicker
                  id="manual-rate-date"
                  value={rateDate}
                  onChange={setRateDate}
                  ariaLabel={t("currencies.rateDate")}
                />
              </div>
            </div>

            <div className="grid gap-2">
              <label htmlFor="manual-rate-value" className="text-sm font-medium">
                {t("currencies.rate")}
              </label>
              <div className="grid grid-cols-[auto_auto_minmax(0,1fr)_auto] items-center gap-2 text-sm">
                <span className="whitespace-nowrap font-medium">
                  1 {normalizedCurrency || "—"}
                </span>
                <span className="text-muted-foreground">=</span>
                <Input
                  id="manual-rate-value"
                  value={rate}
                  onChange={(event) => setRate(event.target.value)}
                  inputMode="decimal"
                  placeholder="4,0000"
                  aria-label={t("currencies.rate")}
                />
                <span className="font-medium">{baseCurrency}</span>
              </div>
            </div>

            {affectedTransactions !== null ? (
              <div className="rounded-md border bg-muted/20 px-3 py-2 text-sm text-muted-foreground">
                {t("currencies.affectedTransactions", {
                  count: formatNumber(affectedTransactions),
                })}
              </div>
            ) : null}

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setManualRateOpen(false)}
                disabled={addRate.isPending}
              >
                {t("common.cancel")}
              </Button>
              <Button
                type="submit"
                disabled={!canSaveRate || addRate.isPending}
              >
                {addRate.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-2 h-4 w-4" />
                )}
                {t("currencies.saveRate")}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function CurrencyAmount({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "positive" | "negative";
}) {
  return (
    <div className="min-w-0 border-b border-border/60 pb-2 last:border-b-0 last:pb-0 sm:border-b-0 sm:px-3 sm:pb-0 sm:first:pl-0 sm:last:pr-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd
        className={
          tone === "positive"
            ? "mt-0.5 truncate text-sm font-medium tabular-nums text-positive"
            : "mt-0.5 truncate text-sm font-medium tabular-nums text-negative"
        }
        title={value}
      >
        {value}
      </dd>
    </div>
  );
}

function CurrenciesPageSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-4 w-96 max-w-full" />
      <div className="grid gap-6 xl:grid-cols-[minmax(20rem,2fr)_minmax(0,3fr)]">
        <div className="space-y-3">
          <div className="flex min-h-9 items-center">
            <Skeleton className="h-5 w-44" />
          </div>
          <div className="divide-y rounded-lg border bg-card">
            {Array.from({ length: 2 }).map((_, index) => (
              <div key={index} className="space-y-3 p-4">
                <div className="flex items-center justify-between gap-3">
                  <Skeleton className="h-5 w-16" />
                  <Skeleton className="h-4 w-24" />
                </div>
                <div className="grid grid-cols-3 divide-x divide-border/70">
                  <div className="space-y-1 pr-3">
                    <Skeleton className="h-3 w-12" />
                    <Skeleton className="h-4 w-20" />
                  </div>
                  <div className="space-y-1 px-3">
                    <Skeleton className="h-3 w-12" />
                    <Skeleton className="h-4 w-20" />
                  </div>
                  <div className="space-y-1 pl-3">
                    <Skeleton className="h-3 w-12" />
                    <Skeleton className="h-4 w-20" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="space-y-3">
          <div className="flex min-h-9 items-center">
            <Skeleton className="h-5 w-36" />
          </div>
          <TableSkeleton rows={5} />
          <Skeleton className="h-10 w-full" />
        </div>
      </div>
    </div>
  );
}
