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
import { DEFAULT_TABLE_PAGE_SIZE } from "@/components/table-pagination";
import {
  storedValueOneOf,
  useLocalStorageState,
} from "@/hooks/use-local-storage-state";
import { queryKeys } from "@/lib/query-keys";
import {
  hasCategorySuggestion,
  hasRejectedCategorySuggestion,
} from "../_lib/constants";
import { useTransactionMutations } from "../_lib/use-transaction-mutations";
import { TransactionListBulkActionsBar } from "./bulk-actions-bar";
import { CategoryReviewBulkActionsBar } from "./category-review-bulk-actions-bar";
import { TransactionFilters } from "./transaction-filters";
import {
  type TransactionCategoryReviewControlsProps,
  TransactionListToolbar,
  type TransactionListControlsProps,
} from "./transaction-list-controls";
import {
  TransactionsTable,
  type TransactionSort,
} from "./transactions-table";

interface ListViewProps {
  reviewMode: boolean;
  initialFilters?: TransactionInitialFilters;
  onAddManualTransaction?: () => void;
  onEditManualTransaction?: (transaction: Transaction) => void;
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
  accountId?: number;
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
  "account_id",
  "category_state",
  "include_transfers",
] as const;
const isDirection = storedValueOneOf<Direction>(["all", "debit", "credit"]);

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

export function ListView({
  reviewMode,
  initialFilters,
  onAddManualTransaction,
  onEditManualTransaction,
}: ListViewProps) {
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
    { validate: isDirection },
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
  const [reviewMinAmount, setReviewMinAmount] = useState("");
  const [reviewMaxAmount, setReviewMaxAmount] = useState("");
  const [reviewDirection, setReviewDirection] = useState<Direction>("all");
  const [reviewDateFrom, setReviewDateFrom] = useState("");
  const [reviewDateTo, setReviewDateTo] = useState("");
  const [reviewState, setReviewState] =
    useState<CategoryState>("needs_review");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(DEFAULT_TABLE_PAGE_SIZE);
  const [sort, setSort] = useState<TransactionSort>({
    id: "date",
    dir: "desc",
  });
  const [importId, setImportId] = useState<number | undefined>(
    initialFilters?.importId,
  );
  const [accountId, setAccountId] = useState<number | undefined>(
    initialFilters?.accountId,
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

  /* eslint-disable react-hooks/set-state-in-effect -- apply URL filters after the client location becomes available */
  useEffect(() => {
    if (!initialFilters?.key) return;
    if (reviewMode) {
      setReviewSearch(initialFilters.search ?? "");
      setReviewCategory(initialFilters.category ?? "");
      setReviewMinAmount(initialFilters.minAmount ?? "");
      setReviewMaxAmount(initialFilters.maxAmount ?? "");
      setReviewDirection(initialFilters.direction ?? "all");
      setReviewDateFrom(initialFilters.dateFrom ?? "");
      setReviewDateTo(initialFilters.dateTo ?? "");
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
    setAccountId(initialFilters.accountId);
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
    initialFilters?.accountId,
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
  /* eslint-enable react-hooks/set-state-in-effect */

  const filterParams: TransactionFilterParams = reviewMode
    ? {
        search: searchFilter,
        direction:
          reviewDirection === "all" ? undefined : reviewDirection,
        category: categoryFilter,
        min_amount: amountFilterValue(reviewMinAmount),
        max_amount: amountFilterValue(reviewMaxAmount),
        date_from: reviewDateFrom || undefined,
        date_to: reviewDateTo || undefined,
        category_state: reviewState,
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
        account_id: accountId,
        include_transfers: includeTransfers,
        category_state: categoryFilter ? "categorized" : "all",
        transaction_type: transactionType || undefined,
      };

  const listParams = {
    ...filterParams,
    sort_by: sort.id,
    sort_direction: sort.dir,
  };
  const queryParams = {
    limit: pageSize,
    offset: page * pageSize,
    ...listParams,
  };

  const query = useQuery({
    queryKey: queryKeys.transactions.list(queryParams),
    queryFn: () => api.transactions(queryParams),
    placeholderData: keepPreviousData,
  });

  const summaryQuery = useQuery<FilterSummary>({
    queryKey: queryKeys.transactions.filterSummary(filterParams),
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
  } = useTransactionMutations({
    clearSelection: () => setSelected(new Set()),
    clearBulkCategory: () => setBulkCat(null),
    clearBulkType: () => setBulkType(""),
  });

  const hasActiveFilters = reviewMode
    ? reviewSearch !== "" ||
      reviewCategory !== "" ||
      reviewMinAmount !== "" ||
      reviewMaxAmount !== "" ||
      reviewDirection !== "all" ||
      reviewDateFrom !== "" ||
      reviewDateTo !== "" ||
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
      importId !== undefined ||
      accountId !== undefined;

  const clearFilters = () => {
    if (reviewMode) {
      setReviewSearch("");
      setReviewCategory("");
      setReviewMinAmount("");
      setReviewMaxAmount("");
      setReviewDirection("all");
      setReviewDateFrom("");
      setReviewDateTo("");
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
    setAccountId(undefined);
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
  const clearBulkSelection = () => {
    setSelected(new Set());
    setBulkCat(null);
    setBulkType("");
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

  const handleSearchChange = (value: string) => {
    if (reviewMode) setReviewSearch(value);
    else setSearch(value);
    updateUrlFilter("search", value.trim() || undefined);
    resetPage();
  };
  const handleCategoryChange = (value: string) => {
    if (reviewMode) setReviewCategory(value);
    else setCategory(value);
    updateUrlFilter("category", value || undefined);
    resetPage();
  };
  const handleMinAmountChange = (value: string) => {
    setMinAmount(value);
    updateUrlFilter("min_amount", value || undefined);
    resetPage();
  };
  const handleMaxAmountChange = (value: string) => {
    setMaxAmount(value);
    updateUrlFilter("max_amount", value || undefined);
    resetPage();
  };
  const handleDirectionChange = (value: Direction) => {
    setDirection(value);
    updateUrlFilter("direction", value === "all" ? undefined : value);
    resetPage();
  };
  const handleTransactionTypeChange = (value: string) => {
    setTransactionType(value);
    updateUrlFilter("transaction_type", value || undefined);
    resetPage();
  };
  const handleDateFromChange = (value: string) => {
    setDateFrom(value);
    updateUrlFilter("date_from", value || undefined);
    resetPage();
  };
  const handleDateToChange = (value: string) => {
    setDateTo(value);
    updateUrlFilter("date_to", value || undefined);
    resetPage();
  };
  const handleImportIdChange = (value: number | undefined) => {
    setImportId(value);
    updateUrlFilter(
      "import_id",
      value === undefined ? undefined : String(value),
    );
    resetPage();
  };
  const handleAccountIdChange = (value: number | undefined) => {
    setAccountId(value);
    updateUrlFilter(
      "account_id",
      value === undefined ? undefined : String(value),
    );
    resetPage();
  };
  const handleReviewStateChange = (value: CategoryState) => {
    setReviewState(value);
    updateUrlFilter(
      "category_state",
      value === "needs_review" ? undefined : value,
    );
    setSelected(new Set());
    resetPage();
  };
  const handleReviewMinAmountChange = (value: string) => {
    setReviewMinAmount(value);
    updateUrlFilter("min_amount", value || undefined);
    resetPage();
  };
  const handleReviewMaxAmountChange = (value: string) => {
    setReviewMaxAmount(value);
    updateUrlFilter("max_amount", value || undefined);
    resetPage();
  };
  const handleReviewDirectionChange = (value: Direction) => {
    setReviewDirection(value);
    updateUrlFilter("direction", value === "all" ? undefined : value);
    resetPage();
  };
  const handleReviewDateFromChange = (value: string) => {
    setReviewDateFrom(value);
    updateUrlFilter("date_from", value || undefined);
    resetPage();
  };
  const handleReviewDateToChange = (value: string) => {
    setReviewDateTo(value);
    updateUrlFilter("date_to", value || undefined);
    resetPage();
  };
  const handleIncludeTransfersChange = (value: boolean) => {
    setIncludeTransfers(value);
    updateUrlFilter("include_transfers", value ? undefined : "false");
    resetPage();
  };
  const listControls: TransactionListControlsProps | undefined = reviewMode
    ? undefined
    : {
        search,
        category,
        minAmount,
        maxAmount,
        direction,
        transactionType,
        dateFrom,
        dateTo,
        importId,
        accountId,
        includeTransfers,
        hasActiveFilters,
        filterSummary: summaryQuery.data,
        onAddManualTransaction,
        onSearchChange: handleSearchChange,
        onCategoryChange: handleCategoryChange,
        onMinAmountChange: handleMinAmountChange,
        onMaxAmountChange: handleMaxAmountChange,
        onDirectionChange: handleDirectionChange,
        onTransactionTypeChange: handleTransactionTypeChange,
        onDateFromChange: handleDateFromChange,
        onDateToChange: handleDateToChange,
        onImportIdChange: handleImportIdChange,
        onAccountIdChange: handleAccountIdChange,
        onIncludeTransfersChange: handleIncludeTransfersChange,
        onClearFilters: clearFilters,
      };
  const categoryReviewControls:
    | TransactionCategoryReviewControlsProps
    | undefined = reviewMode
    ? {
        search: reviewSearch,
        category: reviewCategory,
        minAmount: reviewMinAmount,
        maxAmount: reviewMaxAmount,
        direction: reviewDirection,
        dateFrom: reviewDateFrom,
        dateTo: reviewDateTo,
        hasActiveFilters,
        onSearchChange: handleSearchChange,
        onCategoryChange: handleCategoryChange,
        onMinAmountChange: handleReviewMinAmountChange,
        onMaxAmountChange: handleReviewMaxAmountChange,
        onDirectionChange: handleReviewDirectionChange,
        onDateFromChange: handleReviewDateFromChange,
        onDateToChange: handleReviewDateToChange,
        onClearFilters: clearFilters,
      }
    : undefined;

  return (
    <div className="space-y-5">
      {reviewMode ? (
        <TransactionFilters
          reviewState={reviewState}
          onReviewStateChange={handleReviewStateChange}
        />
      ) : listControls ? (
        <section>
          <TransactionListToolbar {...listControls} />
        </section>
      ) : null}

      {reviewMode ? (
        <CategoryReviewBulkActionsBar
          selectedCount={selected.size}
          selectedSuggestionCount={selectedSuggestionIds.length}
          selectedRejectedSuggestionCount={selectedRejectedSuggestionIds.length}
          bulkCategory={bulkCat}
          bulkCategorizePending={bulkCategorize.isPending}
          acceptPending={acceptSuggestions.isPending}
          rejectPending={rejectSuggestions.isPending}
          restorePending={restoreSuggestions.isPending}
          onBulkCategoryChange={setBulkCat}
          onBulkCategorize={() =>
            bulkCategorize.mutate({
              ids: Array.from(selected),
              category: bulkCat,
            })
          }
          onAcceptSuggestions={() =>
            acceptSuggestions.mutate({
              ids: selectedSuggestionIds,
              minConfidence: 0,
              manual: true,
            })
          }
          onRejectSuggestions={() =>
            rejectSuggestions.mutate(selectedSuggestionIds)
          }
          onRestoreSuggestions={() =>
            restoreSuggestions.mutate(selectedRejectedSuggestionIds)
          }
          onCancel={clearBulkSelection}
        />
      ) : (
        <TransactionListBulkActionsBar
          selectedCount={selected.size}
          bulkCategory={bulkCat}
          bulkType={bulkType}
          bulkCategorizePending={bulkCategorize.isPending}
          bulkTypePending={bulkSetType.isPending}
          bulkDeletePending={bulkDelete.isPending}
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
          onDelete={onConfirmDelete}
          onCancel={clearBulkSelection}
        />
      )}

      {summaryQuery.isError ? (
        <ErrorState
          variant="compact"
          description={apiErrorMessage(summaryQuery.error)}
          onRetry={() => void summaryQuery.refetch()}
        />
      ) : null}

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
          pageSize={pageSize}
          sort={sort}
          selected={selected}
          acceptPending={acceptSuggestions.isPending}
          rejectPending={rejectSuggestions.isPending}
          restorePending={restoreSuggestions.isPending}
          listControls={listControls}
          categoryReviewControls={categoryReviewControls}
          onToggleAll={toggleAll}
          onToggleOne={toggleOne}
          onPatchCategory={async (id, value, subcategory) => {
            await patchCategory.mutateAsync({ id, value, subcategory });
          }}
          onPatchType={async (id, value) => {
            await patchType.mutateAsync({ id, value });
          }}
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
          onEditManualTransaction={onEditManualTransaction}
          onSort={(id) => {
            setSort((current) => ({
              id,
              dir:
                current.id === id && current.dir === "asc" ? "desc" : "asc",
            }));
            setPage(0);
          }}
          onPreviousPage={() => setPage((p) => Math.max(0, p - 1))}
          onNextPage={() => setPage((p) => p + 1)}
          onPageSizeChange={(nextPageSize) => {
            setPageSize(nextPageSize);
            setPage(0);
            setSelected(new Set());
          }}
        />
      )}
    </div>
  );
}

function amountFilterValue(value: string): number | undefined {
  if (value.trim() === "") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined;
}
