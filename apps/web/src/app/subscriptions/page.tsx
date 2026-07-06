"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Construction, Repeat } from "lucide-react";
import {
  api,
  type Subscription,
  type SubscriptionPreferenceInput,
} from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { cn, formatCurrency } from "@/lib/utils";
import { showErrorToast } from "@/lib/toasts";
import { CardGridSkeleton } from "@/components/ui/skeleton";
import { useT, type TranslationKey } from "@/lib/i18n";
import { useLocalStorageState } from "@/hooks/use-local-storage-state";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { MetricCard } from "./_components/metric-card";
import { SubscriptionCard } from "./_components/subscription-card";
import { SubscriptionDetailsSheet } from "./_components/subscription-details-sheet";
import { UpcomingPaymentsCard } from "./_components/upcoming-payments-card";
import { SUBSCRIPTION_QUERY_KEYS } from "./_lib/query-keys";
import type { SubscriptionScope } from "./_lib/subscription-format";

type RecurringPaymentsTab = "subscriptions" | "fixed";

const SUBSCRIPTION_SCOPES: SubscriptionScope[] = [
  "all",
  "attention",
  "active",
  "hidden",
];
const SUBSCRIPTION_SCOPE_LABELS: Record<SubscriptionScope, TranslationKey> = {
  all: "subscriptions.scope.all",
  attention: "subscriptions.scope.attention",
  active: "subscriptions.scope.active",
  hidden: "subscriptions.scope.hidden",
};

function isHiddenSubscription(row: Subscription) {
  return row.user_decision === "rejected" || row.status === "ignored";
}

function requiresSubscriptionDecision(row: Subscription) {
  return !row.is_confirmed && !isHiddenSubscription(row);
}

function isRecurringPaymentsTab(value: string): value is RecurringPaymentsTab {
  return value === "subscriptions" || value === "fixed";
}

function applyPreferenceToSubscription(
  row: Subscription,
  payload: SubscriptionPreferenceInput,
): Subscription {
  if (row.merchant_key !== payload.subscription_key) return row;
  if (payload.action === "confirm") {
    return {
      ...row,
      display_name: payload.display_name ?? row.display_name,
      is_confirmed: true,
      user_decision: "confirmed",
    };
  }
  if (payload.action === "reject") {
    return {
      ...row,
      is_confirmed: false,
      status: "ignored",
      user_decision: "rejected",
    };
  }
  if (payload.action === "restore") {
    return {
      ...row,
      is_confirmed: false,
      status: row.status === "ignored" ? "needs_review" : row.status,
      user_decision: "suggested",
    };
  }
  if (payload.cadence_override) {
    return {
      ...row,
      cadence: payload.cadence_override,
    };
  }
  return row;
}

function optimisticSubscriptionList(
  rows: Subscription[] | undefined,
  payload: SubscriptionPreferenceInput,
  includeRejected: boolean,
): Subscription[] | undefined {
  if (!rows) return rows;
  if (payload.action === "reject" && !includeRejected) {
    return rows.filter((row) => row.merchant_key !== payload.subscription_key);
  }
  return rows.map((row) => applyPreferenceToSubscription(row, payload));
}

export default function SubscriptionsPage() {
  const { t } = useT();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useLocalStorageState<RecurringPaymentsTab>(
    "finance.recurringPayments.tab",
    "subscriptions",
  );
  const [scope, setScope] = useState<SubscriptionScope>("all");
  const recurringTab = isRecurringPaymentsTab(activeTab)
    ? activeTab
    : "subscriptions";
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const includeRejected = scope === "hidden" || scope === "all";

  useEffect(() => {
    if (!isRecurringPaymentsTab(activeTab)) {
      setActiveTab("subscriptions");
    }
  }, [activeTab, setActiveTab]);

  const query = useQuery({
    queryKey: SUBSCRIPTION_QUERY_KEYS.list(includeRejected),
    queryFn: () => api.subscriptions(0, includeRejected),
  });
  const overviewQuery = useQuery({
    queryKey: SUBSCRIPTION_QUERY_KEYS.overview,
    queryFn: () => api.subscriptionsOverview(),
  });

  const preference = useMutation({
    mutationFn: api.saveSubscriptionPreference,
    onMutate: async (variables) => {
      const visibleListKey = SUBSCRIPTION_QUERY_KEYS.list(false);
      const fullListKey = SUBSCRIPTION_QUERY_KEYS.list(true);
      await Promise.all([
        queryClient.cancelQueries({ queryKey: visibleListKey }),
        queryClient.cancelQueries({ queryKey: fullListKey }),
      ]);
      const previousVisible =
        queryClient.getQueryData<Subscription[]>(visibleListKey);
      const previousFull = queryClient.getQueryData<Subscription[]>(fullListKey);
      queryClient.setQueryData<Subscription[]>(visibleListKey, (current) =>
        optimisticSubscriptionList(current, variables, false),
      );
      queryClient.setQueryData<Subscription[]>(fullListKey, (current) =>
        optimisticSubscriptionList(current, variables, true),
      );
      return { previousVisible, previousFull };
    },
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: SUBSCRIPTION_QUERY_KEYS.overview,
      });
      if (variables.action === "reject") {
        toast.success(t("subscriptions.rejectedSaved"));
      } else if (variables.action === "restore") {
        toast.success(t("subscriptions.restored"));
      } else {
        toast.success(t("toast.saved"));
      }
    },
    onError: (error, _variables, context) => {
      if (context?.previousVisible !== undefined) {
        queryClient.setQueryData(
          SUBSCRIPTION_QUERY_KEYS.list(false),
          context.previousVisible,
        );
      }
      if (context?.previousFull !== undefined) {
        queryClient.setQueryData(
          SUBSCRIPTION_QUERY_KEYS.list(true),
          context.previousFull,
        );
      }
      showErrorToast(error, t("toast.error"));
    },
    onSettled: () => {
      void queryClient.invalidateQueries({
        queryKey: SUBSCRIPTION_QUERY_KEYS.allLists,
      });
    },
  });

  const attentionCount = useMemo(
    () =>
      (query.data ?? []).filter(requiresSubscriptionDecision).length,
    [query.data],
  );

  const visibleSubscriptions = useMemo(() => {
    const rows = [...(query.data ?? [])].filter((row) => {
      if (scope === "all") return true;
      if (scope === "hidden") {
        return isHiddenSubscription(row);
      }
      if (isHiddenSubscription(row)) return false;
      if (scope === "attention") return requiresSubscriptionDecision(row);
      return !requiresSubscriptionDecision(row);
    });
    const statusRank: Record<Subscription["status"], number> = {
      price_increased: 0,
      needs_review: 1,
      new: 2,
      annual_renewal: 3,
      paused_or_missing: 4,
      price_decreased: 5,
      active: 6,
      probably_cancelled: 7,
      ignored: 8,
    };
    return rows.sort((a, b) => {
      const statusDelta = statusRank[a.status] - statusRank[b.status];
      if (statusDelta !== 0) return statusDelta;
      const nextDelta = (a.next_expected_date ?? "9999").localeCompare(
        b.next_expected_date ?? "9999",
      );
      if (nextDelta !== 0) return nextDelta;
      return b.estimated_monthly_cost - a.estimated_monthly_cost;
    });
  }, [query.data, scope]);

  const selected = useMemo(
    () => (query.data ?? []).find((row) => row.merchant_key === selectedKey) ?? null,
    [query.data, selectedKey],
  );

  const overview = overviewQuery.data;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("subscriptions.title")}
        description={t("subscriptions.subtitle")}
      />

      <div className="grid gap-3 md:grid-cols-4">
        <MetricCard
          label={t("subscriptions.monthlyTotal")}
          value={formatCurrency(
            overview?.monthly_total ?? 0,
            overview?.base_currency ?? "PLN",
          )}
        />
        <MetricCard
          label={t("subscriptions.yearlyTotal")}
          value={formatCurrency(
            overview?.yearly_total ?? 0,
            overview?.base_currency ?? "PLN",
          )}
        />
        <MetricCard
          label={t("subscriptions.next30Total")}
          value={formatCurrency(
            overview?.next_30_days_total ?? 0,
            overview?.base_currency ?? "PLN",
          )}
        />
        <MetricCard
          label={t("subscriptions.needsAttention")}
          value={String(attentionCount)}
        />
      </div>

      <Tabs
        value={recurringTab}
        onValueChange={(value) => {
          if (isRecurringPaymentsTab(value)) setActiveTab(value);
        }}
        className="space-y-4"
      >
        <TabsList className="h-auto flex-wrap justify-start">
          <TabsTrigger value="subscriptions">
            {t("subscriptions.tab.subscriptions")}
          </TabsTrigger>
          <TabsTrigger value="fixed">
            {t("subscriptions.tab.fixed")}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="subscriptions" className="space-y-4">
          <UpcomingPaymentsCard overview={overview} />

          <section className="space-y-3">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold">
                  {t("subscriptions.listTitle")}
                </h2>
                <p className="text-xs text-muted-foreground">
                  {t("subscriptions.listHint")}
                </p>
              </div>
              <div className="text-xs text-muted-foreground">
                {t("subscriptions.visibleCount", {
                  count: visibleSubscriptions.length,
                })}
              </div>
            </div>

            <SubscriptionScopeFilter
              value={scope}
              onChange={setScope}
              labelFor={(item) => t(SUBSCRIPTION_SCOPE_LABELS[item])}
            />

            {query.isLoading ? (
              <CardGridSkeleton />
            ) : !query.data || visibleSubscriptions.length === 0 ? (
              <EmptyState title={t("subscriptions.empty")} icon={Repeat} />
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {visibleSubscriptions.map((subscription) => (
                  <SubscriptionCard
                    key={subscription.merchant_key}
                    subscription={subscription}
                    isPending={preference.isPending}
                    onConfirm={() =>
                      preference.mutate({
                        subscription_key: subscription.merchant_key,
                        action: "confirm",
                        display_name: subscription.display_name,
                      })
                    }
                    onReject={() =>
                      preference.mutate({
                        subscription_key: subscription.merchant_key,
                        action: "reject",
                      })
                    }
                    onRestore={() =>
                      preference.mutate({
                        subscription_key: subscription.merchant_key,
                        action: "restore",
                      })
                    }
                    onDetails={() => setSelectedKey(subscription.merchant_key)}
                  />
                ))}
              </div>
            )}
          </section>
        </TabsContent>

        <TabsContent value="fixed">
          <FixedPaymentsPlaceholder />
        </TabsContent>
      </Tabs>

      <SubscriptionDetailsSheet
        subscription={selected}
        open={selected !== null}
        isPending={preference.isPending}
        onOpenChange={(open) => {
          if (!open) setSelectedKey(null);
        }}
        onPreference={(payload) => preference.mutate(payload)}
      />
    </div>
  );
}

function FixedPaymentsPlaceholder() {
  const { t } = useT();
  return (
    <Card>
      <CardContent className="flex min-h-64 flex-col items-center justify-center gap-3 p-8 text-center">
        <div className="rounded-full bg-muted p-3 text-muted-foreground">
          <Construction className="h-6 w-6" />
        </div>
        <Badge variant="secondary">{t("subscriptions.fixed.badge")}</Badge>
        <div className="space-y-1">
          <div className="text-base font-medium">
            {t("subscriptions.fixed.title")}
          </div>
          <p className="max-w-xl text-sm text-muted-foreground">
            {t("subscriptions.fixed.description")}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function SubscriptionScopeFilter({
  value,
  onChange,
  labelFor,
}: {
  value: SubscriptionScope;
  onChange: (value: SubscriptionScope) => void;
  labelFor: (value: SubscriptionScope) => string;
}) {
  return (
    <div className="inline-flex h-auto flex-wrap items-center justify-start rounded-lg bg-muted p-1 text-muted-foreground">
      {SUBSCRIPTION_SCOPES.map((item) => {
        const active = item === value;
        return (
          <button
            key={item}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(item)}
            className={cn(
              "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              active
                ? "bg-card text-foreground shadow-sm"
                : "hover:bg-background/60 hover:text-foreground",
            )}
          >
            {labelFor(item)}
          </button>
        );
      })}
    </div>
  );
}
