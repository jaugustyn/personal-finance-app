export const TRANSACTION_TYPE_OPTIONS = [
  "purchase",
  "person_transfer",
  "own_transfer",
  "salary",
  "income",
  "refund",
  "cash_withdrawal",
  "debt_payment",
  "bank_fee",
  "savings_investment",
  "other",
] as const;

export type TransactionTypeOption = (typeof TRANSACTION_TYPE_OPTIONS)[number];
