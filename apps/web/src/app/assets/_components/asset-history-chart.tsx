"use client";

import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AssetHistory } from "@/lib/api";
import { useFormatters, useT } from "@/lib/i18n";
import {
  formatCompactAxisNumber,
  tooltipStyle,
} from "@/components/charts/chart-utils";

export function AssetHistoryChart({ data }: { data: AssetHistory["points"] }) {
  const { t } = useT();
  const { formatCurrency, formatDate, localeTag } = useFormatters();
  const points = useMemo(
    () =>
      data.map((point) => ({
        date: new Date(`${point.date}T00:00:00`).getTime(),
        label: formatDate(point.date),
        value: Number(point.amount_pln),
      })),
    [data, formatDate],
  );

  return (
    <ResponsiveContainer width="100%" height={280}>
      <AreaChart
        data={points}
        margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
      >
        <defs>
          <linearGradient id="asset-value-fill" x1="0" y1="0" x2="0" y2="1">
            <stop
              offset="0%"
              stopColor="hsl(var(--primary))"
              stopOpacity={0.35}
            />
            <stop
              offset="100%"
              stopColor="hsl(var(--primary))"
              stopOpacity={0.03}
            />
          </linearGradient>
        </defs>
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="hsl(var(--border))"
          vertical={false}
        />
        <XAxis
          dataKey="date"
          type="number"
          scale="time"
          domain={["dataMin", "dataMax"]}
          tickFormatter={(value) => formatDate(new Date(value))}
          tick={{ fontSize: 11 }}
          stroke="hsl(var(--muted-foreground))"
          minTickGap={52}
          tickCount={5}
        />
        <YAxis
          width={46}
          tick={{ fontSize: 11 }}
          stroke="hsl(var(--muted-foreground))"
          tickFormatter={(value) => formatCompactAxisNumber(value, localeTag)}
        />
        <Tooltip
          contentStyle={tooltipStyle()}
          formatter={(value) => [
            formatCurrency(Number(value), "PLN"),
            t("assets.value"),
          ]}
          labelFormatter={(_, payload) => payload[0]?.payload?.label ?? ""}
        />
        <Area
          type="linear"
          dataKey="value"
          name={t("assets.value")}
          stroke="hsl(var(--primary))"
          fill="url(#asset-value-fill)"
          strokeWidth={2}
          isAnimationActive={false}
          dot={points.length === 1 ? { r: 4 } : false}
          activeDot={{ r: 4 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
