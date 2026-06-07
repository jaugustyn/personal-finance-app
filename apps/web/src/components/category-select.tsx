"use client";

import { useMemo } from "react";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CategoryColorDot } from "@/components/category-combobox";
import { useCategories } from "@/hooks/use-categories";
import { useT, tCategory } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const ALL = "__all__";
const SHOW_SUBCATEGORIES = false;

interface Props {
  /** Selected category name, or "" for "all". */
  value: string;
  onChange: (value: string) => void;
  /** Label shown for the "all categories" option. */
  allLabel: string;
  className?: string;
  ariaLabel?: string;
}

/**
 * Grouped category dropdown for filters. The backend can return subcategories,
 * but the UI currently exposes only top-level ML categories.
 */
export function CategorySelect({
  value,
  onChange,
  allLabel,
  className,
  ariaLabel,
}: Props) {
  const { t } = useT();
  const { data: categories = [] } = useCategories();

  const groups = useMemo(() => {
    const parents = categories
      .filter((c) => !c.parent)
      .sort((a, b) => {
        if (a.is_system !== b.is_system) return a.is_system ? -1 : 1;
        return a.name.localeCompare(b.name);
      });
    return parents.map((parent) => ({
      parent,
      children: SHOW_SUBCATEGORIES
        ? categories
            .filter((c) => c.parent === parent.name)
            .sort((a, b) => a.name.localeCompare(b.name))
        : [],
    }));
  }, [categories]);

  const label = (name: string, isSystem: boolean) =>
    isSystem ? tCategory(t, name) : name;

  return (
    <Select
      value={value || ALL}
      onValueChange={(v) => onChange(v === ALL ? "" : v)}
    >
      <SelectTrigger
        className={cn("w-auto min-w-44", className)}
        aria-label={ariaLabel}
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent className="max-h-80">
        <SelectItem value={ALL}>{allLabel}</SelectItem>
        {groups.map(({ parent, children }) => (
          <SelectGroup key={parent.id}>
            <SelectItem value={parent.name}>
              <span className="flex items-center gap-2">
                <CategoryColorDot color={parent.color} />
                {label(parent.name, parent.is_system)}
              </span>
            </SelectItem>
            {SHOW_SUBCATEGORIES &&
              children.map((child) => (
                <SelectItem key={child.id} value={child.name} className="pl-12">
                  <span className="text-muted-foreground">
                    {label(child.name, child.is_system)}
                  </span>
                </SelectItem>
              ))}
          </SelectGroup>
        ))}
      </SelectContent>
    </Select>
  );
}
