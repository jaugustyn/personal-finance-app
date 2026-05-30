"use client";

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatCurrency } from "@/lib/utils";
import { tooltipStyle } from "./chart-utils";

export function PortfolioHistoryChart({
  data,
}: {
  data: { snapshot_date: string; value_pln: number | string }[];
}) {
  const rows = data.map((d) => ({ label: d.snapshot_date.slice(5), value: Number(d.value_pln) }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={rows} margin={{ top: 10, right: 10, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="pnl" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(var(--chart-4))" stopOpacity={0.6} />
            <stop offset="100%" stopColor="hsl(var(--chart-4))" stopOpacity={0.05} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis dataKey="label" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
        <YAxis
          tick={{ fontSize: 11 }}
          stroke="hsl(var(--muted-foreground))"
          tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
        />
        <Tooltip contentStyle={tooltipStyle()} formatter={(value) => formatCurrency(Number(value))} />
        <Area
          type="monotone"
          dataKey="value"
          name="Wartość"
          stroke="hsl(var(--chart-4))"
          fill="url(#pnl)"
          strokeWidth={2}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
