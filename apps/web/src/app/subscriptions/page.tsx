"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertTriangle,
  CalendarClock,
  Check,
  EyeOff,
  ExternalLink,
  Pencil,
  Repeat,
} from "lucide-react";
import { api, type Subscription, type SubscriptionPreferenceInput } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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
import { formatCurrency, formatDate } from "@/lib/utils";
import { CardGridSkeleton } from "@/components/ui/skeleton";
import { useT } from "@/lib/i18n";
import { useLocalStorageState } from "@/hooks/use-local-storage-state";
import { transactionsHref } from "@/lib/transaction-links";

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
  ignored: "Ignorowana",
};

const cadenceLabels: Record<string, string> = {
  weekly: "Co tydzień",
  biweekly: "Co 2 tygodnie",
  monthly: "Co miesiąc",
  yearly: "Co rok",
  unknown: "Nieznany",
};

type SortMode =
  | "cost_desc"
  | "status"
  | "next_due"
  | "confidence_desc"
  | "last_seen_desc"
  | "merchant_asc";
type CadenceOverride = NonNullable<SubscriptionPreferenceInput["cadence_override"]>;

export default function SubscriptionsPage() {
  const { t } = useT();
  const queryClient = useQueryClient();
  const [minConfidence, setMinConfidence] = useLocalStorageState(
    "finance.subscriptions.minConfidence",
    0.35,
  );
  const [sortBy, setSortBy] = useLocalStorageState<SortMode>(
    "finance.subscriptions.sortBy",
    "status",
  );
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editCadence, setEditCadence] = useState<CadenceOverride>("unknown");

  const query = useQuery({
    queryKey: ["subscriptions", minConfidence],
    queryFn: () => api.subscriptions(minConfidence),
  });
  const overviewQuery = useQuery({
    queryKey: ["subscriptions-overview"],
    queryFn: () => api.subscriptionsOverview(),
  });

  const preference = useMutation({
    mutationFn: api.saveSubscriptionPreference,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
      void queryClient.invalidateQueries({ queryKey: ["subscriptions-overview"] });
      toast.success(t("toast.saved"));
      setEditingKey(null);
    },
    onError: () => toast.error(t("toast.error")),
  });

  const sortedSubscriptions = useMemo(() => {
    const rows = [...(query.data ?? [])];
    const statusRank: Record<Subscription["status"], number> = {
      price_increased: 0,
      needs_review: 1,
      new: 2,
      annual_renewal: 3,
      paused_or_missing: 4,
      active: 5,
      price_decreased: 6,
      probably_cancelled: 7,
      ignored: 8,
    };
    return rows.sort((a, b) => {
      switch (sortBy) {
        case "status":
          return statusRank[a.status] - statusRank[b.status];
        case "next_due":
          return (a.next_expected_date ?? "9999").localeCompare(
            b.next_expected_date ?? "9999",
          );
        case "confidence_desc":
          return b.confidence - a.confidence;
        case "last_seen_desc":
          return b.last_seen.localeCompare(a.last_seen);
        case "merchant_asc":
          return a.display_name.localeCompare(b.display_name, "pl", {
            sensitivity: "base",
          });
        case "cost_desc":
        default:
          return b.estimated_monthly_cost - a.estimated_monthly_cost;
      }
    });
  }, [query.data, sortBy]);

  function startEdit(row: Subscription) {
    setEditingKey(row.merchant_key);
    setEditName(row.display_name);
    setEditCadence((row.cadence || "unknown") as CadenceOverride);
  }

  function saveEdit(row: Subscription) {
    preference.mutate({
      subscription_key: row.merchant_key,
      action: "update",
      display_name: editName,
      cadence_override: editCadence,
    });
  }

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
          label={t("subscriptions.next30Count")}
          value={`${overview?.next_30_days_count ?? 0}`}
        />
        <MetricCard
          label={t("subscriptions.next30Total")}
          value={formatCurrency(
            overview?.next_30_days_total ?? 0,
            overview?.base_currency ?? "PLN",
          )}
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
            <div className="divide-y">
              {overview.upcoming.slice(0, 6).map((item) => (
                <div
                  key={`${item.subscription_key}-${item.due_date}`}
                  className="grid gap-2 py-2 text-sm sm:grid-cols-[7rem_1fr_auto]"
                >
                  <span className="text-muted-foreground">
                    {formatDate(item.due_date)}
                  </span>
                  <span className="font-medium">{item.display_name}</span>
                  <span className="tabular-nums">
                    {formatCurrency(item.amount_base, item.base_currency)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <FilterPanel gridClassName="md:grid-cols-[minmax(16rem,1fr)_14rem]">
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
          <Select value={sortBy} onValueChange={(v) => setSortBy(v as SortMode)}>
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
      </FilterPanel>

      {query.isLoading ? (
        <CardGridSkeleton />
      ) : !query.data || query.data.length === 0 ? (
        <EmptyState title={t("subscriptions.empty")} icon={Repeat} />
      ) : (
        <div className="space-y-3">
          {sortedSubscriptions.map((s) => (
            <Card key={s.merchant_key}>
              <CardContent className="space-y-3 p-4">
                <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
                  <div className="min-w-0 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        href={transactionsHref({ search: s.display_name })}
                        className="min-w-0 truncate font-medium underline-offset-4 hover:underline"
                        title={s.display_name}
                      >
                        {s.display_name}
                      </Link>
                      <Badge className={statusTone[s.status]}>
                        {statusLabels[s.status]}
                      </Badge>
                      {s.is_confirmed ? (
                        <Badge variant="outline">
                          {t("subscriptions.confirmed")}
                        </Badge>
                      ) : null}
                      <Badge variant="outline">
                        {(s.confidence * 100).toFixed(0)}%
                      </Badge>
                    </div>
                    <div className="grid gap-x-6 gap-y-1 text-sm text-muted-foreground sm:grid-cols-2 xl:grid-cols-4">
                      <span>
                        {cadenceLabels[s.cadence] ?? s.cadence} · {s.occurrences}x
                      </span>
                      <span>
                        {t("subscriptions.lastSeen", {
                          date: formatDate(s.last_seen),
                        })}
                      </span>
                      <span>
                        {t("subscriptions.nextExpected", {
                          date: s.next_expected_date
                            ? formatDate(s.next_expected_date)
                            : t("common.unknown"),
                        })}
                      </span>
                      <Link
                        href={`/merchants?search=${encodeURIComponent(s.display_name)}`}
                        className="inline-flex items-center gap-1 hover:text-primary"
                      >
                        {t("subscriptions.mergeAliases")}
                        <ExternalLink className="h-3 w-3" />
                      </Link>
                    </div>
                  </div>
                  <div className="text-left lg:text-right">
                    <div className="text-xl font-semibold tabular-nums">
                      {formatCurrency(s.estimated_monthly_cost, s.base_currency)}
                      <span className="ml-1 text-sm font-normal text-muted-foreground">
                        {t("subscriptions.perMonth")}
                      </span>
                    </div>
                    {s.currency !== s.base_currency ? (
                      <div className="text-xs text-muted-foreground">
                        {formatCurrency(
                          s.estimated_monthly_cost_original,
                          s.currency,
                        )}{" "}
                        {t("subscriptions.originalCurrency")}
                      </div>
                    ) : null}
                    {s.price_change_pct !== null ? (
                      <div className="mt-1 inline-flex items-center gap-1 text-xs text-amber-700 dark:text-amber-300">
                        <AlertTriangle className="h-3 w-3" />
                        {s.price_change_pct > 0 ? "+" : ""}
                        {s.price_change_pct.toFixed(1)}%
                        {s.price_change_annual_impact !== null
                          ? ` / ${formatCurrency(
                              s.price_change_annual_impact,
                              s.base_currency,
                            )} rocznie`
                          : ""}
                      </div>
                    ) : null}
                  </div>
                </div>

                {editingKey === s.merchant_key ? (
                  <div className="grid gap-2 rounded-md border bg-muted/30 p-3 md:grid-cols-[minmax(10rem,1fr)_12rem_auto]">
                    <Input
                      value={editName}
                      onChange={(event) => setEditName(event.target.value)}
                      placeholder={t("subscriptions.displayName")}
                    />
                    <Select
                      value={editCadence}
                      onValueChange={(value) =>
                        setEditCadence(value as CadenceOverride)
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
                    <Button
                      onClick={() => saveEdit(s)}
                      disabled={preference.isPending}
                    >
                      {t("common.save")}
                    </Button>
                  </div>
                ) : null}

                <div className="flex flex-wrap gap-2">
                  {!s.is_confirmed ? (
                    <Button
                      size="sm"
                      onClick={() =>
                        preference.mutate({
                          subscription_key: s.merchant_key,
                          action: "confirm",
                          display_name: s.display_name,
                        })
                      }
                      disabled={preference.isPending}
                    >
                      <Check className="mr-2 h-4 w-4" />
                      {t("subscriptions.confirm")}
                    </Button>
                  ) : null}
                  <Button size="sm" variant="outline" onClick={() => startEdit(s)}>
                    <Pencil className="mr-2 h-4 w-4" />
                    {t("common.edit")}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      preference.mutate({
                        subscription_key: s.merchant_key,
                        action: "not_subscription",
                      })
                    }
                    disabled={preference.isPending}
                  >
                    <AlertTriangle className="mr-2 h-4 w-4" />
                    {t("subscriptions.notSubscription")}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      preference.mutate({
                        subscription_key: s.merchant_key,
                        action: "ignore",
                      })
                    }
                    disabled={preference.isPending}
                  >
                    <EyeOff className="mr-2 h-4 w-4" />
                    {t("subscriptions.hide")}
                  </Button>
                </div>

                <details className="rounded-md border bg-muted/20 p-3 text-sm">
                  <summary className="cursor-pointer font-medium">
                    {t("subscriptions.evidence")}
                  </summary>
                  <div className="mt-3 grid gap-2 text-muted-foreground md:grid-cols-2">
                    <span>
                      {t("subscriptions.evidenceSource")}: {s.source}
                    </span>
                    <span>
                      {t("subscriptions.evidenceStability")}:{" "}
                      {s.evidence.amount_stability == null
                        ? t("common.unknown")
                        : `${(s.evidence.amount_stability * 100).toFixed(0)}%`}
                    </span>
                    <span>
                      {t("subscriptions.evidenceManual")}:{" "}
                      {s.evidence.manual_category_count ?? 0}
                    </span>
                    <span>
                      {t("subscriptions.evidenceDates")}:{" "}
                      {(s.evidence.recent_dates ?? []).join(", ") ||
                        t("common.unknown")}
                    </span>
                  </div>
                </details>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
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
