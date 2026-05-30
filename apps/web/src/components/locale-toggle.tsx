"use client";

import { Languages } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";

export function LocaleToggle() {
  const { locale, setLocale, t } = useT();
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => setLocale(locale === "pl" ? "en" : "pl")}
      aria-label={t("header.localeToggle")}
      className="gap-1.5"
    >
      <Languages className="h-4 w-4" />
      <span className="text-xs font-semibold uppercase">{locale}</span>
    </Button>
  );
}
