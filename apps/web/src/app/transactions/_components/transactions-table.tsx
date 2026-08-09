"use client";

import { useMemo, useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { SortableTableHead } from "@/components/sortable-table-head";
import { TablePagination } from "@/components/table-pagination";
import { TableSkeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type {
  FilterSummary,
  Transaction,
  TransactionSortBy,
  TransactionSortDirection,
} from "@/lib/api";
import { useCategories } from "@/hooks/use-categories";
import { useFormatters, useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import {
  TransactionCategoryReviewFiltersRow,
  TransactionColumnFiltersRow,
  type TransactionCategoryReviewControlsProps,
  type TransactionListControlsProps,
} from "./transaction-list-controls";
import { TransactionRow } from "./transaction-row";

export type TransactionSort = {
  id: TransactionSortBy;
  dir: TransactionSortDirection;
};

interface TransactionsTableProps {
  reviewMode: boolean;
  rows: Transaction[];
  fetchedCount: number;
  totalCount?: number;
  isLoading: boolean;
  page: number;
  pageSize: number;
  sort: TransactionSort;
  selected: Set<number>;
  acceptPending: boolean;
  rejectPending: boolean;
  restorePending: boolean;
  listControls?: TransactionListControlsProps;
  categoryReviewControls?: TransactionCategoryReviewControlsProps;
  onToggleAll: () => void;
  onToggleOne: (id: number) => void;
  onPatchCategory: (
    id: number,
    value: string | null,
    subcategory: string | null,
  ) => Promise<void>;
  onPatchType: (id: number, value: string) => Promise<void>;
  onAcceptSuggestion: (id: number) => void;
  onRejectSuggestion: (id: number) => void;
  onRestoreSuggestion: (id: number) => void;
  onDeleteOne: (id: number) => void;
  onPatchAnnotations: (
    id: number,
    notes: string | null,
    tags: string[],
  ) => void;
  onEditManualTransaction?: (transaction: Transaction) => void;
  onSort: (id: TransactionSortBy) => void;
  onPreviousPage: () => void;
  onNextPage: () => void;
  onPageSizeChange: (pageSize: number) => void;
}

export function TransactionsTable({
  reviewMode,
  rows,
  fetchedCount,
  totalCount,
  isLoading,
  page,
  pageSize,
  sort,
  selected,
  acceptPending,
  rejectPending,
  restorePending,
  listControls,
  categoryReviewControls,
  onToggleAll,
  onToggleOne,
  onPatchCategory,
  onPatchType,
  onAcceptSuggestion,
  onRejectSuggestion,
  onRestoreSuggestion,
  onDeleteOne,
  onPatchAnnotations,
  onEditManualTransaction,
  onSort,
  onPreviousPage,
  onNextPage,
  onPageSizeChange,
}: TransactionsTableProps) {
  const { t } = useT();
  const { data: categories = [] } = useCategories();
  const categoryColors = useMemo(
    () => new Map(categories.map((category) => [category.name, category.color])),
    [categories],
  );
  const [editing, setEditing] = useState<number | null>(null);
  const [editingType, setEditingType] = useState<number | null>(null);
  const [annotating, setAnnotating] = useState<number | null>(null);
  const allOnPageSelected =
    rows.length > 0 && rows.every((r) => selected.has(r.id));
  const amountHeader = (
    <SortableTableHead
      id="amount"
      sort={sort}
      onSort={onSort}
      className={cn(
        "border-r tabular-nums",
        listControls
          ? "w-52 border-border/50"
          : "w-52 border-border/40",
      )}
    >
      {t("transactions.column.amount")}
    </SortableTableHead>
  );

  return (
    <div className="overflow-hidden rounded-lg border bg-card">
      <Table className="table-fixed">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-10 border-r border-border/60 p-0">
              <div className="flex h-10 w-full items-center justify-center">
                <Checkbox
                  checked={allOnPageSelected}
                  onCheckedChange={onToggleAll}
                  aria-label={t("transactions.selectAll")}
                />
              </div>
            </TableHead>
            <SortableTableHead
              id="date"
              sort={sort}
              onSort={onSort}
              className={
                listControls
                  ? "w-[10rem] border-r border-border/50"
                  : "w-[10rem] border-r border-border/40"
              }
            >
              {t("transactions.column.date")}
            </SortableTableHead>
            <SortableTableHead
              id="merchant"
              sort={sort}
              onSort={onSort}
              className={
                reviewMode
                  ? "border-r border-border/40"
                  : "border-r border-border/50"
              }
            >
              {t("transactions.column.merchant")}
            </SortableTableHead>
            {reviewMode ? amountHeader : null}
            {!reviewMode ? (
              <SortableTableHead
                id="transaction_type"
                sort={sort}
                onSort={onSort}
                className="w-52 border-r border-border/50"
              >
                {t("transactions.column.type")}
              </SortableTableHead>
            ) : null}
            <SortableTableHead
              id="category"
              sort={sort}
              onSort={onSort}
              className={
                listControls
                  ? "w-52 border-r border-border/50"
                  : "w-52 border-r border-border/40"
              }
            >
              {t("transactions.column.category")}
            </SortableTableHead>
            {!reviewMode ? amountHeader : null}
            <TableHead
              className={
                reviewMode
                  ? "w-20 text-center"
                  : "w-12 text-center"
              }
            />
          </TableRow>
          {listControls ? (
            <TransactionColumnFiltersRow {...listControls} />
          ) : categoryReviewControls ? (
            <TransactionCategoryReviewFiltersRow
              {...categoryReviewControls}
            />
          ) : null}
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={reviewMode ? 6 : 7} className="p-3">
                <TableSkeleton />
              </TableCell>
            </TableRow>
          ) : rows.length === 0 ? (
            <TableRow className="hover:bg-transparent">
              <TableCell
                colSpan={reviewMode ? 6 : 7}
                className="h-40 text-center text-sm text-muted-foreground"
              >
                {t("transactions.empty")}
              </TableCell>
            </TableRow>
          ) : (
            rows.map((tx) => (
              <TransactionRow
                key={tx.id}
                tx={tx}
                categoryColor={
                  tx.category || (reviewMode && tx.category_predicted)
                    ? (categoryColors.get(
                        tx.category ?? tx.category_predicted!,
                      ) ?? null)
                    : null
                }
                reviewMode={reviewMode}
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
                onPatchCategory={(value, subcategory) => {
                  void onPatchCategory(tx.id, value, subcategory).then(
                    () => setEditing(null),
                    () => undefined,
                  );
                }}
                onPatchType={(value) => {
                  void onPatchType(tx.id, value).then(
                    () => setEditingType(null),
                    () => undefined,
                  );
                }}
                onAcceptSuggestion={() => {
                  setEditing(null);
                  onAcceptSuggestion(tx.id);
                }}
                onRejectSuggestion={() => {
                  setEditing(null);
                  onRejectSuggestion(tx.id);
                }}
                onRestoreSuggestion={() => {
                  setEditing(null);
                  onRestoreSuggestion(tx.id);
                }}
                onDelete={() => onDeleteOne(tx.id)}
                annotating={annotating === tx.id}
                onAnnotate={() => setAnnotating(tx.id)}
                onCancelAnnotate={() => setAnnotating(null)}
                onSaveAnnotations={(notes, tags) => {
                  onPatchAnnotations(tx.id, notes, tags);
                  setAnnotating(null);
                }}
                onEditTransaction={() => onEditManualTransaction?.(tx)}
              />
            ))
          )}
        </TableBody>
      </Table>
      <TransactionsPagination
        page={page}
        pageSize={pageSize}
        rowCount={rows.length}
        fetchedCount={fetchedCount}
        totalCount={totalCount}
        filterSummary={reviewMode ? undefined : listControls?.filterSummary}
        onPreviousPage={onPreviousPage}
        onNextPage={onNextPage}
        onPageSizeChange={onPageSizeChange}
      />
    </div>
  );
}

function TransactionsPagination({
  page,
  pageSize,
  rowCount,
  fetchedCount,
  totalCount,
  filterSummary,
  onPreviousPage,
  onNextPage,
  onPageSizeChange,
}: {
  page: number;
  pageSize: number;
  rowCount: number;
  fetchedCount: number;
  totalCount?: number;
  filterSummary?: FilterSummary;
  onPreviousPage: () => void;
  onNextPage: () => void;
  onPageSizeChange: (pageSize: number) => void;
}) {
  const { formatCurrency } = useFormatters();
  const { t } = useT();

  return (
    <TablePagination
      page={page}
      pageSize={pageSize}
      currentCount={rowCount}
      total={totalCount}
      hasNext={
        totalCount !== undefined
          ? (page + 1) * pageSize < totalCount
          : fetchedCount >= pageSize
      }
      onPageChange={(nextPage) => {
        if (nextPage < page) onPreviousPage();
        else if (nextPage > page) onNextPage();
      }}
      onPageSizeChange={onPageSizeChange}
      alwaysVisible
      leadingContent={
        filterSummary ? (
          <div className="flex flex-wrap items-center gap-x-7 gap-y-1.5 tabular-nums">
            <FooterSummaryValue
              label={t("transactions.filterSummary.income")}
              value={formatCurrency(filterSummary.total_income, "PLN")}
              valueClassName="text-positive"
            />
            <FooterSummaryValue
              label={t("transactions.filterSummary.outflow")}
              value={formatCurrency(filterSummary.total_expenses, "PLN")}
              valueClassName="text-negative"
            />
            <FooterSummaryValue
              label={t("transactions.filterSummary.balance")}
              value={`${filterSummary.net >= 0 ? "+" : "−"}${formatCurrency(
                Math.abs(filterSummary.net),
                "PLN",
              )}`}
              valueClassName={
                filterSummary.net >= 0
                  ? "font-semibold text-positive"
                  : "font-semibold text-negative"
              }
            />
            {filterSummary.unconverted_count > 0 ? (
              <FooterSummaryValue
                label={t("transactions.filterSummary.unconverted")}
                value={String(filterSummary.unconverted_count)}
                valueClassName="text-warning"
              />
            ) : null}
          </div>
        ) : undefined
      }
    />
  );
}

function FooterSummaryValue({
  label,
  value,
  valueClassName,
}: {
  label: string;
  value: string;
  valueClassName?: string;
}) {
  return (
    <span className="inline-flex items-baseline gap-1.5 whitespace-nowrap">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("font-medium text-foreground", valueClassName)}>
        {value}
      </span>
    </span>
  );
}
