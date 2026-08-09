"use client";

import { CategoryCombobox } from "@/components/category-combobox";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";
import { Ban, Check, RotateCcw, X } from "lucide-react";

interface CategoryReviewBulkActionsBarProps {
  selectedCount: number;
  selectedSuggestionCount: number;
  selectedRejectedSuggestionCount: number;
  bulkCategory: string | null;
  bulkCategorizePending: boolean;
  acceptPending: boolean;
  rejectPending: boolean;
  restorePending: boolean;
  onBulkCategoryChange: (category: string | null) => void;
  onBulkCategorize: () => void;
  onAcceptSuggestions: () => void;
  onRejectSuggestions: () => void;
  onRestoreSuggestions: () => void;
  onCancel: () => void;
}

export function CategoryReviewBulkActionsBar({
  selectedCount,
  selectedSuggestionCount,
  selectedRejectedSuggestionCount,
  bulkCategory,
  bulkCategorizePending,
  acceptPending,
  rejectPending,
  restorePending,
  onBulkCategoryChange,
  onBulkCategorize,
  onAcceptSuggestions,
  onRejectSuggestions,
  onRestoreSuggestions,
  onCancel,
}: CategoryReviewBulkActionsBarProps) {
  const { t } = useT();

  if (selectedCount === 0) return null;

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-40 flex justify-center px-4">
      <div className="pointer-events-auto w-full max-w-4xl rounded-lg border border-transparent bg-popover p-3 shadow-[0_18px_60px_rgba(15,23,42,0.24),0_6px_18px_rgba(15,23,42,0.16)] ring-1 ring-black/10 dark:shadow-[0_20px_70px_rgba(0,0,0,0.65),0_0_0_1px_rgba(255,255,255,0.04)] dark:ring-white/12">
        <div className="grid gap-3 md:grid-cols-[9rem_minmax(24rem,1fr)_minmax(15rem,20rem)] md:items-center">
          <div className="flex items-center justify-center border-b pb-3 text-sm font-medium md:border-b-0 md:border-r md:pb-0 md:pr-3">
            {t("common.selected", { n: selectedCount })}
          </div>

          <div className="grid content-center md:px-1">
            <AssignmentRow label={t("transactions.bulk.groupCategory")}>
              <CategoryCombobox
                value={bulkCategory}
                onChange={(selection) =>
                  onBulkCategoryChange(selection.category)
                }
                groupsOnly
                size="sm"
                className="min-w-0"
              />
              <Button
                size="sm"
                className="h-8 w-full px-2.5 text-xs"
                disabled={!bulkCategory || bulkCategorizePending}
                onClick={onBulkCategorize}
              >
                {t("transactions.bulkCategorize")}
              </Button>
            </AssignmentRow>
          </div>

          <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 border-t pt-3 md:border-l md:border-t-0 md:pl-3 md:pt-0">
            <div className="grid min-w-0 gap-1.5">
              {selectedSuggestionCount > 0 ? (
                <>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 w-full px-2.5 text-xs"
                    disabled={acceptPending}
                    onClick={onAcceptSuggestions}
                  >
                    <Check className="mr-1.5 h-3.5 w-3.5 text-positive" />
                    {t("transactions.acceptSuggestions", {
                      n: selectedSuggestionCount,
                    })}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 w-full px-2.5 text-xs"
                    disabled={rejectPending}
                    onClick={onRejectSuggestions}
                  >
                    <Ban className="mr-1.5 h-3.5 w-3.5" />
                    {t("transactions.rejectSuggestions", {
                      n: selectedSuggestionCount,
                    })}
                  </Button>
                </>
              ) : null}
              {selectedRejectedSuggestionCount > 0 ? (
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 w-full px-2.5 text-xs"
                  disabled={restorePending}
                  onClick={onRestoreSuggestions}
                >
                  <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                  {t("transactions.restoreSuggestions", {
                    n: selectedRejectedSuggestionCount,
                  })}
                </Button>
              ) : null}
            </div>
            <div className="flex items-center justify-center">
              <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8 text-muted-foreground hover:text-foreground"
                onClick={onCancel}
                title={t("common.cancel")}
                aria-label={t("common.cancel")}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function AssignmentRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid min-w-0 grid-cols-[4.5rem_minmax(0,1fr)_9rem] items-center gap-2">
      <span className="text-[11px] font-medium uppercase text-muted-foreground">
        {label}
      </span>
      {children}
    </div>
  );
}
