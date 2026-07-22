import { request } from "./client";
import type {
  FixedCharge,
  FixedChargeCreateInput,
  FixedChargeListResponse,
  FixedChargeTransaction,
  FixedChargeTransactionsResponse,
  FixedChargeUpdateInput,
} from "./types";
import type { ManualTransactionInput } from "./transactions";

export const fixedChargesApi = {
  fixedCharges: () => request<FixedChargeListResponse>("/fixed-charges"),
  createFixedCharge: (payload: FixedChargeCreateInput) =>
    request<FixedCharge>("/fixed-charges", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateFixedCharge: (id: number, payload: FixedChargeUpdateInput) =>
    request<FixedCharge>(`/fixed-charges/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteFixedCharge: (id: number) =>
    request<void>(`/fixed-charges/${id}`, { method: "DELETE" }),
  fixedChargeTransactions: (id: number) =>
    request<FixedChargeTransactionsResponse>(
      `/fixed-charges/${id}/transactions`,
    ),
  linkFixedChargeTransactions: (
    id: number,
    payload: { transaction_ids: number[]; scheduled_due_date: string },
  ) =>
    request<{ status: "saved" }>(`/fixed-charges/${id}/transactions`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  unlinkFixedChargeTransaction: (id: number, transactionId: number) =>
    request<void>(`/fixed-charges/${id}/transactions/${transactionId}`, {
      method: "DELETE",
    }),
  createFixedChargeManualPayment: (
    id: number,
    payload: ManualTransactionInput & { scheduled_due_date: string },
  ) =>
    request<FixedChargeTransaction>(`/fixed-charges/${id}/transactions/manual`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
