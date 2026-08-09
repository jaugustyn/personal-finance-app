"use client";

import Link from "next/link";

import { CategoryCompactAccent } from "@/components/category-accent";
import { EmptyState } from "@/components/empty-state";
import { useCategories } from "@/hooks/use-categories";
import type { Recap } from "@/lib/api";
import { useFormatters, useT, tCategory } from "@/lib/i18n";
import { transactionsHref } from "@/lib/transaction-links";
import { cn } from "@/lib/utils";

type CategoryChange = Recap["category_changes"][number];

export function CategoryChangeList({
  data,
  currency,
  currentFrom,
  currentTo,
  previousFrom,
  previousTo,
}: {
  data: CategoryChange[];
  currency: string;
  currentFrom: string;
  currentTo: string;
  previousFrom: string;
  previousTo: string;
}) {
  const { t } = useT();
  const { formatCurrency } = useFormatters();
  const { data: categories = [] } = useCategories();
  const colorByCategory = new Map(
    categories.map((category) => [category.name, category.color]),
  );

  if (data.length === 0) {
    return (
      <EmptyState
        title={t("recap.changes.empty")}
        className="min-h-40 bg-card"
      />
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border bg-card">
      <div className="hidden grid-cols-[minmax(10rem,0.8fr)_minmax(10rem,1.7fr)_minmax(7rem,auto)] items-center gap-4 border-b bg-muted/20 px-4 py-2 text-xs font-medium text-muted-foreground sm:grid">
        <span />
        <div className="mx-auto flex w-[92%] justify-between px-1">
          <span>{t("recap.changes.less")}</span>
          <span>{t("recap.changes.more")}</span>
        </div>
        <span className="text-right">{t("recap.delta")}</span>
      </div>
      <div className="divide-y divide-border/70">
        {data.map((row) => {
          const category = tCategory(t, row.category);
          const barWidth = relativeChangeBarWidth(row);
          const showCurrentPeriod = row.current_count > 0;
          const href = transactionsHref({
            category: row.category,
            date_from: showCurrentPeriod ? currentFrom : previousFrom,
            date_to: showCurrentPeriod ? currentTo : previousTo,
          });
          const delta = `${row.delta > 0 ? "+" : ""}${formatCurrency(
            row.delta,
            currency,
          )}`;

          return (
            <Link
              key={row.category}
              href={href}
              className="group grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 px-4 py-3 transition-colors hover:bg-muted/35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring sm:grid-cols-[minmax(10rem,0.8fr)_minmax(10rem,1.7fr)_minmax(7rem,auto)]"
              aria-label={`${category}: ${delta}`}
            >
              <span className="flex min-w-0 items-start gap-2.5">
                <CategoryCompactAccent
                  color={colorByCategory.get(row.category)}
                  className="mt-1"
                />
                <span className="min-w-0">
                  <span className="block truncate font-medium underline-offset-4 group-hover:text-primary group-hover:underline">
                    {category}
                  </span>
                  <span className="mt-0.5 block text-xs text-muted-foreground">
                    {changeReason(row, t)}
                  </span>
                </span>
              </span>

              <span className="order-3 col-span-2 min-w-0 sm:order-none sm:col-span-1">
                <span className="mx-auto block w-full sm:w-[92%]">
                  <span className="relative block h-5 overflow-hidden rounded-sm bg-muted/60">
                    <span className="absolute inset-y-0 left-1/2 w-px bg-border" />
                    <span
                      className={cn(
                        "absolute top-1/2 h-2.5 -translate-y-1/2 rounded-sm",
                        row.delta > 0 ? "bg-negative/70" : "bg-positive/70",
                      )}
                      style={{
                        left: row.delta > 0 ? "50%" : `${50 - barWidth}%`,
                        width: `${barWidth}%`,
                      }}
                    />
                  </span>
                  <span className="mt-1 flex min-w-0 justify-between gap-3 text-[11px] tabular-nums text-muted-foreground">
                    <span className="truncate">
                      {t("recap.previousCompact")}{" "}
                      {formatCurrency(row.previous, currency)}
                    </span>
                    <span className="truncate text-right">
                      {t("recap.currentCompact")}{" "}
                      {formatCurrency(row.current, currency)}
                    </span>
                  </span>
                </span>
              </span>

              <span
                className={cn(
                  "text-right font-medium tabular-nums",
                  row.delta > 0 ? "text-negative" : "text-positive",
                )}
              >
                {delta}
              </span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

function relativeChangeBarWidth(row: CategoryChange): number {
  const previous = Math.abs(row.previous);
  const change = Math.abs(row.delta);

  if (change === 0) return 0;
  if (previous === 0) return 48;

  return Math.max(2, Math.min(48, (change / previous) * 48));
}

function changeReason(
  row: CategoryChange,
  t: ReturnType<typeof useT>["t"],
): string {
  if (row.previous_count === 0 && row.current_count > 0) {
    return t("recap.changes.newInPeriod");
  }
  if (row.current_count === 0 && row.previous_count > 0) {
    return t("recap.changes.absentInPeriod");
  }

  const difference = row.current_count - row.previous_count;
  if (difference > 0) {
    return t("recap.changes.operationsMore", { count: difference });
  }
  if (difference < 0) {
    return t("recap.changes.operationsLess", { count: Math.abs(difference) });
  }
  return t("recap.changes.operationsUnchanged");
}
