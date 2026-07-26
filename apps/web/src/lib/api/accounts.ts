import { request } from "./client";
import { withQuery } from "./query";
import type {
  TransactionAccount,
  TransactionAccountInput,
} from "./types";

export const accountsApi = {
  accounts: (includeArchived = false) =>
    request<TransactionAccount[]>(
      withQuery("/accounts", { include_archived: includeArchived || undefined }),
    ),
  createAccount: (payload: TransactionAccountInput) =>
    request<TransactionAccount>("/accounts", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateAccount: (id: number, payload: Partial<TransactionAccountInput>) =>
    request<TransactionAccount>(`/accounts/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  archiveAccount: (id: number) =>
    request<TransactionAccount>(`/accounts/${id}/archive`, { method: "POST" }),
  restoreAccount: (id: number) =>
    request<TransactionAccount>(`/accounts/${id}/restore`, { method: "POST" }),
};
