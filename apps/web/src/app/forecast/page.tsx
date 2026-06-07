"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { CategorySelect } from "@/components/category-select";
import { ForecastChart } from "@/components/charts";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatCurrency, formatMonth } from "@/lib/utils";
import { Info, Loader2 } from "lucide-react";
import { useT } from "@/lib/i18n";

function forecastConfidenceLabel(
  historyMonths: number,
  t: ReturnType<typeof useT>["t"],
) {
  if (historyMonths >= 12) return t("forecast.confidence.good");
  if (historyMonths >= 6) return t("forecast.confidence.medium");
  return t("forecast.confidence.low");
}

export default function ForecastPage() {
  const { t } = useT();
  const [category, setCategory] = useState("");
  const [horizon, setHorizon] = useState(3);
  const [submitted, setSubmitted] = useState<{
    category: string | null;
    horizon: number;
  }>({ category: null, horizon: 3 });

  const query = useQuery({
    queryKey: ["forecast", submitted],
    queryFn: () => api.forecast(submitted.category, submitted.horizon),
  });

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
            className="grid gap-3 sm:grid-cols-[16rem_8rem_auto] sm:items-start"
            onSubmit={(e) => {
              e.preventDefault();
              setSubmitted({ category: category || null, horizon });
            }}
          >
            <div className="grid grid-rows-[1rem_2.25rem] gap-1">
              <label className="flex items-center text-xs text-muted-foreground">
                {t("forecast.category")}
              </label>
              <CategorySelect
                value={category}
                onChange={setCategory}
                allLabel={t("forecast.allCategories")}
                ariaLabel={t("forecast.category")}
                className="h-9 w-full"
              />
            </div>
            <div className="grid grid-rows-[1rem_2.25rem] gap-1">
              <label className="flex items-center text-xs text-muted-foreground">
                {t("forecast.horizon")}
              </label>
              <Input
                type="number"
                min={1}
                max={12}
                value={horizon}
                onChange={(e) => setHorizon(Number(e.target.value))}
                className="h-9 w-full"
              />
            </div>
            <div className="grid grid-rows-[1rem_2.25rem] gap-1 justify-self-start">
              <span
                className="block h-4 select-none"
                aria-hidden
              />
              <Button type="submit" className="h-9 w-fit min-w-28 px-4">
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
                    model: query.data.model,
                    n: query.data.history.length,
                  })})
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Info
                        className="h-3.5 w-3.5 cursor-help"
                        aria-label={t("forecast.confidence.title")}
                      />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-72">
                      <div className="font-medium">
                        {forecastConfidenceLabel(query.data.history.length, t)}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {t("forecast.confidence.history", {
                          n: query.data.history.length,
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
              />
              <Table className="mt-4">
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("forecast.column.month")}</TableHead>
                    <TableHead className="text-right">
                      {t("forecast.column.amount")}
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {query.data.forecast.map((f) => (
                    <TableRow key={f.month}>
                      <TableCell>
                        {formatMonth(String(f.month).slice(0, 7))}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatCurrency(f.amount)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
