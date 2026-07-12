"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  CalendarClock,
  ClipboardCheck,
  Loader2,
  Search,
  type LucideIcon,
} from "lucide-react";

import type {
  Anomaly,
  ReviewQueueItem,
  SubscriptionOverview,
  SubscriptionUpcomingPayment,
} from "@/lib/api";
import { tCategory, useT } from "@/lib/i18n";
import { cn, formatCurrency, formatDate } from "@/lib/utils";
import { transactionsHref } from "@/lib/transaction-links";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type AttentionTone = "info" | "negative" | "warning";

export function AttentionPanel({
  reviewRows,
  anomalies,
  subscriptions,
  baseCurrency,
  reviewLoading,
  anomaliesLoading,
  subscriptionsLoading,
  layout = "grid",
}: {
  reviewRows: ReviewQueueItem[] | undefined;
  anomalies: Anomaly[] | undefined;
  subscriptions: SubscriptionOverview | undefined;
  baseCurrency: string;
  reviewLoading: boolean;
  anomaliesLoading: boolean;
  subscriptionsLoading: boolean;
  layout?: "grid" | "rail";
}) {
  const { t } = useT();
  const upcoming = subscriptions?.upcoming ?? [];
  const totalCount =
    (reviewRows?.length ?? 0) + (anomalies?.length ?? 0) + upcoming.length;

  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b bg-muted/30 p-4">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-base text-foreground">
            <Search className="h-4 w-4 text-muted-foreground" />
            {t("dashboard.attention.title")}
          </CardTitle>
          <div className="rounded-full border bg-background px-2.5 py-1 text-xs font-semibold tabular-nums text-foreground">
            {totalCount}
          </div>
        </div>
      </CardHeader>
      <CardContent
        className={cn(
          "p-0",
          layout === "grid"
            ? "grid divide-y lg:grid-cols-3 lg:divide-x lg:divide-y-0"
            : "divide-y",
        )}
      >
        <AttentionSection
          icon={ClipboardCheck}
          tone="info"
          title={t("dashboard.operational.review")}
          count={reviewRows?.length ?? 0}
          href="/review"
          footer={t("dashboard.operational.openReview")}
          loading={reviewLoading}
        >
          {reviewRows?.slice(0, 2).map((row) => (
            <AttentionItem
              key={row.transaction_id}
              tone="info"
              href={transactionsHref({
                view: "review",
                merchant_canonical_key: row.merchant_canonical_key,
                search: row.merchant_canonical_key
                  ? undefined
                  : row.merchant || row.title,
              })}
            >
              <div className="flex items-center justify-between gap-3">
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
                <div className="shrink-0 text-xs font-medium tabular-nums text-muted-foreground">
                  {formatCurrency(Number(row.amount), row.currency)}
                </div>
              </div>
            </AttentionItem>
          ))}
        </AttentionSection>

        <AttentionSection
          icon={AlertTriangle}
          tone="negative"
          title={t("dashboard.operational.alerts")}
          count={anomalies?.length ?? 0}
          href="/anomalies"
          footer={t("dashboard.operational.openAnomalies")}
          loading={anomaliesLoading}
        >
          {anomalies?.slice(0, 2).map((row) => (
            <AttentionItem
              key={row.id}
              tone="negative"
              href={transactionsHref({
                merchant_canonical_key: row.merchant_canonical_key,
                search: row.merchant_canonical_key
                  ? undefined
                  : row.merchant || row.title,
              })}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">
                    {row.merchant_display || row.merchant || row.title}
                  </div>
                  <div className="truncate text-xs text-muted-foreground">
                    {row.reasons[0] ?? row.anomaly_type}
                  </div>
                </div>
                <div className="shrink-0 text-xs font-semibold tabular-nums text-negative">
                  {formatCurrency(Number(row.amount), baseCurrency)}
                </div>
              </div>
            </AttentionItem>
          ))}
        </AttentionSection>

        <AttentionSection
          icon={CalendarClock}
          tone="warning"
          title={t("dashboard.operational.payments")}
          count={upcoming.length}
          href="/subscriptions"
          footer={t("dashboard.operational.openSubscriptions")}
          loading={subscriptionsLoading}
        >
          {upcoming.slice(0, 2).map((row) => (
            <UpcomingRow key={row.subscription_key} row={row} tone="warning" />
          ))}
        </AttentionSection>
      </CardContent>
    </Card>
  );
}

function AttentionSection({
  icon: Icon,
  tone,
  title,
  count,
  href,
  footer,
  loading,
  children,
}: {
  icon: LucideIcon;
  tone: AttentionTone;
  title: string;
  count: number;
  href: string;
  footer: string;
  loading: boolean;
  children: ReactNode;
}) {
  return (
    <section className="min-w-0 p-4">
      <div className="flex items-center gap-3">
        <div
          className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-md border",
            tone === "info" && "border-info/20 bg-info/10 text-info",
            tone === "negative" &&
              "border-negative/20 bg-negative/10 text-negative",
            tone === "warning" &&
              "border-warning/20 bg-warning/10 text-warning",
          )}
        >
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center justify-between gap-2">
            <div className="truncate text-sm font-medium text-foreground">
              {title}
            </div>
            <div className="rounded-full bg-muted px-2 py-0.5 text-xs font-semibold tabular-nums text-foreground">
              {count}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-3 overflow-hidden rounded-md border border-border/70 bg-background divide-y">
        {loading ? <ListLoading /> : count > 0 ? children : <ListEmpty />}
      </div>

      <Button
        asChild
        variant="ghost"
        size="sm"
        className="-ml-2 mt-3 h-8 justify-start px-2 text-xs"
      >
        <Link href={href}>
          {footer}
          <ArrowUpRight className="h-3.5 w-3.5" />
        </Link>
      </Button>
    </section>
  );
}

function AttentionItem({
  href,
  tone,
  children,
}: {
  href: string;
  tone: AttentionTone;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      className="group relative block min-w-0 px-3 py-2.5 pl-4 transition-colors hover:bg-muted/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
    >
      <span
        className={cn(
          "absolute bottom-2.5 left-1.5 top-2.5 w-0.5 rounded-full opacity-70 transition-opacity group-hover:opacity-100",
          tone === "info" && "bg-info",
          tone === "negative" && "bg-negative",
          tone === "warning" && "bg-warning",
        )}
      />
      {children}
    </Link>
  );
}

function UpcomingRow({
  row,
  tone,
}: {
  row: SubscriptionUpcomingPayment;
  tone: AttentionTone;
}) {
  return (
    <AttentionItem href="/subscriptions" tone={tone}>
      <div className="flex items-center justify-between gap-3">
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
    </AttentionItem>
  );
}

function ListLoading() {
  return (
    <div className="flex h-20 items-center justify-center text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />
    </div>
  );
}

function ListEmpty() {
  const { t } = useT();
  return (
    <div className="flex h-20 items-center justify-center px-3 text-center text-xs text-muted-foreground">
      {t("common.empty")}
    </div>
  );
}
