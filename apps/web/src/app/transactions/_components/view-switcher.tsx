"use client";

import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import type { TransactionsMode } from "../_lib/constants";

interface ViewSwitcherProps {
  value: TransactionsMode;
  onChange: (view: TransactionsMode) => void;
}

export function ViewSwitcher({ value, onChange }: ViewSwitcherProps) {
  const { t } = useT();
  const summary = useQuery({
    queryKey: queryKeys.transactions.reviewSummary,
    queryFn: () => api.reviewSummary(),
  });
  const categoryReviewCount = summary.data
    ? summary.data.counts.no_suggestion +
      summary.data.counts.low_confidence +
      summary.data.counts.ready_to_accept
    : undefined;
  const items: {
    value: TransactionsMode;
    label: string;
    count?: number;
  }[] = [
    { value: "list", label: t("transactions.viewList") },
    {
      value: "transaction_type_review",
      label: t("transactions.viewTypeReview"),
      count: summary.data?.transaction_type_quality.needs_review,
    },
    {
      value: "category_review",
      label: t("transactions.viewCategoryReview"),
      count: categoryReviewCount,
    },
    { value: "groups", label: t("transactions.viewGroups") },
  ];

  return (
    <div>
      <nav
        className="flex max-w-full overflow-x-auto border-b"
        aria-label={t("transactions.title")}
      >
      {items.map((item) => {
        const active = value === item.value;
        return (
          <button
            key={item.value}
            type="button"
            onClick={() => onChange(item.value)}
            className={cn(
              "inline-flex h-11 shrink-0 items-center gap-2 border-b-2 px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
              active
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:border-border hover:text-foreground",
            )}
          >
            {item.label}
            {item.count !== undefined ? (
              <Badge
                variant="muted"
                className={cn(
                  "px-1.5 text-[10px] tabular-nums",
                  active &&
                    "bg-primary/10 text-primary ring-1 ring-primary/15",
                )}
              >
                {item.count}
              </Badge>
            ) : null}
          </button>
        );
      })}
      </nav>
      {summary.isError ? (
        <button
          type="button"
          onClick={() => void summary.refetch()}
          className="mt-2 text-xs text-destructive underline-offset-4 hover:underline"
        >
          {t("common.error")} · {t("common.retry")}
        </button>
      ) : null}
    </div>
  );
}
