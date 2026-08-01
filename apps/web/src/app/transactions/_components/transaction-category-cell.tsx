"use client";

import { CategoryCombobox } from "@/components/category-combobox";
import { ConfidenceBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Transaction } from "@/lib/api";
import { tCategory, type TranslationKey, useT } from "@/lib/i18n";
import { Ban, Check, RotateCcw } from "lucide-react";
import {
  hasCategorySuggestion,
  hasRejectedCategorySuggestion,
  isCategoryCandidate,
} from "../_lib/constants";
import { AssignmentValue } from "./assignment-value";

interface TransactionCategoryCellProps {
  tx: Transaction;
  reviewMode: boolean;
  editing: boolean;
  acceptPending: boolean;
  rejectPending: boolean;
  restorePending: boolean;
  onEdit: () => void;
  onPatchCategory: (
    value: string | null,
    subcategory: string | null,
  ) => void;
  onAcceptSuggestion: () => void;
  onRejectSuggestion: () => void;
  onRestoreSuggestion: () => void;
}

export function TransactionCategoryCell({
  tx,
  reviewMode,
  editing,
  acceptPending,
  rejectPending,
  restorePending,
  onEdit,
  onPatchCategory,
  onAcceptSuggestion,
  onRejectSuggestion,
  onRestoreSuggestion,
}: TransactionCategoryCellProps) {
  const { t } = useT();
  const hasSuggestion = hasCategorySuggestion(tx);
  const hasRejectedSuggestion = hasRejectedCategorySuggestion(tx);
  const hasRejectedMarker =
    !tx.category && tx.category_suggestion_rejected && isCategoryCandidate(tx);
  const decisionAction = tx.classification_decision?.action;

  if (editing) {
    return (
      <CategoryCombobox
        value={tx.category}
        subValue={tx.subcategory}
        onChange={(sel) => onPatchCategory(sel.category, sel.subcategory)}
        autoFocus
      />
    );
  }

  if (tx.category) {
    return (
      <AssignmentValue
        label={tCategory(t, tx.category)}
        onEdit={onEdit}
        title={t("transactions.editCategory")}
      />
    );
  }

  if (!reviewMode) {
    return <span className="text-muted-foreground">-</span>;
  }

  if (hasRejectedSuggestion) {
    return (
      <div className="flex items-start gap-1.5">
        <button
          type="button"
          onClick={onEdit}
          className="flex min-w-0 flex-1 flex-col items-start gap-1 text-left"
          title={t("transactions.suggestionRejected")}
        >
          <Badge variant="outline" className="max-w-full truncate">
            {t("transactions.suggestionRejected")}:{" "}
            {tCategory(t, tx.category_predicted!)}
          </Badge>
          {tx.category_confidence !== null && (
            <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
              <ConfidenceBadge value={tx.category_confidence} />
            </span>
          )}
        </button>
        <Button
          size="icon"
          variant="ghost"
          className="h-7 w-7 shrink-0"
          disabled={restorePending}
          onClick={onRestoreSuggestion}
          title={t("transactions.restoreSuggestion")}
          aria-label={t("transactions.restoreSuggestion")}
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </Button>
      </div>
    );
  }

  if (hasSuggestion) {
    return (
      <div className="flex items-start gap-1.5">
        <button
          type="button"
          onClick={onEdit}
          className="flex min-w-0 flex-1 flex-col items-start gap-1 text-left"
          title={t("transactions.suggestion")}
        >
          <Badge variant="outline" className="max-w-full truncate border-dashed">
            {tCategory(t, tx.category_predicted)}
          </Badge>
          {tx.category_confidence !== null && (
            <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
              {t("transactions.suggestion")}
              <ConfidenceBadge value={tx.category_confidence} />
              {decisionAction ? (
                <ClassificationDecisionBadge action={decisionAction} />
              ) : null}
            </span>
          )}
        </button>
        <div className="flex shrink-0 gap-1">
          <Button
            size="icon"
            variant="ghost"
            className="h-7 w-7 text-positive hover:text-positive"
            disabled={acceptPending}
            onClick={onAcceptSuggestion}
            title={t("transactions.acceptOne")}
            aria-label={t("transactions.acceptOne")}
          >
            <Check className="h-3.5 w-3.5" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            className="h-7 w-7 text-muted-foreground"
            disabled={rejectPending}
            onClick={onRejectSuggestion}
            title={t("transactions.rejectOne")}
            aria-label={t("transactions.rejectOne")}
          >
            <Ban className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    );
  }

  if (hasRejectedMarker) {
    return (
      <Badge variant="outline">
        {t("transactions.suggestionRejected")}
      </Badge>
    );
  }

  return <span className="text-muted-foreground">-</span>;
}

function ClassificationDecisionBadge({
  action,
}: {
  action: NonNullable<Transaction["classification_decision"]>["action"];
}) {
  const { t } = useT();
  const labelKey: Record<typeof action, TranslationKey> = {
    accept: "transactions.classificationDecision.accept",
    review: "transactions.classificationDecision.review",
    manual: "transactions.classificationDecision.manual",
    not_applicable: "transactions.classificationDecision.not_applicable",
  };
  const variant =
    action === "accept" ? "success" : action === "review" ? "warning" : "muted";
  return (
    <Badge variant={variant} className="text-[11px]">
      {t(labelKey[action])}
    </Badge>
  );
}
