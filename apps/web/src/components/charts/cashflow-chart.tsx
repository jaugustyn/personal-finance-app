"use client";

import {
  Bar,
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
import type { CashflowPoint } from "@/lib/api";
import { formatCurrency, formatMonth } from "@/lib/utils";
import { tooltipStyle } from "./chart-utils";

export function CashflowChart({
  data,
  currency = "PLN",
}: {
  data: CashflowPoint[];
  currency?: string;
}) {
  const formatted = useMemo(
    () =>
      data.map((d) => ({
        label: formatMonth(d.month),
        income: Number(d.income),
        expenses: Number(d.expenses),
        net: Number(d.net),
      })),
    [data],
  );
  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart
        data={formatted}
        margin={{ top: 10, right: 10, bottom: 0, left: 0 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          dataKey="label"
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
          formatter={(value, name) => [
            formatCurrency(Number(value), currency),
            String(name),
          ]}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar
          dataKey="income"
          name="Przychody"
          fill="hsl(var(--chart-positive))"
          radius={[4, 4, 0, 0]}
        />
        <Bar
          dataKey="expenses"
          name="Wydatki"
          fill="hsl(var(--chart-negative))"
          radius={[4, 4, 0, 0]}
        />
        <Line
          type="monotone"
          dataKey="net"
          name="Saldo"
          stroke="hsl(var(--chart-4))"
          strokeWidth={2}
          dot={{ r: 3 }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
