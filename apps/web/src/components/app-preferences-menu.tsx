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
            <p className="text-xs font-medium text-foreground">
              {t("header.theme")}
            </p>
            <div
              className="grid grid-cols-3 divide-x divide-border/60 overflow-hidden rounded-md border border-input bg-card"
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
                      "relative flex h-10 min-w-0 flex-col items-center justify-center gap-0.5 px-1 text-[11px] font-medium transition-colors focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                      selected
                        ? "bg-accent-soft text-accent-soft-foreground"
                        : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                    )}
                  >
                    <Icon className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate">
                      {t(option.label as TranslationKey)}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="space-y-2.5">
            <p className="text-xs font-medium text-foreground">
              {t("header.accentToggle")}
            </p>
            <div className="grid grid-cols-6 gap-1.5">
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
            <p className="text-xs font-medium text-foreground">
              {t("header.language")}
            </p>
            <div className="flex items-center gap-3">
              {(["pl", "en"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setLocale(option)}
                  aria-pressed={locale === option}
                  className={cn(
                    "text-xs font-semibold uppercase transition-colors hover:text-foreground",
                    locale === option ? "text-primary" : "text-muted-foreground",
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
          "group h-9 w-full justify-start gap-2.5 px-2 text-xs font-medium text-muted-foreground hover:bg-background/40 hover:text-foreground",
          open && "font-semibold text-foreground",
        )}
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls="appearance-options"
      >
        <span
          className={cn(
            "flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-border/70 bg-background/65 text-muted-foreground transition-colors group-hover:border-foreground/15 group-hover:text-foreground",
            open && "border-foreground/10 bg-foreground/[0.06] text-foreground",
          )}
        >
          <SlidersHorizontal className="h-3.5 w-3.5" />
        </span>
        {t("header.preferences")}
      </Button>
    </div>
  );
}
