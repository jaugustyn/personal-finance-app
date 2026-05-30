"use client";

import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";
import { useT } from "@/lib/i18n";

export function AppHeader() {
  const { t } = useT();
  return (
    <header className="flex h-14 items-center justify-between border-b px-6">
      <div className="text-sm text-muted-foreground">{t("app.subtitle")}</div>
      <div className="flex items-center gap-1">
        <LocaleToggle />
        <ThemeToggle />
      </div>
    </header>
  );
}
