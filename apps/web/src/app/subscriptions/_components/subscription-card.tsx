"use client";

import Link from "next/link";
import { Check, ChevronRight, RotateCcw, X } from "lucide-react";

import type { Subscription } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { formatCurrency, formatDate } from "@/lib/utils";
import { transactionsHref } from "@/lib/transaction-links";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cadenceLabels, statusLabels, statusTone } from "../_lib/subscription-format";

export function SubscriptionCard({
  subscription,
  isPending,
  onConfirm,
  onReject,
  onRestore,
  onDetails,
}: {
  subscription: Subscription;
  isPending: boolean;
  onConfirm: () => void;
  onReject: () => void;
  onRestore: () => void;
  onDetails: () => void;
}) {
  const { t } = useT();
  const isRejected = subscription.user_decision === "rejected";
  const isHidden = isRejected || subscription.status === "ignored";
  const needsDecision = !isHidden && !subscription.is_confirmed;
  return (
    <Card className="transition-colors hover:border-foreground/15">
      <CardContent className="flex h-full flex-col gap-4 p-4">
        <div className="flex items-start justify-between gap-2">
          <Link
            href={transactionsHref({
              search: subscription.merchant,
            })}
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

        <div className="flex items-end justify-between gap-5">
          <div className="min-w-0">
            <div className="truncate text-2xl font-semibold tabular-nums">
              {formatCurrency(
                subscription.estimated_monthly_cost,
                subscription.base_currency,
              )}
              <span className="ml-1 text-sm font-normal text-muted-foreground">
                {t("subscriptions.perMonth")}
              </span>
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {cadenceLabels[subscription.cadence] ?? subscription.cadence}
            </div>
          </div>
          <div className="min-w-0 text-right">
            <div className="truncate text-base font-semibold tabular-nums">
              {subscription.next_expected_date
                ? formatDate(subscription.next_expected_date)
                : t("common.unknown")}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {t("subscriptions.nextPayment")}
            </div>
          </div>
        </div>

        <div className="mt-auto flex flex-wrap items-center gap-2 pt-1">
          {isHidden ? (
            <Button size="sm" onClick={onRestore} disabled={isPending}>
              <RotateCcw className="h-4 w-4" />
              {t("subscriptions.restore")}
            </Button>
          ) : needsDecision ? (
            <>
              <Button size="sm" onClick={onConfirm} disabled={isPending}>
                <Check className="h-4 w-4" />
                {t("subscriptions.confirm")}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={onReject}
                disabled={isPending}
              >
                <X className="h-4 w-4" />
                {t("subscriptions.notSubscription")}
              </Button>
            </>
          ) : null}
          <Button
            size="sm"
            variant="ghost"
            className="ml-auto"
            onClick={onDetails}
          >
            {t("subscriptions.details")}
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
