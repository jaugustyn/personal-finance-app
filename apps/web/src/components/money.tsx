import { cn } from "@/lib/utils";
import { formatCurrency } from "@/lib/utils";

export type MoneyDirection = "debit" | "credit";

interface MoneyProps {
  amount: number;
  currency?: string;
  /** When provided, renders a signed, color-coded amount (expense vs income). */
  direction?: MoneyDirection;
  /** Force sign display even without a direction (e.g. deltas). */
  signed?: boolean;
  className?: string;
}

/**
 * Consistent monetary rendering: tabular figures, optional sign and
 * income/expense color semantics. Replaces ad-hoc debit/credit formatting.
 */
export function Money({
  amount,
  currency = "PLN",
  direction,
  signed,
  className,
}: MoneyProps) {
  const abs = Math.abs(amount);
  let sign = "";
  let color = "";

  if (direction) {
    sign = direction === "debit" ? "−" : "+";
    color = direction === "debit" ? "text-negative" : "text-positive";
  } else if (signed) {
    sign = amount < 0 ? "−" : "+";
    color = amount < 0 ? "text-negative" : "text-positive";
  }

  return (
    <span className={cn("tabular-nums", color, className)}>
      {sign}
      {formatCurrency(direction || signed ? abs : amount, currency)}
    </span>
  );
}
