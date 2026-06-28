import { request } from "./client";
import type { CategoryState, FilterSummary, MerchantGroup, ReviewSummary, Transaction } from "./types";

export const transactionsApi = {
  transactions: (
    params: {
      limit?: number;
      offset?: number;
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
    } = {},
  ) => {
    const q = new URLSearchParams();
    if (params.limit) q.set("limit", String(params.limit));
    if (params.offset) q.set("offset", String(params.offset));
    if (params.date_from) q.set("date_from", params.date_from);
    if (params.date_to) q.set("date_to", params.date_to);
    if (params.include_transfers === false) q.set("include_transfers", "false");
    if (params.import_id !== undefined) q.set("import_id", String(params.import_id));
    if (params.merchant) q.set("merchant", params.merchant);
    if (params.search) q.set("search", params.search);
    if (params.direction) q.set("direction", params.direction);
    if (params.category) q.set("category", params.category);
    if (params.category_state && params.category_state !== "all") {
      q.set("category_state", params.category_state);
    }
    if (params.has_suggestion !== undefined) {
      q.set("has_suggestion", String(params.has_suggestion));
    }
    if (params.min_confidence !== undefined) {
      q.set("min_confidence", String(params.min_confidence));
    }
    if (params.max_confidence !== undefined) {
      q.set("max_confidence", String(params.max_confidence));
    }
    if (params.transaction_type) q.set("transaction_type", params.transaction_type);
    if (params.review_priority) q.set("review_priority", "true");
    const qs = q.toString();
    return request<Transaction[]>(`/transactions${qs ? `?${qs}` : ""}`);
  },
  filterSummary: (
    params: {
      date_from?: string;
      date_to?: string;
      include_transfers?: boolean;
      import_id?: number;
      search?: string;
      direction?: "debit" | "credit";
      category?: string;
      category_state?: CategoryState;
      min_confidence?: number;
      transaction_type?: string;
      review_priority?: boolean;
    } = {},
  ) => {
    const q = new URLSearchParams();
    if (params.date_from) q.set("date_from", params.date_from);
    if (params.date_to) q.set("date_to", params.date_to);
    if (params.include_transfers === false) q.set("include_transfers", "false");
    if (params.import_id !== undefined) q.set("import_id", String(params.import_id));
    if (params.search) q.set("search", params.search);
    if (params.direction) q.set("direction", params.direction);
    if (params.category) q.set("category", params.category);
    if (params.category_state && params.category_state !== "all") {
      q.set("category_state", params.category_state);
    }
    if (params.min_confidence !== undefined) {
      q.set("min_confidence", String(params.min_confidence));
    }
    if (params.transaction_type) q.set("transaction_type", params.transaction_type);
    if (params.review_priority) q.set("review_priority", "true");
    const qs = q.toString();
    return request<FilterSummary>(`/transactions/filter-summary${qs ? `?${qs}` : ""}`);
  },
  exportTransactionsUrl: (
    params: {
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
    } = {},
  ) => {
    const q = new URLSearchParams();
    if (params.date_from) q.set("date_from", params.date_from);
    if (params.date_to) q.set("date_to", params.date_to);
    if (params.include_transfers === false) q.set("include_transfers", "false");
    if (params.import_id !== undefined) q.set("import_id", String(params.import_id));
    if (params.merchant) q.set("merchant", params.merchant);
    if (params.search) q.set("search", params.search);
    if (params.direction) q.set("direction", params.direction);
    if (params.category) q.set("category", params.category);
    if (params.category_state && params.category_state !== "all") {
      q.set("category_state", params.category_state);
    }
    if (params.has_suggestion !== undefined) {
      q.set("has_suggestion", String(params.has_suggestion));
    }
    if (params.min_confidence !== undefined) {
      q.set("min_confidence", String(params.min_confidence));
    }
    if (params.max_confidence !== undefined) {
      q.set("max_confidence", String(params.max_confidence));
    }
    if (params.transaction_type) q.set("transaction_type", params.transaction_type);
    if (params.review_priority) q.set("review_priority", "true");
    const qs = q.toString();
    return `/api/proxy/transactions/export.csv${qs ? `?${qs}` : ""}`;
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
  acceptSuggestions: (payload: { ids?: number[]; min_confidence?: number }) =>
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
    const q = new URLSearchParams();
    if (params.only_uncategorized !== undefined) {
      q.set("only_uncategorized", String(params.only_uncategorized));
    }
    if (params.min_count !== undefined) q.set("min_count", String(params.min_count));
    if (params.limit !== undefined) q.set("limit", String(params.limit));
    const qs = q.toString();
    return request<MerchantGroup[]>(`/transactions/groups${qs ? `?${qs}` : ""}`);
  },
  reviewSummary: () => request<ReviewSummary>("/transactions/review-summary"),
};
