import type { Transaction } from "@/lib/api";

export const PAGE_SIZE = 100;

export type TransactionsView = "list" | "review" | "groups";

export const TRANSACTION_TYPE_OPTIONS = [
  "purchase",
  "person_transfer",
  "own_transfer",
  "salary",
  "refund",
  "cash_withdrawal",
  "bank_fee",
  "savings_investment",
  "other",
];

export function hasCategorySuggestion(tx: Transaction): boolean {
  return Boolean(
    !tx.category && tx.category_predicted && !tx.category_suggestion_rejected,
  );
}
