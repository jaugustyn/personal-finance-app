"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";
import { CategoryCompactAccent } from "@/components/category-accent";
import { FilterSelect } from "@/components/filter-select";
import { useCategories } from "@/hooks/use-categories";
import { useFormatters, useT, tCategory } from "@/lib/i18n";

const ALL = "__all__";

interface Props {
  id?: string;
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
  id,
  value,
  onChange,
  allLabel,
  className,
  ariaLabel,
}: Props) {
  const { t } = useT();
  const { compare } = useFormatters();
  const {
    data: categories = [],
    isError,
    refetch,
  } = useCategories();

  const options = useMemo(
    () => [
      { value: ALL, label: allLabel, muted: true },
      ...categories
        .filter((category) => !category.parent)
        .sort((left, right) => {
          if (left.is_system !== right.is_system) {
            return left.is_system ? -1 : 1;
          }
          return compare(tCategory(t, left.name), tCategory(t, right.name));
        })
        .map((category) => ({
          value: category.name,
          label: tCategory(t, category.name),
          leading: <CategoryCompactAccent color={category.color} />,
        })),
    ],
    [allLabel, categories, compare, t],
  );

  return (
    <div className="space-y-1">
      <FilterSelect
        id={id}
        value={value || ALL}
        onValueChange={(nextValue) => onChange(nextValue === ALL ? "" : nextValue)}
        options={options}
        ariaLabel={ariaLabel}
        className={cn(
          className ?? "w-auto min-w-44",
          isError && "border-destructive",
        )}
        contentClassName="max-h-80"
        disabled={isError}
      />
      {isError ? (
        <button
          type="button"
          onClick={() => void refetch()}
          className="block text-xs text-destructive underline-offset-4 hover:underline"
        >
          {t("common.error")} · {t("common.retry")}
        </button>
      ) : null}
    </div>
  );
}
