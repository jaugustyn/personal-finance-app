"use client";

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { toast } from "sonner";

import { api, type MerchantAlias, type MerchantCandidate } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";
import { invalidateMerchantData, queryKeys } from "@/lib/query-keys";
import { useConfirm } from "@/components/confirm-dialog";
import type { MerchantAliasPayload } from "./merchant-aliases";

export function useMerchantAliases({
  onCreateSuccess,
  candidateSearch = "",
  candidateSort = { id: "count", dir: "desc" },
}: {
  onCreateSuccess?: () => void;
  candidateSearch?: string;
  candidateSort?: {
    id: "suggested_label" | "variants" | "count" | "total_debit";
    dir: "asc" | "desc";
  };
} = {}) {
  const { t } = useT();
  const queryClient = useQueryClient();
  const confirm = useConfirm();

  const aliasesQuery = useQuery<MerchantAlias[]>({
    queryKey: queryKeys.merchants.aliases,
    queryFn: () => api.merchantAliases(),
    refetchOnMount: "always",
    refetchOnWindowFocus: "always",
  });
  const candidatesQuery = useQuery<MerchantCandidate[]>({
    queryKey: queryKeys.merchants.candidates({
      query: candidateSearch,
      sortBy: candidateSort.id,
      sortDir: candidateSort.dir,
    }),
    queryFn: () =>
      api.merchantAliasCandidates({
        q: candidateSearch,
        sortBy: candidateSort.id,
        sortDir: candidateSort.dir,
      }),
    placeholderData: keepPreviousData,
    refetchOnMount: "always",
    refetchOnWindowFocus: "always",
  });

  const createAliases = useMutation({
    mutationFn: (payload: MerchantAliasPayload) => api.createMerchantAliases(payload),
    onSuccess: () => {
      void invalidateMerchantData(queryClient);
      toast.success(t("toast.saved"));
      onCreateSuccess?.();
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const updateLabel = useMutation({
    mutationFn: (payload: { canonical_key: string; canonical_label: string }) =>
      api.updateMerchantAliasGroupLabel(payload),
    onSuccess: () => {
      void invalidateMerchantData(queryClient);
      toast.success(t("toast.saved"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const deleteAlias = useMutation({
    mutationFn: (id: number) => api.deleteMerchantAlias(id),
    onSuccess: () => {
      void invalidateMerchantData(queryClient);
      toast.success(t("merchants.aliasDetached"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const handleDeleteAlias = async (alias: MerchantAlias) => {
    const ok = await confirm({
      title: t("merchants.deleteAliasTitle"),
      description: t("merchants.deleteAliasDescription", {
        alias: alias.alias_label,
      }),
      confirmLabel: t("merchants.detachAlias"),
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
