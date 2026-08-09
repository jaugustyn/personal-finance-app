"use client";

import Link from "next/link";
import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  PiggyBank,
  RefreshCw,
} from "lucide-react";

import { HelpTooltip } from "@/components/help-tooltip";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { AssetOverview } from "@/lib/api";
import { useFormatters, useT } from "@/lib/i18n";
import { assetTypeKey } from "../assets/_lib/asset-options";

export function DashboardAssetsSummary({
  data,
  isLoading,
  isError,
  onRetry,
}: {
  data?: AssetOverview;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}) {
  const { t } = useT();
  const { formatCurrency, formatDate, formatNumber, formatPercent } =
    useFormatters();
  const leadingAsset = data?.breakdown[0];
  const hasValuationIssues = Boolean(
    data &&
      (data.stale_count ||
        data.matured_count ||
        data.unconverted_count ||
        data.missing_valuation_count),
  );

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">
            <PiggyBank className="h-4 w-4 shrink-0 text-muted-foreground" />
            <h3 className="font-semibold text-foreground">
              {t("dashboard.assets.title")}
            </h3>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-3">
            {!isLoading && !isError && data?.account_count ? (
              <HelpTooltip
                content={
                  hasValuationIssues
                    ? t("dashboard.assets.needsReviewHint", {
                        stale: formatNumber(data.stale_count),
                        matured: formatNumber(data.matured_count),
                        unconverted: formatNumber(data.unconverted_count),
                        missing: formatNumber(data.missing_valuation_count),
                      })
                    : t("dashboard.assets.upToDateHint")
                }
              >
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  {hasValuationIssues ? (
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-warning" />
                  ) : (
                    <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-positive" />
                  )}
                  <span>
                    {hasValuationIssues
                      ? t("dashboard.assets.needsReview")
                      : t("dashboard.assets.upToDate")}
                  </span>
                </div>
              </HelpTooltip>
            ) : null}
            <Button asChild variant="ghost" size="sm" className="h-8">
              <Link href="/assets">
                {t("dashboard.assets.open")}
                <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
            </Button>
          </div>
        </div>

        {isLoading ? (
          <div className="mt-4 grid gap-5 md:grid-cols-2">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : isError ? (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
            <span>{t("dashboard.assets.loadError")}</span>
            <Button variant="outline" size="sm" onClick={onRetry}>
              <RefreshCw className="h-3.5 w-3.5" />
              {t("common.retry")}
            </Button>
          </div>
        ) : !data?.account_count ? (
          <p className="mt-3 text-sm text-muted-foreground">
            {t("dashboard.assets.empty")}
          </p>
        ) : (
          <div className="mt-4 grid gap-x-10 gap-y-5 md:grid-cols-[minmax(14rem,0.8fr)_minmax(18rem,1.2fr)] md:items-end">
            <div>
              <HelpTooltip content={t("dashboard.assets.estimatedValueHint")}>
                <p className="w-fit text-xs text-muted-foreground">
                  {t("dashboard.assets.estimatedValue")}
                </p>
              </HelpTooltip>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-foreground">
                {formatCurrency(Number(data.total_pln), data.base_currency)}
              </p>
              <p className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs text-muted-foreground">
                <span>
                  {t("dashboard.assets.counts", {
                    items: data.item_count,
                  })}
                </span>
                <span aria-hidden>·</span>
                <span>{t("assets.asOf", { date: formatDate(data.as_of) })}</span>
              </p>
            </div>

            <div className="min-w-0">
              <p className="text-xs text-muted-foreground">
                {t("dashboard.assets.largestShare")}
              </p>
              {leadingAsset ? (
                <>
                  <div className="mt-1 flex items-baseline justify-between gap-3 text-sm">
                    <span className="truncate font-medium">
                      {t(assetTypeKey(leadingAsset.asset_type))}
                    </span>
                    <span className="shrink-0 tabular-nums text-muted-foreground">
                      {formatPercent(Number(leadingAsset.share))}
                    </span>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary/75"
                      style={{
                        width: `${Math.min(100, Math.max(0, Number(leadingAsset.share) * 100))}%`,
                      }}
                    />
                  </div>
                </>
              ) : (
                <p className="mt-1 text-sm text-muted-foreground">—</p>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
