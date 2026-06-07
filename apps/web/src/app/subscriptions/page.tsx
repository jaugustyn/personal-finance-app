"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { ConfidenceBadge } from "@/components/status-badge";
import { formatCurrency, formatDate } from "@/lib/utils";
import { Repeat } from "lucide-react";
import { CardGridSkeleton } from "@/components/ui/skeleton";
import { useT } from "@/lib/i18n";

export default function SubscriptionsPage() {
  const { t } = useT();
  const [minConfidence, setMinConfidence] = useState(0.5);
  const query = useQuery({
    queryKey: ["subscriptions", minConfidence],
    queryFn: () => api.subscriptions(minConfidence),
  });

  const monthlyTotal = useMemo(
    () =>
      (query.data ?? []).reduce((sum, s) => sum + s.estimated_monthly_cost, 0),
    [query.data],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("subscriptions.title")}
        description={t("subscriptions.subtitle")}
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">
            {t("anomalies.filter")}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">
              {t("subscriptions.minConfidence", {
                value: (minConfidence * 100).toFixed(0),
              })}
            </label>
            <Input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={minConfidence}
              onChange={(e) => setMinConfidence(Number(e.target.value))}
              className="w-64"
            />
          </div>
          <div className="ml-auto text-right">
            <div className="text-xs text-muted-foreground">
              {t("subscriptions.monthlyTotal")}
            </div>
            <div className="text-lg font-semibold tabular-nums">
              {formatCurrency(monthlyTotal)}
            </div>
          </div>
        </CardContent>
      </Card>

      {query.isLoading ? (
        <CardGridSkeleton />
      ) : !query.data || query.data.length === 0 ? (
        <EmptyState title={t("subscriptions.empty")} icon={Repeat} />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {query.data.map((s, i) => (
            <Card key={`${s.merchant}-${i}`}>
              <CardContent className="space-y-3 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 font-medium">
                    <Repeat className="h-4 w-4 text-muted-foreground" />
                    {s.merchant}
                  </div>
                  <ConfidenceBadge value={s.confidence} />
                </div>
                <div className="text-2xl font-semibold tabular-nums">
                  {formatCurrency(s.estimated_monthly_cost)}
                  <span className="ml-1 text-sm font-normal text-muted-foreground">
                    {t("subscriptions.perMonth")}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>
                    {s.cadence} · {s.occurrences}×
                  </span>
                  <span>
                    {t("subscriptions.lastSeen", {
                      date: formatDate(s.last_seen),
                    })}
                  </span>
                </div>
                <Button asChild variant="outline" size="sm">
                  <Link
                    href={`/transactions?search=${encodeURIComponent(s.merchant)}`}
                  >
                    {t("subscriptions.openTransactions")}
                  </Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
