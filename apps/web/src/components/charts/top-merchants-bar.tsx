"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useMemo } from "react";
import { useCategories } from "@/hooks/use-categories";
import { formatCurrency } from "@/lib/utils";
import {
  formatCompactAxisNumber,
  tooltipStyle,
  truncateChartLabel,
} from "./chart-utils";

export function TopMerchantsBar({
  data,
  currency = "PLN",
}: {
  data: {
    merchant: string;
    amount: number | string;
    category?: string | null;
  }[];
  currency?: string;
}) {
  const { data: categories = [] } = useCategories();
  const colorByCategory = useMemo(() => {
    const map = new Map<string, string>();
    for (const c of categories) {
      if (c.color) map.set(c.name, c.color);
    }
    return map;
  }, [categories]);

  const rows = data.map((d) => ({
    merchant: d.merchant,
    amount: Number(d.amount),
    category: d.category ?? null,
  }));
  return (
    <ResponsiveContainer width="100%" height={Math.max(180, rows.length * 38)}>
      <BarChart
        data={rows}
        layout="vertical"
        barCategoryGap={6}
        margin={{ top: 0, right: 16, bottom: 0, left: 10 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          type="number"
          tick={{ fontSize: 11 }}
          stroke="hsl(var(--muted-foreground))"
          tickFormatter={formatCompactAxisNumber}
        />
        <YAxis
          type="category"
          dataKey="merchant"
          tick={{ fontSize: 11 }}
          tickFormatter={(value) => truncateChartLabel(value, 16)}
          stroke="hsl(var(--muted-foreground))"
          tickMargin={8}
          width={128}
        />
        <Tooltip
          contentStyle={tooltipStyle()}
          formatter={(value) => formatCurrency(Number(value), currency)}
          labelFormatter={(label) => String(label)}
        />
        <Bar dataKey="amount" name="Wydatki" radius={[0, 4, 4, 0]}>
          {rows.map((row, i) => (
            <Cell
              key={i}
              fill={
                (row.category && colorByCategory.get(row.category)) ||
                "hsl(var(--muted-foreground))"
              }
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
