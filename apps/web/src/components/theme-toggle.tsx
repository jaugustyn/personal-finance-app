"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";
import { withThemeTransition } from "@/lib/theme-transition";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const { t } = useT();
  const isDark = resolvedTheme === "dark";
  return (
    <Button
      variant="ghost"
      size="icon"
      className="relative overflow-hidden"
      onClick={() =>
        withThemeTransition(() => setTheme(isDark ? "light" : "dark"))
      }
      aria-label={t("header.themeToggle")}
    >
      <Sun
        className={`h-4 w-4 transition-[opacity,transform] duration-150 ease-out motion-reduce:transition-none ${
          isDark ? "scale-100 opacity-100" : "scale-90 opacity-0"
        }`}
      />
      <Moon
        className={`absolute h-4 w-4 transition-[opacity,transform] duration-150 ease-out motion-reduce:transition-none ${
          isDark ? "scale-90 opacity-0" : "scale-100 opacity-100"
        }`}
      />
    </Button>
  );
}
