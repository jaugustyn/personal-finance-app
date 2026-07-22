import type { Locale } from "@/lib/i18n/provider";

export const LOCALE_TAGS: Record<Locale, string> = {
  pl: "pl-PL",
  en: "en-US",
};

export interface Formatters {
  localeTag: string;
  formatCurrency: (amount: number, currency?: string) => string;
  formatNumber: (value: number, fractionDigits?: number) => string;
  formatPercent: (ratio: number, fractionDigits?: number) => string;
  formatDate: (value: string | Date) => string;
  formatDateTime: (value: string | Date) => string;
  formatMonth: (value: string) => string;
  compare: (left: string, right: string) => number;
}

export function createFormatters(locale: Locale): Formatters {
  const localeTag = LOCALE_TAGS[locale];
  const collator = new Intl.Collator(localeTag, { sensitivity: "base" });

  return {
    localeTag,
    formatCurrency: (amount, currency = "PLN") =>
      new Intl.NumberFormat(localeTag, {
        style: "currency",
        currency,
        maximumFractionDigits: 2,
      }).format(amount),
    formatNumber: (value, fractionDigits = 0) =>
      new Intl.NumberFormat(localeTag, {
        maximumFractionDigits: fractionDigits,
        minimumFractionDigits: fractionDigits,
      }).format(value),
    formatPercent: (ratio, fractionDigits = 1) =>
      new Intl.NumberFormat(localeTag, {
        style: "percent",
        maximumFractionDigits: fractionDigits,
        minimumFractionDigits: fractionDigits,
      }).format(ratio),
    formatDate: (value) =>
      new Intl.DateTimeFormat(localeTag, {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).format(toDate(value)),
    formatDateTime: (value) =>
      new Intl.DateTimeFormat(localeTag, {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }).format(toDate(value)),
    formatMonth: (value) => {
      const match = /^(\d{4})-(\d{2})/.exec(value);
      if (!match) return value;
      const date = new Date(Number(match[1]), Number(match[2]) - 1, 1);
      return new Intl.DateTimeFormat(localeTag, {
        month: "short",
        year: "numeric",
      }).format(date);
    },
    compare: (left, right) => collator.compare(left, right),
  };
}

function toDate(value: string | Date): Date {
  if (value instanceof Date) return value;

  const calendarDate = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (calendarDate) {
    return new Date(
      Number(calendarDate[1]),
      Number(calendarDate[2]) - 1,
      Number(calendarDate[3]),
    );
  }

  return new Date(value);
}
