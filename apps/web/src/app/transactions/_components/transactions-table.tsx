"use client";

import { type ReactNode, useMemo, useState } from "react";
import { CategoryCombobox } from "@/components/category-combobox";
import { TransactionTypeCombobox } from "@/components/transaction-type-combobox";
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
import { tCategory, tTransactionType, type TranslationKey, useT } from "@/lib/i18n";
import { cn, formatCurrency, formatDate } from "@/lib/utils";
import {
  ArrowDown,
  ArrowLeftRight,
  ArrowUp,
  Ban,
  Check,
  ChevronsUpDown,
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
  TRANSACTION_TYPE_OPTIONS,
  hasCategorySuggestion,
  hasRejectedCategorySuggestion,
  isCategoryCandidate,
  isSuggestionReadyToAccept,
} from "../_lib/constants";

type TransactionSortId = "date" | "merchant" | "type" | "category" | "amount";
type TransactionSort = { id: TransactionSortId; dir: "asc" | "desc" } | null;

interface TransactionsTableProps {
  rows: Transaction[];
  fetchedCount: number;
  totalCount?: number;
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
  totalCount,
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
  const [editingType, setEditingType] = useState<number | null>(null);
  const [annotating, setAnnotating] = useState<number | null>(null);
  const [sort, setSort] = useState<TransactionSort>(null);
  const allOnPageSelected =
    rows.length > 0 && rows.every((r) => selected.has(r.id));
  const sortedRows = useMemo(() => {
    if (!sort) return rows;
    const factor = sort.dir === "asc" ? 1 : -1;
    return rows
      .map((row, index) => ({ row, index }))
      .sort((a, b) => {
        const av = transactionSortValue(a.row, sort.id);
        const bv = transactionSortValue(b.row, sort.id);
        let result: number;
        if (typeof av === "number" && typeof bv === "number") {
          result = av - bv;
        } else {
          result = String(av).localeCompare(String(bv), "pl", {
            sensitivity: "base",
          });
        }
        return result === 0 ? a.index - b.index : result * factor;
      })
      .map(({ row }) => row);
  }, [rows, sort]);
  const toggleSort = (id: TransactionSortId) => {
    setSort((prev) => {
      if (prev?.id !== id) return { id, dir: "asc" };
      if (prev.dir === "asc") return { id, dir: "desc" };
      return null;
    });
  };

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
                  <SortableTableHead
                    id="date"
                    sort={sort}
                    onSort={toggleSort}
                    className="w-28"
                  >
                    {t("transactions.column.date")}
                  </SortableTableHead>
                  <SortableTableHead
                    id="merchant"
                    sort={sort}
                    onSort={toggleSort}
                  >
                    {t("transactions.column.merchant")}
                  </SortableTableHead>
                  <SortableTableHead
                    id="type"
                    sort={sort}
                    onSort={toggleSort}
                    className="w-40"
                  >
                    {t("transactions.column.type")}
                  </SortableTableHead>
                  <SortableTableHead
                    id="category"
                    sort={sort}
                    onSort={toggleSort}
                    className="w-64"
                  >
                    {t("transactions.column.category")}
                  </SortableTableHead>
                  <SortableTableHead
                    id="amount"
                    sort={sort}
                    onSort={toggleSort}
                    className="w-32 text-right"
                    align="right"
                  >
                    {t("transactions.column.amount")}
                  </SortableTableHead>
                  <TableHead className="w-12" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedRows.map((tx) => (
                  <TransactionRow
                    key={tx.id}
                    tx={tx}
                    selected={selected.has(tx.id)}
                    editing={editing === tx.id}
                    editingType={editingType === tx.id}
                    acceptPending={acceptPending}
                    rejectPending={rejectPending}
                    restorePending={restorePending}
                    onToggle={() => onToggleOne(tx.id)}
                    onEdit={() => setEditing(tx.id)}
                    onCancelEdit={() => setEditing(null)}
                    onEditType={() => setEditingType(tx.id)}
                    onCancelEditType={() => setEditingType(null)}
                    onPatchCategory={(value, subcategory, rememberRule) => {
                      onPatchCategory(tx.id, value, subcategory, rememberRule);
                      setEditing(null);
                    }}
                    onPatchType={(value) => {
                      onPatchType(tx.id, value);
                      setEditingType(null);
                    }}
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
                {totalCount ?? fetchedCount}
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

function transactionSortValue(tx: Transaction, id: TransactionSortId) {
  switch (id) {
    case "date":
      return tx.booking_date;
    case "merchant":
      return tx.merchant || tx.title;
    case "type":
      return tx.transaction_type;
    case "category":
      return tx.category ?? tx.category_predicted ?? "";
    case "amount":
      return Number(tx.amount);
  }
}

function SortableTableHead({
  id,
  sort,
  onSort,
  children,
  className,
  align = "left",
}: {
  id: TransactionSortId;
  sort: TransactionSort;
  onSort: (id: TransactionSortId) => void;
  children: ReactNode;
  className?: string;
  align?: "left" | "right";
}) {
  const { t } = useT();
  const active = sort?.id === id;
  return (
    <TableHead
      aria-sort={
        active ? (sort!.dir === "asc" ? "ascending" : "descending") : "none"
      }
      className={className}
    >
      <button
        type="button"
        onClick={() => onSort(id)}
        title={t("table.sort")}
        className={cn(
          "inline-flex items-center gap-1 transition-colors hover:text-foreground",
          active && "text-foreground",
          align === "right" && "ml-auto flex-row-reverse",
        )}
      >
        {children}
        {active ? (
          sort!.dir === "asc" ? (
            <ArrowUp className="h-3.5 w-3.5" />
          ) : (
            <ArrowDown className="h-3.5 w-3.5" />
          )
        ) : (
          <ChevronsUpDown className="h-3.5 w-3.5 opacity-50" />
        )}
      </button>
    </TableHead>
  );
}

interface TransactionRowProps {
  tx: Transaction;
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
}: TransactionRowProps) {
  const { t } = useT();
  const hasSuggestion = hasCategorySuggestion(tx);
  const hasRejectedSuggestion = hasRejectedCategorySuggestion(tx);
  const hasRejectedMarker =
    !tx.category && tx.category_suggestion_rejected && isCategoryCandidate(tx);
  const canEditCategory = isCategoryCandidate(tx) || Boolean(tx.category);
  const canAcceptSuggestion = isSuggestionReadyToAccept(tx);
  const decisionAction = tx.classification_decision?.action;
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
      <TableCell
        onDoubleClick={() => {
          if (!editingType) onEditType();
        }}
        title={!editingType ? t("transactions.editTypeHint") : undefined}
      >
        {editingType ? (
          <TransactionTypeInlineSelect
            value={tx.transaction_type || "purchase"}
            onChange={onPatchType}
            onCancel={onCancelEditType}
          />
        ) : (
          <Badge variant="outline" className="max-w-full truncate">
            {tx.is_transfer ? (
              <ArrowLeftRight className="mr-1 h-3 w-3 shrink-0" />
            ) : null}
            {tTransactionType(t, tx.transaction_type)}
          </Badge>
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
                disabled={acceptPending || !canAcceptSuggestion}
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
        <div className="space-y-0.5">
          <Money
            amount={Number(tx.amount)}
            currency={tx.currency}
            direction={tx.direction}
          />
          {tx.amount_base != null && tx.base_currency && tx.base_currency !== tx.currency ? (
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
    <Badge variant={variant} className="text-[10px]">
      {t(labelKey[action])}
    </Badge>
  );
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
