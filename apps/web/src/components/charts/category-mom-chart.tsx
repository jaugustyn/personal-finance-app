"use client";

import {
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useMemo } from "react";
import type { CategoryTrendPoint } from "@/lib/api";
import { useFormatters, useT, tCategory } from "@/lib/i18n";
import { tooltipStyle } from "./chart-utils";

/**
 * Diverging horizontal bars for either latest month-over-month change or
 * first-vs-last month change inside the selected dashboard period.
 */
export function CategoryMoMChart({
  data,
  currency = "PLN",
  comparisonMode = "latest",
}: {
  data: CategoryTrendPoint[];
  currency?: string;
  comparisonMode?: "latest" | "period";
}) {
  const { t } = useT();
  const { formatCurrency } = useFormatters();

  const { rows } = useMemo(() => {
    const months = Array.from(new Set(data.map((d) => d.month))).sort();
    if (months.length < 2) return { rows: [] };
    const [prev, curr] =
      comparisonMode === "period"
        ? [months[0], months[months.length - 1]]
        : [months[months.length - 2], months[months.length - 1]];
    const prevByCat = new Map<string, number>();
    const currByCat = new Map<string, number>();
    for (const point of data) {
      if (point.month === prev)
        prevByCat.set(point.category, Number(point.amount));
      if (point.month === curr)
        currByCat.set(point.category, Number(point.amount));
    }
    const cats = new Set([...prevByCat.keys(), ...currByCat.keys()]);
    const rows = Array.from(cats)
      .map((cat) => ({
        category: cat,
        delta: (currByCat.get(cat) ?? 0) - (prevByCat.get(cat) ?? 0),
      }))
      .filter((r) => r.delta !== 0)
      .sort((a, b) => b.delta - a.delta);
    return { rows };
  }, [comparisonMode, data]);

  if (rows.length === 0) {
    return (
      <div className="flex h-[220px] items-center justify-center text-sm text-muted-foreground">
        {t("dashboard.noChange")}
      </div>
    );
  }

  return (
    <div className="relative">
      <ResponsiveContainer
        width="100%"
        height={Math.max(220, rows.length * 36)}
      >
        <BarChart
          layout="vertical"
          data={rows}
          margin={{ top: 10, right: 16, bottom: 0, left: 8 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            type="number"
            tick={{ fontSize: 12 }}
            stroke="hsl(var(--muted-foreground))"
            tickFormatter={(v) => `${(v / 1000).toFixed(1)}k`}
          />
          <YAxis
            type="category"
            dataKey="category"
            tick={{ fontSize: 12 }}
            stroke="hsl(var(--muted-foreground))"
            width={96}
            tickFormatter={(v) => tCategory(t, String(v))}
          />
          <Tooltip
            contentStyle={tooltipStyle()}
            formatter={(value) => [
              formatCurrency(Number(value), currency),
              t("dashboard.momDelta"),
            ]}
            labelFormatter={(v) => tCategory(t, String(v))}
          />
          <ReferenceLine x={0} stroke="hsl(var(--border))" />
          <Bar dataKey="delta" radius={[4, 4, 4, 4]}>
            {rows.map((r) => (
              <Cell
                key={r.category}
                fill={
                  r.delta >= 0
                    ? "hsl(var(--chart-negative))"
                    : "hsl(var(--chart-positive))"
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
