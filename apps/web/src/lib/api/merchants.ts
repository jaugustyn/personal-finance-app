import { request } from "./client";
import type {
  MerchantAlias,
  MerchantAliasGroupLabelInput,
  MerchantAliasInput,
  MerchantAliasSuggestion,
  MerchantCandidate,
} from "./types";

export const merchantsApi = {
  merchantAliases: () => request<MerchantAlias[]>("/merchants/aliases"),
  merchantAliasCandidates: ({
    q = "",
    sortBy = "count",
    sortDir = "desc",
  }: {
    q?: string;
    sortBy?: "suggested_label" | "variants" | "count" | "total_debit";
    sortDir?: "asc" | "desc";
  } = {}) => {
    const query = new URLSearchParams({
      limit: "100",
      sort_by: sortBy,
      sort_dir: sortDir,
    });
    if (q.trim()) query.set("q", q.trim());
    return request<MerchantCandidate[]>(`/merchants/candidates?${query}`);
  },
  merchantAliasSuggestions: (q: string) =>
    request<MerchantAliasSuggestion[]>(
      `/merchants/suggestions?q=${encodeURIComponent(q)}`,
    ),
  createMerchantAliases: (payload: MerchantAliasInput) =>
    request<MerchantAlias[]>("/merchants/aliases", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateMerchantAliasGroupLabel: (payload: MerchantAliasGroupLabelInput) =>
    request<MerchantAlias[]>("/merchants/aliases/group-label", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteMerchantAlias: (id: number) =>
    request<void>(`/merchants/aliases/${id}`, { method: "DELETE" }),
};
