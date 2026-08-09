"use client";

import * as React from "react";
import { Menu } from "lucide-react";
import { AppUtilities } from "@/components/app-utilities";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { SidebarBrand, SidebarNav } from "@/components/sidebar";
import { useT } from "@/lib/i18n";

export function AppHeader() {
  const { t } = useT();
  const [mobileOpen, setMobileOpen] = React.useState(false);

  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b bg-background/95 px-3 backdrop-blur md:hidden">
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

      <span className="text-sm font-semibold tracking-tight">
        {t("app.title")}
      </span>
      <AppUtilities className="ml-auto" />
    </header>
  );
}
