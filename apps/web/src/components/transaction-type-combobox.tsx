"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowDownCircle,
  ArrowLeftRight,
  Banknote,
  Check,
  ChevronsUpDown,
  CircleDollarSign,
  CreditCard,
  HelpCircle,
  Landmark,
  Receipt,
  RotateCcw,
  WalletCards,
  X,
  type LucideIcon,
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
  TRANSACTION_TYPE_OPTIONS,
  type TransactionTypeOption,
} from "@/lib/transaction-types";
import { cn } from "@/lib/utils";

const TYPE_ICONS: Record<TransactionTypeOption, LucideIcon> = {
  purchase: CreditCard,
  person_transfer: ArrowLeftRight,
  own_transfer: ArrowLeftRight,
  salary: Banknote,
  income: CircleDollarSign,
  refund: RotateCcw,
  cash_withdrawal: ArrowDownCircle,
  debt_payment: Receipt,
  bank_fee: Landmark,
  savings_investment: WalletCards,
  other: HelpCircle,
};

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
      TRANSACTION_TYPE_OPTIONS.map((type) => ({
        value: type,
        label: tTransactionType(t, type),
        Icon: TYPE_ICONS[type],
      })),
    [t],
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

  const SelectedIcon = selectedType ? TYPE_ICONS[selectedType] : X;

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
            <SelectedIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
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
          <CommandInput placeholder={t("transactions.typeSearch")} />
          <CommandList>
            <CommandEmpty>{t("common.empty")}</CommandEmpty>
            {includeEmpty && (
              <CommandGroup>
                <CommandItem
                  value={emptyLabel ?? t("transactions.filterType.all")}
                  onSelect={() => selectValue(emptyValue)}
                >
                  <X className="h-3.5 w-3.5 text-muted-foreground" />
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
