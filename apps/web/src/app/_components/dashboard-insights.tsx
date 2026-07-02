"use client";

import type { ComponentType } from "react";
import {
  AlertTriangle,
  ListChecks,
  PieChart,
  ReceiptText,
  ShoppingBag,
} from "lucide-react";

import type { CategoryBreakdown, MerchantStat } from "@/lib/api";
import { tCategory, useT } from "@/lib/i18n";
import { cn, formatCurrency, formatPercent } from "@/lib/utils";

export function InsightStrip({
  topCategory,
  topMerchant,
  transactionCount,
  reviewCount,
  anomalyCount,
  baseCurrency,
}: {
  topCategory: CategoryBreakdown | null;
  topMerchant: MerchantStat | null;
  transactionCount: number;
  reviewCount: number;
  anomalyCount: number;
  baseCurrency: string;
}) {
  const { t } = useT();
  return (
    <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
      <InsightItem
        icon={PieChart}
        label={t("dashboard.insight.topCategory")}
        value={
          topCategory?.category
            ? tCategory(t, topCategory.category)
            : t("common.empty")
        }
        detail={
          topCategory
            ? `${formatCurrency(Number(topCategory.amount), baseCurrency)} · ${formatPercent(
                Number(topCategory.share),
              )}`
            : undefined
        }
      />
      <InsightItem
        icon={ShoppingBag}
        label={t("dashboard.insight.topMerchant")}
        value={
          topMerchant?.merchant_display ??
          topMerchant?.merchant ??
          t("common.empty")
        }
        detail={
          topMerchant
            ? formatCurrency(Number(topMerchant.amount), baseCurrency)
            : undefined
        }
      />
      <InsightItem
        icon={ReceiptText}
        label={t("dashboard.insight.transactions")}
        value={String(transactionCount)}
        detail={t("dashboard.insight.transactionsHint")}
      />
      <InsightItem
        icon={ListChecks}
        label={t("dashboard.insight.review")}
        value={String(reviewCount)}
        detail={t("dashboard.insight.reviewHint")}
      />
      <InsightItem
        icon={AlertTriangle}
        label={t("dashboard.insight.alerts")}
        value={String(anomalyCount)}
        detail={t("dashboard.insight.alertsHint")}
      />
    </div>
  );
}

function InsightItem({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <div className="flex min-w-0 items-center gap-3 rounded-lg border bg-card p-3">
      <div
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-md",
          "bg-accent-soft text-accent-soft-foreground",
        )}
      >
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="truncate text-sm font-semibold text-foreground">{value}</div>
        {detail && (
          <div className="truncate text-xs text-muted-foreground">{detail}</div>
        )}
      </div>
    </div>
  );
}
