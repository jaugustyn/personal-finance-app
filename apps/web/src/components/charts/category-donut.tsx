"use client";

import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { CategoryBreakdown } from "@/lib/api";
import { tCategory, useFormatters, useT } from "@/lib/i18n";
import { PIE_COLORS, tooltipStyle } from "./chart-utils";

export function CategoryDonut({ data }: { data: CategoryBreakdown[] }) {
  const { t } = useT();
  const { formatCurrency } = useFormatters();
  const top = data.slice(0, 8).map((d) => ({
    category: d.category ? tCategory(t, d.category) : t("common.unknown"),
    amount: Number(d.amount),
  }));
  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie data={top} dataKey="amount" nameKey="category" innerRadius={60} outerRadius={100} paddingAngle={2}>
          {top.map((_, idx) => (
            <Cell key={idx} fill={PIE_COLORS[idx % PIE_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip contentStyle={tooltipStyle()} formatter={(value) => formatCurrency(Number(value))} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
      </PieChart>
    </ResponsiveContainer>
  );
}
