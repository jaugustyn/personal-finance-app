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
import { useT } from "@/lib/i18n";
import { tooltipStyle } from "./chart-utils";

/**
 * Horizontal bar chart of the merchants with the highest *number* of
 * transactions (recurring spending touchpoints), as opposed to the highest
 * total amount shown by {@link TopMerchantsBar}.
 */
export function FrequentMerchantsBar({
  data,
}: {
  data: { merchant: string; count: number; category?: string | null }[];
}) {
  const { t } = useT();
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
    count: Number(d.count),
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
          allowDecimals={false}
          tick={{ fontSize: 11 }}
          stroke="hsl(var(--muted-foreground))"
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
          formatter={(value) => [String(value), t("dashboard.frequentCount")]}
        />
        <Bar
          dataKey="count"
          name={t("dashboard.frequentCount")}
          radius={[0, 4, 4, 0]}
        >
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
