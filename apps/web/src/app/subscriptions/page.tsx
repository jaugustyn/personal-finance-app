"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  CalendarClock,
  Check,
  ChevronRight,
  ExternalLink,
  Repeat,
  RotateCcw,
  XCircle,
} from "lucide-react";
import { api, type Subscription, type SubscriptionPreferenceInput } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { FilterField, FilterPanel } from "@/components/filter-panel";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { formatCurrency, formatDate } from "@/lib/utils";
import { CardGridSkeleton } from "@/components/ui/skeleton";
import { useT } from "@/lib/i18n";
import { useLocalStorageState } from "@/hooks/use-local-storage-state";
import { transactionsHref } from "@/lib/transaction-links";

const ATTENTION_STATUSES = new Set<Subscription["status"]>([
  "price_increased",
  "needs_review",
  "new",
  "annual_renewal",
  "paused_or_missing",
]);

const statusTone: Record<Subscription["status"], string> = {
  active: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  new: "border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-300",
  price_increased: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  price_decreased: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  probably_cancelled: "border-muted bg-muted text-muted-foreground",
  paused_or_missing: "border-orange-500/30 bg-orange-500/10 text-orange-700 dark:text-orange-300",
  annual_renewal: "border-violet-500/30 bg-violet-500/10 text-violet-700 dark:text-violet-300",
  needs_review: "border-yellow-500/30 bg-yellow-500/10 text-yellow-700 dark:text-yellow-300",
  ignored: "border-muted bg-muted text-muted-foreground",
};

const statusLabels: Record<Subscription["status"], string> = {
  active: "Aktywna",
  new: "Nowa",
  price_increased: "Podwyżka",
  price_decreased: "Obniżka",
  probably_cancelled: "Prawdopodobnie anulowana",
  paused_or_missing: "Brak płatności",
  annual_renewal: "Roczne odnowienie",
  needs_review: "Do sprawdzenia",
  ignored: "Ukryta",
};

const statusFilterOptions: Subscription["status"][] = [
  "active",
  "new",
  "price_increased",
  "price_decreased",
  "probably_cancelled",
  "paused_or_missing",
  "annual_renewal",
  "needs_review",
  "ignored",
];

const cadenceLabels: Record<string, string> = {
  weekly: "Co tydzień",
  biweekly: "Co 2 tygodnie",
  monthly: "Co miesiąc",
  yearly: "Co rok",
  unknown: "Nieznany",
};

type SortMode = "status" | "next_due" | "cost_desc" | "last_seen_desc" | "merchant_asc";
type StatusFilter = "all" | "attention" | "rejected" | Subscription["status"];
type CadenceOverride = NonNullable<SubscriptionPreferenceInput["cadence_override"]>;

function merchantAliasSearch(subscription: Subscription): string {
  return subscription.merchant_key.split("|")[0] || subscription.display_name;
}

function sourceLabel(
  source: Subscription["source"],
  t: ReturnType<typeof useT>["t"],
): string {
  switch (source) {
    case "category":
      return t("subscriptions.source.category");
    case "confirmed":
      return t("subscriptions.source.confirmed");
    case "preference":
      return t("subscriptions.source.preference");
    case "detected":
    default:
      return t("subscriptions.source.detected");
  }
}

export default function SubscriptionsPage() {
  const { t } = useT();
  const queryClient = useQueryClient();
  const [sortBy, setSortBy] = useLocalStorageState<SortMode>(
    "finance.subscriptions.sortBy.v2",
    "status",
  );
  const [statusFilter, setStatusFilter] = useLocalStorageState<StatusFilter>(
    "finance.subscriptions.statusFilter",
    "all",
  );
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const includeRejected = statusFilter === "rejected";

  const query = useQuery({
    queryKey: ["subscriptions", includeRejected],
    queryFn: () => api.subscriptions(0, includeRejected),
  });
  const overviewQuery = useQuery({
    queryKey: ["subscriptions-overview"],
    queryFn: () => api.subscriptionsOverview(),
  });

  const preference = useMutation({
    mutationFn: api.saveSubscriptionPreference,
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
      void queryClient.invalidateQueries({ queryKey: ["subscriptions-overview"] });
      if (variables.action === "reject") {
        toast.success(t("subscriptions.rejectedSaved"), {
          action: {
            label: t("subscriptions.restore"),
            onClick: () =>
              preference.mutate({
                subscription_key: variables.subscription_key,
                action: "restore",
              }),
          },
        });
      } else if (variables.action === "restore") {
        toast.success(t("subscriptions.restored"));
      } else {
        toast.success(t("toast.saved"));
      }
    },
    onError: () => toast.error(t("toast.error")),
  });

  const attentionCount = useMemo(
    () =>
      (query.data ?? []).filter((row) => ATTENTION_STATUSES.has(row.status)).length,
    [query.data],
  );

  const visibleSubscriptions = useMemo(() => {
    const rows = [...(query.data ?? [])].filter((row) => {
      if (statusFilter === "rejected") return row.user_decision === "rejected";
      if (row.user_decision === "rejected") return false;
      if (statusFilter === "all") return true;
      if (statusFilter === "attention") return ATTENTION_STATUSES.has(row.status);
      return row.status === statusFilter;
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
      switch (sortBy) {
        case "next_due":
          return (a.next_expected_date ?? "9999").localeCompare(
            b.next_expected_date ?? "9999",
          );
        case "cost_desc":
          return b.estimated_monthly_cost - a.estimated_monthly_cost;
        case "last_seen_desc":
          return b.last_seen.localeCompare(a.last_seen);
        case "merchant_asc":
          return a.display_name.localeCompare(b.display_name, "pl", {
            sensitivity: "base",
          });
        case "status":
        default:
          return statusRank[a.status] - statusRank[b.status];
      }
    });
  }, [query.data, sortBy, statusFilter]);

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

      <Card>
        <CardContent className="space-y-3 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold">
                {t("subscriptions.upcoming")}
              </h2>
              <p className="text-xs text-muted-foreground">
                {t("subscriptions.upcomingHint")}
              </p>
            </div>
            <CalendarClock className="h-4 w-4 text-muted-foreground" />
          </div>
          {!overview || overview.upcoming.length === 0 ? (
            <div className="text-sm text-muted-foreground">
              {t("subscriptions.upcomingEmpty")}
            </div>
          ) : (
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {overview.upcoming.slice(0, 6).map((item) => (
                <div
                  key={`${item.subscription_key}-${item.due_date}`}
                  className="rounded-md border bg-muted/20 p-3 text-sm"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-medium">{item.display_name}</span>
                    <span className="shrink-0 tabular-nums">
                      {formatCurrency(item.amount_base, item.base_currency)}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {formatDate(item.due_date)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <FilterPanel gridClassName="md:grid-cols-[14rem_14rem]">
        <FilterField label={t("subscriptions.filterStatus")}>
          <Select
            value={statusFilter}
            onValueChange={(value) => setStatusFilter(value as StatusFilter)}
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("subscriptions.filterStatus.all")}</SelectItem>
              <SelectItem value="attention">
                {t("subscriptions.filterStatus.attention")}
              </SelectItem>
              <SelectItem value="rejected">
                {t("subscriptions.filterStatus.rejected")}
              </SelectItem>
              {statusFilterOptions.map((status) => (
                <SelectItem key={status} value={status}>
                  {statusLabels[status]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FilterField>
        <FilterField label={t("subscriptions.sort")}>
          <Select value={sortBy} onValueChange={(value) => setSortBy(value as SortMode)}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="status">
                {t("subscriptions.sort.status")}
              </SelectItem>
              <SelectItem value="next_due">
                {t("subscriptions.sort.nextDue")}
              </SelectItem>
              <SelectItem value="cost_desc">
                {t("subscriptions.sort.cost")}
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
      </FilterPanel>

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

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="mt-1 text-xl font-semibold tabular-nums">{value}</div>
      </CardContent>
    </Card>
  );
}

function SubscriptionCard({
  subscription,
  isPending,
  onConfirm,
  onRestore,
  onDetails,
}: {
  subscription: Subscription;
  isPending: boolean;
  onConfirm: () => void;
  onRestore: () => void;
  onDetails: () => void;
}) {
  const { t } = useT();
  const isRejected = subscription.user_decision === "rejected";
  return (
    <Card>
      <CardContent className="flex h-full flex-col gap-4 p-4">
        <div className="min-w-0 space-y-2">
          <div className="flex items-start justify-between gap-2">
            <Link
              href={transactionsHref({ search: subscription.display_name })}
              className="min-w-0 truncate font-medium underline-offset-4 hover:underline"
              title={subscription.display_name}
            >
              {subscription.display_name}
            </Link>
            <Badge className={statusTone[subscription.status]}>
              {isRejected
                ? t("subscriptions.rejected")
                : statusLabels[subscription.status]}
            </Badge>
          </div>
          <div className="text-2xl font-semibold tabular-nums">
            {formatCurrency(
              subscription.estimated_monthly_cost,
              subscription.base_currency,
            )}
            <span className="ml-1 text-sm font-normal text-muted-foreground">
              {t("subscriptions.perMonth")}
            </span>
          </div>
        </div>

        <div className="mt-auto grid grid-cols-3 gap-2 rounded-md bg-muted/30 p-2 text-xs">
          <div className="min-w-0">
            <div className="truncate text-muted-foreground">
              {t("subscriptions.nextPaymentShort")}
            </div>
            <div className="mt-1 truncate font-medium tabular-nums">
              {subscription.next_expected_date
                ? formatDate(subscription.next_expected_date)
                : t("common.unknown")}
            </div>
          </div>
          <div className="min-w-0">
            <div className="truncate text-muted-foreground">
              {t("subscriptions.cadence")}
            </div>
            <div className="mt-1 truncate font-medium">
              {cadenceLabels[subscription.cadence] ?? subscription.cadence}
            </div>
          </div>
          <div className="min-w-0">
            <div className="truncate text-muted-foreground">
              {t("subscriptions.lastPaymentShort")}
            </div>
            <div className="mt-1 truncate font-medium tabular-nums">
              {formatDate(subscription.last_seen)}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {isRejected ? (
            <Button size="sm" onClick={onRestore} disabled={isPending}>
              <RotateCcw className="mr-2 h-4 w-4" />
              {t("subscriptions.restore")}
            </Button>
          ) : !subscription.is_confirmed ? (
            <Button size="sm" onClick={onConfirm} disabled={isPending}>
              <Check className="mr-2 h-4 w-4" />
              {t("subscriptions.confirm")}
            </Button>
          ) : null}
          <Button size="sm" variant="outline" onClick={onDetails}>
            {t("subscriptions.details")}
            <ChevronRight className="ml-2 h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function SubscriptionDetailsSheet({
  subscription,
  open,
  isPending,
  onOpenChange,
  onPreference,
}: {
  subscription: Subscription | null;
  open: boolean;
  isPending: boolean;
  onOpenChange: (open: boolean) => void;
  onPreference: (payload: SubscriptionPreferenceInput) => void;
}) {
  const { t } = useT();
  const isRejected = subscription?.user_decision === "rejected";
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full max-w-2xl overflow-y-auto sm:w-[42rem] lg:w-[46rem]">
        {subscription ? (
          <>
            <SheetHeader>
              <SheetTitle>{subscription.display_name}</SheetTitle>
              <div className="flex flex-wrap gap-2 pt-2">
                <Badge className={statusTone[subscription.status]}>
                  {isRejected
                    ? t("subscriptions.rejected")
                    : statusLabels[subscription.status]}
                </Badge>
                {subscription.is_confirmed ? (
                  <Badge variant="outline">{t("subscriptions.confirmed")}</Badge>
                ) : null}
                <Badge variant="outline">
                  {(subscription.confidence * 100).toFixed(0)}%
                </Badge>
              </div>
            </SheetHeader>

            <div className="space-y-5 p-4 pt-0">
              <section className="grid gap-3 sm:grid-cols-2">
                <DetailMetric
                  label={t("subscriptions.monthlyTotal")}
                  value={formatCurrency(
                    subscription.estimated_monthly_cost,
                    subscription.base_currency,
                  )}
                />
                <DetailMetric
                  label={t("subscriptions.yearlyTotal")}
                  value={formatCurrency(
                    subscription.estimated_monthly_cost * 12,
                    subscription.base_currency,
                  )}
                />
                <DetailMetric
                  label={t("subscriptions.lastPayment")}
                  value={formatDate(subscription.last_seen)}
                />
                <DetailMetric
                  label={t("subscriptions.nextPayment")}
                  value={
                    subscription.next_expected_date
                      ? formatDate(subscription.next_expected_date)
                      : t("common.unknown")
                  }
                />
              </section>

              <section className="space-y-2">
                <h3 className="text-sm font-semibold">
                  {t("subscriptions.management")}
                </h3>
                <div className="grid gap-2">
                  <Select
                    value={subscription.cadence}
                    onValueChange={(value) =>
                      onPreference({
                        subscription_key: subscription.merchant_key,
                        action: "update",
                        cadence_override: value as CadenceOverride,
                      })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.entries(cadenceLabels).map(([value, label]) => (
                        <SelectItem key={value} value={value}>
                          {label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-wrap gap-2 pt-1">
                  {isRejected ? (
                    <Button
                      size="sm"
                      onClick={() =>
                        onPreference({
                          subscription_key: subscription.merchant_key,
                          action: "restore",
                        })
                      }
                      disabled={isPending}
                    >
                      <RotateCcw className="mr-2 h-4 w-4" />
                      {t("subscriptions.restore")}
                    </Button>
                  ) : !subscription.is_confirmed ? (
                    <Button
                      size="sm"
                      onClick={() =>
                        onPreference({
                          subscription_key: subscription.merchant_key,
                          action: "confirm",
                          display_name: subscription.display_name,
                        })
                      }
                      disabled={isPending}
                    >
                      <Check className="mr-2 h-4 w-4" />
                      {t("subscriptions.confirm")}
                    </Button>
                  ) : null}
                  {!isRejected ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        onPreference({
                          subscription_key: subscription.merchant_key,
                          action: "reject",
                        })
                      }
                      disabled={isPending}
                    >
                      <XCircle className="mr-2 h-4 w-4" />
                      {t("subscriptions.reject")}
                    </Button>
                  ) : null}
                  <Button size="sm" variant="outline" asChild>
                    <Link
                      href={`/merchants?search=${encodeURIComponent(
                        merchantAliasSearch(subscription),
                      )}`}
                    >
                      {t("subscriptions.manageAliases")}
                      <ExternalLink className="ml-2 h-4 w-4" />
                    </Link>
                  </Button>
                </div>
              </section>

              <section className="space-y-2">
                <h3 className="text-sm font-semibold">
                  {t("subscriptions.evidence")}
                </h3>
                <div className="grid gap-2 rounded-md border bg-muted/20 p-3 text-sm text-muted-foreground">
                  <EvidenceRow
                    label={t("subscriptions.evidenceSource")}
                    value={sourceLabel(subscription.source, t)}
                  />
                  <EvidenceRow
                    label={t("subscriptions.evidenceOccurrences")}
                    value={String(subscription.evidence.occurrences ?? subscription.occurrences)}
                  />
                  <EvidenceRow
                    label={t("subscriptions.evidenceCadence")}
                    value={cadenceLabels[subscription.cadence] ?? subscription.cadence}
                  />
                  <EvidenceRow
                    label={t("subscriptions.evidenceStability")}
                    value={
                      subscription.evidence.amount_stability == null
                        ? t("common.unknown")
                        : `${(subscription.evidence.amount_stability * 100).toFixed(0)}%`
                    }
                  />
                  <EvidenceRow
                    label={t("subscriptions.evidenceManual")}
                    value={String(subscription.evidence.manual_category_count ?? 0)}
                  />
                </div>
              </section>

              <section className="space-y-2">
                <h3 className="text-sm font-semibold">
                  {t("subscriptions.transactions")}
                </h3>
                {subscription.transactions.length === 0 ? (
                  <div className="rounded-md border bg-muted/20 p-3 text-sm text-muted-foreground">
                    {t("subscriptions.transactionsEmpty")}
                  </div>
                ) : (
                  <div className="overflow-hidden rounded-md border">
                    {subscription.transactions.map((transaction) => (
                      <Link
                        key={transaction.id}
                        href={transactionsHref({ search: transaction.merchant })}
                        className="grid gap-1 border-b p-3 text-sm last:border-b-0 hover:bg-muted/50 sm:grid-cols-[6.5rem_minmax(0,1fr)_auto]"
                      >
                        <span className="text-muted-foreground">
                          {formatDate(transaction.booking_date)}
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate font-medium">
                            {transaction.merchant || transaction.title}
                          </span>
                          <span className="block truncate text-xs text-muted-foreground">
                            {transaction.title}
                          </span>
                        </span>
                        <span className="tabular-nums sm:text-right">
                          {formatCurrency(
                            transaction.amount_base,
                            transaction.base_currency,
                          )}
                        </span>
                      </Link>
                    ))}
                  </div>
                )}
              </section>
            </div>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

function DetailMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-muted/20 p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function EvidenceRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[10rem_1fr]">
      <span>{label}</span>
      <span className="text-foreground">{value}</span>
    </div>
  );
}
