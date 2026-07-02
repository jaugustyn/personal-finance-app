"use client";

import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Download, Loader2, RefreshCw, Save } from "lucide-react";
import { api, type FxRate } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { formatCurrency, formatDate } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";

const STATUS_KEY = ["currencies", "status"] as const;
const RATES_KEY = ["currencies", "rates"] as const;

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function invalidateMoneyQueries(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: STATUS_KEY });
  qc.invalidateQueries({ queryKey: RATES_KEY });
  qc.invalidateQueries({ queryKey: ["overview"] });
  qc.invalidateQueries({ queryKey: ["cashflow"] });
  qc.invalidateQueries({ queryKey: ["categoryTrend"] });
  qc.invalidateQueries({ queryKey: ["networth"] });
  qc.invalidateQueries({ queryKey: ["topMerchants"] });
  qc.invalidateQueries({ queryKey: ["transactions"] });
  qc.invalidateQueries({ queryKey: ["subscriptions"] });
}

export default function CurrenciesPage() {
  const { t } = useT();
  const qc = useQueryClient();
  const [currency, setCurrency] = useState("USD");
  const [rateDate, setRateDate] = useState(todayIso());
  const [rate, setRate] = useState("");

  const statusQuery = useQuery({
    queryKey: STATUS_KEY,
    queryFn: api.currencyStatus,
  });
  const ratesQuery = useQuery({
    queryKey: RATES_KEY,
    queryFn: api.fxRates,
  });

  const addRate = useMutation({
    mutationFn: api.addFxRate,
    onSuccess: () => {
      toast.success(t("currencies.rateSaved"));
      setRate("");
      invalidateMoneyQueries(qc);
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });
  const fetchNbp = useMutation({
    mutationFn: api.fetchNbpRates,
    onSuccess: (result) => {
      toast.success(
        t("currencies.nbpFetched", {
          fetched: result.fetched,
          missing: result.missing,
        }),
      );
      invalidateMoneyQueries(qc);
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
      invalidateMoneyQueries(qc);
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const baseCurrency = statusQuery.data?.base_currency ?? "PLN";
  const missing = statusQuery.data?.missing_rates ?? [];
  const currencyTotals = statusQuery.data?.currencies ?? [];

  const rateColumns = useMemo<DataTableColumn<FxRate>[]>(
    () => [
      {
        id: "pair",
        header: t("currencies.ratePair"),
        cell: (row) => `${row.currency}/${row.base_currency}`,
      },
      {
        id: "date",
        header: t("currencies.rateDate"),
        sortValue: (row) => row.rate_date,
        cell: (row) => formatDate(row.rate_date),
      },
      {
        id: "rate",
        header: t("currencies.rate"),
        align: "right",
        sortValue: (row) => Number(row.rate),
        cell: (row) => Number(row.rate).toFixed(4),
      },
      {
        id: "source",
        header: t("currencies.source"),
        cell: (row) => <Badge variant="secondary">{row.source}</Badge>,
      },
    ],
    [t],
  );

  function submitRate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const numericRate = Number(rate);
    if (!Number.isFinite(numericRate) || numericRate <= 0) {
      toast.error(t("currencies.invalidRate"));
      return;
    }
    addRate.mutate({
      currency: currency.trim().toUpperCase(),
      base_currency: baseCurrency,
      rate_date: rateDate,
      rate: numericRate,
    });
  }

  if (statusQuery.isError || ratesQuery.isError) {
    return <ErrorState title={t("currencies.error")} />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("currencies.title")}
        description={t("currencies.subtitle")}
      />

      <div className="grid gap-3 md:grid-cols-3">
        <Metric label={t("currencies.baseCurrency")} value={baseCurrency} />
        <Metric label={t("currencies.detectedCurrencies")} value={currencyTotals.length} />
        <Metric
          label={t("currencies.missingRates")}
          value={statusQuery.data?.missing_rate_count ?? 0}
          tone={(statusQuery.data?.missing_rate_count ?? 0) > 0 ? "warning" : "default"}
        />
      </div>

      <Card>
        <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <CardTitle className="text-base">{t("currencies.statusTitle")}</CardTitle>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => fetchNbp.mutate()}
              disabled={fetchNbp.isPending}
            >
              {fetchNbp.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Download className="mr-2 h-4 w-4" />
              )}
              {t("currencies.fetchNbp")}
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={() => recompute.mutate()}
              disabled={recompute.isPending}
            >
              {recompute.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              {t("currencies.recompute")}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-2">
            <h2 className="text-sm font-medium">{t("currencies.detectedCurrencies")}</h2>
            {currencyTotals.length === 0 ? (
              <EmptyState title={t("currencies.noTransactions")} />
            ) : (
              <div className="overflow-x-auto rounded-md border">
                <div className="grid min-w-[34rem] grid-cols-[minmax(8rem,1fr)_9rem_9rem_9rem] gap-3 border-b bg-muted/40 px-3 py-2 text-right text-[10px] uppercase text-muted-foreground">
                  <div className="text-left">{t("currencies.currency")}</div>
                  <div>{t("currencies.income")}</div>
                  <div>{t("currencies.expenses")}</div>
                  <div>{t("currencies.net")}</div>
                </div>
                {currencyTotals.map((row) => (
                  <div
                    key={row.currency}
                    className="grid min-w-[34rem] grid-cols-[minmax(8rem,1fr)_9rem_9rem_9rem] items-center gap-3 border-b px-3 py-2 text-right text-sm last:border-b-0"
                  >
                    <div className="text-left">
                      <div className="font-medium">{row.currency}</div>
                      <div className="text-xs text-muted-foreground">
                        {t("currencies.transactionCount", { count: row.count })}
                      </div>
                    </div>
                    <div className="tabular-nums text-positive">
                      +{formatCurrency(Number(row.total_income), row.currency)}
                    </div>
                    <div className="tabular-nums text-negative">
                      -{formatCurrency(Number(row.total_expenses), row.currency)}
                    </div>
                    <div
                      className={
                        Number(row.net) >= 0
                          ? "tabular-nums text-positive"
                          : "tabular-nums text-negative"
                      }
                    >
                      {Number(row.net) >= 0 ? "+" : "-"}
                      {formatCurrency(Math.abs(Number(row.net)), row.currency)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="space-y-2">
            <h2 className="text-sm font-medium">{t("currencies.missingRates")}</h2>
            {missing.length === 0 ? (
              <EmptyState title={t("currencies.noMissingRates")} />
            ) : (
              <div className="max-h-80 divide-y overflow-auto rounded-md border">
                {missing.map((row) => (
                  <button
                    key={`${row.currency}-${row.base_currency}-${row.rate_date}`}
                    type="button"
                    onClick={() => {
                      setCurrency(row.currency);
                      setRateDate(row.rate_date);
                    }}
                    className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-muted/60"
                  >
                    <span>
                      <span className="font-medium">
                        {row.currency}/{row.base_currency}
                      </span>{" "}
                      <span className="text-muted-foreground">
                        {formatDate(row.rate_date)}
                      </span>
                    </span>
                    <Badge variant="outline">{row.count}</Badge>
                  </button>
                ))}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-[22rem_1fr]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("currencies.manualRate")}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={submitRate} className="space-y-3">
              <label className="space-y-1 text-sm">
                <span>{t("currencies.currency")}</span>
                <Input
                  value={currency}
                  onChange={(event) => setCurrency(event.target.value.toUpperCase())}
                  maxLength={3}
                />
              </label>
              <label className="space-y-1 text-sm">
                <span>{t("currencies.rateDate")}</span>
                <Input
                  type="date"
                  value={rateDate}
                  onChange={(event) => setRateDate(event.target.value)}
                />
              </label>
              <label className="space-y-1 text-sm">
                <span>{t("currencies.rateToBase", { base: baseCurrency })}</span>
                <Input
                  value={rate}
                  onChange={(event) => setRate(event.target.value)}
                  inputMode="decimal"
                  placeholder="4.0000"
                />
              </label>
              <div className="pt-1">
                <Button
                  type="submit"
                  className="w-full sm:w-auto"
                  disabled={addRate.isPending}
                >
                  {addRate.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Save className="mr-2 h-4 w-4" />
                  )}
                  {t("currencies.saveRate")}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("currencies.savedRates")}</CardTitle>
          </CardHeader>
          <CardContent>
            {ratesQuery.isLoading ? (
              <div className="text-sm text-muted-foreground">{t("common.loading")}</div>
            ) : ratesQuery.data && ratesQuery.data.length > 0 ? (
              <DataTable
                data={ratesQuery.data}
                columns={rateColumns}
                rowKey={(row) => row.id}
              />
            ) : (
              <EmptyState title={t("currencies.noRates")} />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string | number;
  tone?: "default" | "warning";
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div
          className={
            tone === "warning"
              ? "mt-1 text-2xl font-semibold text-warning"
              : "mt-1 text-2xl font-semibold"
          }
        >
          {value}
        </div>
      </CardContent>
    </Card>
  );
}
