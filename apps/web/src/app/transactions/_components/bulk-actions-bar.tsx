"use client";

import { CategoryCombobox } from "@/components/category-combobox";
import { TransactionTypeCombobox } from "@/components/transaction-type-combobox";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";
import { Trash2, X } from "lucide-react";

interface TransactionListBulkActionsBarProps {
  selectedCount: number;
  bulkCategory: string | null;
  bulkType: string;
  bulkCategorizePending: boolean;
  bulkTypePending: boolean;
  bulkDeletePending: boolean;
  onBulkCategoryChange: (category: string | null) => void;
  onBulkTypeChange: (transactionType: string) => void;
  onBulkCategorize: () => void;
  onBulkType: () => void;
  onDelete: () => void;
  onCancel: () => void;
}

export function TransactionListBulkActionsBar({
  selectedCount,
  bulkCategory,
  bulkType,
  bulkCategorizePending,
  bulkTypePending,
  bulkDeletePending,
  onBulkCategoryChange,
  onBulkTypeChange,
  onBulkCategorize,
  onBulkType,
  onDelete,
  onCancel,
}: TransactionListBulkActionsBarProps) {
  const { t } = useT();

  if (selectedCount === 0) return null;

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-40 flex justify-center px-4">
      <div className="pointer-events-auto w-full max-w-3xl rounded-lg border border-transparent bg-popover p-3 shadow-[0_18px_60px_rgba(15,23,42,0.24),0_6px_18px_rgba(15,23,42,0.16)] ring-1 ring-black/10 dark:shadow-[0_20px_70px_rgba(0,0,0,0.65),0_0_0_1px_rgba(255,255,255,0.04)] dark:ring-white/12">
        <div className="grid gap-3 md:grid-cols-[9rem_minmax(28rem,1fr)_auto] md:items-stretch">
          <div className="flex items-center justify-center border-b pb-3 text-sm font-medium md:border-b-0 md:border-r md:pb-0 md:pr-3">
            {t("common.selected", { n: selectedCount })}
          </div>

          <div className="grid content-center gap-2 md:px-1">
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
                disabled={bulkCategorizePending}
                onClick={onBulkCategorize}
              >
                {t("transactions.bulkCategorize")}
              </Button>
            </AssignmentRow>

            <AssignmentRow label={t("transactions.bulk.groupType")}>
              <TransactionTypeCombobox
                value={bulkType || "none"}
                onChange={onBulkTypeChange}
                includeEmpty
                emptyValue="none"
                emptyLabel={t("transactions.bulkType")}
                ariaLabel={t("transactions.bulkType")}
                size="sm"
                className="min-w-0"
              />
              <Button
                size="sm"
                variant="outline"
                className="h-8 w-full px-2.5 text-xs"
                disabled={!bulkType || bulkTypePending}
                onClick={onBulkType}
              >
                {t("transactions.bulkSetType")}
              </Button>
            </AssignmentRow>
          </div>

          <div className="flex items-center justify-center gap-1 border-t pt-3 md:flex-col md:border-l md:border-t-0 md:pl-3 md:pt-0">
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-destructive hover:bg-destructive/10 hover:text-destructive"
              disabled={bulkDeletePending}
              onClick={onDelete}
              title={t("transactions.bulkDelete")}
              aria-label={t("transactions.bulkDelete")}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
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
