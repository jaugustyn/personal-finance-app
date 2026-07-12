"use client";

import { CategoryCombobox } from "@/components/category-combobox";
import { TransactionTypeCombobox } from "@/components/transaction-type-combobox";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";
import { Ban, Check, RotateCcw, Trash2, X } from "lucide-react";

interface BulkActionsBarProps {
  reviewMode: boolean;
  selectedCount: number;
  selectedSuggestionCount: number;
  selectedRejectedSuggestionCount: number;
  selectedTypeSuggestionCount: number;
  bulkCategory: string | null;
  bulkType: string;
  bulkCategorizePending: boolean;
  bulkTypePending: boolean;
  bulkDeletePending: boolean;
  rejectPending: boolean;
  restorePending: boolean;
  typeSuggestionPending: boolean;
  onBulkCategoryChange: (category: string | null) => void;
  onBulkTypeChange: (transactionType: string) => void;
  onBulkCategorize: () => void;
  onBulkType: () => void;
  onRejectSuggestions: () => void;
  onRestoreSuggestions: () => void;
  onAcceptTypeSuggestions: () => void;
  onDelete: () => void;
  onCancel: () => void;
}

export function BulkActionsBar({
  reviewMode,
  selectedCount,
  selectedSuggestionCount,
  selectedRejectedSuggestionCount,
  selectedTypeSuggestionCount,
  bulkCategory,
  bulkType,
  bulkCategorizePending,
  bulkTypePending,
  bulkDeletePending,
  rejectPending,
  restorePending,
  typeSuggestionPending,
  onBulkCategoryChange,
  onBulkTypeChange,
  onBulkCategorize,
  onBulkType,
  onRejectSuggestions,
  onRestoreSuggestions,
  onAcceptTypeSuggestions,
  onDelete,
  onCancel,
}: BulkActionsBarProps) {
  const { t } = useT();
  const hasSuggestionActions =
    reviewMode &&
    (selectedSuggestionCount > 0 ||
      selectedRejectedSuggestionCount > 0 ||
      selectedTypeSuggestionCount > 0);

  if (selectedCount === 0) return null;

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-40 flex justify-center px-4">
      <div className="pointer-events-auto w-full max-w-6xl rounded-lg border border-transparent bg-popover shadow-[0_18px_60px_rgba(15,23,42,0.24),0_6px_18px_rgba(15,23,42,0.16)] ring-1 ring-black/10 dark:shadow-[0_20px_70px_rgba(0,0,0,0.65),0_0_0_1px_rgba(255,255,255,0.04)] dark:ring-white/12">
        <div className="flex flex-col p-3 lg:flex-row lg:items-stretch">
          <div className="flex items-center gap-3 border-b pb-3 lg:w-52 lg:shrink-0 lg:border-b-0 lg:border-r lg:pb-0 lg:pr-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary text-sm font-semibold text-primary-foreground">
              {selectedCount}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium">
                {t("common.selected", { n: selectedCount })}
              </div>
              <div className="text-xs text-muted-foreground">
                {t("transactions.bulk.selection")}
              </div>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="ml-auto h-8 w-8 text-muted-foreground hover:text-foreground lg:hidden"
              aria-label={t("common.cancel")}
              onClick={onCancel}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          <div className="grid flex-1 gap-3 pt-3 lg:pl-3 lg:pt-0 xl:grid-cols-[minmax(18rem,1fr)_minmax(18rem,1fr)_auto]">
            <div className="space-y-1.5 border-b pb-3 xl:border-b-0 xl:border-r xl:pb-0 xl:pr-3">
              <div className="text-[11px] font-medium uppercase text-muted-foreground">
                {t("transactions.bulk.groupCategory")}
              </div>
              <div className="flex min-w-0 items-center gap-2">
                <CategoryCombobox
                  value={bulkCategory}
                  onChange={(sel) => onBulkCategoryChange(sel.category)}
                  groupsOnly
                  size="md"
                  className="min-w-0 flex-1"
                />
                <Button
                  size="sm"
                  className="h-9 shrink-0"
                  disabled={bulkCategorizePending}
                  onClick={onBulkCategorize}
                >
                  {t("transactions.bulkCategorize")}
                </Button>
              </div>
            </div>

            <div className="space-y-1.5 border-b pb-3 xl:border-b-0 xl:border-r xl:pb-0 xl:pr-3">
              <div className="text-[11px] font-medium uppercase text-muted-foreground">
                {t("transactions.bulk.groupType")}
              </div>
              <div className="flex min-w-0 items-center gap-2">
                <TransactionTypeCombobox
                  value={bulkType || "none"}
                  onChange={onBulkTypeChange}
                  includeEmpty
                  emptyValue="none"
                  emptyLabel={t("transactions.bulkType")}
                  ariaLabel={t("transactions.bulkType")}
                  size="md"
                  className="min-w-0 flex-1"
                />
                <Button
                  size="sm"
                  variant="outline"
                  className="h-9 shrink-0"
                  disabled={!bulkType || bulkTypePending}
                  onClick={onBulkType}
                >
                  {t("transactions.bulkSetType")}
                </Button>
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="text-[11px] font-medium uppercase text-muted-foreground">
                {t("common.actions")}
              </div>
              <div className="flex flex-wrap items-center justify-start gap-2 xl:justify-end">
                {hasSuggestionActions ? (
                  <div className="flex flex-wrap gap-2 border-r pr-2">
                    {selectedSuggestionCount > 0 ? (
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-9"
                        disabled={rejectPending}
                        onClick={onRejectSuggestions}
                      >
                        <Ban className="mr-2 h-4 w-4" />
                        {t("transactions.rejectSuggestions", {
                          n: selectedSuggestionCount,
                        })}
                      </Button>
                    ) : null}
                    {selectedRejectedSuggestionCount > 0 ? (
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-9"
                        disabled={restorePending}
                        onClick={onRestoreSuggestions}
                      >
                        <RotateCcw className="mr-2 h-4 w-4" />
                        {t("transactions.restoreSuggestions", {
                          n: selectedRejectedSuggestionCount,
                        })}
                      </Button>
                    ) : null}
                    {selectedTypeSuggestionCount > 0 ? (
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-9"
                        disabled={typeSuggestionPending}
                        onClick={onAcceptTypeSuggestions}
                      >
                        <Check className="mr-2 h-4 w-4" />
                        {t("transactions.acceptTypeSuggestions", {
                          n: selectedTypeSuggestionCount,
                        })}
                      </Button>
                    ) : null}
                  </div>
                ) : null}

                <Button
                  size="sm"
                  variant="destructive"
                  className="h-9"
                  onClick={onDelete}
                  disabled={bulkDeletePending}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  {t("transactions.bulkDelete")}
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  className="hidden h-9 w-9 text-muted-foreground hover:text-foreground lg:inline-flex"
                  aria-label={t("common.cancel")}
                  onClick={onCancel}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
