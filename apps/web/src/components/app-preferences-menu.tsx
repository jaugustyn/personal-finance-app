"use client";

import { Languages, Moon, SlidersHorizontal, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { ACCENTS, useAccent, type Accent } from "@/components/accent-provider";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useT, type TranslationKey } from "@/lib/i18n";
import { withThemeTransition } from "@/lib/theme-transition";
import { cn } from "@/lib/utils";

const SWATCH: Record<Accent, string> = {
  emerald: "bg-[hsl(160_84%_36%)]",
  teal: "bg-[hsl(174_80%_36%)]",
  blue: "bg-[hsl(221_83%_53%)]",
  violet: "bg-[hsl(262_83%_58%)]",
};

export function AppPreferencesMenu() {
  const { accent, setAccent } = useAccent();
  const { locale, setLocale, t } = useT();
  const { resolvedTheme, setTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-9 gap-1.5 px-2 text-xs"
        >
          <SlidersHorizontal className="h-4 w-4" />
          {t("header.preferences")}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent side="top" align="center" className="w-56">
        <DropdownMenuLabel>{t("header.preferences")}</DropdownMenuLabel>
        <DropdownMenuItem
          onSelect={(event) => {
            event.preventDefault();
            setLocale(locale === "pl" ? "en" : "pl");
          }}
        >
          <Languages className="h-4 w-4 text-muted-foreground" />
          <span>{t("header.language")}</span>
          <span className="ml-auto text-xs font-semibold uppercase text-muted-foreground">
            {locale}
          </span>
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={(event) => {
            event.preventDefault();
            withThemeTransition(() => setTheme(isDark ? "light" : "dark"));
          }}
        >
          {isDark ? (
            <Moon className="h-4 w-4 text-muted-foreground" />
          ) : (
            <Sun className="h-4 w-4 text-muted-foreground" />
          )}
          <span>{t("header.theme")}</span>
          <span className="ml-auto text-xs text-muted-foreground">
            {t(isDark ? "header.theme.dark" : "header.theme.light")}
          </span>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuLabel>{t("header.accentToggle")}</DropdownMenuLabel>
        {ACCENTS.map((option) => (
          <DropdownMenuCheckboxItem
            key={option}
            checked={accent === option}
            onSelect={(event) => {
              event.preventDefault();
              setAccent(option);
            }}
          >
            <span
              className={cn(
                "mr-2 h-3.5 w-3.5 rounded-full ring-1 ring-black/10",
                SWATCH[option],
              )}
            />
            {t(`header.accent.${option}` as TranslationKey)}
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
