"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  api,
  type CategoryState,
  type ReviewQueueItem,
  type ReviewSummary,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { Money } from "@/components/money";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { CardGridSkeleton } from "@/components/ui/skeleton";
import {
  useT,
  tCategory,
  tTransactionType,
  type TranslationKey,
} from "@/lib/i18n";
import { transactionsHref } from "@/lib/transaction-links";
import { ClipboardCheck, Layers, ListChecks, Repeat } from "lucide-react";

type CountKey = keyof ReviewSummary["counts"];

const PRIMARY_COUNT_KEYS: CountKey[] = [
  "categorized",
  "uncategorized",
  "ready_to_accept",
];
const SECONDARY_COUNT_KEYS: CountKey[] = [
  "no_suggestion",
  "low_confidence",
  "rejected",
];

const COUNT_FILTERS: Record<CountKey, CategoryState> = {
  categorized: "categorized",
  uncategorized: "uncategorized",
  no_suggestion: "uncategorized",
  low_confidence: "needs_review",
  ready_to_accept: "suggested",
  rejected: "rejected",
};

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
  const queueQuery = useQuery({
    queryKey: ["review-queue"],
    queryFn: () => api.reviewQueue(15),
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
      <PageHeader
        title={t("review.title")}
        description={t("review.subtitle")}
      />

      {query.isLoading ? (
        <CardGridSkeleton />
      ) : query.isError ? (
        <ErrorState onRetry={() => query.refetch()} />
      ) : !query.data ? (
        <EmptyState title={t("common.empty")} icon={ClipboardCheck} />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-3 sm:grid-cols-3">
            {PRIMARY_COUNT_KEYS.map((key) => (
              <ReviewCountCard
                key={key}
                label={t(`review.counts.${key}`)}
                count={query.data.counts[key]}
                categoryState={COUNT_FILTERS[key]}
              />
            ))}
          </div>

          <div className="flex flex-wrap gap-x-6 gap-y-2 rounded-lg border bg-muted/20 px-4 py-3">
            {SECONDARY_COUNT_KEYS.map((key) => (
              <Link
                key={key}
                href={transactionsHref({
                  view: "review",
                  category_state: COUNT_FILTERS[key],
                })}
                className="inline-flex items-baseline gap-2 text-sm hover:text-primary"
              >
                <span className="text-muted-foreground">
                  {t(`review.counts.${key}`)}
                </span>
                <span className="font-semibold tabular-nums">
                  {query.data.counts[key]}
                </span>
              </Link>
            ))}
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t("review.types.title")}</CardTitle>
              <p className="text-xs text-muted-foreground">
                {t("review.types.subtitle")}
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <TypeQualityMetric
                  label={t("review.types.confirmed")}
                  value={query.data.transaction_type_quality.confirmed}
                />
                <TypeQualityMetric
                  label={t("review.types.needsReview")}
                  value={query.data.transaction_type_quality.needs_review}
                  href={transactionsHref({
                    view: "review",
                    subject: "transaction_type",
                  })}
                />
                <TypeQualityMetric
                  label={t("review.types.suggested")}
                  value={query.data.transaction_type_quality.suggested}
                />
                <TypeQualityMetric
                  label={t("review.types.unsupported")}
                  value={query.data.transaction_type_quality.unsupported_classes.length}
                />
              </div>
              <div className="grid gap-4 border-t pt-4 lg:grid-cols-2">
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
                <div>
                  <div className="text-xs font-medium text-muted-foreground">
                    {t("review.types.corrections")}
                  </div>
                  <div className="mt-2 space-y-1 text-sm">
                    {query.data.transaction_type_quality.corrections.length ? (
                      query.data.transaction_type_quality.corrections
                        .slice(0, 5)
                        .map((row) => (
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
              </div>
              {query.data.transaction_type_quality.unsupported_classes.length ? (
                <div className="border-t pt-4">
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
            </CardContent>
          </Card>

          <ReviewActionPanel data={query.data} />

          <ReviewQueuePanel
            rows={queueQuery.data}
            isLoading={queueQuery.isLoading}
            isError={queueQuery.isError}
            onRetry={() => queueQuery.refetch()}
          />

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base text-foreground">
                  <Layers className="h-4 w-4 text-muted-foreground" />
                  {t("review.rareClasses.title")}
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                  {t("review.rareClasses.subtitle")}
                </p>
              </CardHeader>
              <CardContent>
                <DataTable
                  columns={rareClassColumns}
                  data={query.data.rare_classes}
                  rowKey={(row) => row.category}
                  emptyTitle={t("review.rareClasses.empty")}
                  initialSort={{ id: "count", dir: "asc" }}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base text-foreground">
                  <Repeat className="h-4 w-4 text-muted-foreground" />
                  {t("review.recurring.title")}
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                  {t("review.recurring.subtitle")}
                </p>
              </CardHeader>
              <CardContent>
                <DataTable
                  columns={recurringColumns}
                  data={query.data.recurring_unruled}
                  rowKey={(row) => row.merchant_canonical_key || row.merchant}
                  emptyTitle={t("review.recurring.empty")}
                  initialSort={{ id: "count", dir: "desc" }}
                />
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

function TypeQualityMetric({
  label,
  value,
  href,
}: {
  label: string;
  value: number;
  href?: string;
}) {
  const content = (
    <div className="rounded-md border bg-muted/10 p-3 transition-colors hover:bg-muted/30">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums">{value}</div>
    </div>
  );
  return href ? <Link href={href}>{content}</Link> : content;
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

function ReviewCountCard({
  label,
  count,
  categoryState,
}: {
  label: string;
  count: number;
  categoryState: CategoryState;
}) {
  return (
    <Link
      href={transactionsHref({ view: "review", category_state: categoryState })}
      className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <Card className="h-full transition-colors hover:border-primary/40 hover:bg-muted/20">
        <CardContent className="space-y-1 p-4">
          <div className="text-xs text-muted-foreground">{label}</div>
          <div className="text-2xl font-semibold tabular-nums">{count}</div>
        </CardContent>
      </Card>
    </Link>
  );
}

function reviewReasonLabel(code: string, t: ReturnType<typeof useT>["t"]): string {
  const keys: Record<string, TranslationKey> = {
    manual_required: "review.queue.reason.manual_required",
    review_confidence: "review.queue.reason.review_confidence",
    review_without_confidence: "review.queue.reason.review_without_confidence",
    safe_suggestion: "review.queue.reason.safe_suggestion",
    large_amount: "review.queue.reason.large_amount",
    merchant_cluster: "review.queue.reason.merchant_cluster",
    merchant_feedback_history: "review.queue.reason.merchant_feedback_history",
    bank_model_conflict: "review.queue.reason.bank_model_conflict",
    rule_model_conflict: "review.queue.reason.rule_model_conflict",
    rare_predicted_category: "review.queue.reason.rare_predicted_category",
    weak_predicted_category: "review.queue.reason.weak_predicted_category",
    missing_prediction: "review.queue.reason.missing_prediction",
    other_prediction: "review.queue.reason.other_prediction",
  };
  const key = keys[code];
  return key ? t(key) : code;
}

function ReviewQueuePanel({
  rows,
  isLoading,
  isError,
  onRetry,
}: {
  rows: ReviewQueueItem[] | undefined;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}) {
  const { t } = useT();
  const columns: DataTableColumn<ReviewQueueItem>[] = [
    {
      id: "score",
      header: t("review.queue.score"),
      align: "right",
      className: "tabular-nums font-medium",
      sortValue: (row) => row.priority_score,
      cell: (row) => row.priority_score.toFixed(1),
    },
    {
      id: "merchant",
      header: t("transactions.column.merchant"),
      sortValue: (row) => row.merchant_display || row.merchant,
      cell: (row) => (
        <Link
          href={transactionsHref({
            view: "review",
            merchant_canonical_key: row.merchant_canonical_key,
            search: row.merchant_canonical_key ? undefined : row.merchant,
          })}
          className="block min-w-0 text-primary underline-offset-4 hover:underline"
        >
          <span className="block truncate font-medium">
            {row.merchant_display || row.merchant || row.title}
          </span>
          {row.title && row.title !== row.merchant ? (
            <span className="block truncate text-xs text-muted-foreground">
              {row.title}
            </span>
          ) : null}
        </Link>
      ),
    },
    {
      id: "prediction",
      header: t("transactions.suggestion"),
      sortValue: (row) => row.confidence ?? -1,
      cell: (row) => (
        <div className="space-y-1">
          <Badge variant={row.decision_action === "manual" ? "warning" : "outline"}>
            {row.predicted_category
              ? tCategory(t, row.predicted_category)
              : t("common.unknown")}
          </Badge>
          {row.confidence != null ? (
            <div className="text-xs text-muted-foreground">
              {Math.round(row.confidence * 100)}%
            </div>
          ) : null}
        </div>
      ),
    },
    {
      id: "amount",
      header: t("transactions.column.amount"),
      align: "right",
      sortValue: (row) => Math.abs(Number(row.amount)),
      cell: (row) => (
        <Money
          amount={Number(row.amount)}
          currency={row.currency}
          direction={row.direction}
        />
      ),
    },
    {
      id: "reasons",
      header: t("review.queue.reasons"),
      cell: (row) => (
        <div className="flex flex-wrap gap-1">
          {row.reason_codes.slice(0, 3).map((code) => (
            <Badge key={code} variant="muted" className="text-[10px]">
              {reviewReasonLabel(code, t)}
            </Badge>
          ))}
        </div>
      ),
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base text-foreground">
          <ListChecks className="h-4 w-4 text-muted-foreground" />
          {t("review.queue.title")}
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          {t("review.queue.subtitle")}
        </p>
      </CardHeader>
      <CardContent>
        {isError ? (
          <div className="flex items-center justify-between gap-3 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm">
            <span className="text-destructive">{t("review.queue.error")}</span>
            <Button variant="outline" size="sm" onClick={onRetry}>
              {t("common.retry")}
            </Button>
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={rows}
            isLoading={isLoading}
            rowKey={(row) => row.transaction_id}
            emptyTitle={t("review.queue.empty")}
            initialSort={{ id: "score", dir: "desc" }}
            tableClassName="min-w-[760px]"
          />
        )}
      </CardContent>
    </Card>
  );
}

function ReviewActionPanel({ data }: { data: ReviewSummary }) {
  const { t } = useT();
  const needsReview = data.counts.uncategorized;
  const rareCount = data.rare_classes.length;
  const recurringCount = data.recurring_unruled.length;
  const hasActions = needsReview > 0 || rareCount > 0 || recurringCount > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base text-foreground">
          {t("review.next.title")}
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          {t("review.next.subtitle")}
        </p>
      </CardHeader>
      <CardContent>
        {hasActions ? (
          <div className="grid gap-3 lg:grid-cols-3">
            {needsReview > 0 ? (
              <ActionTile
                title={t("review.next.labelTransactions")}
                description={t("review.next.labelTransactionsHint", {
                  n: needsReview,
                })}
                href={transactionsHref({
                  view: "review",
                })}
                cta={t("review.openQueue")}
              />
            ) : null}
            {rareCount > 0 ? (
              <ActionTile
                title={t("review.next.rareClasses")}
                description={t("review.next.rareClassesHint", {
                  n: rareCount,
                })}
                href={transactionsHref({
                  view: "review",
                })}
                cta={t("review.openQueue")}
              />
            ) : null}
            {recurringCount > 0 ? (
              <ActionTile
                title={t("review.next.rules")}
                description={t("review.next.rulesHint", {
                  n: recurringCount,
                })}
                href="/settings"
                cta={t("review.next.openSettings")}
              />
            ) : null}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            {t("review.next.allGood")}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function ActionTile({
  title,
  description,
  href,
  cta,
}: {
  title: string;
  description: string;
  href: string;
  cta: string;
}) {
  return (
    <div className="rounded-md border bg-muted/20 p-3">
      <div className="font-medium text-sm">{title}</div>
      <p className="mt-1 text-xs text-muted-foreground">{description}</p>
      <Button asChild variant="outline" size="sm" className="mt-3">
        <Link href={href}>{cta}</Link>
      </Button>
    </div>
  );
}
