"use client";

import { CategoryCombobox } from "@/components/category-combobox";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useT } from "@/lib/i18n";
import { ArrowLeftRight, Ban, Trash2 } from "lucide-react";

interface BulkActionsBarProps {
  selectedCount: number;
  selectedSuggestionCount: number;
  bulkCategory: string | null;
  bulkCategorizePending: boolean;
  bulkDeletePending: boolean;
  rejectPending: boolean;
  onBulkCategoryChange: (category: string | null) => void;
  onBulkCategorize: () => void;
  onRejectSuggestions: () => void;
  onMarkTransfer: () => void;
  onDelete: () => void;
  onCancel: () => void;
}

export function BulkActionsBar({
  selectedCount,
  selectedSuggestionCount,
  bulkCategory,
  bulkCategorizePending,
  bulkDeletePending,
  rejectPending,
  onBulkCategoryChange,
  onBulkCategorize,
  onRejectSuggestions,
  onMarkTransfer,
  onDelete,
  onCancel,
}: BulkActionsBarProps) {
  const { t } = useT();

  if (selectedCount === 0) return null;

  return (
    <Card className="border-primary/40 bg-primary/5">
      <CardContent className="flex flex-wrap items-center gap-3 pt-6">
        <span className="text-sm font-medium">
          {t("common.selected", { n: selectedCount })}
        </span>
        <div className="flex items-center gap-2">
          <CategoryCombobox
            value={bulkCategory}
            onChange={onBulkCategoryChange}
            size="md"
          />
          <Button size="sm" disabled={bulkCategorizePending} onClick={onBulkCategorize}>
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
          {t("transactions.rejectSuggestions", { n: selectedSuggestionCount })}
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
  );
}
