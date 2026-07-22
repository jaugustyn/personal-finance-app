"use client";

import * as React from "react";
import {
  storedValueOneOf,
  useLocalStorageState,
} from "@/hooks/use-local-storage-state";

export const ACCENTS = ["emerald", "teal", "blue", "violet"] as const;
export type Accent = (typeof ACCENTS)[number];

const STORAGE_KEY = "finance-accent";
const DEFAULT_ACCENT: Accent = "emerald";
const isAccent = storedValueOneOf(ACCENTS);

interface AccentContextValue {
  accent: Accent;
  setAccent: (accent: Accent) => void;
}

const AccentContext = React.createContext<AccentContextValue | null>(null);

function applyAccent(accent: Accent) {
  document.documentElement.setAttribute("data-accent", accent);
}

export function AccentProvider({ children }: { children: React.ReactNode }) {
  const [accent, setAccentState] = useLocalStorageState<Accent>(
    STORAGE_KEY,
    DEFAULT_ACCENT,
    { validate: isAccent },
  );

  React.useEffect(() => {
    applyAccent(accent);
  }, [accent]);

  const setAccent = React.useCallback((next: Accent) => {
    setAccentState(next);
    applyAccent(next);
  }, [setAccentState]);

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
