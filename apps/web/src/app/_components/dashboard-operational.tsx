"use client";

import Link from "next/link";
import type { ComponentType, ReactNode } from "react";
import {
  AlertTriangle,
  CalendarClock,
  ListChecks,
  Loader2,
  ReceiptText,
} from "lucide-react";

import type {
  Anomaly,
  ReviewQueueItem,
  SubscriptionOverview,
  SubscriptionUpcomingPayment,
  Transaction,
} from "@/lib/api";
import { tCategory, useT } from "@/lib/i18n";
import { formatCurrency, formatDate } from "@/lib/utils";
import { transactionsHref } from "@/lib/transaction-links";
import { Money } from "@/components/money";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function OperationalHeader() {
  const { t } = useT();
  return (
    <div className="mb-3 flex items-start justify-between gap-3 xl:mb-0">
      <div>
        <h2 className="text-base font-semibold text-foreground">
          {t("dashboard.section.operational")}
        </h2>
        <p className="text-sm text-muted-foreground">
          {t("dashboard.section.operationalShortHint")}
        </p>
      </div>
      <Badge variant="muted">{t("dashboard.filters.independent")}</Badge>
    </div>
  );
}

export function OperationalPanels({
  reviewRows,
  anomalies,
  subscriptions,
  recent,
  baseCurrency,
  reviewLoading,
  anomaliesLoading,
  subscriptionsLoading,
  recentLoading,
  layout,
}: {
  reviewRows: ReviewQueueItem[] | undefined;
  anomalies: Anomaly[] | undefined;
  subscriptions: SubscriptionOverview | undefined;
  recent: Transaction[] | undefined;
  baseCurrency: string;
  reviewLoading: boolean;
  anomaliesLoading: boolean;
  subscriptionsLoading: boolean;
  recentLoading: boolean;
  layout: "rail" | "grid";
}) {
  return (
    <div
      className={
        layout === "grid"
          ? "grid gap-4 md:grid-cols-2 xl:grid-cols-4"
          : "space-y-3"
      }
    >
      <ReviewPanel rows={reviewRows} isLoading={reviewLoading} />
      <AnomaliesPanel
        rows={anomalies}
        isLoading={anomaliesLoading}
        currency={baseCurrency}
      />
      <UpcomingPanel
        overview={subscriptions}
        isLoading={subscriptionsLoading}
      />
      <RecentPanel rows={recent} isLoading={recentLoading} />
    </div>
  );
}

function ReviewPanel({
  rows,
  isLoading,
}: {
  rows: ReviewQueueItem[] | undefined;
  isLoading: boolean;
}) {
  const { t } = useT();
  return (
    <ListCard
      title={t("dashboard.operational.review")}
      icon={ListChecks}
      href="/review"
      footer={t("dashboard.operational.openReview")}
    >
      {isLoading ? (
        <ListLoading />
      ) : rows && rows.length > 0 ? (
        rows.slice(0, 5).map((row) => (
          <Link
            key={row.transaction_id}
            href={transactionsHref({
              view: "review",
              merchant_canonical_key: row.merchant_canonical_key,
              search: row.merchant_canonical_key
                ? undefined
                : row.merchant || row.title,
            })}
            className="block rounded-md px-2 py-1.5 transition-colors hover:bg-muted"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">
                  {row.merchant_display || row.merchant || row.title}
                </div>
                <div className="truncate text-xs text-muted-foreground">
                  {row.predicted_category
                    ? tCategory(t, row.predicted_category)
                    : t("review.queue.reason.missing_prediction")}
                </div>
              </div>
              <Money
                amount={Number(row.amount)}
                currency={row.currency}
                direction={row.direction}
                className="shrink-0 text-xs"
              />
            </div>
          </Link>
        ))
      ) : (
        <ListEmpty />
      )}
    </ListCard>
  );
}

function AnomaliesPanel({
  rows,
  isLoading,
  currency,
}: {
  rows: Anomaly[] | undefined;
  isLoading: boolean;
  currency: string;
}) {
  const { t } = useT();
  return (
    <ListCard
      title={t("dashboard.operational.alerts")}
      icon={AlertTriangle}
      href="/anomalies"
      footer={t("dashboard.operational.openAnomalies")}
    >
      {isLoading ? (
        <ListLoading />
      ) : rows && rows.length > 0 ? (
        rows.slice(0, 3).map((row) => (
          <Link
            key={row.id}
            href={transactionsHref({
              merchant_canonical_key: row.merchant_canonical_key,
              search: row.merchant_canonical_key
                ? undefined
                : row.merchant || row.title,
            })}
            className="block rounded-md px-2 py-1.5 transition-colors hover:bg-muted"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">
                  {row.merchant_display || row.merchant || row.title}
                </div>
                <div className="truncate text-xs text-muted-foreground">
                  {row.reasons[0] ?? row.anomaly_type}
                </div>
              </div>
              <div className="shrink-0 text-xs font-medium tabular-nums text-negative">
                {formatCurrency(Number(row.amount), currency)}
              </div>
            </div>
          </Link>
        ))
      ) : (
        <ListEmpty />
      )}
    </ListCard>
  );
}

function UpcomingPanel({
  overview,
  isLoading,
}: {
  overview: SubscriptionOverview | undefined;
  isLoading: boolean;
}) {
  const { t } = useT();
  const rows = overview?.upcoming ?? [];
  return (
    <ListCard
      title={t("dashboard.operational.payments")}
      icon={CalendarClock}
      href="/subscriptions"
      footer={t("dashboard.operational.openSubscriptions")}
    >
      {isLoading ? (
        <ListLoading />
      ) : rows.length > 0 ? (
        rows.slice(0, 3).map((row) => <UpcomingRow key={row.subscription_key} row={row} />)
      ) : (
        <ListEmpty />
      )}
    </ListCard>
  );
}

function UpcomingRow({ row }: { row: SubscriptionUpcomingPayment }) {
  return (
    <Link
      href="/subscriptions"
      className="block rounded-md px-2 py-1.5 transition-colors hover:bg-muted"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">{row.display_name}</div>
          <div className="text-xs text-muted-foreground">
            {formatDate(row.due_date)}
          </div>
        </div>
        <div className="shrink-0 text-xs font-medium tabular-nums">
          {formatCurrency(Number(row.amount_base), row.base_currency)}
        </div>
      </div>
    </Link>
  );
}

function RecentPanel({
  rows,
  isLoading,
}: {
  rows: Transaction[] | undefined;
  isLoading: boolean;
}) {
  const { t } = useT();
  return (
    <ListCard
      title={t("dashboard.recentTitle")}
      icon={ReceiptText}
      href="/transactions"
      footer={t("dashboard.operational.openTransactions")}
    >
      {isLoading ? (
        <ListLoading />
      ) : rows && rows.length > 0 ? (
        rows.slice(0, 5).map((row) => (
          <Link
            key={row.id}
            href={transactionsHref({
              merchant_canonical_key: row.merchant_canonical_key,
              search: row.merchant_canonical_key
                ? undefined
                : row.merchant || row.title,
            })}
            className="block rounded-md px-2 py-1.5 transition-colors hover:bg-muted"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">
                  {row.merchant_display || row.merchant || row.title}
                </div>
                <div className="text-xs text-muted-foreground">
                  {formatDate(row.booking_date)}
                </div>
              </div>
              <Money
                amount={Number(row.amount)}
                currency={row.currency}
                direction={row.direction}
                className="shrink-0 text-xs"
              />
            </div>
          </Link>
        ))
      ) : (
        <ListEmpty />
      )}
    </ListCard>
  );
}

function ListCard({
  title,
  icon: Icon,
  href,
  footer,
  children,
}: {
  title: string;
  icon: ComponentType<{ className?: string }>;
  href: string;
  footer: string;
  children: ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm text-foreground">
          <Icon className="h-4 w-4 text-muted-foreground" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="space-y-1">{children}</div>
        <Button asChild variant="link" size="sm" className="h-auto px-0 text-xs">
          <Link href={href}>{footer}</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

function ListLoading() {
  return (
    <div className="flex h-24 items-center justify-center text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />
    </div>
  );
}

function ListEmpty() {
  const { t } = useT();
  return (
    <div className="rounded-md border border-dashed px-3 py-6 text-center text-xs text-muted-foreground">
      {t("common.empty")}
    </div>
  );
}
