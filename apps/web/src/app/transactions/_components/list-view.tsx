/* eslint-disable react-hooks/set-state-in-effect */
"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  api,
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
  isSuggestionReadyToAccept,
} from "../_lib/constants";
import { transactionQueryKeys } from "../_lib/query-keys";
import { useTransactionMutations } from "../_lib/use-transaction-mutations";
import { BulkActionsBar } from "./bulk-actions-bar";
import { TransactionFilters } from "./transaction-filters";
import { TransactionsTable } from "./transactions-table";

interface ListViewProps {
  reviewMode: boolean;
  initialFilters?: TransactionInitialFilters;
}

export interface TransactionInitialFilters {
  key: string;
  search?: string;
  category?: string;
  merchantCanonicalKey?: string;
  direction?: Direction;
  transactionType?: string;
  dateFrom?: string;
  dateTo?: string;
  importId?: number;
  reviewState?: CategoryState;
  includeTransfers?: boolean;
}

export function ListView({ reviewMode, initialFilters }: ListViewProps) {
  const { t } = useT();
  const confirm = useConfirm();
  const storagePrefix = reviewMode
    ? "finance.transactions.review"
    : "finance.transactions.list";
  const [search, setSearch] = useLocalStorageState(
    `${storagePrefix}.search`,
    "",
  );
  const [direction, setDirection] = useLocalStorageState<Direction>(
    `${storagePrefix}.direction`,
    "all",
  );
  const [category, setCategory] = useLocalStorageState(
    `${storagePrefix}.category`,
    "",
  );
  const [page, setPage] = useState(0);
  const [importId, setImportId] = useState<number | undefined>(
    initialFilters?.importId,
  );
  const [merchantCanonicalKey, setMerchantCanonicalKey] = useState<
    string | undefined
  >(initialFilters?.merchantCanonicalKey);
  const [includeTransfers, setIncludeTransfers] = useLocalStorageState(
    `${storagePrefix}.includeTransfers`,
    !reviewMode,
  );
  const [transactionType, setTransactionType] = useLocalStorageState(
    `${storagePrefix}.transactionType`,
    "",
  );
  const [dateFrom, setDateFrom] = useLocalStorageState(
    `${storagePrefix}.dateFrom`,
    "",
  );
  const [dateTo, setDateTo] = useLocalStorageState(
    `${storagePrefix}.dateTo`,
    "",
  );
  const [minConfidence, setMinConfidence] = useLocalStorageState(
    `${storagePrefix}.minConfidence`,
    "",
  );
  const [reviewState, setReviewState] = useLocalStorageState<CategoryState>(
    `${storagePrefix}.reviewState`,
    "assignable",
  );
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkCat, setBulkCat] = useState<string | null>(null);
  const [bulkType, setBulkType] = useState("");
  const confidenceFilter = minConfidence ? Number(minConfidence) : undefined;
  const searchFilter = search.trim() || undefined;
  const directionFilter = direction === "all" ? undefined : direction;
  const categoryFilter = category || undefined;

  useEffect(() => {
    if (!initialFilters?.key) return;
    if (initialFilters.search !== undefined) setSearch(initialFilters.search);
    if (initialFilters.category !== undefined) setCategory(initialFilters.category);
    setMerchantCanonicalKey(initialFilters.merchantCanonicalKey);
    if (initialFilters.direction !== undefined) setDirection(initialFilters.direction);
    if (initialFilters.transactionType !== undefined) {
      setTransactionType(initialFilters.transactionType);
    }
    if (initialFilters.dateFrom !== undefined) setDateFrom(initialFilters.dateFrom);
    if (initialFilters.dateTo !== undefined) setDateTo(initialFilters.dateTo);
    if (initialFilters.importId !== undefined) setImportId(initialFilters.importId);
    if (initialFilters.reviewState !== undefined) {
      setReviewState(initialFilters.reviewState);
    }
    if (initialFilters.includeTransfers !== undefined) {
      setIncludeTransfers(initialFilters.includeTransfers);
    }
    setPage(0);
  }, [
    initialFilters?.key,
    initialFilters?.search,
    initialFilters?.category,
    initialFilters?.merchantCanonicalKey,
    initialFilters?.direction,
    initialFilters?.transactionType,
    initialFilters?.dateFrom,
    initialFilters?.dateTo,
    initialFilters?.importId,
    initialFilters?.reviewState,
    initialFilters?.includeTransfers,
    setCategory,
    setDateFrom,
    setDateTo,
    setDirection,
    setIncludeTransfers,
    setReviewState,
    setSearch,
    setTransactionType,
  ]);

  const filterParams: TransactionFilterParams = {
    search: searchFilter,
    direction: directionFilter,
    category: categoryFilter,
    merchant_canonical_key: merchantCanonicalKey,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    import_id: importId,
    include_transfers: includeTransfers,
    category_state: (reviewMode ? reviewState : "all") as CategoryState,
    min_confidence: confidenceFilter,
    transaction_type: transactionType || undefined,
    review_priority: reviewMode,
  };

  const query = useQuery({
    queryKey: transactionQueryKeys.list(page, filterParams),
    queryFn: () =>
      api.transactions({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        ...filterParams,
      }),
  });

  const summaryQuery = useQuery<FilterSummary>({
    queryKey: transactionQueryKeys.filterSummary(filterParams),
    queryFn: () => api.filterSummary(filterParams),
  });

  const filtered = useMemo<Transaction[]>(() => {
    return query.data ?? [];
  }, [query.data]);

  const suggestionIds = useMemo(
    () =>
      filtered
        .filter(isSuggestionReadyToAccept)
        .map((tx) => tx.id),
    [filtered],
  );
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
    markTransfer,
    acceptSuggestions,
    rejectSuggestions,
    restoreSuggestions,
  } = useTransactionMutations({
    clearSelection: () => setSelected(new Set()),
    clearBulkCategory: () => setBulkCat(null),
    clearBulkType: () => setBulkType(""),
  });

  const hasActiveFilters =
    search !== "" ||
    direction !== "all" ||
    category !== "" ||
    transactionType !== "" ||
    dateFrom !== "" ||
    dateTo !== "" ||
    minConfidence !== "" ||
    includeTransfers !== !reviewMode ||
    (reviewMode && reviewState !== "assignable") ||
    merchantCanonicalKey !== undefined ||
    importId !== undefined;

  const clearFilters = () => {
    setSearch("");
    setDirection("all");
    setCategory("");
    setTransactionType("");
    setDateFrom("");
    setDateTo("");
    setMinConfidence("");
    setIncludeTransfers(!reviewMode);
    setReviewState("assignable");
    setImportId(undefined);
    setMerchantCanonicalKey(undefined);
    setPage(0);
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
        search={search}
        category={category}
        direction={direction}
        transactionType={transactionType}
        dateFrom={dateFrom}
        dateTo={dateTo}
        importId={importId}
        minConfidence={minConfidence}
        reviewState={reviewState}
        includeTransfers={includeTransfers}
        suggestionCount={suggestionIds.length}
        acceptPending={acceptSuggestions.isPending}
        hasActiveFilters={hasActiveFilters}
        filterSummary={summaryQuery.data}
        onSearchChange={(value) => {
          setSearch(value);
          resetPage();
        }}
        onCategoryChange={(value) => {
          setCategory(value);
          resetPage();
        }}
        onDirectionChange={(value) => {
          setDirection(value);
          resetPage();
        }}
        onTransactionTypeChange={(value) => {
          setTransactionType(value);
          resetPage();
        }}
        onDateFromChange={(value) => {
          setDateFrom(value);
          resetPage();
        }}
        onDateToChange={(value) => {
          setDateTo(value);
          resetPage();
        }}
        onMinConfidenceChange={(value) => {
          setMinConfidence(value);
          resetPage();
        }}
        onReviewStateChange={(value) => {
          setReviewState(value);
          setSelected(new Set());
          resetPage();
        }}
        onIncludeTransfersChange={(value) => {
          setIncludeTransfers(value);
          resetPage();
        }}
        onAcceptSuggestions={() =>
          acceptSuggestions.mutate({ ids: suggestionIds, minConfidence: 0 })
        }
        onClearFilters={clearFilters}
      />

      <BulkActionsBar
        selectedCount={selected.size}
        selectedSuggestionCount={selectedSuggestionIds.length}
        selectedRejectedSuggestionCount={selectedRejectedSuggestionIds.length}
        bulkCategory={bulkCat}
        bulkType={bulkType}
        bulkCategorizePending={bulkCategorize.isPending}
        bulkTypePending={bulkSetType.isPending}
        bulkDeletePending={bulkDelete.isPending}
        rejectPending={rejectSuggestions.isPending}
        restorePending={restoreSuggestions.isPending}
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
        onMarkTransfer={() =>
          markTransfer.mutate({
            ids: Array.from(selected),
            transfer: true,
          })
        }
        onDelete={onConfirmDelete}
        onCancel={() => {
          setSelected(new Set());
          setBulkType("");
        }}
      />

      {query.isError ? (
        <ErrorState onRetry={() => query.refetch()} />
      ) : (
        <TransactionsTable
          rows={filtered}
          fetchedCount={query.data?.length ?? 0}
          totalCount={summaryQuery.data?.count}
          isLoading={query.isLoading}
          page={page}
          selected={selected}
          acceptPending={acceptSuggestions.isPending}
          rejectPending={rejectSuggestions.isPending}
          restorePending={restoreSuggestions.isPending}
          onToggleAll={toggleAll}
          onToggleOne={toggleOne}
          onPatchCategory={(id, value, subcategory, rememberRule) =>
            patchCategory.mutate({ id, value, subcategory, rememberRule })
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
          onPreviousPage={() => setPage((p) => Math.max(0, p - 1))}
          onNextPage={() => setPage((p) => p + 1)}
        />
      )}
    </>
  );
}
