import { request } from "./client";
import { buildQuery, withQuery, type QueryValue } from "./query";
import type { CategoryState, FilterSummary, MerchantGroup, ReviewSummary, Transaction } from "./types";

type TransactionFilterParams = {
  date_from?: string;
  date_to?: string;
  include_transfers?: boolean;
  import_id?: number;
  merchant?: string;
  search?: string;
  direction?: "debit" | "credit";
  category?: string;
  category_state?: CategoryState;
  has_suggestion?: boolean;
  min_confidence?: number;
  max_confidence?: number;
  transaction_type?: string;
  review_priority?: boolean;
};

type TransactionListParams = TransactionFilterParams & {
  limit?: number;
  offset?: number;
};

function transactionFilterQueryValues(
  params: TransactionFilterParams,
): Record<string, QueryValue> {
  return {
    date_from: params.date_from,
    date_to: params.date_to,
    include_transfers: params.include_transfers === false ? false : undefined,
    import_id: params.import_id,
    merchant: params.merchant,
    search: params.search,
    direction: params.direction,
    category: params.category,
    category_state:
      params.category_state && params.category_state !== "all"
        ? params.category_state
        : undefined,
    has_suggestion: params.has_suggestion,
    min_confidence: params.min_confidence,
    max_confidence: params.max_confidence,
    transaction_type: params.transaction_type,
    review_priority: params.review_priority ? true : undefined,
  };
}

export function transactionFiltersQuery(params: TransactionFilterParams = {}): string {
  return buildQuery(transactionFilterQueryValues(params));
}

export const transactionsApi = {
  transactions: (params: TransactionListParams = {}) =>
    request<Transaction[]>(
      withQuery("/transactions", {
        limit: params.limit || undefined,
        offset: params.offset || undefined,
        ...transactionFilterQueryValues(params),
      }),
    ),
  filterSummary: (params: TransactionFilterParams = {}) =>
    request<FilterSummary>(
      withQuery("/transactions/filter-summary", transactionFilterQueryValues(params)),
    ),
  exportTransactionsUrl: (params: TransactionFilterParams = {}) => {
    const query = transactionFiltersQuery(params);
    return `/api/proxy/transactions/export.csv${query ? `?${query}` : ""}`;
  },
  patchCategory: (
    id: number,
    category: string | null,
    options: { subcategory?: string | null; remember_rule?: boolean } = {},
  ) =>
    request<Transaction>(`/transactions/${id}/category`, {
      method: "PATCH",
      body: JSON.stringify({
        category,
        subcategory: options.subcategory ?? null,
        remember_rule: options.remember_rule ?? false,
      }),
    }),
  patchType: (id: number, transaction_type: string) =>
    request<Transaction>(`/transactions/${id}/type`, {
      method: "PATCH",
      body: JSON.stringify({ transaction_type }),
    }),
  deleteTransaction: (id: number) =>
    request<void>(`/transactions/${id}`, { method: "DELETE" }),
  patchAnnotations: (
    id: number,
    payload: { notes?: string | null; tags?: string[] },
  ) =>
    request<Transaction>(`/transactions/${id}/annotations`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  bulkCategorize: (payload: {
    ids?: number[];
    merchant?: string;
    category?: string | null;
    mark_transfer?: boolean;
    transaction_type?: string | null;
  }) =>
    request<{ affected: number }>("/transactions/bulk/categorize", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  acceptSuggestions: (payload: { ids?: number[]; min_confidence?: number; manual?: boolean }) =>
    request<{ affected: number }>("/transactions/bulk/accept-suggestions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  rejectSuggestions: (payload: { ids?: number[] }) =>
    request<{ affected: number }>("/transactions/bulk/reject-suggestions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  restoreSuggestions: (payload: { ids?: number[] }) =>
    request<{ affected: number }>("/transactions/bulk/restore-suggestions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  bulkDelete: (ids: number[]) =>
    request<{ affected: number }>("/transactions/bulk/delete", {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),
  merchantGroups: (
    params: { only_uncategorized?: boolean; min_count?: number; limit?: number } = {},
  ) => {
    return request<MerchantGroup[]>(
      withQuery("/transactions/groups", {
        only_uncategorized: params.only_uncategorized,
        min_count: params.min_count,
        limit: params.limit,
      }),
    );
  },
  reviewSummary: () => request<ReviewSummary>("/transactions/review-summary"),
};
