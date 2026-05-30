"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Direction, type Transaction } from "@/lib/api";
import { useT } from "@/lib/i18n";
import {
  PAGE_SIZE,
  hasCategorySuggestion,
} from "../_lib/constants";
import { BulkActionsBar } from "./bulk-actions-bar";
import { TransactionFilters } from "./transaction-filters";
import { TransactionsTable } from "./transactions-table";

interface ListViewProps {
  reviewMode: boolean;
}

export function ListView({ reviewMode }: ListViewProps) {
  const { t } = useT();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [direction, setDirection] = useState<Direction>("all");
  const [category, setCategory] = useState("");
  const [page, setPage] = useState(0);
  const [includeTransfers, setIncludeTransfers] = useState(!reviewMode);
  const [transactionType, setTransactionType] = useState("");
  const [minConfidence, setMinConfidence] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkCat, setBulkCat] = useState<string | null>(null);
  const confidenceFilter = minConfidence ? Number(minConfidence) : undefined;

  const query = useQuery({
    queryKey: [
      "transactions",
      {
        page,
        includeTransfers,
        reviewMode,
        transactionType,
        minConfidence,
      },
    ],
    queryFn: () =>
      api.transactions({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        include_transfers: includeTransfers,
        category_state: reviewMode ? "needs_review" : "all",
        min_confidence: confidenceFilter,
        transaction_type: transactionType || undefined,
        review_priority: reviewMode,
      }),
  });

  const filtered = useMemo<Transaction[]>(() => {
    const rows = query.data ?? [];
    const s = search.trim().toLowerCase();
    const c = category.trim().toLowerCase();
    return rows.filter((tx) => {
      if (direction !== "all" && tx.direction !== direction) return false;
      if (c) {
        const cat = (tx.category ?? tx.category_predicted ?? "").toLowerCase();
        if (!cat.includes(c)) return false;
      }
      if (s) {
        const hay = `${tx.merchant} ${tx.title}`.toLowerCase();
        if (!hay.includes(s)) return false;
      }
      return true;
    });
  }, [query.data, search, direction, category]);

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
      rememberRule,
    }: {
      id: number;
      value: string | null;
      rememberRule?: boolean;
    }) => api.patchCategory(id, value, rememberRule),
    onSuccess: () => {
      invalidateAll();
      qc.invalidateQueries({ queryKey: ["personalRules"] });
    },
  });

  const deleteOne = useMutation({
    mutationFn: (id: number) => api.deleteTransaction(id),
    onSuccess: invalidateAll,
  });

  const bulkCategorize = useMutation({
    mutationFn: (vars: { ids: number[]; category: string | null }) =>
      api.bulkCategorize({ ids: vars.ids, category: vars.category }),
    onSuccess: () => {
      invalidateAll();
      setSelected(new Set());
      setBulkCat(null);
    },
  });

  const bulkDelete = useMutation({
    mutationFn: (ids: number[]) => api.bulkDelete(ids),
    onSuccess: () => {
      invalidateAll();
      setSelected(new Set());
    },
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
    },
  });

  const acceptSuggestions = useMutation({
    mutationFn: (ids: number[]) =>
      api.acceptSuggestions({ ids, min_confidence: 0.75 }),
    onSuccess: () => {
      invalidateAll();
      setSelected(new Set());
    },
  });

  const rejectSuggestions = useMutation({
    mutationFn: (ids: number[]) => api.rejectSuggestions({ ids }),
    onSuccess: () => {
      invalidateAll();
      setSelected(new Set());
    },
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

  const onConfirmDelete = () => {
    const ids = Array.from(selected);
    if (ids.length === 0) return;
    if (window.confirm(t("transactions.deleteConfirm", { n: ids.length }))) {
      bulkDelete.mutate(ids);
    }
  };
  const onDeleteOne = (id: number) => {
    if (window.confirm(t("transactions.deleteConfirm", { n: 1 }))) {
      deleteOne.mutate(id);
    }
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
        includeTransfers={includeTransfers}
        suggestionCount={suggestionIds.length}
        acceptPending={acceptSuggestions.isPending}
        onSearchChange={setSearch}
        onCategoryChange={setCategory}
        onDirectionChange={setDirection}
        onTransactionTypeChange={(value) => {
          setTransactionType(value);
          resetPage();
        }}
        onMinConfidenceChange={(value) => {
          setMinConfidence(value);
          resetPage();
        }}
        onIncludeTransfersChange={(value) => {
          setIncludeTransfers(value);
          resetPage();
        }}
        onAcceptSuggestions={() => acceptSuggestions.mutate(suggestionIds)}
      />

      <BulkActionsBar
        selectedCount={selected.size}
        selectedSuggestionCount={selectedSuggestionIds.length}
        bulkCategory={bulkCat}
        bulkCategorizePending={bulkCategorize.isPending}
        bulkDeletePending={bulkDelete.isPending}
        rejectPending={rejectSuggestions.isPending}
        onBulkCategoryChange={setBulkCat}
        onBulkCategorize={() =>
          bulkCategorize.mutate({
            ids: Array.from(selected),
            category: bulkCat,
          })
        }
        onRejectSuggestions={() => rejectSuggestions.mutate(selectedSuggestionIds)}
        onMarkTransfer={() =>
          markTransfer.mutate({
            ids: Array.from(selected),
            transfer: true,
          })
        }
        onDelete={onConfirmDelete}
        onCancel={() => setSelected(new Set())}
      />

      <TransactionsTable
        rows={filtered}
        fetchedCount={query.data?.length ?? 0}
        isLoading={query.isLoading}
        page={page}
        selected={selected}
        acceptPending={acceptSuggestions.isPending}
        rejectPending={rejectSuggestions.isPending}
        onToggleAll={toggleAll}
        onToggleOne={toggleOne}
        onPatchCategory={(id, value, rememberRule) =>
          patch.mutate({ id, value, rememberRule })
        }
        onAcceptSuggestion={(id) => acceptSuggestions.mutate([id])}
        onRejectSuggestion={(id) => rejectSuggestions.mutate([id])}
        onDeleteOne={onDeleteOne}
        onPreviousPage={() => setPage((p) => Math.max(0, p - 1))}
        onNextPage={() => setPage((p) => p + 1)}
      />
    </>
  );
}
