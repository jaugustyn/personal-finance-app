"use client";

import { SegmentedControl } from "@/components/segmented-control";
import type { CategoryState } from "@/lib/api";
import { useT } from "@/lib/i18n";

export function TransactionFilters({
  reviewState,
  onReviewStateChange,
}: {
  reviewState: CategoryState;
  onReviewStateChange: (value: CategoryState) => void;
}) {
  const { t } = useT();

  return (
    <section>
      <div className="flex min-h-12 flex-wrap items-center gap-4 px-1 py-2">
        <SegmentedControl
          value={reviewState}
          onValueChange={(value) =>
            onReviewStateChange(value as CategoryState)
          }
          ariaLabel={t("transactions.reviewQueue")}
          options={[
            {
              value: "needs_review",
              label: t("transactions.reviewQueue.needsReview"),
            },
            {
              value: "rejected",
              label: t("transactions.reviewQueue.rejected"),
            },
          ]}
        />
      </div>
    </section>
  );
}
