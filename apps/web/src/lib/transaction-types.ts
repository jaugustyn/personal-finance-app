export const TRANSACTION_TYPE_OPTIONS = [
  "expense",
  "salary",
  "income",
  "refund",
  "own_transfer",
  "cash_withdrawal",
  "debt_payment",
  "asset_allocation",
  "other",
] as const;

export type TransactionTypeOption = (typeof TRANSACTION_TYPE_OPTIONS)[number];
