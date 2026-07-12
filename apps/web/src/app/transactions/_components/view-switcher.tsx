"use client";

import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { Check, Layers, LayoutList, type LucideIcon } from "lucide-react";
import type { TransactionsView } from "../_lib/constants";

interface ViewSwitcherProps {
  value: TransactionsView;
  onChange: (view: TransactionsView) => void;
}

export function ViewSwitcher({ value, onChange }: ViewSwitcherProps) {
  const { t } = useT();
  const items: { value: TransactionsView; label: string; icon: LucideIcon }[] = [
    { value: "list", label: t("transactions.viewList"), icon: LayoutList },
    { value: "review", label: t("transactions.viewReview"), icon: Check },
    { value: "groups", label: t("transactions.viewGroups"), icon: Layers },
  ];

  return (
    <div className="inline-flex max-w-full flex-wrap gap-0.5">
      {items.map((item) => {
        const Icon = item.icon;
        const active = value === item.value;
        return (
          <button
            key={item.value}
            type="button"
            onClick={() => onChange(item.value)}
            className={cn(
              "inline-flex h-9 items-center gap-2 rounded-[calc(var(--radius)-0.25rem)] px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background",
              active
                ? "bg-muted text-foreground shadow-sm"
                : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
            )}
          >
            <Icon className="h-4 w-4" />
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
