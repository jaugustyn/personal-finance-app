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
  const commonStoragePrefix = "finance.transactions.filters";
  const reviewStoragePrefix = "finance.transactions.review";
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
  const [page, setPage] = useState(0);
  const [importId, setImportId] = useState<number | undefined>(
    initialFilters?.importId,
  );
  const [merchantCanonicalKey, setMerchantCanonicalKey] = useState<
    string | undefined
  >(initialFilters?.merchantCanonicalKey);
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
  const [minConfidence, setMinConfidence] = useLocalStorageState(
    `${reviewStoragePrefix}.minConfidence`,
    "",
  );
  const [reviewState, setReviewState] = useLocalStorageState<CategoryState>(
    `${reviewStoragePrefix}.reviewState`,
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
    setSearch(initialFilters.search ?? "");
    setCategory(initialFilters.category ?? "");
    setMerchantCanonicalKey(initialFilters.merchantCanonicalKey);
    setDirection(initialFilters.direction ?? "all");
    setTransactionType(initialFilters.transactionType ?? "");
    setDateFrom(initialFilters.dateFrom ?? "");
    setDateTo(initialFilters.dateTo ?? "");
    setImportId(initialFilters.importId);
    setMinConfidence("");
    setReviewState(initialFilters.reviewState ?? "assignable");
    setIncludeTransfers(initialFilters.includeTransfers ?? true);
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
    reviewMode,
    setCategory,
    setDateFrom,
    setDateTo,
    setDirection,
    setIncludeTransfers,
    setMinConfidence,
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
    min_confidence: reviewMode ? confidenceFilter : undefined,
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
    acceptTypeSuggestion,
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

  const hasActiveFilters =
    search !== "" ||
    direction !== "all" ||
    category !== "" ||
    transactionType !== "" ||
    dateFrom !== "" ||
    dateTo !== "" ||
    (reviewMode && minConfidence !== "") ||
    includeTransfers !== true ||
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
    setIncludeTransfers(true);
    if (reviewMode) {
      setMinConfidence("");
      setReviewState("assignable");
    }
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
          selected={selected}
          acceptPending={acceptSuggestions.isPending}
          rejectPending={rejectSuggestions.isPending}
          restorePending={restoreSuggestions.isPending}
          typeAcceptPending={acceptTypeSuggestion.isPending}
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
          onAcceptTypeSuggestion={(id) => acceptTypeSuggestion.mutate(id)}
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
