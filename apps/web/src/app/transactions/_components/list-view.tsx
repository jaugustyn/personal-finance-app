/* eslint-disable react-hooks/set-state-in-effect */
"use client";

import { useEffect, useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  api,
  apiErrorMessage,
  type CategoryState,
  type Direction,
  type FilterSummary,
  type Transaction,
  type TransactionFilterParams,
} from "@/lib/api";
import { useT } from "@/lib/i18n";
import { useConfirm } from "@/components/confirm-dialog";
import { ErrorState } from "@/components/error-state";
import { useLocalStorageState } from "@/hooks/use-local-storage-state";
import {
  PAGE_SIZE,
  hasCategorySuggestion,
  hasRejectedCategorySuggestion,
} from "../_lib/constants";
import { transactionQueryKeys } from "../_lib/query-keys";
import { useTransactionMutations } from "../_lib/use-transaction-mutations";
import { BulkActionsBar } from "./bulk-actions-bar";
import { TransactionFilters } from "./transaction-filters";
import {
  TransactionsTable,
  type TransactionSort,
} from "./transactions-table";

interface ListViewProps {
  reviewMode: boolean;
  initialFilters?: TransactionInitialFilters;
}

export interface TransactionInitialFilters {
  key: string;
  search?: string;
  category?: string;
  minAmount?: string;
  maxAmount?: string;
  direction?: Direction;
  transactionType?: string;
  dateFrom?: string;
  dateTo?: string;
  importId?: number;
  reviewState?: CategoryState;
  includeTransfers?: boolean;
}

const URL_FILTER_KEYS = [
  "search",
  "category",
  "min_amount",
  "max_amount",
  "direction",
  "transaction_type",
  "date_from",
  "date_to",
  "import_id",
  "category_state",
  "include_transfers",
] as const;

function updateUrlFilter(key: (typeof URL_FILTER_KEYS)[number], value?: string) {
  const url = new URL(window.location.href);
  if (value) url.searchParams.set(key, value);
  else url.searchParams.delete(key);
  window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

function clearUrlFilters() {
  const url = new URL(window.location.href);
  URL_FILTER_KEYS.forEach((key) => url.searchParams.delete(key));
  window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

export function ListView({ reviewMode, initialFilters }: ListViewProps) {
  const { t } = useT();
  const confirm = useConfirm();
  const commonStoragePrefix = "finance.transactions.filters";
  const [search, setSearch] = useLocalStorageState(
    `${commonStoragePrefix}.search`,
    "",
  );
  const [direction, setDirection] = useLocalStorageState<Direction>(
    `${commonStoragePrefix}.direction`,
    "all",
  );
  const [category, setCategory] = useLocalStorageState(
    `${commonStoragePrefix}.category`,
    "",
  );
  const [minAmount, setMinAmount] = useLocalStorageState(
    `${commonStoragePrefix}.minAmount`,
    "",
  );
  const [maxAmount, setMaxAmount] = useLocalStorageState(
    `${commonStoragePrefix}.maxAmount`,
    "",
  );
  const [reviewSearch, setReviewSearch] = useState("");
  const [reviewCategory, setReviewCategory] = useState("");
  const [reviewState, setReviewState] =
    useState<CategoryState>("needs_review");
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState<TransactionSort>({
    id: "date",
    dir: "desc",
  });
  const [importId, setImportId] = useState<number | undefined>(
    initialFilters?.importId,
  );
  const [includeTransfers, setIncludeTransfers] = useLocalStorageState(
    `${commonStoragePrefix}.includeTransfers`,
    true,
  );
  const [transactionType, setTransactionType] = useLocalStorageState(
    `${commonStoragePrefix}.transactionType`,
    "",
  );
  const [dateFrom, setDateFrom] = useLocalStorageState(
    `${commonStoragePrefix}.dateFrom`,
    "",
  );
  const [dateTo, setDateTo] = useLocalStorageState(
    `${commonStoragePrefix}.dateTo`,
    "",
  );
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkCat, setBulkCat] = useState<string | null>(null);
  const [bulkType, setBulkType] = useState("");
  const activeSearch = reviewMode ? reviewSearch : search;
  const activeCategory = reviewMode ? reviewCategory : category;
  const searchFilter = activeSearch.trim() || undefined;
  const directionFilter = direction === "all" ? undefined : direction;
  const categoryFilter = activeCategory || undefined;
  const minAmountFilter = amountFilterValue(minAmount);
  const maxAmountFilter = amountFilterValue(maxAmount);

  useEffect(() => {
    if (!initialFilters?.key) return;
    if (reviewMode) {
      setReviewSearch(initialFilters.search ?? "");
      setReviewCategory(initialFilters.category ?? "");
      setReviewState(
        initialFilters.reviewState === "rejected" ? "rejected" : "needs_review",
      );
      setPage(0);
      return;
    }
    setSearch(initialFilters.search ?? "");
    setCategory(initialFilters.category ?? "");
    setMinAmount(initialFilters.minAmount ?? "");
    setMaxAmount(initialFilters.maxAmount ?? "");
    setDirection(initialFilters.direction ?? "all");
    setTransactionType(initialFilters.transactionType ?? "");
    setDateFrom(initialFilters.dateFrom ?? "");
    setDateTo(initialFilters.dateTo ?? "");
    setImportId(initialFilters.importId);
    setIncludeTransfers(initialFilters.includeTransfers ?? true);
    setPage(0);
  }, [
    initialFilters?.key,
    initialFilters?.search,
    initialFilters?.category,
    initialFilters?.minAmount,
    initialFilters?.maxAmount,
    initialFilters?.direction,
    initialFilters?.transactionType,
    initialFilters?.dateFrom,
    initialFilters?.dateTo,
    initialFilters?.importId,
    initialFilters?.reviewState,
    initialFilters?.includeTransfers,
    reviewMode,
    setCategory,
    setDateFrom,
    setDateTo,
    setDirection,
    setIncludeTransfers,
    setMaxAmount,
    setMinAmount,
    setSearch,
    setTransactionType,
  ]);

  const filterParams: TransactionFilterParams = reviewMode
    ? {
        search: searchFilter,
        category: categoryFilter,
        category_state: reviewState,
        review_priority: true,
      }
    : {
        search: searchFilter,
        direction: directionFilter,
        category: categoryFilter,
        min_amount: minAmountFilter,
        max_amount: maxAmountFilter,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        import_id: importId,
        include_transfers: includeTransfers,
        category_state: categoryFilter ? "categorized" : "all",
        transaction_type: transactionType || undefined,
      };

  const listParams = reviewMode
    ? filterParams
    : {
        ...filterParams,
        sort_by: sort.id,
        sort_direction: sort.dir,
      };

  const query = useQuery({
    queryKey: transactionQueryKeys.list(page, listParams),
    queryFn: () =>
      api.transactions({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        ...listParams,
      }),
    placeholderData: keepPreviousData,
  });

  const summaryQuery = useQuery<FilterSummary>({
    queryKey: transactionQueryKeys.filterSummary(filterParams),
    queryFn: () => api.filterSummary(filterParams),
    placeholderData: keepPreviousData,
  });

  const filtered = useMemo<Transaction[]>(() => {
    return query.data ?? [];
  }, [query.data]);

  const selectedSuggestionIds = useMemo(
    () =>
      filtered
        .filter((tx) => selected.has(tx.id) && hasCategorySuggestion(tx))
        .map((tx) => tx.id),
    [filtered, selected],
  );
  const selectedRejectedSuggestionIds = useMemo(
    () =>
      filtered
        .filter((tx) => selected.has(tx.id) && hasRejectedCategorySuggestion(tx))
        .map((tx) => tx.id),
    [filtered, selected],
  );
  const selectedTypeSuggestionIds = useMemo(
    () =>
      filtered
        .filter(
          (tx) =>
            selected.has(tx.id) &&
            Boolean(tx.transaction_type_needs_review),
        )
        .map((tx) => tx.id),
    [filtered, selected],
  );

  const {
    patchCategory,
    deleteOne,
    patchType,
    patchAnnotations,
    bulkCategorize,
    bulkSetType,
    bulkDelete,
    acceptSuggestions,
    rejectSuggestions,
    restoreSuggestions,
    acceptTypeSuggestions,
  } = useTransactionMutations({
    clearSelection: () => setSelected(new Set()),
    clearBulkCategory: () => setBulkCat(null),
    clearBulkType: () => setBulkType(""),
  });

  const hasActiveFilters = reviewMode
    ? reviewSearch !== "" ||
      reviewCategory !== "" ||
      reviewState !== "needs_review"
    : search !== "" ||
      direction !== "all" ||
      category !== "" ||
      minAmount !== "" ||
      maxAmount !== "" ||
      transactionType !== "" ||
      dateFrom !== "" ||
      dateTo !== "" ||
      includeTransfers !== true ||
      importId !== undefined;

  const clearFilters = () => {
    if (reviewMode) {
      setReviewSearch("");
      setReviewCategory("");
      setReviewState("needs_review");
      setPage(0);
      clearUrlFilters();
      return;
    }
    setSearch("");
    setDirection("all");
    setCategory("");
    setMinAmount("");
    setMaxAmount("");
    setTransactionType("");
    setDateFrom("");
    setDateTo("");
    setIncludeTransfers(true);
    setImportId(undefined);
    setPage(0);
    clearUrlFilters();
  };

  const resetPage = () => setPage(0);
  const toggleAll = () => {
    const allOnPageSelected =
      filtered.length > 0 && filtered.every((r) => selected.has(r.id));
    if (allOnPageSelected) setSelected(new Set());
    else setSelected(new Set(filtered.map((r) => r.id)));
  };
  const toggleOne = (id: number) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  };

  const onConfirmDelete = async () => {
    const ids = Array.from(selected);
    if (ids.length === 0) return;
    const ok = await confirm({
      title: t("transactions.deleteConfirm", { n: ids.length }),
      destructive: true,
    });
    if (ok) bulkDelete.mutate(ids);
  };
  const onDeleteOne = async (id: number) => {
    const ok = await confirm({
      title: t("transactions.deleteConfirm", { n: 1 }),
      destructive: true,
    });
    if (ok) deleteOne.mutate(id);
  };

  return (
    <>
      <TransactionFilters
        reviewMode={reviewMode}
        search={activeSearch}
        category={activeCategory}
        minAmount={minAmount}
        maxAmount={maxAmount}
        direction={direction}
        transactionType={transactionType}
        dateFrom={dateFrom}
        dateTo={dateTo}
        importId={importId}
        reviewState={reviewState}
        includeTransfers={includeTransfers}
        hasActiveFilters={hasActiveFilters}
        filterSummary={summaryQuery.data}
        onSearchChange={(value) => {
          if (reviewMode) setReviewSearch(value);
          else setSearch(value);
          updateUrlFilter("search", value.trim() || undefined);
          resetPage();
        }}
        onCategoryChange={(value) => {
          if (reviewMode) setReviewCategory(value);
          else setCategory(value);
          updateUrlFilter("category", value || undefined);
          resetPage();
        }}
        onMinAmountChange={(value) => {
          setMinAmount(value);
          updateUrlFilter("min_amount", value || undefined);
          resetPage();
        }}
        onMaxAmountChange={(value) => {
          setMaxAmount(value);
          updateUrlFilter("max_amount", value || undefined);
          resetPage();
        }}
        onDirectionChange={(value) => {
          setDirection(value);
          updateUrlFilter("direction", value === "all" ? undefined : value);
          resetPage();
        }}
        onTransactionTypeChange={(value) => {
          setTransactionType(value);
          updateUrlFilter("transaction_type", value || undefined);
          resetPage();
        }}
        onDateFromChange={(value) => {
          setDateFrom(value);
          updateUrlFilter("date_from", value || undefined);
          resetPage();
        }}
        onDateToChange={(value) => {
          setDateTo(value);
          updateUrlFilter("date_to", value || undefined);
          resetPage();
        }}
        onImportIdChange={(value) => {
          setImportId(value);
          updateUrlFilter(
            "import_id",
            value === undefined ? undefined : String(value),
          );
          resetPage();
        }}
        onReviewStateChange={(value) => {
          setReviewState(value);
          updateUrlFilter(
            "category_state",
            value === "needs_review" ? undefined : value,
          );
          setSelected(new Set());
          resetPage();
        }}
        onIncludeTransfersChange={(value) => {
          setIncludeTransfers(value);
          updateUrlFilter("include_transfers", value ? undefined : "false");
          resetPage();
        }}
        onClearFilters={clearFilters}
      />

      <BulkActionsBar
        reviewMode={reviewMode}
        selectedCount={selected.size}
        selectedSuggestionCount={selectedSuggestionIds.length}
        selectedRejectedSuggestionCount={selectedRejectedSuggestionIds.length}
        selectedTypeSuggestionCount={selectedTypeSuggestionIds.length}
        bulkCategory={bulkCat}
        bulkType={bulkType}
        bulkCategorizePending={bulkCategorize.isPending}
        bulkTypePending={bulkSetType.isPending}
        bulkDeletePending={bulkDelete.isPending}
        rejectPending={rejectSuggestions.isPending}
        restorePending={restoreSuggestions.isPending}
        typeSuggestionPending={acceptTypeSuggestions.isPending}
        onBulkCategoryChange={setBulkCat}
        onBulkTypeChange={(value) =>
          setBulkType(value === "none" ? "" : value)
        }
        onBulkCategorize={() =>
          bulkCategorize.mutate({
            ids: Array.from(selected),
            category: bulkCat,
          })
        }
        onBulkType={() =>
          bulkSetType.mutate({
            ids: Array.from(selected),
            transactionType: bulkType,
          })
        }
        onRejectSuggestions={() =>
          rejectSuggestions.mutate(selectedSuggestionIds)
        }
        onRestoreSuggestions={() =>
          restoreSuggestions.mutate(selectedRejectedSuggestionIds)
        }
        onAcceptTypeSuggestions={() =>
          acceptTypeSuggestions.mutate(selectedTypeSuggestionIds)
        }
        onDelete={onConfirmDelete}
        onCancel={() => {
          setSelected(new Set());
          setBulkCat(null);
          setBulkType("");
        }}
      />

      {query.isError ? (
        <ErrorState
          description={apiErrorMessage(query.error)}
          onRetry={() => query.refetch()}
        />
      ) : (
        <TransactionsTable
          reviewMode={reviewMode}
          rows={filtered}
          fetchedCount={query.data?.length ?? 0}
          totalCount={summaryQuery.data?.count}
          isLoading={query.isLoading}
          page={page}
          sort={sort}
          selected={selected}
          acceptPending={acceptSuggestions.isPending}
          rejectPending={rejectSuggestions.isPending}
          restorePending={restoreSuggestions.isPending}
          onToggleAll={toggleAll}
          onToggleOne={toggleOne}
          onPatchCategory={(id, value, subcategory) =>
            patchCategory.mutate({ id, value, subcategory })
          }
          onPatchType={(id, value) => patchType.mutate({ id, value })}
          onAcceptSuggestion={(id) =>
            acceptSuggestions.mutate({
              ids: [id],
              minConfidence: 0,
              manual: true,
            })
          }
          onRejectSuggestion={(id) => rejectSuggestions.mutate([id])}
          onRestoreSuggestion={(id) => restoreSuggestions.mutate([id])}
          onDeleteOne={onDeleteOne}
          onPatchAnnotations={(id, notes, tags) =>
            patchAnnotations.mutate({ id, notes, tags })
          }
          onSort={(id) => {
            setSort((current) => ({
              id,
              dir:
                current.id === id && current.dir === "desc" ? "asc" : "desc",
            }));
            setPage(0);
          }}
          onPreviousPage={() => setPage((p) => Math.max(0, p - 1))}
          onNextPage={() => setPage((p) => p + 1)}
        />
      )}
    </>
  );
}

function amountFilterValue(value: string): number | undefined {
  if (value.trim() === "") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined;
}
