import { request } from "./client";
import { withQuery, type QueryValue } from "./query";
import type {
  CashflowPoint,
  CategoryBreakdown,
  CategoryTrendPoint,
  CumulativeCashflowPoint,
  Direction,
  MerchantStat,
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

function rangeQueryValues(
  months: number,
  options: StatsRangeOptions = {},
): Record<string, QueryValue> {
  return {
    months,
    all_data: options.allData ? true : undefined,
    include_transfers: options.includeTransfers ? true : undefined,
  };
}

function directionalRangeQueryValues(
  months: number,
  options: DirectionalStatsOptions = {},
): Record<string, QueryValue> {
  return {
    ...rangeQueryValues(months, options),
    direction: options.direction,
  };
}

export const statsApi = {
  health: () =>
    request<{ status: string; checks: Record<string, boolean>; auth_enabled: boolean }>("/health"),
  overview: (months = 12, allData = false, includeTransfers = false) =>
    request<OverviewStats>(
      withQuery("/stats/overview", rangeQueryValues(months, { allData, includeTransfers })),
    ),
  cashflow: (months = 12, allData = false, includeTransfers = false) =>
    request<CashflowPoint[]>(
      withQuery("/stats/cashflow", rangeQueryValues(months, { allData, includeTransfers })),
    ),
  byCategory: (
    months = 3,
    limit = 8,
    allData = false,
    direction: StatsDirection = "debit",
    includeTransfers = false,
  ) =>
    request<CategoryBreakdown[]>(
      withQuery("/stats/by-category", {
        ...directionalRangeQueryValues(months, {
          allData,
          direction,
          includeTransfers,
        }),
        limit,
      }),
    ),
  byTransactionType: (
    months = 3,
    limit = 8,
    allData = false,
    direction: StatsDirection = "credit",
    includeTransfers = false,
  ) =>
    request<CategoryBreakdown[]>(
      withQuery("/stats/by-transaction-type", {
        ...directionalRangeQueryValues(months, {
          allData,
          direction,
          includeTransfers,
        }),
        limit,
      }),
    ),
  cumulativeCashflow: (
    months = 12,
    allData = false,
    includeTransfers = false,
  ) =>
    request<CumulativeCashflowPoint[]>(
      withQuery(
        "/stats/cumulative-cashflow",
        rangeQueryValues(months, { allData, includeTransfers }),
      ),
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
      withQuery("/stats/top-merchants", {
        ...directionalRangeQueryValues(months, {
          allData,
          direction,
          includeTransfers,
        }),
        limit,
        sort,
      }),
    ),
  categoryTrend: (
    months = 12,
    limit = 5,
    allData = false,
    direction: StatsDirection = "debit",
    includeTransfers = false,
  ) =>
    request<CategoryTrendPoint[]>(
      withQuery("/stats/category-trend", {
        ...directionalRangeQueryValues(months, {
          allData,
          direction,
          includeTransfers,
        }),
        limit,
      }),
    ),
  recap: (period: "week" | "month" = "month", dateFrom?: string, dateTo?: string) => {
    return request<Recap>(
      withQuery("/stats/recap", {
        period,
        date_from: dateFrom,
        date_to: dateTo,
      }),
    );
  },
};
