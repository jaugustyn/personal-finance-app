"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { CardGridSkeleton } from "@/components/ui/skeleton";
import { useT, tCategory } from "@/lib/i18n";
import { formatCurrency, formatDate, cn } from "@/lib/utils";
import {
  CalendarRange,
  TrendingUp,
  TrendingDown,
  Store,
  AlertTriangle,
  PiggyBank,
} from "lucide-react";

import { Input } from "@/components/ui/input";

type Period = "week" | "month" | "custom";

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
  const [period, setPeriod] = useState<Period>("month");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

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
                {query.data.category_changes.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {t("recap.changes.empty")}
                  </p>
                ) : (
                  <ul className="divide-y divide-border">
                    {query.data.category_changes.map((c) => (
                      <li
                        key={c.category}
                        className="flex items-center justify-between gap-3 py-2 text-sm"
                      >
                        <span>{tCategory(t, c.category)}</span>
                        <span
                          className={cn(
                            "flex items-center gap-1 tabular-nums",
                            deltaTone(c.delta),
                          )}
                        >
                          {c.delta > 0 ? (
                            <TrendingUp className="h-3.5 w-3.5" />
                          ) : (
                            <TrendingDown className="h-3.5 w-3.5" />
                          )}
                          {c.delta > 0 ? "+" : ""}
                          {formatCurrency(c.delta)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
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
                {query.data.top_merchants.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {t("recap.merchants.empty")}
                  </p>
                ) : (
                  <ul className="divide-y divide-border">
                    {query.data.top_merchants.map((m) => (
                      <li
                        key={m.merchant}
                        className="flex items-center justify-between gap-3 py-2 text-sm"
                      >
                        <span className="truncate">{m.merchant}</span>
                        <span className="shrink-0 tabular-nums text-muted-foreground">
                          {formatCurrency(m.amount)} · {m.count}×
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base text-foreground">
                  <AlertTriangle className="h-4 w-4 text-muted-foreground" />
                  {t("recap.breaches.title")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {query.data.limit_breaches.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {t("recap.breaches.empty")}
                  </p>
                ) : (
                  <ul className="divide-y divide-border">
                    {query.data.limit_breaches.map((b) => (
                      <li
                        key={b.category}
                        className="flex items-center justify-between gap-3 py-2 text-sm"
                      >
                        <span>{tCategory(t, b.category)}</span>
                        <span className="shrink-0 tabular-nums text-negative">
                          {formatCurrency(b.spent)} / {formatCurrency(b.limit)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base text-foreground">
                  <PiggyBank className="h-4 w-4 text-muted-foreground" />
                  {t("recap.savings.title")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {!query.data.savings_progress ? (
                  <p className="text-sm text-muted-foreground">
                    {t("common.unknown")}
                  </p>
                ) : (
                  <div className="space-y-2">
                    <div className="text-2xl font-semibold tabular-nums">
                      {formatCurrency(query.data.savings_progress.net)}
                      <span className="ml-1 text-sm font-normal text-muted-foreground">
                        / {formatCurrency(query.data.savings_progress.goal)}
                      </span>
                    </div>
                    <p
                      className={cn(
                        "text-sm",
                        query.data.savings_progress.met
                          ? "text-positive"
                          : "text-muted-foreground",
                      )}
                    >
                      {query.data.savings_progress.met
                        ? t("recap.savings.met")
                        : t("recap.savings.missed")}
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
