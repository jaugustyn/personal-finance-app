"use client";

import * as React from "react";
import { Check, Monitor, Moon, SlidersHorizontal, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { ACCENTS, useAccent, type Accent } from "@/components/accent-provider";
import { Button } from "@/components/ui/button";
import { useT, type TranslationKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const SWATCH: Record<Accent, string> = {
  emerald: "bg-[hsl(160_84%_36%)]",
  teal: "bg-[hsl(174_80%_36%)]",
  blue: "bg-[hsl(221_83%_53%)]",
  indigo: "bg-[hsl(243_75%_59%)]",
  violet: "bg-[hsl(262_83%_58%)]",
  pink: "bg-[hsl(333_71%_51%)]",
};

const THEME_OPTIONS = [
  { value: "light", label: "header.theme.light", icon: Sun },
  { value: "system", label: "header.theme.system", icon: Monitor },
  { value: "dark", label: "header.theme.dark", icon: Moon },
] as const;

export function AppPreferencesMenu() {
  const [open, setOpen] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const { accent, setAccent } = useAccent();
  const { locale, setLocale, t } = useT();
  const { theme, setTheme } = useTheme();
  const selectedTheme = theme ?? "system";

  React.useEffect(() => {
    if (!open) return;

    const handlePointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  return (
    <div ref={containerRef} className="w-full">
      {open ? (
        <div
          id="appearance-options"
          className="absolute bottom-full left-0 z-30 w-full space-y-5 border-t border-border/80 bg-sidebar px-5 py-4 animate-in fade-in slide-in-from-bottom-1 duration-150"
        >
          <div className="space-y-2">
            <p className="text-[13px] font-medium text-foreground">
              {t("header.theme")}
            </p>
            <div
              className="overflow-hidden rounded-[6px] border border-border/80 bg-card"
              role="group"
              aria-label={t("header.theme")}
            >
              {THEME_OPTIONS.map((option) => {
                const selected = selectedTheme === option.value;
                const Icon = option.icon;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setTheme(option.value)}
                    aria-pressed={selected}
                    className={cn(
                      "relative flex h-9 w-full items-center gap-2.5 border-b border-border/60 px-3 text-[13px] font-normal transition-colors last:border-b-0 focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                      selected
                        ? "bg-primary/[0.055] font-medium text-foreground dark:bg-primary/[0.09]"
                        : "text-foreground/[0.68] hover:bg-foreground/[0.02] hover:text-foreground dark:text-foreground/70 dark:hover:bg-foreground/[0.035]",
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className="min-w-0 flex-1 truncate text-left">
                      {t(option.label as TranslationKey)}
                    </span>
                    {selected ? (
                      <Check className="h-3.5 w-3.5 shrink-0 text-primary" />
                    ) : null}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="space-y-2.5">
            <p className="text-[13px] font-medium text-foreground">
              {t("header.accentToggle")}
            </p>
            <div
              className="grid grid-cols-6 gap-1.5"
              role="group"
              aria-label={t("header.accentToggle")}
            >
              {ACCENTS.map((option) => {
                const selected = accent === option;
                const label = t(
                  `header.accent.${option}` as TranslationKey,
                );

                return (
                  <button
                    key={option}
                    type="button"
                    onClick={() => setAccent(option)}
                    aria-label={label}
                    aria-pressed={selected}
                    title={label}
                    className={cn(
                      "flex h-7 w-7 items-center justify-center rounded-full text-white ring-1 ring-black/10 transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                      SWATCH[option],
                      selected && "ring-2 ring-primary ring-offset-2 ring-offset-sidebar",
                    )}
                  >
                    {selected ? <Check className="h-3 w-3" /> : null}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-[13px] font-medium text-foreground">
              {t("header.language")}
            </p>
            <div
              className="grid grid-cols-2 divide-x divide-border/60 overflow-hidden rounded-[6px] border border-border/80 bg-card"
              role="group"
              aria-label={t("header.language")}
            >
              {(["pl", "en"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setLocale(option)}
                  aria-pressed={locale === option}
                  className={cn(
                    "h-9 text-[13px] font-normal uppercase transition-colors focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                    locale === option
                      ? "bg-primary/[0.055] font-medium text-foreground dark:bg-primary/[0.09]"
                      : "text-foreground/[0.68] hover:bg-foreground/[0.02] hover:text-foreground dark:text-foreground/70 dark:hover:bg-foreground/[0.035]",
                  )}
                >
                  {option}
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : null}

      <Button
        variant="ghost"
        size="sm"
        className={cn(
          "group h-[38px] w-full justify-start gap-3 rounded-[6px] px-4 text-[15px] font-normal tracking-[-0.01em] text-foreground/[0.68] hover:bg-foreground/[0.018] hover:text-foreground dark:text-foreground/70 dark:hover:bg-foreground/[0.03]",
          open &&
            "bg-primary/[0.055] font-medium text-foreground hover:bg-primary/[0.07] dark:bg-primary/[0.09] dark:hover:bg-primary/[0.11]",
        )}
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls="appearance-options"
      >
        <SlidersHorizontal
          className={cn(
            "h-[17px] w-[17px] shrink-0 transition-colors",
            open ? "text-primary" : "group-hover:text-foreground",
          )}
        />
        {t("header.preferences")}
      </Button>
    </div>
  );
}
