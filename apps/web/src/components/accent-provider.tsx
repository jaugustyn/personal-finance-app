"use client";

import * as React from "react";
import {
  storedValueOneOf,
  useLocalStorageState,
} from "@/hooks/use-local-storage-state";
import {
  LOGO_MARK_LAYERS,
  LOGO_MARK_VIEW_BOX,
} from "@/components/logo-mark";

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
  syncFavicon();
}

function syncFavicon() {
  const primary = getComputedStyle(document.documentElement)
    .getPropertyValue("--primary")
    .trim();
  if (!primary) return;

  const color = `hsl(${primary.split(/\s+/).join(", ")})`;
  const paths = LOGO_MARK_LAYERS.map(
    ({ d, opacity }) =>
      `<path d="${d}" fill="${color}" opacity="${opacity}"/>`,
  ).join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${LOGO_MARK_VIEW_BOX}" fill="none">${paths}</svg>`;
  const href = `data:image/svg+xml,${encodeURIComponent(svg)}`;
  const links = document.querySelectorAll<HTMLLinkElement>('link[rel~="icon"]');

  if (links.length) {
    links.forEach((link) => {
      link.type = "image/svg+xml";
      link.href = href;
    });
    return;
  }

  const link = document.createElement("link");
  link.rel = "icon";
  link.type = "image/svg+xml";
  link.href = href;
  document.head.append(link);
}

export function AccentProvider({ children }: { children: React.ReactNode }) {
  const [accent, setAccentState] = useLocalStorageState<Accent>(
    STORAGE_KEY,
    DEFAULT_ACCENT,
    { validate: isAccent },
  );

  React.useEffect(() => {
    applyAccent(accent);

    const themeObserver = new MutationObserver(syncFavicon);
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    return () => themeObserver.disconnect();
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
