"use client";

import { useState } from "react";
import { CategoryCombobox } from "@/components/category-combobox";
import { Money } from "@/components/money";
import { ConfidenceBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
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
import { TableSkeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Transaction } from "@/lib/api";
import { tCategory, tTransactionType, useT } from "@/lib/i18n";
import { formatDate } from "@/lib/utils";
import {
  ArrowLeftRight,
  Ban,
  Check,
  MoreHorizontal,
  Pencil,
  RotateCcw,
  Save,
  StickyNote,
  Tag,
  Trash2,
  X,
} from "lucide-react";
import {
  PAGE_SIZE,
  hasCategorySuggestion,
  hasRejectedCategorySuggestion,
  isCategoryCandidate,
} from "../_lib/constants";

/** All manually assignable transaction types (mirrors the backend enum). */
const TRANSACTION_TYPES = [
  "purchase",
  "own_transfer",
  "person_transfer",
  "salary",
  "income",
  "refund",
  "cash_withdrawal",
  "debt_payment",
  "bank_fee",
  "savings_investment",
  "other",
] as const;

interface TransactionsTableProps {
  rows: Transaction[];
  fetchedCount: number;
  isLoading: boolean;
  page: number;
  selected: Set<number>;
  acceptPending: boolean;
  rejectPending: boolean;
  restorePending: boolean;
  onToggleAll: () => void;
  onToggleOne: (id: number) => void;
  onPatchCategory: (
    id: number,
    value: string | null,
    subcategory: string | null,
    rememberRule?: boolean,
  ) => void;
  onPatchType: (id: number, value: string) => void;
  onAcceptSuggestion: (id: number) => void;
  onRejectSuggestion: (id: number) => void;
  onRestoreSuggestion: (id: number) => void;
  onDeleteOne: (id: number) => void;
  onPatchAnnotations: (
    id: number,
    notes: string | null,
    tags: string[],
  ) => void;
  onPreviousPage: () => void;
  onNextPage: () => void;
}

export function TransactionsTable({
  rows,
  fetchedCount,
  isLoading,
  page,
  selected,
  acceptPending,
  rejectPending,
  restorePending,
  onToggleAll,
  onToggleOne,
  onPatchCategory,
  onPatchType,
  onAcceptSuggestion,
  onRejectSuggestion,
  onRestoreSuggestion,
  onDeleteOne,
  onPatchAnnotations,
  onPreviousPage,
  onNextPage,
}: TransactionsTableProps) {
  const { t } = useT();
  const [editing, setEditing] = useState<number | null>(null);
  const [annotating, setAnnotating] = useState<number | null>(null);
  const allOnPageSelected =
    rows.length > 0 && rows.every((r) => selected.has(r.id));

  return (
    <Card>
      <CardContent className="pt-6">
        {isLoading ? (
          <TableSkeleton />
        ) : rows.length === 0 ? (
          <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
            {t("transactions.empty")}
          </div>
        ) : (
          <>
            <Table className="table-fixed">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">
                    <Checkbox
                      checked={allOnPageSelected}
                      onCheckedChange={onToggleAll}
                      aria-label="select all"
                    />
                  </TableHead>
                  <TableHead className="w-28">
                    {t("transactions.column.date")}
                  </TableHead>
                  <TableHead>{t("transactions.column.merchant")}</TableHead>
                  <TableHead className="w-40">
                    {t("transactions.column.type")}
                  </TableHead>
                  <TableHead className="w-64">
                    {t("transactions.column.category")}
                  </TableHead>
                  <TableHead className="w-32 text-right">
                    {t("transactions.column.amount")}
                  </TableHead>
                  <TableHead className="w-12" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((tx) => (
                  <TransactionRow
                    key={tx.id}
                    tx={tx}
                    selected={selected.has(tx.id)}
                    editing={editing === tx.id}
                    acceptPending={acceptPending}
                    rejectPending={rejectPending}
                    restorePending={restorePending}
                    onToggle={() => onToggleOne(tx.id)}
                    onEdit={() => setEditing(tx.id)}
                    onCancelEdit={() => setEditing(null)}
                    onPatchCategory={(value, subcategory, rememberRule) => {
                      onPatchCategory(tx.id, value, subcategory, rememberRule);
                      setEditing(null);
                    }}
                    onPatchType={(value) => onPatchType(tx.id, value)}
                    onAcceptSuggestion={() => onAcceptSuggestion(tx.id)}
                    onRejectSuggestion={() => onRejectSuggestion(tx.id)}
                    onRestoreSuggestion={() => onRestoreSuggestion(tx.id)}
                    onDelete={() => onDeleteOne(tx.id)}
                    annotating={annotating === tx.id}
                    onAnnotate={() => setAnnotating(tx.id)}
                    onCancelAnnotate={() => setAnnotating(null)}
                    onSaveAnnotations={(notes, tags) => {
                      onPatchAnnotations(tx.id, notes, tags);
                      setAnnotating(null);
                    }}
                  />
                ))}
              </TableBody>
            </Table>
            <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
              <span>
                {t("pagination.page", { n: page + 1 })} · {rows.length} /{" "}
                {fetchedCount}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 0}
                  onClick={onPreviousPage}
                >
                  {t("pagination.previous")}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={fetchedCount < PAGE_SIZE}
                  onClick={onNextPage}
                >
                  {t("pagination.next")}
                </Button>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

interface TransactionRowProps {
  tx: Transaction;
  selected: boolean;
  editing: boolean;
  acceptPending: boolean;
  rejectPending: boolean;
  restorePending: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onCancelEdit: () => void;
  onPatchCategory: (
    value: string | null,
    subcategory: string | null,
    rememberRule?: boolean,
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
}

function TransactionRow({
  tx,
  selected,
  editing,
  acceptPending,
  rejectPending,
  restorePending,
  onToggle,
  onEdit,
  onCancelEdit,
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
}: TransactionRowProps) {
  const { t } = useT();
  const hasSuggestion = hasCategorySuggestion(tx);
  const hasRejectedSuggestion = hasRejectedCategorySuggestion(tx);
  const hasRejectedMarker =
    !tx.category && tx.category_suggestion_rejected && isCategoryCandidate(tx);
  const canEditCategory = isCategoryCandidate(tx) || Boolean(tx.category);
  const [rememberRule, setRememberRule] = useState(false);

  return (
    <TableRow className={selected ? "bg-primary/5" : ""}>
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
        <div className="flex items-center gap-2">
          <span className="truncate">{tx.merchant || tx.title}</span>
        </div>
        {tx.merchant && tx.title && tx.merchant !== tx.title && (
          <div className="truncate text-xs text-muted-foreground">
            {tx.title}
          </div>
        )}
        {annotating ? (
          <AnnotationEditor
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
      <TableCell>
        <Badge variant="outline" className="max-w-full truncate">
          {tx.is_transfer ? (
            <ArrowLeftRight className="mr-1 h-3 w-3 shrink-0" />
          ) : null}
          {tTransactionType(t, tx.transaction_type)}
        </Badge>
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
        {editing ? (
          <div className="space-y-2">
            <CategoryCombobox
              value={tx.category}
              subValue={tx.subcategory}
              onChange={(sel) =>
                onPatchCategory(sel.category, sel.subcategory, rememberRule)
              }
              autoFocus
            />
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <Checkbox
                checked={rememberRule}
                onCheckedChange={(c) => setRememberRule(c === true)}
                className="h-3.5 w-3.5"
              />
              {t("transactions.rememberRule")}
            </label>
          </div>
        ) : tx.category ? (
          <Badge variant="secondary" className="max-w-full truncate">
            {tCategory(t, tx.category)}
          </Badge>
        ) : hasRejectedSuggestion ? (
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
                <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
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
        ) : hasSuggestion ? (
          <div className="flex items-start gap-1.5">
            <button
              type="button"
              onClick={onEdit}
              className="flex min-w-0 flex-1 flex-col items-start gap-1 text-left"
              title={t("transactions.suggestion")}
            >
              <Badge
                variant="outline"
                className="max-w-full truncate border-dashed"
              >
                {tCategory(t, tx.category_predicted)}
              </Badge>
              {tx.category_confidence !== null && (
                <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
                  {t("transactions.suggestion")}
                  <ConfidenceBadge value={tx.category_confidence} />
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
        ) : hasRejectedMarker ? (
          <Badge variant="outline">
            {t("transactions.suggestionRejected")}
          </Badge>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell className="text-right">
        <Money
          amount={Number(tx.amount)}
          currency={tx.currency}
          direction={tx.direction}
        />
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
                  {TRANSACTION_TYPES.map((type) => (
                    <DropdownMenuItem
                      key={type}
                      onClick={() => onPatchType(type)}
                      disabled={tx.transaction_type === type}
                    >
                      {tx.transaction_type === type ? (
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

interface AnnotationEditorProps {
  tx: Transaction;
  onCancel: () => void;
  onSave: (notes: string | null, tags: string[]) => void;
}

function AnnotationEditor({ tx, onCancel, onSave }: AnnotationEditorProps) {
  const { t } = useT();
  const [notes, setNotes] = useState(tx.notes ?? "");
  const [tagsText, setTagsText] = useState((tx.tags ?? []).join(", "));

  const handleSave = () => {
    const tags = tagsText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    onSave(notes.trim() || null, tags);
  };

  return (
    <div className="mt-2 space-y-2" onClick={(e) => e.stopPropagation()}>
      <Input
        value={tagsText}
        onChange={(e) => setTagsText(e.target.value)}
        placeholder={t("transactions.tagsPlaceholder")}
        className="h-8 text-xs"
        autoFocus
      />
      <Input
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder={t("transactions.notesPlaceholder")}
        className="h-8 text-xs"
      />
      <div className="flex gap-2">
        <Button size="sm" className="h-7" onClick={handleSave}>
          <Save className="h-3.5 w-3.5" />
          {t("common.save")}
        </Button>
        <Button size="sm" variant="ghost" className="h-7" onClick={onCancel}>
          <X className="h-3.5 w-3.5" />
          {t("common.cancel")}
        </Button>
      </div>
    </div>
  );
}
