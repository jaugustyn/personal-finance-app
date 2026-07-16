import type { Transaction } from "@/lib/api";
export { TRANSACTION_TYPE_OPTIONS } from "@/lib/transaction-types";

export const PAGE_SIZE = 100;

export type TransactionsView = "list" | "review" | "groups";
export type TransactionsSubject = "category" | "transaction_type";
export type TransactionsMode =
  | "list"
  | "transaction_type_review"
  | "category_review"
  | "groups";

export function isCategoryCandidate(tx: Transaction): boolean {
  const effectiveType = tx.transaction_type_effective ??
    tx.transaction_type ??
    (tx.direction === "credit" ? "income" : "expense");
  return (
    !tx.is_transfer &&
    ((tx.direction === "debit" && effectiveType === "expense") ||
      (tx.direction === "credit" && effectiveType === "refund"))
  );
}

export function hasCategorySuggestion(tx: Transaction): boolean {
  return Boolean(
    !tx.category &&
      tx.category_predicted &&
      !tx.category_suggestion_rejected &&
      isCategoryCandidate(tx),
  );
}

export function hasRejectedCategorySuggestion(tx: Transaction): boolean {
  return Boolean(
    !tx.category &&
      tx.category_predicted &&
      tx.category_suggestion_rejected &&
      isCategoryCandidate(tx),
  );
}
