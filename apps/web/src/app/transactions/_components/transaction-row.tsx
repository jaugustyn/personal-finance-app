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
import { tTransactionType, useT } from "@/lib/i18n";
import { cn, formatCurrency, formatDate } from "@/lib/utils";
import {
  ArrowLeftRight,
  Check,
  MoreHorizontal,
  Pencil,
  StickyNote,
  Tag,
  Trash2,
  X,
} from "lucide-react";
import { TRANSACTION_TYPE_OPTIONS, isCategoryCandidate } from "../_lib/constants";
import { TransactionAnnotationEditor } from "./transaction-annotation-editor";
import { TransactionCategoryCell } from "./transaction-category-cell";

interface TransactionRowProps {
  tx: Transaction;
  reviewMode: boolean;
  selected: boolean;
  editing: boolean;
  editingType: boolean;
  acceptPending: boolean;
  rejectPending: boolean;
  restorePending: boolean;
  typeAcceptPending: boolean;
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
  onAcceptTypeSuggestion: () => void;
  onDelete: () => void;
  annotating: boolean;
  onAnnotate: () => void;
  onCancelAnnotate: () => void;
  onSaveAnnotations: (notes: string | null, tags: string[]) => void;
}

export function TransactionRow({
  tx,
  reviewMode,
  selected,
  editing,
  editingType,
  acceptPending,
  rejectPending,
  restorePending,
  typeAcceptPending,
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
  onAcceptTypeSuggestion,
  onDelete,
  annotating,
  onAnnotate,
  onCancelAnnotate,
  onSaveAnnotations,
}: TransactionRowProps) {
  const { t } = useT();
  const canEditCategory = isCategoryCandidate(tx) || Boolean(tx.category);
  const merchantDisplay = tx.merchant_display || tx.merchant || tx.title;
  const rawMerchant = tx.merchant_raw || tx.merchant;
  const showRawMerchant =
    Boolean(rawMerchant) && !sameDisplayText(rawMerchant, merchantDisplay);
  const showTitle =
    Boolean(tx.title) &&
    !sameDisplayText(tx.title, merchantDisplay) &&
    !sameDisplayText(tx.title, rawMerchant);
  const typeSource =
    tx.transaction_type_source ??
    tx.transaction_type_predicted_source ??
    "direction";
  const typeSourceLabels: Record<string, string> = {
    manual: t("transactions.typeSource.manual"),
    model: t("transactions.typeSource.model"),
    rule: t("transactions.typeSource.rule"),
    bank: t("transactions.typeSource.bank"),
    direction: t("transactions.typeSource.direction"),
  };
  const typeSourceLabel = typeSourceLabels[typeSource] ?? typeSource;
  const typeNeedsReview = tx.transaction_type_needs_review ?? false;
  const typeStatusLabel = t("transactions.needsReview");
  const displayedType = typeNeedsReview
    ? tx.transaction_type_predicted
    : tx.transaction_type_effective;

  return (
    <TableRow
      className={cn(
        "divide-x divide-border/40",
        selected && "bg-primary/5",
      )}
    >
      <TableCell>
        <Checkbox
          checked={selected}
          onCheckedChange={onToggle}
          aria-label={`select ${tx.id}`}
        />
      </TableCell>
      <TableCell className="text-muted-foreground">
        {formatDate(tx.booking_date)}
      </TableCell>
      <TableCell className="font-medium">
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
                    <Badge key={tag} variant="outline" className="text-[10px]">
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
      <TableCell
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
          <div className="space-y-1">
            <Badge
              variant="outline"
              className={cn(
                "max-w-full truncate",
                typeNeedsReview && "border-dashed",
              )}
              title={`${typeSourceLabel}${typeNeedsReview ? ` · ${typeStatusLabel}` : ""}`}
            >
              {tx.is_transfer ? (
                <ArrowLeftRight className="mr-1 h-3 w-3 shrink-0" />
              ) : null}
              {tTransactionType(t, displayedType)}
            </Badge>
            {typeNeedsReview ? (
              <div className="flex items-center gap-1">
                <span className="text-[10px] text-muted-foreground">
                  {typeStatusLabel}
                </span>
                {tx.transaction_type_predicted || tx.transaction_type ? (
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className="h-6 w-6 text-positive hover:text-positive"
                    disabled={typeAcceptPending}
                    onClick={onAcceptTypeSuggestion}
                    aria-label={t("transactions.acceptSuggestion")}
                  >
                    <Check className="h-3 w-3" />
                  </Button>
                ) : null}
              </div>
            ) : null}
          </div>
        )}
      </TableCell>
      <TableCell
        onDoubleClick={() => {
          if (canEditCategory && !editing) onEdit();
        }}
        title={
          canEditCategory && !editing
            ? t("transactions.editCategoryHint")
            : undefined
        }
      >
        <TransactionCategoryCell
          tx={tx}
          reviewMode={reviewMode}
          editing={editing}
          acceptPending={acceptPending}
          rejectPending={rejectPending}
          restorePending={restorePending}
          onEdit={onEdit}
          onPatchCategory={onPatchCategory}
          onAcceptSuggestion={onAcceptSuggestion}
          onRejectSuggestion={onRejectSuggestion}
          onRestoreSuggestion={onRestoreSuggestion}
        />
      </TableCell>
      <TableCell className="text-right">
        <div className="space-y-0.5">
          <Money
            amount={Number(tx.amount)}
            currency={tx.currency}
            direction={tx.direction}
          />
          {tx.amount_base != null &&
          tx.base_currency &&
          tx.base_currency !== tx.currency ? (
            <div className="text-xs text-muted-foreground">
              {formatCurrency(Number(tx.amount_base), tx.base_currency)}
            </div>
          ) : null}
        </div>
      </TableCell>
      <TableCell className="text-right">
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
    </TableRow>
  );
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
    />
  );
}
