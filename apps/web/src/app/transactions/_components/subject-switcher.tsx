"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { TransactionsSubject } from "../_lib/constants";

export function SubjectSwitcher({
  value,
  onChange,
}: {
  value: TransactionsSubject;
  onChange: (value: TransactionsSubject) => void;
}) {
  const { t } = useT();
  const summary = useQuery({
    queryKey: ["review-summary"],
    queryFn: () => api.reviewSummary(),
  });
  const items: { value: TransactionsSubject; label: string; count?: number }[] = [
    {
      value: "category",
      label: t("transactions.subject.categories"),
      count: summary.data?.counts.uncategorized,
    },
    {
      value: "transaction_type",
      label: t("transactions.subject.types"),
      count: summary.data?.transaction_type_quality.needs_review,
    },
  ];

  return (
    <div className="flex flex-wrap items-center gap-0.5">
      <span className="px-2 text-xs font-medium text-muted-foreground">
        {t("transactions.subject.label")}
      </span>
      {items.map((item) => (
        <button
          key={item.value}
          type="button"
          onClick={() => onChange(item.value)}
          className={cn(
            "inline-flex h-9 items-center gap-2 rounded-[calc(var(--radius)-0.25rem)] px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            value === item.value
              ? "bg-primary/10 text-primary"
              : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
          )}
        >
          {item.label}
          {item.count !== undefined ? (
            <Badge variant="muted" className="px-1.5 text-[10px] tabular-nums">
              {item.count}
            </Badge>
          ) : null}
        </button>
      ))}
    </div>
  );
}
