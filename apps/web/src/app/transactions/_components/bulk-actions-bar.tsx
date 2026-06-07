"use client";

import { CategoryCombobox } from "@/components/category-combobox";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useT } from "@/lib/i18n";
import { ArrowLeftRight, Ban, RotateCcw, Trash2 } from "lucide-react";

interface BulkActionsBarProps {
  selectedCount: number;
  selectedSuggestionCount: number;
  selectedRejectedSuggestionCount: number;
  bulkCategory: string | null;
  bulkCategorizePending: boolean;
  bulkDeletePending: boolean;
  rejectPending: boolean;
  restorePending: boolean;
  onBulkCategoryChange: (category: string | null) => void;
  onBulkCategorize: () => void;
  onRejectSuggestions: () => void;
  onRestoreSuggestions: () => void;
  onMarkTransfer: () => void;
  onDelete: () => void;
  onCancel: () => void;
}

export function BulkActionsBar({
  selectedCount,
  selectedSuggestionCount,
  selectedRejectedSuggestionCount,
  bulkCategory,
  bulkCategorizePending,
  bulkDeletePending,
  rejectPending,
  restorePending,
  onBulkCategoryChange,
  onBulkCategorize,
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
      <Card className="pointer-events-auto border-primary/40 bg-card shadow-lg">
        <CardContent className="flex flex-wrap items-center gap-3 py-3">
          <span className="text-sm font-medium">
            {t("common.selected", { n: selectedCount })}
          </span>
          <div className="flex items-center gap-2">
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
          </div>
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
            disabled={selectedRejectedSuggestionCount === 0 || restorePending}
            onClick={onRestoreSuggestions}
          >
            <RotateCcw className="mr-2 h-4 w-4" />
            {t("transactions.restoreSuggestions", {
              n: selectedRejectedSuggestionCount,
            })}
          </Button>
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
        </CardContent>
      </Card>
    </div>
  );
}
