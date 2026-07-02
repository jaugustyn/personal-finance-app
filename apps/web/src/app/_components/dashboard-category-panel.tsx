"use client";

import type { CategoryBreakdown } from "@/lib/api";
import { EmptyState } from "@/components/empty-state";
import { CategoryDonut } from "@/components/charts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { tCategory, useT } from "@/lib/i18n";
import { formatCurrency } from "@/lib/utils";
import { ChartSkeleton } from "./dashboard-section";

export function CategoryPanel({
  data,
  isLoading,
  currency,
}: {
  data: CategoryBreakdown[] | undefined;
  isLoading: boolean;
  currency: string;
}) {
  const { t } = useT();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base text-foreground">
          {t("dashboard.byCategoryTitle")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <ChartSkeleton />
        ) : data && data.length > 0 ? (
          <>
            <CategoryDonut data={data} />
            <div className="space-y-2">
              {data.slice(0, 5).map((row) => (
                <div
                  key={row.category ?? "none"}
                  className="flex items-center justify-between gap-3 text-sm"
                >
                  <div className="min-w-0 truncate font-medium">
                    {row.category ? tCategory(t, row.category) : t("common.unknown")}
                  </div>
                  <div className="shrink-0 text-right tabular-nums text-muted-foreground">
                    {formatCurrency(Number(row.amount), currency)}
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <EmptyState title={t("common.empty")} />
        )}
      </CardContent>
    </Card>
  );
}
