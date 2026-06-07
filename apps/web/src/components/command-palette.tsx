"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { Monitor, Moon, Sun } from "lucide-react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { NAV_ITEMS } from "@/lib/nav";
import { useT } from "@/lib/i18n";

export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const { setTheme } = useTheme();
  const { t } = useT();

  const run = (fn: () => void) => {
    onOpenChange(false);
    fn();
  };

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder={t("command.placeholder")} />
      <CommandList>
        <CommandEmpty>{t("command.empty")}</CommandEmpty>
        <CommandGroup heading={t("command.navigation")}>
          {NAV_ITEMS.map((it) => {
            const Icon = it.icon;
            return (
              <CommandItem
                key={it.href}
                value={t(it.labelKey)}
                onSelect={() => run(() => router.push(it.href))}
              >
                <Icon className="h-4 w-4 text-muted-foreground" />
                {t(it.labelKey)}
              </CommandItem>
            );
          })}
        </CommandGroup>
        <CommandGroup heading={t("command.theme")}>
          <CommandItem
            value="light"
            onSelect={() => run(() => setTheme("light"))}
          >
            <Sun className="h-4 w-4 text-muted-foreground" />
            {t("command.theme.light")}
          </CommandItem>
          <CommandItem
            value="dark"
            onSelect={() => run(() => setTheme("dark"))}
          >
            <Moon className="h-4 w-4 text-muted-foreground" />
            {t("command.theme.dark")}
          </CommandItem>
          <CommandItem
            value="system"
            onSelect={() => run(() => setTheme("system"))}
          >
            <Monitor className="h-4 w-4 text-muted-foreground" />
            {t("command.theme.system")}
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
