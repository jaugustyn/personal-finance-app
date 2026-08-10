"use client";

import { Check, Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useT, type TranslationKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const THEME_OPTIONS = [
  { value: "light", label: "header.theme.light", icon: Sun },
  { value: "system", label: "header.theme.system", icon: Monitor },
  { value: "dark", label: "header.theme.dark", icon: Moon },
] as const;

export function ThemeToggle() {
  const { resolvedTheme, theme, setTheme } = useTheme();
  const { t } = useT();
  const isDark = resolvedTheme === "dark";
  const selectedTheme = theme ?? "system";
  const TriggerIcon = selectedTheme === "system" ? Monitor : isDark ? Moon : Sun;

  return (
    <Tooltip>
      <DropdownMenu>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              aria-label={t("header.themeToggle")}
            >
              <TriggerIcon className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <DropdownMenuContent align="end" className="w-40">
          <DropdownMenuLabel>{t("header.theme")}</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {THEME_OPTIONS.map((option) => {
            const selected = selectedTheme === option.value;
            const Icon = option.icon;
            return (
              <DropdownMenuItem
                key={option.value}
                onSelect={() => setTheme(option.value)}
              >
                <Icon className="h-4 w-4 text-muted-foreground" />
                <span>{t(option.label as TranslationKey)}</span>
                <Check
                  className={cn(
                    "ml-auto h-4 w-4 text-primary",
                    !selected && "invisible",
                  )}
                />
              </DropdownMenuItem>
            );
          })}
        </DropdownMenuContent>
      </DropdownMenu>
      <TooltipContent>{t("header.themeToggle")}</TooltipContent>
    </Tooltip>
  );
}
