import type { QueryClient, QueryKey } from "@tanstack/react-query";

import type {
  TransactionFilterParams,
  TransactionListParams,
} from "@/lib/api";

interface DashboardRangeKey {
  months: number;
  allData: boolean;
  includeTransfers: boolean;
}

interface DashboardRankingKey extends DashboardRangeKey {
  limit: number;
}

export const queryKeys = {
  assets: {
    all: ["assets"] as const,
    overview: ["assets", "overview"] as const,
    accounts: (includeArchived = false) =>
      ["assets", "accounts", { includeArchived }] as const,
    history: (range: "3m" | "1y" | "all", accountId?: number | null) =>
      ["assets", "history", { range, accountId: accountId ?? null }] as const,
    valuations: (itemId: number | null) =>
      ["assets", "valuations", { itemId }] as const,
  },
  categories: {
    all: ["categories"] as const,
    list: ["categories", "list"] as const,
  },
  currencies: {
    all: ["currencies"] as const,
    status: ["currencies", "status"] as const,
    rates: ["currencies", "rates"] as const,
  },
  dashboard: {
    all: ["dashboard"] as const,
    overview: (params: DashboardRangeKey) =>
      ["dashboard", "overview", params] as const,
    currencyStatus: ["dashboard", "currency-status"] as const,
    cashflow: (params: DashboardRangeKey) =>
      ["dashboard", "cashflow", params] as const,
    categoryBreakdown: (params: DashboardRankingKey) =>
      ["dashboard", "category-breakdown", params] as const,
    transactionTypeBreakdown: (params: DashboardRankingKey) =>
      ["dashboard", "transaction-type-breakdown", params] as const,
    categoryTrend: (params: DashboardRankingKey) =>
      ["dashboard", "category-trend", params] as const,
    categoryDeltaTrend: (params: DashboardRankingKey) =>
      ["dashboard", "category-delta-trend", params] as const,
    netWorth: (params: DashboardRangeKey) =>
      ["dashboard", "net-worth", params] as const,
    topMerchants: (params: DashboardRankingKey) =>
      ["dashboard", "top-merchants", params] as const,
    incomeSources: (params: DashboardRankingKey) =>
      ["dashboard", "income-sources", params] as const,
    reviewQueue: (limit: number) =>
      ["dashboard", "review-queue", { limit }] as const,
    anomalies: (params: {
      direction: "all";
      reviewState: "pending" | "reviewed";
      limit: number;
    }) => ["dashboard", "anomalies", params] as const,
    subscriptionsOverview: ["dashboard", "subscriptions-overview"] as const,
  },
  fixedCharges: {
    all: ["fixed-charges"] as const,
    list: ["fixed-charges", "list"] as const,
    transactions: (chargeId: number | null) =>
      ["fixed-charges", "transactions", { chargeId }] as const,
  },
  forecast: {
    all: ["forecast"] as const,
    detail: (params: { category: string | null; horizon: number }) =>
      ["forecast", "detail", params] as const,
  },
  imports: {
    all: ["imports"] as const,
    history: ["imports", "history"] as const,
  },
  merchants: {
    all: ["merchants"] as const,
    aliases: ["merchants", "aliases"] as const,
    candidates: (params: { query: string; sortBy: string; sortDir: string }) =>
      ["merchants", "candidates", params] as const,
    suggestions: (query?: string) =>
      ["merchants", "suggestions", ...(query ? [query] : [])] as const,
  },
  ml: {
    all: ["ml"] as const,
    dashboard: ["ml", "dashboard"] as const,
    retrainStatus: ["ml", "retrain-status"] as const,
    modelVersions: ["ml", "model-versions"] as const,
  },
  anomalies: {
    all: ["anomalies"] as const,
    list: (params: {
      direction: "all" | "debit" | "credit";
      reviewState: "pending" | "reviewed";
      contamination?: number;
      limit?: number;
    }) => ["anomalies", "list", params] as const,
  },
  profile: {
    all: ["profile"] as const,
    rules: ["profile", "rules"] as const,
  },
  recap: {
    all: ["recap"] as const,
    detail: (params: {
      period: "week" | "month" | "custom";
      dateFrom: string | null;
      dateTo: string | null;
    }) => ["recap", "detail", params] as const,
  },
  subscriptions: {
    all: ["subscriptions"] as const,
    list: (minConfidence: number, includeRejected: boolean) =>
      ["subscriptions", "list", { minConfidence, includeRejected }] as const,
    overview: ["subscriptions", "overview"] as const,
  },
  transactions: {
    all: ["transactions"] as const,
    reviewSummary: ["transactions", "review-summary"] as const,
    list: (params: TransactionListParams) =>
      ["transactions", "list", params] as const,
    filterSummary: (filters: TransactionFilterParams) =>
      ["transactions", "filter-summary", filters] as const,
    groups: (params: {
      onlyUncategorized: boolean;
      minCount: number;
      page: number;
      pageSize: number;
      sortBy: string;
      sortDirection: string;
    }) => ["transactions", "groups", params] as const,
  },
} as const;

function invalidateRoots(queryClient: QueryClient, roots: readonly QueryKey[]) {
  return Promise.all(
    roots.map((queryKey) => queryClient.invalidateQueries({ queryKey })),
  ).then(() => undefined);
}

const transactionDerivedRoots: readonly QueryKey[] = [
  queryKeys.transactions.all,
  queryKeys.dashboard.all,
  queryKeys.recap.all,
  queryKeys.anomalies.all,
  queryKeys.subscriptions.all,
  queryKeys.fixedCharges.all,
  queryKeys.ml.all,
  queryKeys.currencies.all,
  queryKeys.merchants.all,
];

export function invalidateTransactionData(queryClient: QueryClient) {
  return invalidateRoots(queryClient, transactionDerivedRoots);
}

export function invalidateImportData(queryClient: QueryClient) {
  return invalidateRoots(queryClient, [
    queryKeys.imports.all,
    ...transactionDerivedRoots,
  ]);
}

export function invalidateCurrencyData(queryClient: QueryClient) {
  return invalidateRoots(queryClient, [
    ...transactionDerivedRoots,
    queryKeys.assets.all,
  ]);
}

export function invalidateAssetData(queryClient: QueryClient) {
  return invalidateRoots(queryClient, [queryKeys.assets.all]);
}

export function invalidateMerchantData(queryClient: QueryClient) {
  return invalidateRoots(queryClient, [
    queryKeys.merchants.all,
    queryKeys.transactions.all,
    queryKeys.dashboard.all,
    queryKeys.recap.all,
    queryKeys.anomalies.all,
    queryKeys.subscriptions.all,
    queryKeys.fixedCharges.all,
    queryKeys.ml.all,
  ]);
}

export function invalidateAnomalyData(queryClient: QueryClient) {
  return invalidateRoots(queryClient, [
    queryKeys.anomalies.all,
    queryKeys.dashboard.all,
    queryKeys.ml.all,
  ]);
}

export function invalidateSubscriptionData(queryClient: QueryClient) {
  return invalidateRoots(queryClient, [
    queryKeys.subscriptions.all,
    queryKeys.fixedCharges.all,
    queryKeys.dashboard.all,
  ]);
}
