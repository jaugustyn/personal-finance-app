"use client";

import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { AssetOverview } from "@/lib/api";
import { PIE_COLORS, tooltipStyle } from "@/components/charts/chart-utils";
import { useFormatters, useT } from "@/lib/i18n";
import { assetTypeKey } from "../_lib/asset-options";

export function AssetAllocation({
  data,
}: {
  data: AssetOverview["breakdown"];
}) {
  const { t } = useT();
  const { formatCurrency, formatPercent } = useFormatters();

  if (!data.length) {
    return (
      <p className="py-10 text-center text-sm text-muted-foreground">
        {t("assets.noAllocation")}
      </p>
    );
  }

  const rows = data.map((row, index) => ({
    assetType: row.asset_type,
    label: t(assetTypeKey(row.asset_type)),
    value: Number(row.amount_pln),
    share: Number(row.share),
    color: PIE_COLORS[index % PIE_COLORS.length],
  }));

  return (
    <div className="space-y-4">
      <div className="h-52 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={rows}
              dataKey="value"
              nameKey="label"
              innerRadius={52}
              outerRadius={82}
              paddingAngle={2}
              cornerRadius={3}
            >
              {rows.map((row) => (
                <Cell key={row.assetType} fill={row.color} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={tooltipStyle()}
              formatter={(value) => formatCurrency(Number(value), "PLN")}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)_max-content_3.25rem] items-center gap-x-2.5 gap-y-2.5 text-sm">
        {rows.map((row) => (
          <div key={row.assetType} className="contents">
            <div className="flex min-w-0 items-center gap-2">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-sm"
                style={{ backgroundColor: row.color }}
              />
              <span className="truncate">{row.label}</span>
            </div>
            <span className="text-right tabular-nums">
              {formatCurrency(row.value, "PLN")}
            </span>
            <span className="text-right text-xs tabular-nums text-muted-foreground">
              {formatPercent(row.share)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
