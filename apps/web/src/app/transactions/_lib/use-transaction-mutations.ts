"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useConfirm } from "@/components/confirm-dialog";
import { api, isApiError, type Transaction } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { invalidateTransactionData } from "@/lib/query-keys";
import { showErrorToast } from "@/lib/toasts";

interface UseTransactionMutationsOptions {
  clearSelection: () => void;
  clearBulkCategory: () => void;
  clearBulkType: () => void;
}

export function useTransactionMutations({
  clearSelection,
  clearBulkCategory,
  clearBulkType,
}: UseTransactionMutationsOptions) {
  const { t } = useT();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const invalidateAll = () => void invalidateTransactionData(qc);
  const updateCachedTransaction = (updated: Transaction) => {
    qc.setQueriesData<Transaction[]>(
      { queryKey: ["transactions", "list"] },
      (rows) =>
        rows?.map((row) => (row.id === updated.id ? updated : row)),
    );
  };

  const patchCategory = useMutation({
    mutationFn: ({
      id,
      value,
      subcategory,
    }: {
      id: number;
      value: string | null;
      subcategory?: string | null;
    }) =>
      api.patchCategory(id, value, {
        subcategory,
      }),
    onSuccess: (updated) => {
      updateCachedTransaction(updated);
      invalidateAll();
      toast.success(t("toast.saved"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const deleteOne = useMutation({
    mutationFn: (id: number) => api.deleteTransaction(id),
    onSuccess: () => {
      invalidateAll();
      toast.success(t("toast.deleted"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const patchType = useMutation({
    mutationFn: async ({ id, value }: { id: number; value: string }) => {
      try {
        return await api.patchType(id, value);
      } catch (error) {
        if (
          isApiError(error) &&
          error.code === "transaction_type_direction_mismatch" &&
          (await confirm({ title: t("transactions.typeDirectionWarning") }))
        ) {
          return api.patchType(id, value, true);
        }
        throw error;
      }
    },
    onSuccess: (updated) => {
      updateCachedTransaction(updated);
      invalidateAll();
      toast.success(t("toast.saved"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const acceptTypeSuggestion = useMutation({
    mutationFn: (id: number) => api.acceptTypeSuggestion(id),
    onSuccess: (updated) => {
      updateCachedTransaction(updated);
      invalidateAll();
      toast.success(t("toast.saved"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
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
    onSuccess: (updated) => {
      updateCachedTransaction(updated);
      invalidateAll();
      toast.success(t("toast.saved"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const bulkCategorize = useMutation({
    mutationFn: (vars: { ids: number[]; category: string | null }) =>
      api.bulkCategorize({ ids: vars.ids, category: vars.category }),
    onSuccess: () => {
      invalidateAll();
      clearSelection();
      clearBulkCategory();
      toast.success(t("toast.saved"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const bulkSetType = useMutation({
    mutationFn: async (vars: { ids: number[]; transactionType: string }) => {
      const payload = {
        ids: vars.ids,
        transaction_type: vars.transactionType,
      };
      try {
        return await api.bulkCategorize(payload);
      } catch (error) {
        if (
          isApiError(error) &&
          error.code === "transaction_type_direction_mismatch" &&
          (await confirm({ title: t("transactions.typeDirectionWarning") }))
        ) {
          return api.bulkCategorize({
            ...payload,
            allow_direction_mismatch: true,
          });
        }
        throw error;
      }
    },
    onSuccess: () => {
      invalidateAll();
      clearSelection();
      clearBulkType();
      toast.success(t("toast.saved"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const bulkDelete = useMutation({
    mutationFn: (ids: number[]) => api.bulkDelete(ids),
    onSuccess: () => {
      invalidateAll();
      clearSelection();
      toast.success(t("toast.deleted"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
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
      clearSelection();
      toast.success(t("toast.saved"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const acceptSuggestions = useMutation({
    mutationFn: ({
      ids,
      minConfidence,
      manual,
    }: {
      ids: number[];
      minConfidence: number;
      manual?: boolean;
    }) => api.acceptSuggestions({ ids, min_confidence: minConfidence, manual }),
    onSuccess: () => {
      invalidateAll();
      clearSelection();
      toast.success(t("toast.saved"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const rejectSuggestions = useMutation({
    mutationFn: (ids: number[]) => api.rejectSuggestions({ ids }),
    onSuccess: () => {
      invalidateAll();
      clearSelection();
      toast.success(t("toast.saved"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const restoreSuggestions = useMutation({
    mutationFn: (ids: number[]) => api.restoreSuggestions({ ids }),
    onSuccess: () => {
      invalidateAll();
      clearSelection();
      toast.success(t("toast.saved"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const acceptTypeSuggestions = useMutation({
    mutationFn: (ids: number[]) => api.acceptTypeSuggestions({ ids }),
    onSuccess: () => {
      invalidateAll();
      clearSelection();
      toast.success(t("toast.saved"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  return {
    patchCategory,
    deleteOne,
    patchType,
    acceptTypeSuggestion,
    patchAnnotations,
    bulkCategorize,
    bulkSetType,
    bulkDelete,
    markTransfer,
    acceptSuggestions,
    rejectSuggestions,
    restoreSuggestions,
    acceptTypeSuggestions,
  };
}
