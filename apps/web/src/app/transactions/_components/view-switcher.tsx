"use client";

import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";
import { Check, Layers, LayoutList } from "lucide-react";
import type { TransactionsView } from "../_lib/constants";

interface ViewSwitcherProps {
  value: TransactionsView;
  onChange: (view: TransactionsView) => void;
}

export function ViewSwitcher({ value, onChange }: ViewSwitcherProps) {
  const { t } = useT();

  return (
    <div className="flex gap-1 rounded-md border p-0.5 text-sm">
      <Button
        size="sm"
        variant={value === "list" ? "secondary" : "ghost"}
        onClick={() => onChange("list")}
      >
        <LayoutList className="mr-2 h-4 w-4" />
        {t("transactions.viewList")}
      </Button>
      <Button
        size="sm"
        variant={value === "review" ? "secondary" : "ghost"}
        onClick={() => onChange("review")}
      >
        <Check className="mr-2 h-4 w-4" />
        {t("transactions.viewReview")}
      </Button>
      <Button
        size="sm"
        variant={value === "groups" ? "secondary" : "ghost"}
        onClick={() => onChange("groups")}
      >
        <Layers className="mr-2 h-4 w-4" />
        {t("transactions.viewGroups")}
      </Button>
    </div>
  );
}
