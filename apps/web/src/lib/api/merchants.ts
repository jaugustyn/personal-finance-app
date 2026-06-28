import { request } from "./client";
import type {
  MerchantAlias,
  MerchantAliasGroupLabelInput,
  MerchantAliasInput,
  MerchantCandidate,
} from "./types";

export const merchantsApi = {
  merchantAliases: () => request<MerchantAlias[]>("/merchants/aliases"),
  merchantAliasCandidates: () =>
    request<MerchantCandidate[]>("/merchants/candidates"),
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
