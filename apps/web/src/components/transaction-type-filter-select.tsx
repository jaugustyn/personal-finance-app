"use client";

import { FilterSelect } from "@/components/filter-select";
import { tTransactionType, useT } from "@/lib/i18n";
import {
  TRANSACTION_TYPE_ICONS,
  TRANSACTION_TYPE_OPTIONS,
} from "@/lib/transaction-types";

const ALL = "__all__";

export function TransactionTypeFilterSelect({
  id,
  value,
  onChange,
  allLabel,
  ariaLabel,
  className,
}: {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  allLabel: string;
  ariaLabel?: string;
  className?: string;
}) {
  const { t } = useT();
  const options = [
    { value: ALL, label: allLabel, muted: true },
    ...TRANSACTION_TYPE_OPTIONS.map((type) => {
      const Icon = TRANSACTION_TYPE_ICONS[type];
      return {
        value: type,
        label: tTransactionType(t, type),
        leading: (
          <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        ),
      };
    }),
  ];

  return (
    <FilterSelect
      id={id}
      value={value || ALL}
      onValueChange={(nextValue) => onChange(nextValue === ALL ? "" : nextValue)}
      options={options}
      ariaLabel={ariaLabel}
      className={className}
    />
  );
}
