"use client";

import { useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { SortableTableHead } from "@/components/sortable-table-head";
import { TablePagination } from "@/components/table-pagination";
import { TableSkeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type {
  Transaction,
  TransactionSortBy,
  TransactionSortDirection,
} from "@/lib/api";
import { useT } from "@/lib/i18n";
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
  onToggleAll: () => void;
  onToggleOne: (id: number) => void;
  onPatchCategory: (
    id: number,
    value: string | null,
    subcategory: string | null,
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
  const [editing, setEditing] = useState<number | null>(null);
  const [editingType, setEditingType] = useState<number | null>(null);
  const [annotating, setAnnotating] = useState<number | null>(null);
  const allOnPageSelected =
    rows.length > 0 && rows.every((r) => selected.has(r.id));

  return (
    <div className="overflow-hidden rounded-lg border bg-card">
      {isLoading ? (
        <div className="p-3">
          <TableSkeleton />
        </div>
      ) : rows.length === 0 ? (
        <>
          <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
            {t("transactions.empty")}
          </div>
          <TransactionsPagination
            page={page}
            pageSize={pageSize}
            rowCount={0}
            fetchedCount={0}
            totalCount={totalCount}
            onPreviousPage={onPreviousPage}
            onNextPage={onNextPage}
            onPageSizeChange={onPageSizeChange}
          />
        </>
      ) : (
        <>
          <Table className="table-fixed">
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-10">
                  <Checkbox
                    checked={allOnPageSelected}
                    onCheckedChange={onToggleAll}
                    aria-label={t("transactions.selectAll")}
                  />
                </TableHead>
                <SortableTableHead
                  id="date"
                  sort={sort}
                  onSort={onSort}
                  className="w-28"
                >
                  {t("transactions.column.date")}
                </SortableTableHead>
                <SortableTableHead
                  id="merchant"
                  sort={sort}
                  onSort={onSort}
                >
                  {t("transactions.column.merchant")}
                </SortableTableHead>
                <SortableTableHead
                  id="transaction_type"
                  sort={sort}
                  onSort={onSort}
                  className="w-40"
                >
                  {t("transactions.column.type")}
                </SortableTableHead>
                <SortableTableHead
                  id="category"
                  sort={sort}
                  onSort={onSort}
                  className="w-64"
                >
                  {t("transactions.column.category")}
                </SortableTableHead>
                <SortableTableHead
                  id="amount"
                  sort={sort}
                  onSort={onSort}
                  className="w-32 text-right"
                  align="right"
                >
                  {t("transactions.column.amount")}
                </SortableTableHead>
                <TableHead className="w-12 text-center" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((tx) => (
                <TransactionRow
                  key={tx.id}
                  tx={tx}
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
                    onPatchCategory(tx.id, value, subcategory);
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
                  onEditTransaction={() => onEditManualTransaction?.(tx)}
                />
              ))}
            </TableBody>
          </Table>
          <TransactionsPagination
            page={page}
            pageSize={pageSize}
            rowCount={rows.length}
            fetchedCount={fetchedCount}
            totalCount={totalCount}
            onPreviousPage={onPreviousPage}
            onNextPage={onNextPage}
            onPageSizeChange={onPageSizeChange}
          />
        </>
      )}
    </div>
  );
}

function TransactionsPagination({
  page,
  pageSize,
  rowCount,
  fetchedCount,
  totalCount,
  onPreviousPage,
  onNextPage,
  onPageSizeChange,
}: {
  page: number;
  pageSize: number;
  rowCount: number;
  fetchedCount: number;
  totalCount?: number;
  onPreviousPage: () => void;
  onNextPage: () => void;
  onPageSizeChange: (pageSize: number) => void;
}) {
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
    />
  );
}
