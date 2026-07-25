"use client";

import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useMemo } from "react";
import type { ForecastPoint } from "@/lib/api";
import { useFormatters, useT } from "@/lib/i18n";
import { formatCompactAxisNumber, tooltipStyle } from "./chart-utils";

export function ForecastChart({
  history,
  forecast,
  currency,
}: {
  history: ForecastPoint[];
  forecast: ForecastPoint[];
  currency: string;
}) {
  const { t } = useT();
  const { formatCurrency, formatMonth, localeTag } = useFormatters();
  const data = useMemo(
    () => [
      ...history.map((h) => ({
        label: formatMonth(String(h.month).slice(0, 7)),
        historia: Number(h.amount),
        prognoza: null as number | null,
      })),
      ...forecast.map((f) => ({
        label: formatMonth(String(f.month).slice(0, 7)),
        historia: null as number | null,
        prognoza: Number(f.amount),
      })),
    ],
    [forecast, formatMonth, history],
  );
  return (
    <ResponsiveContainer width="100%" height={320}>
      <ComposedChart data={data} margin={{ top: 10, right: 10, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis dataKey="label" tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
        <YAxis
          tick={{ fontSize: 12 }}
          stroke="hsl(var(--muted-foreground))"
          tickFormatter={(value) =>
            formatCompactAxisNumber(value, localeTag)
          }
        />
        <Tooltip
          contentStyle={tooltipStyle()}
          formatter={(value) =>
            value == null ? "-" : formatCurrency(Number(value), currency)
          }
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line type="monotone" dataKey="historia" name={t("chart.history")} stroke="hsl(var(--chart-2))" strokeWidth={2} connectNulls />
        <Line
          type="monotone"
          dataKey="prognoza"
          name={t("chart.forecast")}
          stroke="hsl(var(--chart-4))"
          strokeWidth={2}
          strokeDasharray="5 5"
          connectNulls
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
