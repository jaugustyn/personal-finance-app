"use client";

import { Palette, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ACCENTS, useAccent, type Accent } from "@/components/accent-provider";
import { useT, type TranslationKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const SWATCH: Record<Accent, string> = {
  emerald: "bg-[hsl(160_84%_36%)]",
  teal: "bg-[hsl(174_80%_36%)]",
  blue: "bg-[hsl(221_83%_53%)]",
  violet: "bg-[hsl(262_83%_58%)]",
};

export function AccentToggle() {
  const { accent, setAccent } = useAccent();
  const { t } = useT();
  return (
    <Tooltip>
      <DropdownMenu>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              aria-label={t("header.accentToggle")}
            >
              <Palette className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <DropdownMenuContent align="end" className="w-44">
          <DropdownMenuLabel>{t("header.accentToggle")}</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {ACCENTS.map((a) => (
            <button
              key={a}
              type="button"
              onClick={() => setAccent(a)}
              className="flex w-full cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span
                className={cn(
                  "h-4 w-4 rounded-full ring-1 ring-black/10",
                  SWATCH[a],
                )}
              />
              <span className="flex-1 text-left">
                {t(`header.accent.${a}` as TranslationKey)}
              </span>
              {accent === a && <Check className="h-4 w-4 text-primary" />}
            </button>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
      <TooltipContent>{t("header.accentToggle")}</TooltipContent>
    </Tooltip>
  );
}
