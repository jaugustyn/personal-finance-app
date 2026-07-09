"use client";

import Link from "next/link";
import { ExternalLink } from "lucide-react";

import type { MerchantStat } from "@/lib/api";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { tCategory, useT } from "@/lib/i18n";
import { transactionsHref } from "@/lib/transaction-links";
import { cn, formatCurrency } from "@/lib/utils";
import type { DashboardDirection } from "../_lib/dashboard-types";
import { ChartSkeleton } from "./dashboard-section";

export function MerchantRankingCard({
  data,
  isLoading,
  currency,
  direction,
}: {
  data: MerchantStat[] | undefined;
  isLoading: boolean;
  currency: string;
  direction: DashboardDirection;
}) {
  const { t } = useT();
  const rows = data ?? [];
  const incomeMode = direction === "credit";

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle className="text-base text-foreground">
          {incomeMode
            ? t("dashboard.topIncomeSourcesTitle")
            : t("dashboard.topMerchantsTitle")}
        </CardTitle>
        <Button asChild variant="ghost" size="sm" className="h-8 px-2 text-xs">
          <Link href="/transactions">
            {t("dashboard.openTransactions")}
            <ExternalLink className="h-3.5 w-3.5" />
          </Link>
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <ChartSkeleton />
        ) : rows.length > 0 ? (
          <div className="divide-y">
            {rows.map((row, index) => {
              const txCount = t("dashboard.categoryTransactions", {
                n: row.count,
              });
              const subtitle = incomeMode
                ? txCount
                : `${
                    row.category ? tCategory(t, row.category) : t("common.unknown")
                  } · ${txCount}`;

              return (
                <Link
                  key={row.merchant_canonical_key ?? row.merchant}
                  href={transactionsHref({
                    merchant_canonical_key: row.merchant_canonical_key,
                    search: row.merchant_canonical_key ? undefined : row.merchant,
                  })}
                  className="grid grid-cols-[2rem_minmax(0,1fr)_auto] items-center gap-3 py-3 transition-colors hover:bg-muted/50"
                >
                  <div
                    className={cn(
                      "flex h-7 w-7 items-center justify-center rounded-md text-xs font-semibold",
                      incomeMode
                        ? "bg-positive/10 text-positive"
                        : "bg-muted text-muted-foreground",
                    )}
                  >
                    {index + 1}
                  </div>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium">
                      {row.merchant_display || row.merchant}
                    </div>
                    <div className="truncate text-xs text-muted-foreground">
                      {subtitle}
                    </div>
                  </div>
                  <div
                    className={cn(
                      "text-right text-sm font-semibold tabular-nums",
                      incomeMode && "text-positive",
                    )}
                  >
                    {formatCurrency(Number(row.amount), currency)}
                  </div>
                </Link>
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
