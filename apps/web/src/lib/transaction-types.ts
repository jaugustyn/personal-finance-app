import {
  ArrowDownCircle,
  ArrowLeftRight,
  Banknote,
  CircleDollarSign,
  CreditCard,
  HelpCircle,
  Receipt,
  RotateCcw,
  WalletCards,
  type LucideIcon,
} from "lucide-react";

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

export const TRANSACTION_TYPE_ICONS: Record<
  TransactionTypeOption,
  LucideIcon
> = {
  expense: CreditCard,
  salary: Banknote,
  income: CircleDollarSign,
  refund: RotateCcw,
  own_transfer: ArrowLeftRight,
  cash_withdrawal: ArrowDownCircle,
  debt_payment: Receipt,
  asset_allocation: WalletCards,
  other: HelpCircle,
};
