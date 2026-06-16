"use client";

import type { ReactNode } from "react";
import { CategoryCombobox } from "@/components/category-combobox";
import { TransactionTypeCombobox } from "@/components/transaction-type-combobox";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useT } from "@/lib/i18n";
import { ArrowLeftRight, Ban, RotateCcw, Trash2 } from "lucide-react";

interface BulkActionsBarProps {
  selectedCount: number;
  selectedSuggestionCount: number;
  selectedRejectedSuggestionCount: number;
  bulkCategory: string | null;
  bulkType: string;
  bulkCategorizePending: boolean;
  bulkTypePending: boolean;
  bulkDeletePending: boolean;
  rejectPending: boolean;
  restorePending: boolean;
  onBulkCategoryChange: (category: string | null) => void;
  onBulkTypeChange: (transactionType: string) => void;
  onBulkCategorize: () => void;
  onBulkType: () => void;
  onRejectSuggestions: () => void;
  onRestoreSuggestions: () => void;
  onMarkTransfer: () => void;
  onDelete: () => void;
  onCancel: () => void;
}

function BulkGroup({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/20 px-2 py-2">
      <span className="text-[11px] font-medium uppercase text-muted-foreground">
        {label}
      </span>
      {children}
    </div>
  );
}

export function BulkActionsBar({
  selectedCount,
  selectedSuggestionCount,
  selectedRejectedSuggestionCount,
  bulkCategory,
  bulkType,
  bulkCategorizePending,
  bulkTypePending,
  bulkDeletePending,
  rejectPending,
  restorePending,
  onBulkCategoryChange,
  onBulkTypeChange,
  onBulkCategorize,
  onBulkType,
  onRejectSuggestions,
  onRestoreSuggestions,
  onMarkTransfer,
  onDelete,
  onCancel,
}: BulkActionsBarProps) {
  const { t } = useT();

  if (selectedCount === 0) return null;

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-40 flex justify-center px-4">
      <Card className="pointer-events-auto max-w-[calc(100vw-2rem)] border-primary/40 bg-card shadow-lg">
        <CardContent className="flex flex-wrap items-center gap-2 py-3">
          <span className="mr-1 shrink-0 text-sm font-medium">
            {t("common.selected", { n: selectedCount })}
          </span>
          <BulkGroup label={t("transactions.bulk.groupCategory")}>
            <CategoryCombobox
              value={bulkCategory}
              onChange={(sel) => onBulkCategoryChange(sel.category)}
              groupsOnly
              size="md"
              className="w-44"
            />
            <Button
              size="sm"
              disabled={bulkCategorizePending}
              onClick={onBulkCategorize}
            >
              {t("transactions.bulkCategorize")}
            </Button>
          </BulkGroup>
          <BulkGroup label={t("transactions.bulk.groupType")}>
            <TransactionTypeCombobox
              value={bulkType || "none"}
              onChange={onBulkTypeChange}
              includeEmpty
              emptyValue="none"
              emptyLabel={t("transactions.bulkType")}
              ariaLabel={t("transactions.bulkType")}
              size="md"
              className="w-44"
            />
            <Button
              size="sm"
              variant="outline"
              disabled={!bulkType || bulkTypePending}
              onClick={onBulkType}
            >
              {t("transactions.bulkSetType")}
            </Button>
          </BulkGroup>
          <BulkGroup label={t("transactions.bulk.groupSuggestions")}>
            <Button
              size="sm"
              variant="outline"
              disabled={selectedSuggestionCount === 0 || rejectPending}
              onClick={onRejectSuggestions}
            >
              <Ban className="mr-2 h-4 w-4" />
              {t("transactions.rejectSuggestions", {
                n: selectedSuggestionCount,
              })}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={
                selectedRejectedSuggestionCount === 0 || restorePending
              }
              onClick={onRestoreSuggestions}
            >
              <RotateCcw className="mr-2 h-4 w-4" />
              {t("transactions.restoreSuggestions", {
                n: selectedRejectedSuggestionCount,
              })}
            </Button>
          </BulkGroup>
          <BulkGroup label={t("transactions.bulk.groupOther")}>
            <Button size="sm" variant="outline" onClick={onMarkTransfer}>
              <ArrowLeftRight className="mr-2 h-4 w-4" />
              {t("transactions.markTransfer")}
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={onDelete}
              disabled={bulkDeletePending}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              {t("transactions.bulkDelete")}
            </Button>
            <Button size="sm" variant="ghost" onClick={onCancel}>
              {t("common.cancel")}
            </Button>
          </BulkGroup>
        </CardContent>
      </Card>
    </div>
  );
}
