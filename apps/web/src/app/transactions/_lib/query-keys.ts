import type { TransactionFilterParams } from "@/lib/api";

export const transactionQueryKeys = {
  all: ["transactions"] as const,
  list: (page: number, filters: TransactionFilterParams) =>
    ["transactions", "list", { page, ...filters }] as const,
  filterSummary: (filters: TransactionFilterParams) =>
    ["transactions", "filter-summary", filters] as const,
  groups: (params: { onlyUncategorized: boolean }) =>
    ["transactions", "groups", params] as const,
};

export const transactionMutationInvalidationKeys = [
  transactionQueryKeys.all,
  ["overview"] as const,
  ["byCategory"] as const,
  ["recent"] as const,
];

export const personalRulesQueryKey = ["personalRules"] as const;
