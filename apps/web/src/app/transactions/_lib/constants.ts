import type { Transaction } from "@/lib/api";
export { TRANSACTION_TYPE_OPTIONS } from "@/lib/transaction-types";

export const PAGE_SIZE = 100;

export type TransactionsView = "list" | "review" | "groups";
export type TransactionsSubject = "category" | "transaction_type";

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

export function classificationDecisionAction(tx: Transaction) {
  return tx.classification_decision?.action;
}

export function isSuggestionReadyToAccept(tx: Transaction): boolean {
  if (!hasCategorySuggestion(tx)) return false;
  const action = classificationDecisionAction(tx);
  if (action) return action === "accept";
  return (tx.category_confidence ?? 0) >= 0.75;
}

export function hasRejectedCategorySuggestion(tx: Transaction): boolean {
  return Boolean(
    !tx.category &&
      tx.category_predicted &&
      tx.category_suggestion_rejected &&
      isCategoryCandidate(tx),
  );
}
