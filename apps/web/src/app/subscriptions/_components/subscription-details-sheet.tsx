"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Check, RotateCcw, XCircle } from "lucide-react";

import type { Subscription, SubscriptionPreferenceInput } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { formatCurrency, formatDate } from "@/lib/utils";
import { transactionsHref } from "@/lib/transaction-links";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
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
import {
  cadenceLabels,
  sourceLabel,
  statusLabels,
  statusTone,
  type CadenceOverride,
} from "../_lib/subscription-format";

export function SubscriptionDetailsSheet({
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
  const isHidden = isRejected || subscription?.status === "ignored";
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

            <div className="space-y-4 p-4 pt-0">
              <DetailsSection title={t("subscriptions.summary")}>
                <div className="grid gap-3 sm:grid-cols-2">
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
                </div>
              </DetailsSection>

              <DetailsSection title={t("subscriptions.management")}>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                  <div className="w-full max-w-56 space-y-1.5">
                    <Label className="text-xs font-medium text-muted-foreground">
                      {t("subscriptions.cadence")}
                    </Label>
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
                      <SelectTrigger className="w-full">
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
                  <div className="flex flex-wrap gap-2">
                    {isHidden ? (
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
                    {!isHidden ? (
                      <Button
                        size="sm"
                        variant="outline"
                        className="border-red-500/30 bg-red-500/5 text-red-700 hover:bg-red-500/10 hover:text-red-800 dark:text-red-300 dark:hover:text-red-200"
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
                  </div>
                </div>
              </DetailsSection>

              <DetailsSection title={t("subscriptions.evidence")}>
                <div className="grid gap-2 text-sm text-muted-foreground">
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
              </DetailsSection>

              <DetailsSection
                title={t("subscriptions.transactions")}
                action={
                  <Link
                    href={transactionsHref({
                      search: subscription.merchant,
                    })}
                    className="shrink-0 text-xs font-medium text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
                  >
                    {t("subscriptions.openTransactions")}
                  </Link>
                }
              >
                {subscription.transactions.length === 0 ? (
                  <div className="rounded-md border bg-muted/20 p-3 text-sm text-muted-foreground">
                    {t("subscriptions.transactionsEmpty")}
                  </div>
                ) : (
                  <div className="overflow-hidden rounded-md border">
                    {subscription.transactions.map((transaction) => (
                      <Link
                        key={transaction.id}
                        href={transactionsHref({
                          search: transaction.merchant || transaction.title,
                        })}
                        className="grid gap-1 border-b p-3 text-sm last:border-b-0 hover:bg-muted/50 sm:grid-cols-[6.5rem_minmax(0,1fr)_auto]"
                      >
                        <span className="text-muted-foreground">
                          {formatDate(transaction.booking_date)}
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate font-medium">
                            {transaction.merchant_display ||
                              transaction.merchant ||
                              transaction.title}
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
              </DetailsSection>
            </div>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

function DetailsSection({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="space-y-3 rounded-md border bg-muted/10 p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold">{title}</h3>
        {action}
      </div>
      {children}
    </section>
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
