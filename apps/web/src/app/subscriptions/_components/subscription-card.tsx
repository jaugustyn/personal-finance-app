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
        <div className="min-w-0 space-y-2">
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
          <div className="text-xl font-semibold tabular-nums">
            {formatCurrency(
              subscription.estimated_monthly_cost,
              subscription.base_currency,
            )}
            <span className="ml-1 text-sm font-normal text-muted-foreground">
              {t("subscriptions.perMonth")}
            </span>
          </div>
        </div>

        <div className="mt-auto grid grid-cols-3 divide-x border-y py-3 text-xs">
          <div className="min-w-0 pr-3">
            <div className="truncate text-muted-foreground">
              {t("subscriptions.nextPaymentShort")}
            </div>
            <div className="mt-1 truncate font-medium tabular-nums">
              {subscription.next_expected_date
                ? formatDate(subscription.next_expected_date)
                : t("common.unknown")}
            </div>
          </div>
          <div className="min-w-0 px-3">
            <div className="truncate text-muted-foreground">
              {t("subscriptions.cadence")}
            </div>
            <div className="mt-1 truncate font-medium">
              {cadenceLabels[subscription.cadence] ?? subscription.cadence}
            </div>
          </div>
          <div className="min-w-0 pl-3">
            <div className="truncate text-muted-foreground">
              {t("subscriptions.lastPaymentShort")}
            </div>
            <div className="mt-1 truncate font-medium tabular-nums">
              {formatDate(subscription.last_seen)}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {isHidden ? (
            <Button size="sm" onClick={onRestore} disabled={isPending}>
              <RotateCcw className="mr-2 h-4 w-4" />
              {t("subscriptions.restore")}
            </Button>
          ) : needsDecision ? (
            <>
              <Button size="sm" onClick={onConfirm} disabled={isPending}>
                <Check className="mr-2 h-4 w-4" />
                {t("subscriptions.confirm")}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={onReject}
                disabled={isPending}
              >
                <X className="mr-2 h-4 w-4" />
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
            <ChevronRight className="ml-2 h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
