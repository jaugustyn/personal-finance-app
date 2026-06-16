"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FilterField, FilterPanel } from "@/components/filter-panel";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { ConfidenceBadge } from "@/components/status-badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatCurrency, formatDate } from "@/lib/utils";
import { Repeat } from "lucide-react";
import { CardGridSkeleton } from "@/components/ui/skeleton";
import { useT } from "@/lib/i18n";
import { useLocalStorageState } from "@/hooks/use-local-storage-state";
import { transactionsHref } from "@/lib/transaction-links";

export default function SubscriptionsPage() {
  const { t } = useT();
  const qc = useQueryClient();
  const [minConfidence, setMinConfidence] = useLocalStorageState(
    "finance.subscriptions.minConfidence",
    0.5,
  );
  const [sortBy, setSortBy] = useLocalStorageState<
    "cost_desc" | "confidence_desc" | "last_seen_desc" | "merchant_asc"
  >("finance.subscriptions.sortBy", "cost_desc");
  const query = useQuery({
    queryKey: ["subscriptions", minConfidence],
    queryFn: () => api.subscriptions(minConfidence),
  });
  const feedback = useMutation({
    mutationFn: ({
      merchant,
      action,
    }: {
      merchant: string;
      action: "confirm" | "hide";
    }) => api.recordSubscriptionFeedback(merchant, action),
    onSuccess: (_result, variables) => {
      qc.invalidateQueries({ queryKey: ["subscriptions"] });
      qc.invalidateQueries({ queryKey: ["mlDashboard"] });
      toast.success(
        variables.action === "confirm"
          ? t("subscriptions.feedback.confirmed")
          : t("subscriptions.feedback.hidden"),
      );
    },
    onError: () => toast.error(t("toast.error")),
  });

  const sortedSubscriptions = useMemo(() => {
    const rows = [...(query.data ?? [])];
    return rows.sort((a, b) => {
      switch (sortBy) {
        case "confidence_desc":
          return b.confidence - a.confidence;
        case "last_seen_desc":
          return b.last_seen.localeCompare(a.last_seen);
        case "merchant_asc":
          return a.merchant.localeCompare(b.merchant, "pl", {
            sensitivity: "base",
          });
        case "cost_desc":
        default:
          return b.estimated_monthly_cost - a.estimated_monthly_cost;
      }
    });
  }, [query.data, sortBy]);
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

      <FilterPanel
        gridClassName="md:grid-cols-[minmax(16rem,1fr)_14rem_auto] xl:grid-cols-[minmax(16rem,1fr)_14rem_auto]"
      >
        <FilterField
          label={t("subscriptions.minConfidence", {
            value: (minConfidence * 100).toFixed(0),
          })}
        >
          <Input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={minConfidence}
            onChange={(e) => setMinConfidence(Number(e.target.value))}
            className="w-full"
          />
        </FilterField>
        <FilterField label={t("subscriptions.sort")}>
          <Select
            value={sortBy}
            onValueChange={(v) => setSortBy(v as typeof sortBy)}
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="cost_desc">
                {t("subscriptions.sort.cost")}
              </SelectItem>
              <SelectItem value="confidence_desc">
                {t("subscriptions.sort.confidence")}
              </SelectItem>
              <SelectItem value="last_seen_desc">
                {t("subscriptions.sort.lastSeen")}
              </SelectItem>
              <SelectItem value="merchant_asc">
                {t("subscriptions.sort.merchant")}
              </SelectItem>
            </SelectContent>
          </Select>
        </FilterField>
        <div className="self-end text-right">
          <div className="text-xs text-muted-foreground">
            {t("subscriptions.monthlyTotal")}
          </div>
          <div className="text-lg font-semibold tabular-nums">
            {formatCurrency(monthlyTotal)}
          </div>
        </div>
      </FilterPanel>

      {query.isLoading ? (
        <CardGridSkeleton />
      ) : !query.data || query.data.length === 0 ? (
        <EmptyState title={t("subscriptions.empty")} icon={Repeat} />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {sortedSubscriptions.map((s, i) => (
            <Card key={`${s.merchant}-${i}`}>
              <CardContent className="space-y-3 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div
                    className="flex min-w-0 items-center gap-2 font-medium"
                    title={s.merchant}
                  >
                    <Repeat className="h-4 w-4 text-muted-foreground" />
                    <span className="truncate">{s.merchant}</span>
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
                <div className="flex flex-wrap gap-2">
                  <Button asChild variant="outline" size="sm">
                    <Link href={transactionsHref({ search: s.merchant })}>
                      {t("subscriptions.openTransactions")}
                    </Link>
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={feedback.isPending}
                    onClick={() =>
                      feedback.mutate({
                        merchant: s.merchant,
                        action: "confirm",
                      })
                    }
                  >
                    {t("subscriptions.confirm")}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={feedback.isPending}
                    onClick={() =>
                      feedback.mutate({ merchant: s.merchant, action: "hide" })
                    }
                  >
                    {t("subscriptions.hide")}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
