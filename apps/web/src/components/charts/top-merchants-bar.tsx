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
import { tooltipStyle } from "./chart-utils";

export function TopMerchantsBar({
  data,
}: {
  data: {
    merchant: string;
    amount: number | string;
    category?: string | null;
  }[];
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
    <ResponsiveContainer width="100%" height={Math.max(160, rows.length * 32)}>
      <BarChart
        data={rows}
        layout="vertical"
        margin={{ top: 0, right: 16, bottom: 0, left: 0 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          type="number"
          tick={{ fontSize: 11 }}
          stroke="hsl(var(--muted-foreground))"
          tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
        />
        <YAxis
          type="category"
          dataKey="merchant"
          tick={{ fontSize: 11 }}
          stroke="hsl(var(--muted-foreground))"
          width={120}
        />
        <Tooltip
          contentStyle={tooltipStyle()}
          formatter={(value) => formatCurrency(Number(value))}
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
