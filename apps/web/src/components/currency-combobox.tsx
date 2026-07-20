"use client";

import { useMemo, useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";
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
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const FALLBACK_CURRENCIES = [
  "AUD",
  "CAD",
  "CHF",
  "CZK",
  "DKK",
  "EUR",
  "GBP",
  "HUF",
  "JPY",
  "NOK",
  "PLN",
  "SEK",
  "USD",
];

function supportedCurrencies(): string[] {
  try {
    if (typeof Intl.supportedValuesOf === "function") {
      return Intl.supportedValuesOf("currency").filter(
        (code) => code !== "XTS" && code !== "XXX",
      );
    }
  } catch {
    // Older runtimes use the compact fallback below.
  }
  return FALLBACK_CURRENCIES;
}

export function CurrencyCombobox({
  value,
  onChange,
  baseCurrency,
  autoFocus,
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  baseCurrency?: string;
  autoFocus?: boolean;
  className?: string;
}) {
  const { locale, t } = useT();
  const [open, setOpen] = useState(false);
  const normalizedValue = value.trim().toUpperCase();

  const options = useMemo(() => {
    let displayNames: Intl.DisplayNames | null = null;
    try {
      displayNames = new Intl.DisplayNames(locale, {
        type: "currency",
        fallback: "code",
      });
    } catch {
      // Codes remain usable if localized display names are unavailable.
    }

    return supportedCurrencies().map((code) => ({
      code,
      name: displayNames?.of(code) ?? code,
      isBase: code === baseCurrency?.toUpperCase(),
    }));
  }, [baseCurrency, locale]);

  return (
    <Popover modal open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-label={t("currencies.currency")}
          autoFocus={autoFocus}
          className={cn("h-9 w-full justify-between px-3 font-normal", className)}
        >
          <span className="font-medium">{normalizedValue || "—"}</span>
          <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 p-0" align="start">
        <Command>
          <CommandInput
            placeholder={t("currencies.searchCurrency")}
            clearLabel={t("common.clear")}
          />
          <CommandList
            className="select-scrollbar max-h-72 overscroll-contain"
            onWheel={(event) => event.stopPropagation()}
            onPointerMoveCapture={(event) => {
              if (event.buttons === 1) event.stopPropagation();
            }}
          >
            <CommandEmpty>{t("currencies.currencyNotFound")}</CommandEmpty>
            <CommandGroup>
              {options.map((option) => (
                <CommandItem
                  key={option.code}
                  value={`${option.code} ${option.name} ${option.isBase ? t("currencies.baseBadge") : ""}`}
                  disabled={option.isBase}
                  onSelect={() => {
                    if (option.isBase) return;
                    onChange(option.code);
                    setOpen(false);
                  }}
                >
                  <span className="w-10 shrink-0 font-medium">{option.code}</span>
                  <span className="min-w-0 flex-1 truncate text-muted-foreground">
                    {option.name}
                  </span>
                  {option.isBase ? (
                    <span className="ml-auto text-xs text-muted-foreground">
                      {t("currencies.baseBadge")}
                    </span>
                  ) : null}
                  {normalizedValue === option.code ? (
                    <Check className="ml-auto h-3.5 w-3.5 shrink-0" />
                  ) : null}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
