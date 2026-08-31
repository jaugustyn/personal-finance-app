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
      <div className={cn("flex flex-col gap-1", className)}>
        <AppPreferencesMenu />
        {appLock.status.enabled ? (
          <Button
            variant="ghost"
            size="sm"
            className="group h-[38px] w-full justify-start gap-3 rounded-[6px] px-4 text-[15px] font-normal tracking-[-0.01em] text-foreground/[0.68] hover:bg-foreground/[0.018] hover:text-foreground dark:text-foreground/70 dark:hover:bg-foreground/[0.03]"
            onClick={() => void appLock.lock()}
            aria-label={t("appLock.lockNow")}
          >
            <LockKeyhole className="h-[17px] w-[17px] shrink-0 transition-colors group-hover:text-foreground" />
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
