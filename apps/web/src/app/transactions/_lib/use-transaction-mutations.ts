"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";
import {
  personalRulesQueryKey,
  transactionMutationInvalidationKeys,
} from "./query-keys";

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

  const invalidateAll = () => {
    transactionMutationInvalidationKeys.forEach((queryKey) => {
      qc.invalidateQueries({ queryKey });
    });
  };

  const patchCategory = useMutation({
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
      qc.invalidateQueries({ queryKey: personalRulesQueryKey });
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
    mutationFn: ({ id, value }: { id: number; value: string }) =>
      api.patchType(id, value),
    onSuccess: () => {
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
    onSuccess: () => {
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
    mutationFn: (vars: { ids: number[]; transactionType: string }) =>
      api.bulkCategorize({
        ids: vars.ids,
        transaction_type: vars.transactionType,
      }),
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

  return {
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
  };
}
