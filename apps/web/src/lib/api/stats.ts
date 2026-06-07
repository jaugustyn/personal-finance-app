import { request } from "./client";
import type {
  CashflowPoint,
  CategoryBreakdown,
  CategoryTrendPoint,
  MerchantStat,
  NetWorthPoint,
  OverviewStats,
  Recap,
} from "./types";

function rangeQuery(months: number, allData = false): string {
  const params = new URLSearchParams({ months: String(months) });
  if (allData) params.set("all_data", "true");
  return params.toString();
}

export const statsApi = {
  health: () =>
    request<{ status: string; checks: Record<string, boolean>; auth_enabled: boolean }>("/health"),
  overview: (months = 12, allData = false) =>
    request<OverviewStats>(`/stats/overview?${rangeQuery(months, allData)}`),
  cashflow: (months = 12, allData = false) =>
    request<CashflowPoint[]>(`/stats/cashflow?${rangeQuery(months, allData)}`),
  byCategory: (months = 3, limit = 8, allData = false) =>
    request<CategoryBreakdown[]>(
      `/stats/by-category?${rangeQuery(months, allData)}&limit=${limit}`,
    ),
  networth: (months = 12, allData = false) =>
    request<NetWorthPoint[]>(`/stats/networth?${rangeQuery(months, allData)}`),
  topMerchants: (
    months = 3,
    limit = 10,
    sort: "amount" | "count" = "amount",
    allData = false,
  ) =>
    request<MerchantStat[]>(
      `/stats/top-merchants?${rangeQuery(months, allData)}&limit=${limit}&sort=${sort}`,
    ),
  categoryTrend: (months = 12, limit = 5, allData = false) =>
    request<CategoryTrendPoint[]>(
      `/stats/category-trend?${rangeQuery(months, allData)}&limit=${limit}`,
    ),
  recap: (period: "week" | "month" = "month", dateFrom?: string, dateTo?: string) => {
    const params = new URLSearchParams({ period });
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    return request<Recap>(`/stats/recap?${params}`);
  },
};
