"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  api,
  type CategoryState,
  type Direction,
  type Transaction,
} from "@/lib/api";
import { useT } from "@/lib/i18n";
import { useConfirm } from "@/components/confirm-dialog";
import { ErrorState } from "@/components/error-state";
import {
  PAGE_SIZE,
  hasCategorySuggestion,
  hasRejectedCategorySuggestion,
} from "../_lib/constants";
import { BulkActionsBar } from "./bulk-actions-bar";
import { TransactionFilters } from "./transaction-filters";
import { TransactionsTable } from "./transactions-table";

interface ListViewProps {
  reviewMode: boolean;
  initialSearch?: string;
}

export function ListView({ reviewMode, initialSearch = "" }: ListViewProps) {
  const { t } = useT();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [search, setSearch] = useState(initialSearch);
  const [direction, setDirection] = useState<Direction>("all");
  const [category, setCategory] = useState("");
  const [page, setPage] = useState(0);
  const [includeTransfers, setIncludeTransfers] = useState(!reviewMode);
  const [transactionType, setTransactionType] = useState("");
  const [minConfidence, setMinConfidence] = useState("");
  const [reviewState, setReviewState] = useState<CategoryState>("needs_review");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkCat, setBulkCat] = useState<string | null>(null);
  const confidenceFilter = minConfidence ? Number(minConfidence) : undefined;
  const searchFilter = search.trim() || undefined;
  const directionFilter = direction === "all" ? undefined : direction;
  const categoryFilter = category || undefined;

  const query = useQuery({
    queryKey: [
      "transactions",
      {
        page,
        search: searchFilter,
        direction: directionFilter,
        category: categoryFilter,
        includeTransfers,
        reviewMode,
        reviewState,
        transactionType,
        minConfidence,
      },
    ],
    queryFn: () =>
      api.transactions({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        search: searchFilter,
        direction: directionFilter,
        category: categoryFilter,
        include_transfers: includeTransfers,
        category_state: reviewMode ? reviewState : "all",
        min_confidence: confidenceFilter,
        transaction_type: transactionType || undefined,
        review_priority: reviewMode,
      }),
  });

  const filtered = useMemo<Transaction[]>(() => {
    return query.data ?? [];
  }, [query.data]);

  const suggestionIds = useMemo(
    () =>
      filtered
        .filter(
          (tx) =>
            hasCategorySuggestion(tx) && (tx.category_confidence ?? 0) >= 0.75,
        )
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

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ["transactions"] });
    qc.invalidateQueries({ queryKey: ["overview"] });
    qc.invalidateQueries({ queryKey: ["byCategory"] });
    qc.invalidateQueries({ queryKey: ["recent"] });
  };

  const patch = useMutation({
    mutationFn: ({
      id,
      value,
      subcategory,
      rememberRule,
    }: {
      id: number;
      value: string | null;
      subcategory?: string | null;
      rememberRule?: boolean;
    }) =>
      api.patchCategory(id, value, {
        subcategory,
        remember_rule: rememberRule,
      }),
    onSuccess: () => {
      invalidateAll();
      qc.invalidateQueries({ queryKey: ["personalRules"] });
      toast.success(t("toast.saved"));
    },
    onError: () => toast.error(t("toast.error")),
  });

  const deleteOne = useMutation({
    mutationFn: (id: number) => api.deleteTransaction(id),
    onSuccess: () => {
      invalidateAll();
      toast.success(t("toast.deleted"));
    },
    onError: () => toast.error(t("toast.error")),
  });

  const patchType = useMutation({
    mutationFn: ({ id, value }: { id: number; value: string }) =>
      api.patchType(id, value),
    onSuccess: () => {
      invalidateAll();
      toast.success(t("toast.saved"));
    },
    onError: () => toast.error(t("toast.error")),
  });

  const patchAnnotations = useMutation({
    mutationFn: ({
      id,
      notes,
      tags,
    }: {
      id: number;
      notes?: string | null;
      tags?: string[];
    }) => api.patchAnnotations(id, { notes, tags }),
    onSuccess: () => {
      invalidateAll();
      toast.success(t("toast.saved"));
    },
    onError: () => toast.error(t("toast.error")),
  });

  const bulkCategorize = useMutation({
    mutationFn: (vars: { ids: number[]; category: string | null }) =>
      api.bulkCategorize({ ids: vars.ids, category: vars.category }),
    onSuccess: () => {
      invalidateAll();
      setSelected(new Set());
      setBulkCat(null);
      toast.success(t("toast.saved"));
    },
    onError: () => toast.error(t("toast.error")),
  });

  const bulkDelete = useMutation({
    mutationFn: (ids: number[]) => api.bulkDelete(ids),
    onSuccess: () => {
      invalidateAll();
      setSelected(new Set());
      toast.success(t("toast.deleted"));
    },
    onError: () => toast.error(t("toast.error")),
  });

  const markTransfer = useMutation({
    mutationFn: (vars: { ids: number[]; transfer: boolean }) =>
      api.bulkCategorize({
        ids: vars.ids,
        category: null,
        mark_transfer: vars.transfer,
      }),
    onSuccess: () => {
      invalidateAll();
      setSelected(new Set());
      toast.success(t("toast.saved"));
    },
    onError: () => toast.error(t("toast.error")),
  });

  const acceptSuggestions = useMutation({
    mutationFn: ({
      ids,
      minConfidence,
    }: {
      ids: number[];
      minConfidence: number;
    }) => api.acceptSuggestions({ ids, min_confidence: minConfidence }),
    onSuccess: () => {
      invalidateAll();
      setSelected(new Set());
      toast.success(t("toast.saved"));
    },
    onError: () => toast.error(t("toast.error")),
  });

  const rejectSuggestions = useMutation({
    mutationFn: (ids: number[]) => api.rejectSuggestions({ ids }),
    onSuccess: () => {
      invalidateAll();
      setSelected(new Set());
      toast.success(t("toast.saved"));
    },
    onError: () => toast.error(t("toast.error")),
  });

  const restoreSuggestions = useMutation({
    mutationFn: (ids: number[]) => api.restoreSuggestions({ ids }),
    onSuccess: () => {
      invalidateAll();
      setSelected(new Set());
      toast.success(t("toast.saved"));
    },
    onError: () => toast.error(t("toast.error")),
  });

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
        minConfidence={minConfidence}
        reviewState={reviewState}
        includeTransfers={includeTransfers}
        suggestionCount={suggestionIds.length}
        acceptPending={acceptSuggestions.isPending}
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
          acceptSuggestions.mutate({ ids: suggestionIds, minConfidence: 0.75 })
        }
      />

      <BulkActionsBar
        selectedCount={selected.size}
        selectedSuggestionCount={selectedSuggestionIds.length}
        selectedRejectedSuggestionCount={selectedRejectedSuggestionIds.length}
        bulkCategory={bulkCat}
        bulkCategorizePending={bulkCategorize.isPending}
        bulkDeletePending={bulkDelete.isPending}
        rejectPending={rejectSuggestions.isPending}
        restorePending={restoreSuggestions.isPending}
        onBulkCategoryChange={setBulkCat}
        onBulkCategorize={() =>
          bulkCategorize.mutate({
            ids: Array.from(selected),
            category: bulkCat,
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
        onCancel={() => setSelected(new Set())}
      />

      {query.isError ? (
        <ErrorState onRetry={() => query.refetch()} />
      ) : (
        <TransactionsTable
          rows={filtered}
          fetchedCount={query.data?.length ?? 0}
          isLoading={query.isLoading}
          page={page}
          selected={selected}
          acceptPending={acceptSuggestions.isPending}
          rejectPending={rejectSuggestions.isPending}
          restorePending={restoreSuggestions.isPending}
          onToggleAll={toggleAll}
          onToggleOne={toggleOne}
          onPatchCategory={(id, value, subcategory, rememberRule) =>
            patch.mutate({ id, value, subcategory, rememberRule })
          }
          onPatchType={(id, value) => patchType.mutate({ id, value })}
          onAcceptSuggestion={(id) =>
            acceptSuggestions.mutate({ ids: [id], minConfidence: 0 })
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
