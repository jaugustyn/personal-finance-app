"use client";

import type { CategoryBreakdown } from "@/lib/api";
import { EmptyState } from "@/components/empty-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { tCategory, tTransactionType, useT } from "@/lib/i18n";
import { cn, formatCurrency, formatPercent } from "@/lib/utils";
import type { DashboardDirection } from "../_lib/dashboard-types";
import { ChartSkeleton } from "./dashboard-section";

export function SpendingBreakdownCard({
  data,
  isLoading,
  currency,
  direction,
}: {
  data: CategoryBreakdown[] | undefined;
  isLoading: boolean;
  currency: string;
  direction: DashboardDirection;
}) {
  const { t } = useT();
  const rows = data ?? [];
  const maxAmount = Math.max(...rows.map((row) => Number(row.amount)), 0);
  const incomeMode = direction === "credit";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base text-foreground">
          {incomeMode
            ? t("dashboard.incomeByTransactionTypeTitle")
            : t("dashboard.byCategoryTitle")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <ChartSkeleton />
        ) : rows.length > 0 ? (
          <div className="space-y-4">
            {rows.map((row, index) => {
              const amount = Number(row.amount);
              const width = maxAmount > 0 ? (amount / maxAmount) * 100 : 0;
              const barClass = breakdownBarClass(incomeMode, index === 0);

              return (
                <div key={row.category ?? "none"} className="space-y-2">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">
                        {incomeMode
                          ? tTransactionType(t, row.category)
                          : row.category
                            ? tCategory(t, row.category)
                            : t("common.unknown")}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {t("dashboard.categoryTransactions", { n: row.count })}
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      <div className="text-sm font-semibold tabular-nums">
                        {formatCurrency(amount, currency)}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {formatPercent(Number(row.share))}
                      </div>
                    </div>
                  </div>
                  <div className="h-2 rounded-full bg-muted">
                    <div
                      className={cn("h-2 rounded-full", barClass)}
                      style={{ width: `${width}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <EmptyState title={t("common.empty")} />
        )}
      </CardContent>
    </Card>
  );
}

function breakdownBarClass(incomeMode: boolean, topRank: boolean): string {
  if (incomeMode) return topRank ? "bg-positive" : "bg-positive/55";
  return topRank ? "bg-accent" : "bg-accent/55";
}
