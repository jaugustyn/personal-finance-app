import { request } from "./client";
import type {
  CashflowPoint,
  CategoryBreakdown,
  MerchantStat,
  NetWorthPoint,
  OverviewStats,
} from "./types";

export const statsApi = {
  health: () =>
    request<{ status: string; checks: Record<string, boolean>; auth_enabled: boolean }>("/health"),
  overview: (months = 12) => request<OverviewStats>(`/stats/overview?months=${months}`),
  cashflow: (months = 12) => request<CashflowPoint[]>(`/stats/cashflow?months=${months}`),
  byCategory: (months = 3, limit = 8) =>
    request<CategoryBreakdown[]>(`/stats/by-category?months=${months}&limit=${limit}`),
  networth: (months = 24) => request<NetWorthPoint[]>(`/stats/networth?months=${months}`),
  topMerchants: (months = 3, limit = 10) =>
    request<MerchantStat[]>(`/stats/top-merchants?months=${months}&limit=${limit}`),
};
