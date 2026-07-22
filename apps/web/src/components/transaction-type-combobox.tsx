"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Check,
  ChevronsUpDown,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { tTransactionType, useT } from "@/lib/i18n";
import {
  TRANSACTION_TYPE_ICONS,
  TRANSACTION_TYPE_OPTIONS,
} from "@/lib/transaction-types";
import { cn } from "@/lib/utils";

interface TransactionTypeComboboxProps {
  value: string;
  onChange: (value: string) => void;
  autoFocus?: boolean;
  onCancel?: () => void;
  size?: "sm" | "md";
  className?: string;
  ariaLabel?: string;
  includeEmpty?: boolean;
  emptyValue?: string;
  emptyLabel?: string;
  allowedValues?: readonly string[];
}

export function TransactionTypeCombobox({
  value,
  onChange,
  autoFocus,
  onCancel,
  size = "sm",
  className,
  ariaLabel,
  includeEmpty = false,
  emptyValue = "",
  emptyLabel,
  allowedValues,
}: TransactionTypeComboboxProps) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  const didAutoOpen = useRef(false);
  const selectedByClick = useRef(false);
  const normalizedValue = value || emptyValue;
  const selectedType = TRANSACTION_TYPE_OPTIONS.find(
    (type) => type === normalizedValue,
  );
  const selectedLabel = selectedType
    ? tTransactionType(t, selectedType)
    : (emptyLabel ?? t("transactions.filterType.all"));
  const heightCls = size === "sm" ? "h-8 text-xs" : "h-9 text-sm";

  useEffect(() => {
    if (autoFocus && !didAutoOpen.current) {
      didAutoOpen.current = true;
      setOpen(true);
    }
  }, [autoFocus]);

  const options = useMemo(
    () =>
      TRANSACTION_TYPE_OPTIONS.filter(
        (type) => !allowedValues || allowedValues.includes(type),
      ).map((type) => ({
        value: type,
        label: tTransactionType(t, type),
        Icon: TRANSACTION_TYPE_ICONS[type],
      })),
    [allowedValues, t],
  );

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (!next && autoFocus && onCancel && !selectedByClick.current) {
      onCancel();
    }
    if (!next) selectedByClick.current = false;
  };

  const selectValue = (nextValue: string) => {
    selectedByClick.current = true;
    onChange(nextValue);
    setOpen(false);
  };

  const SelectedIcon = selectedType
    ? TRANSACTION_TYPE_ICONS[selectedType]
    : null;

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-label={ariaLabel}
          className={cn(
            "w-full justify-between gap-2 font-normal",
            heightCls,
            !selectedType && "text-muted-foreground",
            className,
          )}
        >
          <span className="flex min-w-0 items-center gap-2">
            {SelectedIcon ? (
              <SelectedIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            ) : null}
            <span className="truncate">{selectedLabel}</span>
          </span>
          <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-0" align="start">
        <Command
          filter={(itemValue, query) =>
            itemValue.toLowerCase().includes(query.toLowerCase()) ? 1 : 0
          }
        >
          <CommandInput
            placeholder={t("transactions.typeSearch")}
            clearLabel={t("common.clear")}
          />
          <CommandList>
            <CommandEmpty>{t("common.empty")}</CommandEmpty>
            {includeEmpty && (
              <CommandGroup>
                <CommandItem
                  value={emptyLabel ?? t("transactions.filterType.all")}
                  onSelect={() => selectValue(emptyValue)}
                >
                  <span className="h-3.5 w-3.5" aria-hidden="true" />
                  <span className="text-muted-foreground">
                    {emptyLabel ?? t("transactions.filterType.all")}
                  </span>
                  {normalizedValue === emptyValue && (
                    <Check className="ml-auto h-3.5 w-3.5" />
                  )}
                </CommandItem>
              </CommandGroup>
            )}
            <CommandGroup>
              {options.map(({ value: optionValue, label, Icon }) => (
                <CommandItem
                  key={optionValue}
                  value={`${optionValue} ${label}`}
                  onSelect={() => selectValue(optionValue)}
                >
                  <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="truncate">{label}</span>
                  {selectedType === optionValue && (
                    <Check className="ml-auto h-3.5 w-3.5" />
                  )}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
