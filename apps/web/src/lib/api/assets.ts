import { request } from "./client";
import type {
  AssetAccount,
  AssetAccountInput,
  AssetHistory,
  AssetHistoryRange,
  AssetItem,
  AssetItemInput,
  AssetOverview,
  AssetValuation,
  AssetValuationInput,
} from "./types";

export const assetsApi = {
  deleteAssetAccount: (id: number) =>
    request<void>(`/assets/accounts/${id}`, { method: "DELETE" }),
  deleteAssetItem: (id: number) =>
    request<void>(`/assets/items/${id}`, { method: "DELETE" }),
  assetOverview: () => request<AssetOverview>("/assets/overview"),
  assetAccounts: (includeArchived = false) =>
    request<AssetAccount[]>(
      `/assets/accounts?include_archived=${String(includeArchived)}`,
    ),
  assetHistory: (range: AssetHistoryRange, accountId?: number | null) => {
    const params = new URLSearchParams({ range });
    if (accountId) params.set("account_id", String(accountId));
    return request<AssetHistory>(`/assets/history?${params.toString()}`);
  },
  createAssetAccount: (payload: AssetAccountInput) =>
    request<AssetAccount>("/assets/accounts", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateAssetAccount: (id: number, payload: Partial<AssetAccountInput>) =>
    request<AssetAccount>(`/assets/accounts/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  archiveAssetAccount: (id: number) =>
    request<{ status: "saved" }>(`/assets/accounts/${id}/archive`, {
      method: "POST",
    }),
  restoreAssetAccount: (id: number) =>
    request<{ status: "saved" }>(`/assets/accounts/${id}/restore`, {
      method: "POST",
    }),
  createAssetItem: (accountId: number, payload: AssetItemInput) =>
    request<AssetItem>(`/assets/accounts/${accountId}/items`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateAssetItem: (id: number, payload: Partial<AssetItemInput>) =>
    request<AssetItem>(`/assets/items/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  archiveAssetItem: (id: number) =>
    request<{ status: "saved" }>(`/assets/items/${id}/archive`, {
      method: "POST",
    }),
  restoreAssetItem: (id: number) =>
    request<{ status: "saved" }>(`/assets/items/${id}/restore`, {
      method: "POST",
    }),
  assetValuations: (itemId: number) =>
    request<AssetValuation[]>(`/assets/items/${itemId}/valuations`),
  createAssetValuation: (itemId: number, payload: AssetValuationInput) =>
    request<AssetValuation>(`/assets/items/${itemId}/valuations`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateAssetValuation: (id: number, payload: Partial<AssetValuationInput>) =>
    request<AssetValuation>(`/assets/valuations/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteAssetValuation: (id: number) =>
    request<void>(`/assets/valuations/${id}`, { method: "DELETE" }),
  recomputeAssetFx: () =>
    request<{ updated: number; missing: number }>(
      "/assets/valuations/recompute-fx",
      { method: "POST" },
    ),
};
