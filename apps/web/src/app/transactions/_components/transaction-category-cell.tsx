"use client";

import { CategoryCombobox } from "@/components/category-combobox";
import { CategoryCompactAccent } from "@/components/category-accent";
import { ConfidenceBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { Transaction } from "@/lib/api";
import { tCategory, useT } from "@/lib/i18n";
import { Plus } from "lucide-react";
import {
  hasCategorySuggestion,
  hasRejectedCategorySuggestion,
  isCategoryCandidate,
} from "../_lib/constants";
import { AssignmentValue } from "./assignment-value";

interface TransactionCategoryCellProps {
  tx: Transaction;
  categoryColor: string | null;
  reviewMode: boolean;
  editing: boolean;
  onEdit: () => void;
  onPatchCategory: (
    value: string | null,
    subcategory: string | null,
  ) => void;
  onAcceptSuggestion: () => void;
}

export function TransactionCategoryCell({
  tx,
  categoryColor,
  reviewMode,
  editing,
  onEdit,
  onPatchCategory,
  onAcceptSuggestion,
}: TransactionCategoryCellProps) {
  const { t } = useT();
  const hasSuggestion = hasCategorySuggestion(tx);
  const hasRejectedSuggestion = hasRejectedCategorySuggestion(tx);
  const hasRejectedMarker =
    !tx.category && tx.category_suggestion_rejected && isCategoryCandidate(tx);

  if (editing) {
    return (
      <CategoryCombobox
        value={tx.category ?? (reviewMode ? tx.category_predicted : null)}
        subValue={tx.subcategory}
        onChange={(sel) => {
          if (
            reviewMode &&
            hasSuggestion &&
            sel.category === tx.category_predicted
          ) {
            onAcceptSuggestion();
            return;
          }
          onPatchCategory(sel.category, sel.subcategory);
        }}
        autoFocus
        className="mx-auto"
      />
    );
  }

  if (tx.category) {
    return (
      <AssignmentValue
        label={tCategory(t, tx.category)}
        icon={<CategoryCompactAccent color={categoryColor} />}
        onEdit={onEdit}
        title={t("transactions.editCategory")}
      />
    );
  }

  if (!reviewMode) {
    return (
      <EmptyCategoryValue
        applicable={isCategoryCandidate(tx)}
        onAssign={onEdit}
      />
    );
  }

  if (hasRejectedSuggestion) {
    return (
      <AssignmentValue
        label={tCategory(t, tx.category_predicted!)}
        icon={<CategoryCompactAccent color={categoryColor} />}
        description={t("transactions.suggestionRejected")}
        onEdit={onEdit}
        title={t("transactions.editCategory")}
      />
    );
  }

  if (hasSuggestion) {
    return (
      <AssignmentValue
        label={tCategory(t, tx.category_predicted)}
        icon={<CategoryCompactAccent color={categoryColor} />}
        description={
          tx.category_confidence !== null ? (
            <ConfidenceBadge value={tx.category_confidence} />
          ) : undefined
        }
        onEdit={onEdit}
        title={t("transactions.editCategory")}
      />
    );
  }

  if (hasRejectedMarker) {
    return (
      <Badge variant="outline">
        {t("transactions.suggestionRejected")}
      </Badge>
    );
  }

  return (
    <EmptyCategoryValue
      applicable={isCategoryCandidate(tx)}
      onAssign={onEdit}
    />
  );
}

export function EmptyCategoryValue({
  applicable,
  onAssign,
}: {
  applicable: boolean;
  onAssign: () => void;
}) {
  const { t } = useT();

  if (applicable) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={onAssign}
            className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-dashed border-muted-foreground/45 text-muted-foreground transition-colors hover:border-primary/60 hover:bg-primary/5 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label={t("transactions.bulkCategorize")}
          >
            <Plus className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        </TooltipTrigger>
        <TooltipContent>{t("transactions.bulkCategorize")}</TooltipContent>
      </Tooltip>
    );
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className="inline-flex h-6 w-6 cursor-help items-center justify-center text-muted-foreground"
          aria-label={t("transactions.categoryNotApplicable")}
        >
          <span aria-hidden="true">—</span>
        </span>
      </TooltipTrigger>
      <TooltipContent>{t("transactions.categoryNotApplicable")}</TooltipContent>
    </Tooltip>
  );
}
