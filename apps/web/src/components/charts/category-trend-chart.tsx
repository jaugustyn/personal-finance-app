"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useMemo } from "react";
import { useTheme } from "next-themes";
import type { CategoryTrendPoint } from "@/lib/api";
import { getCategoryChartStyle } from "@/lib/category-colors";
import { useFormatters, useT, tCategory } from "@/lib/i18n";
import { useCategories } from "@/hooks/use-categories";
import { PIE_COLORS, tooltipStyle } from "./chart-utils";

/**
 * Multi-series line chart of monthly spend for the top categories. The flat
 * ``{month, category, amount}`` rows from the API are pivoted into one row per
 * month with a column per category so Recharts can render parallel lines.
 */
export function CategoryTrendChart({
  data,
  currency = "PLN",
}: {
  data: CategoryTrendPoint[];
  currency?: string;
}) {
  const { t } = useT();
  const { formatCurrency, formatMonth } = useFormatters();
  const { resolvedTheme } = useTheme();
  const theme = resolvedTheme === "dark" ? "dark" : "light";
  const { data: categories = [] } = useCategories();

  const colorByCategory = useMemo(() => {
    const map = new Map<string, ReturnType<typeof getCategoryChartStyle>>();
    for (const c of categories) {
      if (c.color) map.set(c.name, getCategoryChartStyle(c.color, theme));
    }
    return map;
  }, [categories, theme]);

  const { rows, categories: cats } = useMemo(() => {
    const cats = Array.from(new Set(data.map((d) => d.category)));
    const byMonth = new Map<string, Record<string, number | string>>();
    for (const point of data) {
      const row = byMonth.get(point.month) ?? { month: point.month };
      row[point.category] = Number(point.amount);
      byMonth.set(point.month, row);
    }
    const ordered = Array.from(byMonth.values()).sort((a, b) =>
      String(a.month).localeCompare(String(b.month)),
    );
    return { rows: ordered, categories: cats };
  }, [data]);

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart
        data={rows}
        margin={{ top: 10, right: 10, bottom: 0, left: 0 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          dataKey="month"
          tickFormatter={(v) => formatMonth(String(v))}
          tick={{ fontSize: 12 }}
          stroke="hsl(var(--muted-foreground))"
        />
        <YAxis
          tick={{ fontSize: 12 }}
          stroke="hsl(var(--muted-foreground))"
          tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
        />
        <Tooltip
          contentStyle={tooltipStyle()}
          labelFormatter={(v) => formatMonth(String(v))}
          formatter={(value, name) => [
            formatCurrency(Number(value), currency),
            tCategory(t, String(name)),
          ]}
        />
        <Legend
          wrapperStyle={{ fontSize: 12 }}
          formatter={(value) => tCategory(t, String(value))}
        />
        {cats.map((cat, i) => (
          <Line
            key={cat}
            type="monotone"
            dataKey={cat}
            stroke={
              colorByCategory.get(cat)?.fill || PIE_COLORS[i % PIE_COLORS.length]
            }
            strokeWidth={2}
            dot={false}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
