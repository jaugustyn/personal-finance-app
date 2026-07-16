"use client";

import { FilterSelect } from "@/components/filter-select";
import type { Direction } from "@/lib/api";
import { useT } from "@/lib/i18n";

export function DirectionFilterSelect({
  value,
  onChange,
  ariaLabel,
  className,
}: {
  value: Direction;
  onChange: (value: Direction) => void;
  ariaLabel?: string;
  className?: string;
}) {
  const { t } = useT();
  const options = [
    {
      value: "all",
      label: t("transactions.filterDirection.all"),
      muted: true,
    },
    {
      value: "debit",
      label: t("transactions.filterDirection.debit"),
    },
    {
      value: "credit",
      label: t("transactions.filterDirection.credit"),
    },
  ];

  return (
    <FilterSelect
      value={value}
      onValueChange={(nextValue) => onChange(nextValue as Direction)}
      options={options}
      ariaLabel={ariaLabel}
      className={className}
    />
  );
}
