"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api, type ReviewSummary } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { CardGridSkeleton } from "@/components/ui/skeleton";
import { useT, tCategory } from "@/lib/i18n";
import { ClipboardCheck, Layers, Repeat } from "lucide-react";

const COUNT_KEYS = [
  "uncategorized",
  "no_suggestion",
  "low_confidence",
  "ready_to_accept",
  "rejected",
  "categorized",
] as const;

export default function ReviewPage() {
  const { t } = useT();
  const query = useQuery({
    queryKey: ["review-summary"],
    queryFn: () => api.reviewSummary(),
  });

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
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {COUNT_KEYS.map((key) => (
              <Card key={key}>
                <CardContent className="space-y-1 p-4">
                  <div className="text-xs text-muted-foreground">
                    {t(`review.counts.${key}`)}
                  </div>
                  <div className="text-2xl font-semibold tabular-nums">
                    {query.data!.counts[key]}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <ReviewActionPanel data={query.data} />

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
                {query.data.rare_classes.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {t("review.rareClasses.empty")}
                  </p>
                ) : (
                  <ul className="divide-y divide-border">
                    {query.data.rare_classes.map((rc) => (
                      <li
                        key={rc.category}
                        className="flex items-center justify-between py-2 text-sm"
                      >
                        <span>{tCategory(t, rc.category)}</span>
                        <span className="tabular-nums text-muted-foreground">
                          {rc.count}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
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
                {query.data.recurring_unruled.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {t("review.recurring.empty")}
                  </p>
                ) : (
                  <ul className="divide-y divide-border">
                    {query.data.recurring_unruled.map((rm) => (
                      <li
                        key={rm.merchant}
                        className="flex items-center justify-between gap-3 py-2 text-sm"
                      >
                        <Link
                          href={`/transactions?search=${encodeURIComponent(rm.merchant)}`}
                          className="truncate font-medium hover:underline"
                        >
                          {rm.merchant}
                        </Link>
                        <span className="shrink-0 tabular-nums text-muted-foreground">
                          {t("review.timesSeen", { count: rm.count })}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

function ReviewActionPanel({ data }: { data: ReviewSummary }) {
  const { t } = useT();
  const needsReview = data.counts.uncategorized + data.counts.no_suggestion;
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
                href="/transactions?view=review"
                cta={t("review.openQueue")}
              />
            ) : null}
            {rareCount > 0 ? (
              <ActionTile
                title={t("review.next.rareClasses")}
                description={t("review.next.rareClassesHint", {
                  n: rareCount,
                })}
                href="/transactions?view=review"
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
