"use client";

import { useMemo } from "react";
import { CategoryCompactAccent } from "@/components/category-accent";
import { FilterSelect } from "@/components/filter-select";
import { useCategories } from "@/hooks/use-categories";
import { useT, tCategory } from "@/lib/i18n";

const ALL = "__all__";

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

  const options = useMemo(
    () => [
      { value: ALL, label: allLabel, muted: true },
      ...categories
        .filter((category) => !category.parent)
        .sort((left, right) => {
          if (left.is_system !== right.is_system) {
            return left.is_system ? -1 : 1;
          }
          return tCategory(t, left.name).localeCompare(tCategory(t, right.name));
        })
        .map((category) => ({
          value: category.name,
          label: tCategory(t, category.name),
          leading: <CategoryCompactAccent color={category.color} />,
        })),
    ],
    [allLabel, categories, t],
  );

  return (
    <FilterSelect
      value={value || ALL}
      onValueChange={(nextValue) => onChange(nextValue === ALL ? "" : nextValue)}
      options={options}
      ariaLabel={ariaLabel}
      className={className ?? "w-auto min-w-44"}
      contentClassName="max-h-80"
    />
  );
}
