import type { TransactionFilterParams, TransactionListParams } from "@/lib/api";

export const transactionQueryKeys = {
  all: ["transactions"] as const,
  list: (page: number, params: TransactionListParams) =>
    ["transactions", "list", { page, ...params }] as const,
  filterSummary: (filters: TransactionFilterParams) =>
    ["transactions", "filter-summary", filters] as const,
  groups: (params: {
    onlyUncategorized: boolean;
    sortBy: string;
    sortDirection: string;
  }) =>
    ["transactions", "groups", params] as const,
};

export const transactionMutationInvalidationKeys = [
  transactionQueryKeys.all,
  ["overview"] as const,
  ["byCategory"] as const,
  ["recent"] as const,
];
