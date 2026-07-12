"use client";

/**
 * Lightweight i18n (PL/EN) with localStorage persistence.
 *
 * Why not next-intl? — Adds router-level prefixes (/pl, /en) and a server
 * components story we don't need for a 4-page admin app. This module keeps
 * everything client-side, type-safe, and ~50 lines.
 *
 * Usage:
 *   const { t, locale, setLocale } = useT();
 *   t("transactions.title")             // "Transakcje" / "Transactions"
 *   t("category.food")                  // "Jedzenie" / "Food"
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { DICT } from "./locales";

export type Locale = "pl" | "en";

export type TranslationKey = keyof (typeof DICT)["pl"];

interface I18nContextValue {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: TranslationKey, vars?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

const LS_KEY = "locale";

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => {
    if (typeof window === "undefined") return "pl";
    try {
      const stored = window.localStorage.getItem(LS_KEY);
      if (stored === "pl" || stored === "en") return stored;
    } catch {
      /* ignore */
    }
    return "pl";
  });

  // Sync <html lang> on locale change.
  useEffect(() => {
    try {
      document.documentElement.lang = locale;
    } catch {
      /* noop */
    }
  }, [locale]);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    try {
      window.localStorage.setItem(LS_KEY, l);
      document.documentElement.lang = l;
    } catch {
      /* noop */
    }
  }, []);

  const t = useCallback(
    (key: TranslationKey, vars?: Record<string, string | number>): string => {
      const raw: string = DICT[locale][key] ?? DICT.pl[key] ?? key;
      if (!vars) return raw;
      return Object.entries(vars).reduce(
        (acc, [k, v]) => acc.replaceAll(`{${k}}`, String(v)),
        raw,
      );
    },
    [locale],
  );

  const value = useMemo(
    () => ({ locale, setLocale, t }),
    [locale, setLocale, t],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useT(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useT must be used within <I18nProvider>");
  return ctx;
}

/** Translate a category enum value, with safe fallback for unknown keys. */
export function tCategory(
  t: I18nContextValue["t"],
  category: string | null | undefined,
): string {
  if (!category) return t("common.unknown");
  const key = `category.${category}` as TranslationKey;
  if (key in DICT.pl) return t(key);
  return category;
}

export function tTransactionType(
  t: I18nContextValue["t"],
  transactionType: string | null | undefined,
): string {
  if (!transactionType) return t("transactions.type.expense");
  const key = `transactions.type.${transactionType}` as TranslationKey;
  if (key in DICT.pl) return t(key);
  return transactionType;
}
