"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ForecastChart } from "@/components/charts";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatCurrency, formatMonth } from "@/lib/utils";
import { Loader2 } from "lucide-react";
import { useT } from "@/lib/i18n";

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
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {t("forecast.title")}
        </h1>
        <p className="text-sm text-muted-foreground">
          {t("forecast.subtitle")}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">
            {t("forecast.params")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              setSubmitted({ category: category || null, horizon });
            }}
          >
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">
                {t("forecast.category")}
              </label>
              <Input
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-48"
                placeholder={t("forecast.categoryPlaceholder")}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">
                {t("forecast.horizon")}
              </label>
              <Input
                type="number"
                min={1}
                max={12}
                value={horizon}
                onChange={(e) => setHorizon(Number(e.target.value))}
                className="w-24"
              />
            </div>
            <Button
              type="submit"
              onClick={() =>
                setSubmitted({ category: category || null, horizon })
              }
            >
              {t("forecast.run")}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">
            {t("forecast.result")}{" "}
            {query.data && (
              <span className="ml-2 text-xs text-muted-foreground">
                ({t("forecast.modelLabel", { model: query.data.model })})
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {query.isLoading ? (
            <div className="flex h-72 items-center justify-center text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" />
            </div>
          ) : query.isError ? (
            <div className="text-sm text-red-600">
              {(query.error as Error).message}
            </div>
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
