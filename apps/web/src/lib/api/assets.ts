import { request } from "./client";
import type {
  Asset,
  AssetHistoryPoint,
  AssetInput,
  PortfolioSummary,
  SankeyData,
} from "./types";

export const assetsApi = {
  assets: () => request<Asset[]>("/assets"),
  portfolioSummary: () => request<PortfolioSummary>("/assets/summary"),
  assetHistory: (days = 180) => request<AssetHistoryPoint[]>(`/assets/history?days=${days}`),
  createAsset: (payload: AssetInput) =>
    request<Asset>("/assets", { method: "POST", body: JSON.stringify(payload) }),
  patchAsset: (id: number, payload: Partial<AssetInput>) =>
    request<Asset>(`/assets/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteAsset: (id: number) => request<void>(`/assets/${id}`, { method: "DELETE" }),
  refreshAssets: () =>
    request<{ refreshed: number; skipped: number; total: number }>("/assets/refresh", {
      method: "POST",
    }),
  sankey: (months = 3, topCategories = 8, topMerchants = 4) =>
    request<SankeyData>(
      `/assets/sankey?months=${months}&top_categories=${topCategories}&top_merchants_per_cat=${topMerchants}`,
    ),
};
