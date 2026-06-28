import type { Transaction } from "@/lib/api";
export { TRANSACTION_TYPE_OPTIONS } from "@/lib/transaction-types";

export const PAGE_SIZE = 100;

export type TransactionsView = "list" | "review" | "groups";

export const CATEGORY_CANDIDATE_TYPES = new Set([
  "purchase",
  "bank_fee",
  "savings_investment",
  "other",
]);

export function isCategoryCandidate(tx: Transaction): boolean {
  return (
    tx.direction === "debit" &&
    !tx.is_transfer &&
    CATEGORY_CANDIDATE_TYPES.has(tx.transaction_type || "purchase")
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
