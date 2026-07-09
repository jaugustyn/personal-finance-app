"use client";

import * as React from "react";
import { withThemeTransition } from "@/lib/theme-transition";

export const ACCENTS = ["emerald", "teal", "blue", "violet"] as const;
export type Accent = (typeof ACCENTS)[number];

const STORAGE_KEY = "finance-accent";
const DEFAULT_ACCENT: Accent = "emerald";

interface AccentContextValue {
  accent: Accent;
  setAccent: (accent: Accent) => void;
}

const AccentContext = React.createContext<AccentContextValue | null>(null);

function applyAccent(accent: Accent) {
  document.documentElement.setAttribute("data-accent", accent);
}

export function AccentProvider({ children }: { children: React.ReactNode }) {
  const [accent, setAccentState] = React.useState<Accent>(() => {
    if (typeof window === "undefined") return DEFAULT_ACCENT;
    const stored = window.localStorage.getItem(STORAGE_KEY) as Accent | null;
    return stored && ACCENTS.includes(stored) ? stored : DEFAULT_ACCENT;
  });

  React.useEffect(() => {
    applyAccent(accent);
  }, [accent]);

  const setAccent = React.useCallback((next: Accent) => {
    withThemeTransition(() => {
      setAccentState(next);
      applyAccent(next);
      window.localStorage.setItem(STORAGE_KEY, next);
    });
  }, []);

  const value = React.useMemo(
    () => ({ accent, setAccent }),
    [accent, setAccent],
  );

  return (
    <AccentContext.Provider value={value}>{children}</AccentContext.Provider>
  );
}

export function useAccent() {
  const ctx = React.useContext(AccentContext);
  if (!ctx) throw new Error("useAccent must be used within AccentProvider");
  return ctx;
}
