"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  api,
  isApiError,
  type ForecastPoint,
  type ForecastResponse,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { CategorySelect } from "@/components/category-select";
import { ForecastChart } from "@/components/charts";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatCurrency, formatMonth } from "@/lib/utils";
import { CalendarClock, Info, Loader2 } from "lucide-react";
import { useT, type TranslationKey } from "@/lib/i18n";
import { useLocalStorageState } from "@/hooks/use-local-storage-state";

const FORECAST_MODEL_LABELS: Record<string, TranslationKey> = {
  naive: "forecast.model.naive",
  mean3: "forecast.model.mean3",
  ses: "forecast.model.ses",
  holt_damped: "forecast.model.holtDamped",
  seasonal_naive: "forecast.model.seasonalNaive",
};

interface ForecastReadinessDetail {
  historyMonths: number;
  activeMonths: number;
  requiredHistoryMonths: number;
  requiredActiveMonths: number;
}

function forecastModelLabel(
  model: string,
  t: ReturnType<typeof useT>["t"],
) {
  const key = FORECAST_MODEL_LABELS[model];
  return key ? t(key) : model;
}

function forecastInterpretation(
  data: ForecastResponse,
  t: ReturnType<typeof useT>["t"],
) {
  if (data.is_baseline) return t("forecast.interpretation.baseline");
  return t("forecast.interpretation.model", {
    improvement: Math.round((data.improvement_vs_baseline ?? 0) * 100),
  });
}

function forecastReadinessDetail(error: unknown): ForecastReadinessDetail | null {
  if (!isApiError(error) || error.code !== "forecast_data_not_ready") return null;
  if (!error.detail || typeof error.detail !== "object") return null;
  const detail = error.detail as Record<string, unknown>;
  const historyMonths = Number(detail.history_months);
  const activeMonths = Number(detail.active_months);
  const requiredHistoryMonths = Number(detail.required_history_months);
  const requiredActiveMonths = Number(detail.required_active_months);
  if (
    ![
      historyMonths,
      activeMonths,
      requiredHistoryMonths,
      requiredActiveMonths,
    ].every(Number.isFinite)
  ) {
    return null;
  }
  return {
    historyMonths,
    activeMonths,
    requiredHistoryMonths,
    requiredActiveMonths,
  };
}

export default function ForecastPage() {
  const { t } = useT();
  const [category, setCategory] = useLocalStorageState(
    "finance.forecast.category",
    "",
  );
  const [horizon, setHorizon] = useLocalStorageState(
    "finance.forecast.horizon",
    3,
  );
  const [submitted, setSubmitted] = useState<{
    category: string | null;
    horizon: number;
  }>({ category: category || null, horizon });

  const query = useQuery({
    queryKey: ["forecast", submitted],
    queryFn: () => api.forecast(submitted.category, submitted.horizon),
  });
  const readiness = forecastReadinessDetail(query.error);
  const forecastColumns: DataTableColumn<ForecastPoint>[] = [
    {
      id: "month",
      header: t("forecast.column.month"),
      sortValue: (f) => f.month,
      cell: (f) => formatMonth(String(f.month).slice(0, 7)),
    },
    {
      id: "amount",
      header: t("forecast.column.amount"),
      align: "right",
      className: "tabular-nums",
      sortValue: (f) => f.amount,
      cell: (f) =>
        formatCurrency(f.amount, query.data?.base_currency ?? "PLN"),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("forecast.title")}
        description={t("forecast.subtitle")}
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">
            {t("forecast.params")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-3 sm:grid-cols-[16rem_8rem_auto]"
            onSubmit={(e) => {
              e.preventDefault();
              setSubmitted({ category: category || null, horizon });
            }}
          >
            <div className="grid gap-1.5 sm:grid-rows-[1rem_2.25rem]">
              <Label className="text-xs font-medium text-muted-foreground">
                {t("forecast.category")}
              </Label>
              <CategorySelect
                value={category}
                onChange={setCategory}
                allLabel={t("forecast.allCategories")}
                ariaLabel={t("forecast.category")}
                className="h-9 w-full"
              />
            </div>
            <div className="grid gap-1.5 sm:grid-rows-[1rem_2.25rem]">
              <Label className="text-xs font-medium text-muted-foreground">
                {t("forecast.horizon")}
              </Label>
              <Input
                type="number"
                min={1}
                max={12}
                value={horizon}
                onChange={(e) => setHorizon(Number(e.target.value))}
                className="h-9 w-full"
              />
            </div>
            <div className="grid gap-1.5 sm:grid-rows-[1rem_2.25rem] sm:justify-start">
              <span className="hidden h-4 sm:block" aria-hidden />
              <Button type="submit" className="h-9 px-3">
                {t("forecast.run")}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">
            {t("forecast.result")}{" "}
            {query.data && (
              <TooltipProvider delayDuration={150}>
                <span className="ml-2 inline-flex items-center gap-1 text-xs text-muted-foreground">
                  ({t("forecast.resultMeta", {
                    model: forecastModelLabel(query.data.model, t),
                    n: query.data.history_months,
                    folds: query.data.validation_folds,
                  })})
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Info
                        className="h-3.5 w-3.5 cursor-help"
                        aria-label={t("forecast.interpretation.title")}
                      />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-72">
                      <div className="font-medium">
                        {forecastInterpretation(query.data, t)}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {t("forecast.diagnostics", {
                          history: query.data.history_months,
                          active: query.data.active_months,
                          folds: query.data.validation_folds,
                        })}
                      </div>
                    </TooltipContent>
                  </Tooltip>
                </span>
              </TooltipProvider>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {query.isLoading ? (
            <div className="flex h-72 items-center justify-center text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" />
            </div>
          ) : readiness ? (
            <EmptyState
              icon={CalendarClock}
              title={t("forecast.dataNotReady.title")}
              description={t("forecast.dataNotReady.description", {
                history: readiness.historyMonths,
                required: readiness.requiredHistoryMonths,
                active: readiness.activeMonths,
                requiredActive: readiness.requiredActiveMonths,
              })}
              className="min-h-72"
            />
          ) : query.isError ? (
            <ErrorState
              description={(query.error as Error).message}
              onRetry={() => query.refetch()}
            />
          ) : query.data ? (
            <>
              <ForecastChart
                history={query.data.history}
                forecast={query.data.forecast}
                currency={query.data.base_currency}
              />
              <DataTable
                columns={forecastColumns}
                data={query.data.forecast}
                rowKey={(f) => f.month}
                initialSort={{ id: "month", dir: "asc" }}
                className="mt-4"
              />
            </>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
