"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatCurrency } from "@/lib/utils";
import { tooltipStyle } from "./chart-utils";

export function TopMerchantsBar({
  data,
}: {
  data: { merchant: string; amount: number | string }[];
}) {
  const rows = data.map((d) => ({ merchant: d.merchant, amount: Number(d.amount) }));
  return (
    <ResponsiveContainer width="100%" height={Math.max(160, rows.length * 32)}>
      <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          type="number"
          tick={{ fontSize: 11 }}
          stroke="hsl(var(--muted-foreground))"
          tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
        />
        <YAxis type="category" dataKey="merchant" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" width={120} />
        <Tooltip contentStyle={tooltipStyle()} formatter={(value) => formatCurrency(Number(value))} />
        <Bar dataKey="amount" name="Wydatki" fill="hsl(var(--chart-1))" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
