"use client";

import { useT } from "@/lib/i18n";

export function SkipLink() {
  const { t } = useT();

  return (
    <a
      href="#main-content"
      className="sr-only fixed left-4 top-4 z-[100] rounded-md bg-background px-4 py-2 text-sm font-medium text-foreground shadow-lg ring-2 ring-ring focus:not-sr-only"
    >
      {t("common.skipToContent")}
    </a>
  );
}
