"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useMemo } from "react";
import type { NetWorthPoint } from "@/lib/api";
import { formatCurrency, formatMonth } from "@/lib/utils";
import { tooltipStyle } from "./chart-utils";

export function NetWorthChart({ data }: { data: NetWorthPoint[] }) {
  const formatted = useMemo(
    () => data.map((d) => ({ label: formatMonth(d.month), balance: Number(d.balance) })),
    [data],
  );
  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={formatted} margin={{ top: 10, right: 10, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="nw" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(var(--chart-2))" stopOpacity={0.6} />
            <stop offset="100%" stopColor="hsl(var(--chart-2))" stopOpacity={0.05} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis dataKey="label" tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
        <YAxis
          tick={{ fontSize: 12 }}
          stroke="hsl(var(--muted-foreground))"
          tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
        />
        <Tooltip contentStyle={tooltipStyle()} formatter={(value) => formatCurrency(Number(value))} />
        <Area
          type="monotone"
          dataKey="balance"
          name="Skumulowane saldo"
          stroke="hsl(var(--chart-2))"
          fill="url(#nw)"
          strokeWidth={2}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
