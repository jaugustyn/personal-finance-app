"use client";

import { TransactionTypeCombobox } from "@/components/transaction-type-combobox";
import { Money } from "@/components/money";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { TableCell, TableRow } from "@/components/ui/table";
import type { Transaction } from "@/lib/api";
import { tTransactionType, useFormatters, useT } from "@/lib/i18n";
import { TRANSACTION_TYPE_ICONS } from "@/lib/transaction-types";
import { cn } from "@/lib/utils";
import {
  ArrowLeftRight,
  Ban,
  Check,
  MoreHorizontal,
  Pencil,
  RotateCcw,
  StickyNote,
  Tag,
  Trash2,
  X,
} from "lucide-react";
import {
  TRANSACTION_TYPE_OPTIONS,
  hasCategorySuggestion,
  hasRejectedCategorySuggestion,
  isCategoryCandidate,
} from "../_lib/constants";
import { TransactionAnnotationEditor } from "./transaction-annotation-editor";
import { AssignmentValue } from "./assignment-value";
import { TransactionCategoryCell } from "./transaction-category-cell";

interface TransactionRowProps {
  tx: Transaction;
  categoryColor: string | null;
  reviewMode: boolean;
  selected: boolean;
  editing: boolean;
  editingType: boolean;
  acceptPending: boolean;
  rejectPending: boolean;
  restorePending: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onCancelEdit: () => void;
  onEditType: () => void;
  onCancelEditType: () => void;
  onPatchCategory: (
    value: string | null,
    subcategory: string | null,
  ) => void;
  onPatchType: (value: string) => void;
  onAcceptSuggestion: () => void;
  onRejectSuggestion: () => void;
  onRestoreSuggestion: () => void;
  onDelete: () => void;
  annotating: boolean;
  onAnnotate: () => void;
  onCancelAnnotate: () => void;
  onSaveAnnotations: (notes: string | null, tags: string[]) => void;
  onEditTransaction: () => void;
}

export function TransactionRow({
  tx,
  categoryColor,
  reviewMode,
  selected,
  editing,
  editingType,
  acceptPending,
  rejectPending,
  restorePending,
  onToggle,
  onEdit,
  onCancelEdit,
  onEditType,
  onCancelEditType,
  onPatchCategory,
  onPatchType,
  onAcceptSuggestion,
  onRejectSuggestion,
  onRestoreSuggestion,
  onDelete,
  annotating,
  onAnnotate,
  onCancelAnnotate,
  onSaveAnnotations,
  onEditTransaction,
}: TransactionRowProps) {
  const { t } = useT();
  const { formatCurrency, formatDate } = useFormatters();
  const canEditCategory = isCategoryCandidate(tx) || Boolean(tx.category);
  const hasActiveCategorySuggestion = hasCategorySuggestion(tx);
  const hasRejectedCategorySuggestionValue =
    hasRejectedCategorySuggestion(tx);
  const merchantDisplay = tx.merchant_display || tx.merchant || tx.title;
  const rawMerchant = tx.merchant_raw || tx.merchant;
  const showRawMerchant =
    Boolean(rawMerchant) && !sameDisplayText(rawMerchant, merchantDisplay);
  const showTitle =
    Boolean(tx.title) &&
    !sameDisplayText(tx.title, merchantDisplay) &&
    !sameDisplayText(tx.title, rawMerchant);
  const typeSource =
    tx.transaction_type_source ?? "direction";
  const typeSourceLabels: Record<string, string> = {
    manual: t("transactions.typeSource.manual"),
    model: t("transactions.typeSource.model"),
    rule: t("transactions.typeSource.rule"),
    bank: t("transactions.typeSource.bank"),
    direction: t("transactions.typeSource.direction"),
  };
  const typeSourceLabel = typeSourceLabels[typeSource] ?? typeSource;
  const displayedType = tx.transaction_type_effective;
  const displayedTypeOption = TRANSACTION_TYPE_OPTIONS.find(
    (type) => type === displayedType,
  );
  const DisplayedTypeIcon = displayedTypeOption
    ? TRANSACTION_TYPE_ICONS[displayedTypeOption]
    : null;
  const amountCell = (
    <TableCell
      className={cn(
        "pr-4 text-right tabular-nums",
        reviewMode
          ? "border-r border-border/40"
          : "border-r border-border/50",
      )}
    >
      <div className="space-y-0.5">
        <Money
          amount={Number(tx.amount)}
          currency={tx.currency}
          direction={tx.direction}
        />
        {reviewMode && displayedType === "refund" ? (
          <div className="text-xs font-normal text-muted-foreground">
            {tTransactionType(t, "refund")}
          </div>
        ) : null}
        {tx.amount_base != null &&
        tx.base_currency &&
        tx.base_currency !== tx.currency ? (
          <div className="text-xs text-muted-foreground">
            {formatCurrency(Number(tx.amount_base), tx.base_currency)}
          </div>
        ) : null}
      </div>
    </TableCell>
  );

  return (
    <TableRow
      className={cn(
        selected && "bg-primary/5",
      )}
    >
      <TableCell className="border-r border-border/60 p-0">
        <div className="flex min-h-10 w-full items-center justify-center">
          <Checkbox
            checked={selected}
            onCheckedChange={onToggle}
            aria-label={t("transactions.selectRow", { id: tx.id })}
          />
        </div>
      </TableCell>
      <TableCell
        className={cn(
          "whitespace-nowrap text-center text-muted-foreground",
          reviewMode
            ? "border-r border-border/40"
            : "border-r border-border/50",
        )}
      >
        {formatDate(tx.booking_date)}
      </TableCell>
      <TableCell
        className={cn(
          "overflow-hidden font-medium",
          reviewMode
            ? "border-r border-border/40"
            : "border-r border-border/50",
        )}
      >
        <div className="min-w-0 space-y-0.5">
          <div className="flex min-w-0 items-center gap-2">
            <span className="truncate">{merchantDisplay}</span>
          </div>
          {showRawMerchant ? (
            <div className="truncate text-xs font-normal text-muted-foreground">
              {t("transactions.originalMerchant", { value: rawMerchant })}
            </div>
          ) : null}
          {showTitle ? (
            <div className="truncate text-xs font-normal text-muted-foreground">
              {t("transactions.sourceTitle", { value: tx.title })}
            </div>
          ) : null}
        </div>
        {annotating ? (
          <TransactionAnnotationEditor
            tx={tx}
            onCancel={onCancelAnnotate}
            onSave={onSaveAnnotations}
          />
        ) : (
          ((tx.tags?.length ?? 0) > 0 || tx.notes) && (
            <div className="mt-1 space-y-1">
              {(tx.tags?.length ?? 0) > 0 && (
                <div className="flex flex-wrap gap-1">
                  {tx.tags!.map((tag) => (
                    <Badge key={tag} variant="outline" className="text-[11px]">
                      <Tag className="mr-1 h-2.5 w-2.5" />
                      {tag}
                    </Badge>
                  ))}
                </div>
              )}
              {tx.notes && (
                <div className="flex items-start gap-1 text-xs text-muted-foreground">
                  <StickyNote className="mt-0.5 h-3 w-3 shrink-0" />
                  <span className="truncate">{tx.notes}</span>
                </div>
              )}
            </div>
          )
        )}
      </TableCell>
      {reviewMode ? amountCell : null}
      {!reviewMode ? (
        <TableCell
          className="overflow-hidden border-r border-border/50"
          onDoubleClick={() => {
            if (!editingType) onEditType();
          }}
          title={!editingType ? t("transactions.editTypeHint") : undefined}
        >
          {editingType ? (
            <TransactionTypeInlineSelect
              value={displayedType || "expense"}
              onChange={onPatchType}
              onCancel={onCancelEditType}
            />
          ) : (
            <div className="flex justify-start">
              <AssignmentValue
                label={displayedType ? tTransactionType(t, displayedType) : null}
                icon={
                  DisplayedTypeIcon ? (
                    <DisplayedTypeIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  ) : undefined
                }
                title={typeSourceLabel}
                onEdit={onEditType}
              />
            </div>
          )}
        </TableCell>
      ) : null}
      <TableCell
        className={cn(
          "overflow-hidden",
          reviewMode
            ? "border-r border-border/40"
            : "border-r border-border/50",
        )}
        onDoubleClick={() => {
          if (canEditCategory && !editing) onEdit();
        }}
        title={
          canEditCategory && !editing
            ? t("transactions.editCategoryHint")
            : undefined
        }
      >
        <div className={cn(!reviewMode && !editing && "flex justify-start")}>
          <TransactionCategoryCell
            tx={tx}
            categoryColor={categoryColor}
            reviewMode={reviewMode}
            editing={editing}
            onEdit={onEdit}
            onPatchCategory={onPatchCategory}
            onAcceptSuggestion={onAcceptSuggestion}
          />
        </div>
      </TableCell>
      {!reviewMode ? amountCell : null}
      {reviewMode ? (
        <TableCell className="px-1 text-center">
          {editing ? (
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8"
              onClick={onCancelEdit}
              aria-label={t("common.cancel")}
            >
              <X className="h-4 w-4" />
            </Button>
          ) : (
            <CategoryReviewActions
              hasSuggestion={hasActiveCategorySuggestion}
              hasRejectedSuggestion={hasRejectedCategorySuggestionValue}
              acceptPending={acceptPending}
              rejectPending={rejectPending}
              restorePending={restorePending}
              onAccept={onAcceptSuggestion}
              onReject={onRejectSuggestion}
              onRestore={onRestoreSuggestion}
            />
          )}
        </TableCell>
      ) : (
        <TableCell className="px-1 text-center">
          {editing ? (
            <Button
              size="icon"
              variant="ghost"
              onClick={onCancelEdit}
              aria-label={t("common.cancel")}
            >
              <X className="h-4 w-4" />
            </Button>
          ) : (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label={t("transactions.rowActions")}
                >
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52">
                {tx.source === "manual" ? (
                  <DropdownMenuItem onClick={onEditTransaction}>
                    <Pencil className="h-4 w-4" />
                    {t("transactions.manual.editTitle")}
                  </DropdownMenuItem>
                ) : null}
                {canEditCategory && (
                  <DropdownMenuItem onClick={onEdit}>
                    <Pencil className="h-4 w-4" />
                    {t("transactions.editCategory")}
                  </DropdownMenuItem>
                )}
                <DropdownMenuItem onClick={onAnnotate}>
                  <Tag className="h-4 w-4" />
                  {t("transactions.editAnnotations")}
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuSub>
                  <DropdownMenuSubTrigger>
                    <ArrowLeftRight className="h-4 w-4" />
                    {t("transactions.changeType")}
                  </DropdownMenuSubTrigger>
                  <DropdownMenuSubContent className="max-h-80 overflow-y-auto">
                    {TRANSACTION_TYPE_OPTIONS.map((type) => (
                      <DropdownMenuItem
                        key={type}
                        onClick={() => onPatchType(type)}
                        disabled={tx.transaction_type_effective === type}
                      >
                        {tx.transaction_type_effective === type ? (
                          <Check className="h-4 w-4 text-primary" />
                        ) : (
                          <span className="h-4 w-4" />
                        )}
                        {tTransactionType(t, type)}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuSubContent>
                </DropdownMenuSub>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={onDelete}
                  className="text-destructive focus:text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                  {t("common.delete")}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </TableCell>
      )}
    </TableRow>
  );
}

function CategoryReviewActions({
  hasSuggestion,
  hasRejectedSuggestion,
  acceptPending,
  rejectPending,
  restorePending,
  onAccept,
  onReject,
  onRestore,
}: {
  hasSuggestion: boolean;
  hasRejectedSuggestion: boolean;
  acceptPending: boolean;
  rejectPending: boolean;
  restorePending: boolean;
  onAccept: () => void;
  onReject: () => void;
  onRestore: () => void;
}) {
  const { t } = useT();

  if (hasSuggestion) {
    return (
      <div className="flex items-center justify-center gap-0.5">
        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8 text-positive hover:text-positive"
          disabled={acceptPending}
          onClick={onAccept}
          title={t("transactions.acceptOne")}
          aria-label={t("transactions.acceptOne")}
        >
          <Check className="h-4 w-4" />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8 text-muted-foreground"
          disabled={rejectPending}
          onClick={onReject}
          title={t("transactions.rejectOne")}
          aria-label={t("transactions.rejectOne")}
        >
          <Ban className="h-4 w-4" />
        </Button>
      </div>
    );
  }

  if (hasRejectedSuggestion) {
    return (
      <Button
        size="icon"
        variant="ghost"
        className="h-8 w-8 text-muted-foreground"
        disabled={restorePending}
        onClick={onRestore}
        title={t("transactions.restoreSuggestion")}
        aria-label={t("transactions.restoreSuggestion")}
      >
        <RotateCcw className="h-4 w-4" />
      </Button>
    );
  }

  return null;
}

function sameDisplayText(left: string | null | undefined, right: string | null | undefined) {
  return normalizeDisplayText(left) === normalizeDisplayText(right);
}

function normalizeDisplayText(value: string | null | undefined) {
  return (value ?? "").trim().replace(/\s+/g, " ").toLocaleLowerCase("pl");
}

function TransactionTypeInlineSelect({
  value,
  onChange,
  onCancel,
}: {
  value: string;
  onChange: (value: string) => void;
  onCancel: () => void;
}) {
  return (
    <TransactionTypeCombobox
      value={value}
      onChange={onChange}
      onCancel={onCancel}
      autoFocus
      size="sm"
      className="mx-auto"
    />
  );
}
