"use client";

import { useFormatters, useT } from "@/lib/i18n";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { PIE_COLORS, tooltipStyle } from "@/components/charts/chart-utils";

export function AssetAllocation({
  data,
}: {
  data: { key: string; label: string; value: number; share: number }[];
}) {
  const { t } = useT();
  const { formatCurrency, formatPercent } = useFormatters();

  const rows = [...data]
    .filter((row) => row.value > 0)
    .sort((left, right) => right.value - left.value);

  if (!rows.length) {
    return (
      <p className="py-10 text-center text-sm text-muted-foreground">
        {t("assets.noAllocation")}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
      <div className="mx-auto h-36 w-36 shrink-0" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={rows}
              dataKey="value"
              nameKey="label"
              innerRadius={42}
              outerRadius={64}
              paddingAngle={2}
              cornerRadius={3}
              isAnimationActive={false}
            >
              {rows.map((row, index) => (
                <Cell
                  key={row.key}
                  fill={PIE_COLORS[index % PIE_COLORS.length]}
                />
              ))}
            </Pie>
            <Tooltip
              contentStyle={tooltipStyle()}
              formatter={(value) => formatCurrency(Number(value), "PLN")}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="min-w-0 flex-1 space-y-4">
        {rows.map((row, index) => (
          <div key={row.key} className="space-y-1.5">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-sm">
              <span className="flex min-w-0 items-center gap-2">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-sm"
                  style={{
                    backgroundColor: PIE_COLORS[index % PIE_COLORS.length],
                  }}
                />
                <span className="break-words">{row.label}</span>
              </span>
              <span className="ml-auto font-semibold tabular-nums">
                {formatCurrency(row.value, "PLN")}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${Math.max(0, Math.min(100, row.share * 100))}%`,
                    backgroundColor: PIE_COLORS[index % PIE_COLORS.length],
                  }}
                />
              </div>
              <span className="w-12 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
                {formatPercent(row.share)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
