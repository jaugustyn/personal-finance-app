"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, type MerchantAlias, type MerchantCandidate } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";
import { useConfirm } from "@/components/confirm-dialog";
import {
  invalidateMerchantQueries,
  MERCHANT_QUERY_KEYS,
} from "./query-keys";
import type { MerchantAliasPayload } from "./merchant-aliases";

export function useMerchantAliases({
  onCreateSuccess,
}: {
  onCreateSuccess?: () => void;
} = {}) {
  const { t } = useT();
  const queryClient = useQueryClient();
  const confirm = useConfirm();

  const aliasesQuery = useQuery<MerchantAlias[]>({
    queryKey: MERCHANT_QUERY_KEYS.aliases,
    queryFn: () => api.merchantAliases(),
  });
  const candidatesQuery = useQuery<MerchantCandidate[]>({
    queryKey: MERCHANT_QUERY_KEYS.candidates,
    queryFn: () => api.merchantAliasCandidates(),
  });

  const createAliases = useMutation({
    mutationFn: (payload: MerchantAliasPayload) => api.createMerchantAliases(payload),
    onSuccess: () => {
      invalidateMerchantQueries(queryClient);
      toast.success(t("toast.saved"));
      onCreateSuccess?.();
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const updateLabel = useMutation({
    mutationFn: (payload: { canonical_key: string; canonical_label: string }) =>
      api.updateMerchantAliasGroupLabel(payload),
    onSuccess: () => {
      invalidateMerchantQueries(queryClient);
      toast.success(t("toast.saved"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const deleteAlias = useMutation({
    mutationFn: (id: number) => api.deleteMerchantAlias(id),
    onSuccess: () => {
      invalidateMerchantQueries(queryClient);
      toast.success(t("toast.deleted"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const handleDeleteAlias = async (alias: MerchantAlias) => {
    const ok = await confirm({
      title: t("merchants.deleteAliasTitle"),
      description: t("merchants.deleteAliasDescription", {
        alias: alias.alias_label,
      }),
      confirmLabel: t("common.delete"),
      destructive: true,
    });
    if (ok) deleteAlias.mutate(alias.id);
  };

  return {
    aliasesQuery,
    candidatesQuery,
    createAliases,
    updateLabel,
    deleteAlias,
    handleDeleteAlias,
  };
}
