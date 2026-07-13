"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeftRight,
  ArrowRight,
  ChevronDown,
  ClipboardCheck,
  Layers,
  Repeat,
  Tags,
  type LucideIcon,
} from "lucide-react";

import { DataTable, type DataTableColumn } from "@/components/data-table";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CardGridSkeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { tCategory, tTransactionType, useT } from "@/lib/i18n";
import { transactionsHref } from "@/lib/transaction-links";

type RareClassRow = { category: string; count: number };
type RecurringMerchantRow = {
  merchant: string;
  merchant_display: string;
  merchant_canonical_key: string;
  count: number;
};

export default function ReviewPage() {
  const { t } = useT();
  const query = useQuery({
    queryKey: ["review-summary"],
    queryFn: () => api.reviewSummary(),
  });
  const rareClassColumns: DataTableColumn<RareClassRow>[] = [
    {
      id: "category",
      header: t("transactions.column.category"),
      sortValue: (row) => tCategory(t, row.category),
      className: "font-medium",
      cell: (row) => (
        <Link
          href={transactionsHref({
            category: row.category,
            direction: "debit",
          })}
          className="text-primary underline-offset-4 hover:underline"
        >
          {tCategory(t, row.category)}
        </Link>
      ),
    },
    {
      id: "count",
      header: t("review.count"),
      align: "right",
      className: "tabular-nums text-muted-foreground",
      sortValue: (row) => row.count,
      cell: (row) => row.count,
    },
  ];
  const recurringColumns: DataTableColumn<RecurringMerchantRow>[] = [
    {
      id: "merchant",
      header: t("transactions.column.merchant"),
      sortValue: (row) => row.merchant_display || row.merchant,
      className: "font-medium",
      cell: (row) => (
        <Link
          href={transactionsHref({
            view: "review",
            merchant_canonical_key: row.merchant_canonical_key,
            search: row.merchant_canonical_key ? undefined : row.merchant,
          })}
          className="text-primary underline-offset-4 hover:underline"
        >
          {row.merchant_display || row.merchant}
        </Link>
      ),
    },
    {
      id: "count",
      header: t("review.count"),
      align: "right",
      className: "tabular-nums text-muted-foreground",
      sortValue: (row) => row.count,
      cell: (row) => t("review.timesSeen", { count: row.count }),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title={t("review.title")} description={t("review.subtitle")} />

      {query.isLoading ? (
        <CardGridSkeleton />
      ) : query.isError ? (
        <ErrorState onRetry={() => query.refetch()} />
      ) : !query.data ? (
        <EmptyState title={t("common.empty")} icon={ClipboardCheck} />
      ) : (
        <div className="space-y-5">
          <div className="grid gap-4 lg:grid-cols-2">
            <QualityAreaCard
              icon={Tags}
              title={t("transactions.subject.categories")}
              confirmed={query.data.counts.categorized}
              needsReview={query.data.counts.uncategorized}
              href={transactionsHref({
                view: "review",
                subject: "category",
              })}
            />
            <QualityAreaCard
              icon={ArrowLeftRight}
              title={t("transactions.subject.types")}
              confirmed={query.data.transaction_type_quality.confirmed}
              needsReview={query.data.transaction_type_quality.needs_review}
              href={transactionsHref({
                view: "review",
                subject: "transaction_type",
              })}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base text-foreground">
                {t("review.next.title")}
              </CardTitle>
              <p className="text-xs text-muted-foreground">
                {t("review.next.subtitle")}
              </p>
            </CardHeader>
            <CardContent className="space-y-2">
              <ReviewActionRow
                label={t("review.counts.ready_to_accept")}
                count={query.data.counts.ready_to_accept}
                href={transactionsHref({
                  view: "review",
                  subject: "category",
                  category_state: "suggested",
                })}
              />
              <ReviewActionRow
                label={t("review.counts.no_suggestion")}
                count={query.data.counts.no_suggestion}
                href={transactionsHref({
                  view: "review",
                  subject: "category",
                  category_state: "uncategorized",
                })}
              />
              <ReviewActionRow
                label={t("review.counts.low_confidence")}
                count={query.data.counts.low_confidence}
                href={transactionsHref({
                  view: "review",
                  subject: "category",
                  category_state: "needs_review",
                })}
              />
              <ReviewActionRow
                label={t("review.types.needsReview")}
                count={query.data.transaction_type_quality.needs_review}
                href={transactionsHref({
                  view: "review",
                  subject: "transaction_type",
                })}
              />
              {query.data.counts.uncategorized === 0 &&
              query.data.transaction_type_quality.needs_review === 0 ? (
                <p className="py-2 text-sm text-muted-foreground">
                  {t("review.next.allGood")}
                </p>
              ) : null}
            </CardContent>
          </Card>

          <details className="group rounded-lg border bg-card">
            <summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-3.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              <div className="min-w-0 flex-1">
                <div className="font-medium text-foreground">
                  {t("review.technical.title")}
                </div>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  {t("review.technical.subtitle")}
                </div>
              </div>
              <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
            </summary>

            <div className="space-y-6 border-t p-4">
              <div className="flex flex-wrap gap-2">
                <DiagnosticBadge
                  label={t("review.counts.rejected")}
                  value={query.data.counts.rejected}
                />
                <DiagnosticBadge
                  label={t("review.types.suggested")}
                  value={query.data.transaction_type_quality.suggested}
                />
                <DiagnosticBadge
                  label={t("review.types.unsupported")}
                  value={
                    query.data.transaction_type_quality.unsupported_classes.length
                  }
                />
              </div>

              <div className="grid gap-6 xl:grid-cols-2">
                <TechnicalSection
                  icon={Layers}
                  title={t("review.rareClasses.title")}
                  subtitle={t("review.rareClasses.subtitle")}
                >
                  <DataTable
                    columns={rareClassColumns}
                    data={query.data.rare_classes}
                    rowKey={(row) => row.category}
                    emptyTitle={t("review.rareClasses.empty")}
                    initialSort={{ id: "count", dir: "asc" }}
                  />
                </TechnicalSection>

                <TechnicalSection
                  icon={Repeat}
                  title={t("review.recurring.title")}
                  subtitle={t("review.recurring.subtitle")}
                >
                  <DataTable
                    columns={recurringColumns}
                    data={query.data.recurring_unruled}
                    rowKey={(row) => row.merchant_canonical_key || row.merchant}
                    emptyTitle={t("review.recurring.empty")}
                    initialSort={{ id: "count", dir: "desc" }}
                  />
                </TechnicalSection>
              </div>

              <div className="grid gap-6 border-t pt-5 lg:grid-cols-2">
                <div className="space-y-4">
                  <TypeDistribution
                    title={t("review.types.sources")}
                    values={query.data.transaction_type_quality.source_counts}
                  />
                  <TypeDistribution
                    title={t("review.types.suggestionSources")}
                    values={
                      query.data.transaction_type_quality.suggestion_source_counts
                    }
                  />
                </div>
                <TypeCorrections
                  rows={query.data.transaction_type_quality.corrections}
                />
              </div>

              {query.data.transaction_type_quality.unsupported_classes.length ? (
                <div className="border-t pt-5">
                  <div className="text-xs font-medium text-muted-foreground">
                    {t("review.types.unsupportedList")}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {query.data.transaction_type_quality.unsupported_classes.map(
                      (type) => (
                        <Badge key={type} variant="outline">
                          {tTransactionType(t, type)}
                        </Badge>
                      ),
                    )}
                  </div>
                </div>
              ) : null}
            </div>
          </details>
        </div>
      )}
    </div>
  );
}

function QualityAreaCard({
  icon: Icon,
  title,
  confirmed,
  needsReview,
  href,
}: {
  icon: LucideIcon;
  title: string;
  confirmed: number;
  needsReview: number;
  href: string;
}) {
  const { t } = useT();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base text-foreground">
          <Icon className="h-4 w-4 text-muted-foreground" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <QualityMetric label={t("review.types.confirmed")} value={confirmed} />
          <QualityMetric
            label={t("review.types.needsReview")}
            value={needsReview}
            highlight={needsReview > 0}
          />
        </div>
        <Button asChild variant={needsReview > 0 ? "default" : "outline"} size="sm">
          <Link href={href}>
            {t("review.openQueue")}
            <ArrowRight className="h-4 w-4" />
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}

function QualityMetric({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: number;
  highlight?: boolean;
}) {
  return (
    <div className="rounded-md border bg-muted/10 p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={
          highlight
            ? "mt-1 text-2xl font-semibold tabular-nums text-warning"
            : "mt-1 text-2xl font-semibold tabular-nums"
        }
      >
        {value}
      </div>
    </div>
  );
}

function ReviewActionRow({
  label,
  count,
  href,
}: {
  label: string;
  count: number;
  href: string;
}) {
  if (count === 0) return null;
  return (
    <Link
      href={href}
      className="flex items-center gap-3 rounded-md border px-3 py-2.5 transition-colors hover:border-primary/30 hover:bg-muted/20"
    >
      <span className="min-w-0 flex-1 text-sm font-medium">{label}</span>
      <Badge variant="muted" className="tabular-nums">
        {count}
      </Badge>
      <ArrowRight className="h-4 w-4 text-muted-foreground" />
    </Link>
  );
}

function DiagnosticBadge({ label, value }: { label: string; value: number }) {
  return (
    <Badge variant="outline" className="gap-2 py-1">
      <span className="font-normal text-muted-foreground">{label}</span>
      <span className="tabular-nums">{value}</span>
    </Badge>
  );
}

function TechnicalSection({
  icon: Icon,
  title,
  subtitle,
  children,
}: {
  icon: LucideIcon;
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <section className="min-w-0">
      <div className="mb-3">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Icon className="h-4 w-4 text-muted-foreground" />
          {title}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>
      </div>
      {children}
    </section>
  );
}

function TypeDistribution({
  title,
  values,
}: {
  title: string;
  values: Record<string, number>;
}) {
  return (
    <div>
      <div className="text-xs font-medium text-muted-foreground">{title}</div>
      <div className="mt-2 flex flex-wrap gap-2">
        {Object.entries(values).length ? (
          Object.entries(values).map(([source, count]) => (
            <Badge key={source} variant="outline">
              {source}: {count}
            </Badge>
          ))
        ) : (
          <span className="text-sm text-muted-foreground">—</span>
        )}
      </div>
    </div>
  );
}

function TypeCorrections({
  rows,
}: {
  rows: {
    source: string;
    suggested_or_previous: string;
    final: string;
    count: number;
  }[];
}) {
  const { t } = useT();
  return (
    <div>
      <div className="text-xs font-medium text-muted-foreground">
        {t("review.types.corrections")}
      </div>
      <div className="mt-2 space-y-1 text-sm">
        {rows.length ? (
          rows.slice(0, 5).map((row) => (
            <div
              key={`${row.source}:${row.suggested_or_previous}:${row.final}`}
              className="flex justify-between gap-3"
            >
              <span className="truncate text-muted-foreground">
                {row.source}: {row.suggested_or_previous} → {row.final}
              </span>
              <span className="font-medium tabular-nums">{row.count}</span>
            </div>
          ))
        ) : (
          <span className="text-muted-foreground">
            {t("review.types.noCorrections")}
          </span>
        )}
      </div>
    </div>
  );
}
