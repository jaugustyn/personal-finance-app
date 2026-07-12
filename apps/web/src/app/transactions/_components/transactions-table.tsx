"use client";

import { type ReactNode, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { TableSkeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Transaction } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { PAGE_SIZE } from "../_lib/constants";
import {
  sortTransactions,
  type TransactionSort,
  type TransactionSortId,
} from "../_lib/table-sorting";
import { TransactionRow } from "./transaction-row";

interface TransactionsTableProps {
  reviewMode: boolean;
  rows: Transaction[];
  fetchedCount: number;
  totalCount?: number;
  isLoading: boolean;
  page: number;
  selected: Set<number>;
  acceptPending: boolean;
  rejectPending: boolean;
  restorePending: boolean;
  typeAcceptPending: boolean;
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
  onAcceptTypeSuggestion: (id: number) => void;
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
  reviewMode,
  rows,
  fetchedCount,
  totalCount,
  isLoading,
  page,
  selected,
  acceptPending,
  rejectPending,
  restorePending,
  typeAcceptPending,
  onToggleAll,
  onToggleOne,
  onPatchCategory,
  onPatchType,
  onAcceptSuggestion,
  onRejectSuggestion,
  onRestoreSuggestion,
  onAcceptTypeSuggestion,
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
  const sortedRows = useMemo(() => sortTransactions(rows, sort), [rows, sort]);
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
                <TableRow className="divide-x divide-border/40">
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
                    reviewMode={reviewMode}
                    selected={selected.has(tx.id)}
                    editing={editing === tx.id}
                    editingType={editingType === tx.id}
                    acceptPending={acceptPending}
                    rejectPending={rejectPending}
                    restorePending={restorePending}
                    typeAcceptPending={typeAcceptPending}
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
                    onAcceptTypeSuggestion={() => onAcceptTypeSuggestion(tx.id)}
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
            <TransactionsPagination
              page={page}
              rowCount={rows.length}
              fetchedCount={fetchedCount}
              totalCount={totalCount}
              onPreviousPage={onPreviousPage}
              onNextPage={onNextPage}
            />
          </>
        )}
      </CardContent>
    </Card>
  );
}

function TransactionsPagination({
  page,
  rowCount,
  fetchedCount,
  totalCount,
  onPreviousPage,
  onNextPage,
}: {
  page: number;
  rowCount: number;
  fetchedCount: number;
  totalCount?: number;
  onPreviousPage: () => void;
  onNextPage: () => void;
}) {
  const { t } = useT();

  return (
    <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
      <span>
        {t("pagination.page", { n: page + 1 })} · {rowCount} /{" "}
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
  );
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
