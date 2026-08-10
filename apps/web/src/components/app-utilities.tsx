"use client";

import { LockKeyhole } from "lucide-react";

import { AccentToggle } from "@/components/accent-toggle";
import { useAppLock } from "@/components/app-lock-provider";
import { AppPreferencesMenu } from "@/components/app-preferences-menu";
import { LocaleToggle } from "@/components/locale-toggle";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

interface AppUtilitiesProps {
  className?: string;
  variant?: "compact" | "sidebar";
}

export function AppUtilities({
  className,
  variant = "compact",
}: AppUtilitiesProps) {
  const { t } = useT();
  const appLock = useAppLock();

  if (variant === "sidebar") {
    return (
      <div className={cn("flex flex-col gap-0.5", className)}>
        <AppPreferencesMenu />
        {appLock.status.enabled ? (
          <Button
            variant="ghost"
            size="sm"
            className="group h-9 w-full justify-start gap-2.5 px-2 text-xs font-medium text-muted-foreground hover:bg-background/40 hover:text-foreground"
            onClick={() => void appLock.lock()}
            aria-label={t("appLock.lockNow")}
          >
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-border/70 bg-background/65 text-muted-foreground transition-colors group-hover:border-foreground/15 group-hover:text-foreground">
              <LockKeyhole className="h-3.5 w-3.5" />
            </span>
            {t("appLock.lockShort")}
          </Button>
        ) : null}
      </div>
    );
  }

  return (
    <div className={cn("flex items-center gap-1", className)}>
      {appLock.status.enabled ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => void appLock.lock()}
              aria-label={t("appLock.lockNow")}
            >
              <LockKeyhole className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("appLock.lockNow")}</TooltipContent>
        </Tooltip>
      ) : null}
      <LocaleToggle />
      <AccentToggle />
      <ThemeToggle />
    </div>
  );
}
