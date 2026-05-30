"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const { t } = useT();
  const isDark = theme === "dark";
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={t("header.themeToggle")}
    >
      {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}
