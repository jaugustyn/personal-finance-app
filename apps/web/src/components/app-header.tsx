"use client";

import * as React from "react";
import { LockKeyhole, Menu } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";
import { AccentToggle } from "@/components/accent-toggle";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { SidebarBrand, SidebarNav } from "@/components/sidebar";
import { useT } from "@/lib/i18n";
import { useAppLock } from "@/components/app-lock-provider";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function AppHeader() {
  const { t } = useT();
  const appLock = useAppLock();
  const [mobileOpen, setMobileOpen] = React.useState(false);

  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b bg-card/60 px-4 backdrop-blur supports-backdrop-filter:bg-card/60 sm:px-6">
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            aria-label={t("nav.openMenu")}
          >
            <Menu className="h-5 w-5" />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="flex w-72 flex-col p-0">
          <SidebarBrand />
          <SidebarNav onNavigate={() => setMobileOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="ml-auto flex items-center gap-1">
        {appLock.status.enabled && (
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
        )}
        <LocaleToggle />
        <AccentToggle />
        <ThemeToggle />
      </div>
    </header>
  );
}
