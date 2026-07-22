"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Repeat } from "lucide-react";
import {
  api,
  type Subscription,
  type SubscriptionOverview,
  type SubscriptionPreferenceInput,
} from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { cn } from "@/lib/utils";
import { showErrorToast } from "@/lib/toasts";
import { CardGridSkeleton } from "@/components/ui/skeleton";
import { useFormatters, useT, type TranslationKey } from "@/lib/i18n";
import { invalidateSubscriptionData, queryKeys } from "@/lib/query-keys";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SubscriptionCard } from "./_components/subscription-card";
import { SubscriptionDetailsSheet } from "./_components/subscription-details-sheet";
import { FixedChargesTab } from "./_components/fixed-charges-tab";
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
  const [scope, setScope] = useState<SubscriptionScope>("all");
  const [activeTab, setActiveTab] =
    useState<RecurringPaymentsTab>("subscriptions");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const includeRejected = true;

  const query = useQuery({
    queryKey: queryKeys.subscriptions.list(0, includeRejected),
    queryFn: () => api.subscriptions(0, includeRejected),
  });
  const overviewQuery = useQuery({
    queryKey: queryKeys.subscriptions.overview,
    queryFn: () => api.subscriptionsOverview(),
  });

  const preference = useMutation({
    mutationFn: api.saveSubscriptionPreference,
    onMutate: async (variables) => {
      const visibleListKey = queryKeys.subscriptions.list(0, false);
      const fullListKey = queryKeys.subscriptions.list(0, true);
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
          queryKeys.subscriptions.list(0, false),
          context.previousVisible,
        );
      }
      if (context?.previousFull !== undefined) {
        queryClient.setQueryData(
          queryKeys.subscriptions.list(0, true),
          context.previousFull,
        );
      }
      showErrorToast(error, t("toast.error"));
    },
    onSettled: () => {
      void invalidateSubscriptionData(queryClient);
    },
  });

  const attentionCount = useMemo(
    () =>
      (query.data ?? []).filter(requiresSubscriptionDecision).length,
    [query.data],
  );

  const scopeCounts = useMemo(() => {
    const rows = query.data ?? [];
    return {
      all: rows.length,
      attention: rows.filter(requiresSubscriptionDecision).length,
      active: rows.filter(
        (row) => !isHiddenSubscription(row) && !requiresSubscriptionDecision(row),
      ).length,
      hidden: rows.filter(isHiddenSubscription).length,
    } satisfies Record<SubscriptionScope, number>;
  }, [query.data]);

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
    <div className="space-y-5">
      <PageHeader title={t("subscriptions.title")} />

      <Tabs
        value={activeTab}
        onValueChange={(value) => {
          if (value === "subscriptions" || value === "fixed") {
            setActiveTab(value);
            setSelectedKey(null);
          }
        }}
        className="space-y-5"
      >
        <TabsList className="h-9 items-stretch justify-start divide-x divide-border/60 overflow-hidden rounded-md border border-input bg-card p-0">
          <TabsTrigger
            value="subscriptions"
            className="h-full rounded-none py-0 focus-visible:z-10 focus-visible:ring-inset data-[state=active]:bg-accent-soft data-[state=active]:text-accent-soft-foreground data-[state=active]:shadow-none"
          >
            {t("subscriptions.tab.subscriptions")}
          </TabsTrigger>
          <TabsTrigger
            value="fixed"
            className="h-full rounded-none py-0 focus-visible:z-10 focus-visible:ring-inset data-[state=active]:bg-accent-soft data-[state=active]:text-accent-soft-foreground data-[state=active]:shadow-none"
          >
            {t("subscriptions.tab.fixed")}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="subscriptions" className="space-y-5">
          {overviewQuery.isError ? (
            <ErrorState
              variant="compact"
              onRetry={() => void overviewQuery.refetch()}
            />
          ) : (
            <SubscriptionSummary
              overview={overview}
              attentionCount={attentionCount}
              isLoading={overviewQuery.isLoading || query.isLoading}
            />
          )}

          <SubscriptionScopeFilter
            value={scope}
            counts={scopeCounts}
            onChange={setScope}
            labelFor={(item) => t(SUBSCRIPTION_SCOPE_LABELS[item])}
          />

          {query.isError ? (
            <ErrorState
              title={t("subscriptions.error")}
              onRetry={() => {
                void query.refetch();
                void overviewQuery.refetch();
              }}
            />
          ) : query.isLoading ? (
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
                  onDetails={() =>
                    setSelectedKey(subscription.merchant_key)
                  }
                />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="fixed">
          <FixedChargesTab />
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

function SubscriptionSummary({
  overview,
  attentionCount,
  isLoading,
}: {
  overview: SubscriptionOverview | undefined;
  attentionCount: number;
  isLoading: boolean;
}) {
  const { t } = useT();
  const { formatCurrency } = useFormatters();
  const currency = overview?.base_currency ?? "PLN";
  const items = [
    {
      label: t("subscriptions.monthlyTotal"),
      value: overview
        ? formatCurrency(overview.monthly_total, currency)
        : "—",
    },
    {
      label: t("subscriptions.yearlyTotal"),
      value: overview
        ? formatCurrency(overview.yearly_total, currency)
        : "—",
    },
    {
      label: t("subscriptions.next30Total"),
      value: overview
        ? formatCurrency(overview.next_30_days_total, currency)
        : "—",
    },
    {
      label: t("subscriptions.needsAttention"),
      value: isLoading ? "—" : String(attentionCount),
    },
  ];

  return (
    <section className="grid overflow-hidden rounded-lg border bg-card sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item, index) => (
        <div
          key={item.label}
          className={cn(
            "px-4 py-3.5",
            index > 0 && "border-t sm:border-t-0",
            index % 2 === 1 && "sm:border-l",
            index >= 2 && "sm:border-t xl:border-t-0",
            index > 0 && "xl:border-l",
          )}
        >
          <div className="text-xs text-muted-foreground">{item.label}</div>
          <div className="mt-1 text-lg font-semibold tabular-nums">
            {item.value}
          </div>
        </div>
      ))}
    </section>
  );
}

function SubscriptionScopeFilter({
  value,
  counts,
  onChange,
  labelFor,
}: {
  value: SubscriptionScope;
  counts: Record<SubscriptionScope, number>;
  onChange: (value: SubscriptionScope) => void;
  labelFor: (value: SubscriptionScope) => string;
}) {
  const { t } = useT();
  return (
    <nav
      className="flex max-w-full overflow-x-auto border-b"
      aria-label={t("subscriptions.scopeLabel")}
    >
      {SUBSCRIPTION_SCOPES.map((item) => {
        const active = item === value;
        return (
          <button
            key={item}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(item)}
            className={cn(
              "inline-flex h-11 shrink-0 items-center justify-center gap-2 whitespace-nowrap border-b-2 px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
              active
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {labelFor(item)}
            <Badge
              variant="secondary"
              className={cn(
                "h-5 min-w-5 justify-center px-1.5 text-[11px] tabular-nums",
                active && "bg-primary/10 text-primary",
              )}
            >
              {counts[item]}
            </Badge>
          </button>
        );
      })}
    </nav>
  );
}
