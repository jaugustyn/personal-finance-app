"use client";

import { Languages } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useT } from "@/lib/i18n";

export function LocaleToggle() {
  const { locale, setLocale, t } = useT();
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setLocale(locale === "pl" ? "en" : "pl")}
          aria-label={t("header.localeToggle")}
          className="h-9 gap-1.5 px-2.5"
        >
          <Languages className="h-4 w-4" />
          <span className="text-xs font-semibold uppercase">{locale}</span>
        </Button>
      </TooltipTrigger>
      <TooltipContent>{t("header.localeToggle")}</TooltipContent>
    </Tooltip>
  );
}
