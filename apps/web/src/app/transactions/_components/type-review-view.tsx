"use client";

import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Check, RotateCcw, X } from "lucide-react";
import { ErrorState } from "@/components/error-state";
import { DateRangePicker } from "@/components/date-range-picker";
import { Money } from "@/components/money";
import { TransactionTypeCombobox } from "@/components/transaction-type-combobox";
import { TransactionTypeFilterSelect } from "@/components/transaction-type-filter-select";
import { SortableTableHead } from "@/components/sortable-table-head";
import {
  DEFAULT_TABLE_PAGE_SIZE,
  TablePagination,
} from "@/components/table-pagination";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { ClearableInput } from "@/components/ui/clearable-input";
import { TableSkeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  api,
  apiErrorMessage,
  type Direction,
  type Transaction,
  type TransactionSortBy,
} from "@/lib/api";
import { tTransactionType, useFormatters, useT } from "@/lib/i18n";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import {
  TRANSACTION_TYPE_ICONS,
  TRANSACTION_TYPE_OPTIONS,
} from "@/lib/transaction-types";
import { useTransactionMutations } from "../_lib/use-transaction-mutations";
import { AssignmentValue } from "./assignment-value";
import {
  AmountAndDirectionFilter,
  TRANSACTION_INLINE_FILTER_ACTIVE_CLASS,
  TRANSACTION_INLINE_FILTER_CONTROL_CLASS,
} from "./transaction-list-controls";
import type { TransactionSort } from "./transactions-table";

export function TypeReviewView() {
  const { t } = useT();
  const { formatDate } = useFormatters();
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(DEFAULT_TABLE_PAGE_SIZE);
  const [sort, setSort] = useState<TransactionSort>({
    id: "date",
    dir: "desc",
  });
  const [search, setSearch] = useState("");
  const [type, setType] = useState("");
  const [minAmount, setMinAmount] = useState("");
  const [maxAmount, setMaxAmount] = useState("");
  const [direction, setDirection] = useState<Direction>("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkType, setBulkType] = useState("");
  const [editingType, setEditingType] = useState<number | null>(null);
  const hasActiveFilters =
    search !== "" ||
    type !== "" ||
    minAmount !== "" ||
    maxAmount !== "" ||
    direction !== "all" ||
    dateFrom !== "" ||
    dateTo !== "";
  const filters = {
    search: search.trim() || undefined,
    direction: direction === "all" ? undefined : direction,
    min_amount: amountFilterValue(minAmount),
    max_amount: amountFilterValue(maxAmount),
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    transaction_type: type || undefined,
    transaction_type_state: "needs_review" as const,
  };
  const queryParams = {
    ...filters,
    limit: pageSize,
    offset: page * pageSize,
    sort_by: sort.id,
    sort_direction: sort.dir,
  };
  const query = useQuery({
    queryKey: queryKeys.transactions.list(queryParams),
    queryFn: () => api.transactions(queryParams),
    placeholderData: keepPreviousData,
  });
  const summary = useQuery({
    queryKey: queryKeys.transactions.filterSummary(filters),
    queryFn: () => api.filterSummary(filters),
    placeholderData: keepPreviousData,
  });
  const clearSelection = () => setSelected(new Set());
  const mutations = useTransactionMutations({
    clearSelection,
    clearBulkCategory: () => undefined,
    clearBulkType: () => setBulkType(""),
  });
  const rows = (query.data ?? []).slice(0, pageSize);
  const allSelected = rows.length > 0 && rows.every((row) => selected.has(row.id));
  const reset = () => {
    setPage(0);
    clearSelection();
  };
  const dropSelection = (id: number) =>
    setSelected((current) => {
      const next = new Set(current);
      next.delete(id);
      return next;
    });
  const updateSort = (id: TransactionSortBy) => {
    setSort((current) => ({
      id,
      dir: current.id === id && current.dir === "asc" ? "desc" : "asc",
    }));
    reset();
  };
  return (
    <div className="space-y-5 pt-2">
      {selected.size > 0 ? (
        <div className="pointer-events-none fixed inset-x-0 bottom-4 z-40 flex justify-center px-4">
          <div className="pointer-events-auto w-full max-w-4xl rounded-lg border border-transparent bg-popover p-3 shadow-[0_18px_60px_rgba(15,23,42,0.24),0_6px_18px_rgba(15,23,42,0.16)] ring-1 ring-black/10 dark:shadow-[0_20px_70px_rgba(0,0,0,0.65),0_0_0_1px_rgba(255,255,255,0.04)] dark:ring-white/12">
            <div className="grid gap-3 md:grid-cols-[9rem_minmax(24rem,1fr)_auto] md:items-center">
              <div className="flex items-center justify-center border-b pb-3 md:border-b-0 md:border-r md:pb-0 md:pr-3">
                <span className="whitespace-nowrap text-sm font-medium">
                  {t("common.selected", { n: selected.size })}
                </span>
              </div>
              <div className="grid min-w-0 grid-cols-[4.5rem_minmax(0,1fr)_9rem] items-center gap-2 md:px-1">
                <span className="text-[11px] font-medium uppercase text-muted-foreground">
                  {t("transactions.bulk.groupType")}
                </span>
                <TransactionTypeCombobox
                  value={bulkType || "none"}
                  onChange={(value) =>
                    setBulkType(value === "none" ? "" : value)
                  }
                  includeEmpty
                  emptyValue="none"
                  emptyLabel={t("transactions.bulkType")}
                  ariaLabel={t("transactions.bulkType")}
                  size="sm"
                  className="min-w-0"
                />
                <Button
                  size="sm"
                  className="h-8 w-full px-2.5 text-xs"
                  disabled={!bulkType || mutations.bulkSetType.isPending}
                  onClick={() =>
                    mutations.bulkSetType.mutate({
                      ids: [...selected],
                      transactionType: bulkType,
                    })
                  }
                >
                  {t("transactions.bulkSetType")}
                </Button>
              </div>
              <div className="flex items-center justify-center gap-1.5 border-t pt-3 md:border-l md:border-t-0 md:pl-3 md:pt-0">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 px-2.5 text-xs"
                  disabled={mutations.acceptTypeSuggestions.isPending}
                  onClick={() =>
                    mutations.acceptTypeSuggestions.mutate([...selected])
                  }
                >
                  <Check className="mr-1.5 h-3.5 w-3.5 text-positive" />
                  {t("transactions.typeReview.confirmSelected")}
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-8 w-8 text-muted-foreground hover:text-foreground"
                  onClick={clearSelection}
                  title={t("common.cancel")}
                  aria-label={t("common.cancel")}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {summary.isError ? (
        <ErrorState
          variant="compact"
          description={apiErrorMessage(summary.error)}
          onRetry={() => void summary.refetch()}
        />
      ) : null}

      {query.isError ? (
        <ErrorState
          description={apiErrorMessage(query.error)}
          onRetry={() => query.refetch()}
        />
      ) : (
        <div className="overflow-hidden rounded-lg border bg-card">
          <Table className="min-w-[900px] table-fixed">
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-10 border-r border-border/60 p-0">
                  <div className="flex h-10 w-full items-center justify-center">
                    <Checkbox
                      checked={allSelected}
                      aria-label={t("transactions.selectAll")}
                      onCheckedChange={() =>
                        setSelected(
                          allSelected
                            ? new Set()
                            : new Set(rows.map((row) => row.id)),
                        )
                      }
                    />
                  </div>
                </TableHead>
                <SortableTableHead
                  id="date"
                  sort={sort}
                  onSort={updateSort}
                  className="w-[10rem] border-r border-border/40"
                >
                  {t("transactions.column.date")}
                </SortableTableHead>
                <SortableTableHead
                  id="merchant"
                  sort={sort}
                  onSort={updateSort}
                  className="border-r border-border/40"
                >
                  {t("transactions.column.merchant")}
                </SortableTableHead>
                <SortableTableHead
                  id="amount"
                  sort={sort}
                  onSort={updateSort}
                  className="w-52 border-r border-border/40"
                >
                  {t("transactions.column.amount")}
                </SortableTableHead>
                <TableHead className="w-52 border-r border-border/40">
                  {t("transactions.typeReview.proposed")}
                </TableHead>
                <TableHead className="w-12" />
              </TableRow>
              <TableRow className="bg-muted/10 hover:bg-muted/10">
                <TableHead className="h-11 w-10 border-r border-border/60 p-0" />
                <TableHead className="h-11 w-[10rem] border-r border-border/40 p-0">
                  <DateRangePicker
                    from={dateFrom}
                    to={dateTo}
                    onFromChange={(value) => {
                      setDateFrom(value);
                      reset();
                    }}
                    onToChange={(value) => {
                      setDateTo(value);
                      reset();
                    }}
                    onClear={() => {
                      setDateFrom("");
                      setDateTo("");
                      reset();
                    }}
                    ariaLabel={t("transactions.filterDateRange")}
                    compactLabel
                    showIcon={false}
                    triggerClassName={cn(
                      TRANSACTION_INLINE_FILTER_CONTROL_CLASS,
                      (dateFrom || dateTo) &&
                        TRANSACTION_INLINE_FILTER_ACTIVE_CLASS,
                      "h-11 justify-start text-xs",
                    )}
                  />
                </TableHead>
                <TableHead className="h-11 border-r border-border/40 p-0">
                  <ClearableInput
                    value={search}
                    onValueChange={(value) => {
                      setSearch(value);
                      reset();
                    }}
                    placeholder={t("transactions.search")}
                    clearLabel={t("common.clear")}
                    inputClassName={cn(
                      TRANSACTION_INLINE_FILTER_CONTROL_CLASS,
                      search && TRANSACTION_INLINE_FILTER_ACTIVE_CLASS,
                      "h-11 text-xs",
                    )}
                  />
                </TableHead>
                <TableHead className="h-11 w-52 border-r border-border/40 p-0 tabular-nums">
                  <AmountAndDirectionFilter
                    minAmount={minAmount}
                    maxAmount={maxAmount}
                    direction={direction}
                    onMinAmountChange={(value) => {
                      setMinAmount(value);
                      reset();
                    }}
                    onMaxAmountChange={(value) => {
                      setMaxAmount(value);
                      reset();
                    }}
                    onDirectionChange={(value) => {
                      setDirection(value);
                      reset();
                    }}
                  />
                </TableHead>
                <TableHead className="h-11 w-52 border-r border-border/40 p-0">
                  <TransactionTypeFilterSelect
                    value={type}
                    onChange={(value) => {
                      setType(value);
                      reset();
                    }}
                    allLabel={t("transactions.filterType.all")}
                    ariaLabel={t("transactions.typeReview.proposed")}
                    className={cn(
                      TRANSACTION_INLINE_FILTER_CONTROL_CLASS,
                      type && TRANSACTION_INLINE_FILTER_ACTIVE_CLASS,
                      "relative h-11 w-full justify-start pr-8 text-xs [&>svg]:absolute [&>svg]:right-3",
                    )}
                  />
                </TableHead>
                <TableHead className="h-11 w-12 p-0 text-center">
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className="h-8 w-8 text-muted-foreground"
                    disabled={!hasActiveFilters}
                    onClick={() => {
                      setSearch("");
                      setType("");
                      setMinAmount("");
                      setMaxAmount("");
                      setDirection("all");
                      setDateFrom("");
                      setDateTo("");
                      reset();
                    }}
                    title={t("transactions.clearFilters")}
                    aria-label={t("transactions.clearFilters")}
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                  </Button>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {query.isLoading ? (
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={6} className="p-3">
                    <TableSkeleton rows={8} />
                  </TableCell>
                </TableRow>
              ) : rows.length === 0 ? (
                <TableRow className="hover:bg-transparent">
                  <TableCell
                    colSpan={6}
                    className="h-40 text-center text-sm text-muted-foreground"
                  >
                    {t("transactions.typeReview.empty")}
                  </TableCell>
                </TableRow>
              ) : (
                rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="border-r border-border/60 p-0">
                      <div className="flex min-h-10 w-full items-center justify-center">
                        <Checkbox
                          checked={selected.has(row.id)}
                          aria-label={t("transactions.selectRow", { id: row.id })}
                          onCheckedChange={() =>
                            setSelected((current) => {
                              const next = new Set(current);
                              if (next.has(row.id)) next.delete(row.id);
                              else next.add(row.id);
                              return next;
                            })
                          }
                        />
                      </div>
                    </TableCell>
                    <TableCell className="whitespace-nowrap border-r border-border/40 text-center text-muted-foreground">
                      {formatDate(row.booking_date)}
                    </TableCell>
                    <TableCell className="border-r border-border/40">
                      <div className="truncate font-medium">
                        {row.merchant_display || row.merchant || row.title}
                      </div>
                      <div className="truncate text-xs text-muted-foreground">
                        {row.title}
                      </div>
                    </TableCell>
                    <TableCell className="border-r border-border/40 pr-4 text-right tabular-nums">
                      <Money
                        amount={Number(row.amount)}
                        currency={row.currency}
                        direction={row.direction}
                      />
                    </TableCell>
                    <TableCell className="border-r border-border/40">
                      <TypeSuggestionCell
                        row={row}
                        editing={editingType === row.id}
                        onEdit={() => setEditingType(row.id)}
                        onCancel={() => setEditingType(null)}
                        onSelect={(value) => {
                          const request =
                            value === row.transaction_type_predicted
                              ? mutations.acceptTypeSuggestion.mutateAsync(row.id)
                              : mutations.patchType.mutateAsync({
                                  id: row.id,
                                  value,
                                });
                          void request.then(
                            () => {
                              dropSelection(row.id);
                              setEditingType(null);
                            },
                            () => undefined,
                          );
                        }}
                      />
                    </TableCell>
                    <TableCell className="px-1 text-center">
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8 text-positive hover:text-positive"
                        disabled={
                          editingType === row.id ||
                          mutations.acceptTypeSuggestion.isPending
                        }
                        onClick={() => {
                          void mutations.acceptTypeSuggestion
                            .mutateAsync(row.id)
                            .then(
                              () => {
                                dropSelection(row.id);
                                setEditingType(null);
                              },
                              () => undefined,
                            );
                        }}
                        title={t("transactions.typeReview.confirm")}
                        aria-label={t("transactions.typeReview.confirm")}
                      >
                        <Check className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
          <TablePagination
            page={page}
            pageSize={pageSize}
            currentCount={query.isLoading ? 0 : rows.length}
            total={summary.data?.count}
            hasNext={query.isLoading ? false : undefined}
            onPageChange={setPage}
            onPageSizeChange={(nextPageSize) => {
              setPageSize(nextPageSize);
              reset();
            }}
            alwaysVisible
          />
        </div>
      )}
    </div>
  );
}

function amountFilterValue(value: string): number | undefined {
  if (value.trim() === "") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined;
}

function TypeSuggestionCell({
  row,
  editing,
  onEdit,
  onCancel,
  onSelect,
}: {
  row: Transaction;
  editing: boolean;
  onEdit: () => void;
  onCancel: () => void;
  onSelect: (value: string) => void;
}) {
  const { t } = useT();
  const proposedType =
    row.transaction_type_predicted ??
    row.transaction_type_effective ??
    (row.direction === "credit" ? "income" : "expense");
  const option = TRANSACTION_TYPE_OPTIONS.find(
    (value) => value === proposedType,
  );
  const Icon = option ? TRANSACTION_TYPE_ICONS[option] : null;

  if (editing) {
    return (
      <TransactionTypeCombobox
        value={proposedType}
        onChange={onSelect}
        onCancel={onCancel}
        autoFocus
        size="sm"
        className="mx-auto"
      />
    );
  }

  return (
    <AssignmentValue
      label={tTransactionType(t, proposedType)}
      icon={
        Icon ? (
          <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        ) : undefined
      }
      onEdit={onEdit}
      title={t("transactions.changeType")}
    />
  );
}
