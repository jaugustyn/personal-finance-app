import { request } from "./client";
import type {
  CashflowPoint,
  CategoryBreakdown,
  CategoryTrendPoint,
  Direction,
  MerchantStat,
  NetWorthPoint,
  OverviewStats,
  Recap,
} from "./types";

type StatsDirection = Exclude<Direction, "all">;

interface StatsRangeOptions {
  allData?: boolean;
  includeTransfers?: boolean;
}

interface DirectionalStatsOptions extends StatsRangeOptions {
  direction?: StatsDirection;
}

function rangeQuery(months: number, options: StatsRangeOptions = {}): string {
  const params = new URLSearchParams({ months: String(months) });
  if (options.allData) params.set("all_data", "true");
  if (options.includeTransfers) params.set("include_transfers", "true");
  return params.toString();
}

function directionalRangeQuery(
  months: number,
  options: DirectionalStatsOptions = {},
): string {
  const params = new URLSearchParams(rangeQuery(months, options));
  if (options.direction) params.set("direction", options.direction);
  return params.toString();
}

export const statsApi = {
  health: () =>
    request<{ status: string; checks: Record<string, boolean>; auth_enabled: boolean }>("/health"),
  overview: (months = 12, allData = false, includeTransfers = false) =>
    request<OverviewStats>(
      `/stats/overview?${rangeQuery(months, { allData, includeTransfers })}`,
    ),
  cashflow: (months = 12, allData = false, includeTransfers = false) =>
    request<CashflowPoint[]>(
      `/stats/cashflow?${rangeQuery(months, { allData, includeTransfers })}`,
    ),
  byCategory: (
    months = 3,
    limit = 8,
    allData = false,
    direction: StatsDirection = "debit",
    includeTransfers = false,
  ) =>
    request<CategoryBreakdown[]>(
      `/stats/by-category?${directionalRangeQuery(months, {
        allData,
        direction,
        includeTransfers,
      })}&limit=${limit}`,
    ),
  networth: (months = 12, allData = false, includeTransfers = false) =>
    request<NetWorthPoint[]>(
      `/stats/networth?${rangeQuery(months, { allData, includeTransfers })}`,
    ),
  topMerchants: (
    months = 3,
    limit = 10,
    sort: "amount" | "count" = "amount",
    allData = false,
    direction: StatsDirection = "debit",
    includeTransfers = false,
  ) =>
    request<MerchantStat[]>(
      `/stats/top-merchants?${directionalRangeQuery(months, {
        allData,
        direction,
        includeTransfers,
      })}&limit=${limit}&sort=${sort}`,
    ),
  categoryTrend: (
    months = 12,
    limit = 5,
    allData = false,
    direction: StatsDirection = "debit",
    includeTransfers = false,
  ) =>
    request<CategoryTrendPoint[]>(
      `/stats/category-trend?${directionalRangeQuery(months, {
        allData,
        direction,
        includeTransfers,
      })}&limit=${limit}`,
    ),
  recap: (period: "week" | "month" = "month", dateFrom?: string, dateTo?: string) => {
    const params = new URLSearchParams({ period });
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    return request<Recap>(`/stats/recap?${params}`);
  },
};
