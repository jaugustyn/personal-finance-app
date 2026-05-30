import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(amount: number, currency = "PLN"): string {
  return new Intl.NumberFormat("pl-PL", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(amount);
}

export function formatNumber(value: number, fractionDigits = 0): string {
  return new Intl.NumberFormat("pl-PL", {
    maximumFractionDigits: fractionDigits,
    minimumFractionDigits: fractionDigits,
  }).format(value);
}

export function formatDate(value: string | Date): string {
  const d = typeof value === "string" ? new Date(value) : value;
  return new Intl.DateTimeFormat("pl-PL", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(d);
}

export function formatMonth(yyyymm: string): string {
  // Accepts "2025-03" or "2025-03-01" -> "mar 2025"
  const ym = yyyymm && yyyymm.length > 7 ? yyyymm.slice(0, 7) : yyyymm;
  const [y, m] = (ym ?? "").split("-");
  if (!y || !m) return yyyymm;
  const d = new Date(Number(y), Number(m) - 1, 1);
  return new Intl.DateTimeFormat("pl-PL", { month: "short", year: "numeric" }).format(d);
}

export function formatPercent(ratio: number, fractionDigits = 1): string {
  return new Intl.NumberFormat("pl-PL", {
    style: "percent",
    maximumFractionDigits: fractionDigits,
    minimumFractionDigits: fractionDigits,
  }).format(ratio);
}
