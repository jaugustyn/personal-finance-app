import type { Transaction } from "@/lib/api";

export type TransactionSortId =
  | "date"
  | "merchant"
  | "type"
  | "category"
  | "amount";

export type TransactionSort = {
  id: TransactionSortId;
  dir: "asc" | "desc";
} | null;

export function sortTransactions(
  rows: Transaction[],
  sort: TransactionSort,
): Transaction[] {
  if (!sort) return rows;

  const factor = sort.dir === "asc" ? 1 : -1;
  return rows
    .map((row, index) => ({ row, index }))
    .sort((a, b) => {
      const av = transactionSortValue(a.row, sort.id);
      const bv = transactionSortValue(b.row, sort.id);
      let result: number;
      if (typeof av === "number" && typeof bv === "number") {
        result = av - bv;
      } else {
        result = String(av).localeCompare(String(bv), "pl", {
          sensitivity: "base",
        });
      }
      return result === 0 ? a.index - b.index : result * factor;
    })
    .map(({ row }) => row);
}

function transactionSortValue(tx: Transaction, id: TransactionSortId) {
  switch (id) {
    case "date":
      return tx.booking_date;
    case "merchant":
      return tx.merchant_display || tx.merchant || tx.title;
    case "type":
      return tx.transaction_type;
    case "category":
      return tx.category ?? tx.category_predicted ?? "";
    case "amount":
      return Number(tx.amount);
  }
}
