"use client";

import { useEffect, useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type { MerchantAliasSuggestion } from "@/lib/api";
import { api } from "@/lib/api";
import { useFormatters, useT } from "@/lib/i18n";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import { ClearableInput } from "@/components/ui/clearable-input";

export function AliasSuggestionInput({
  id,
  value,
  onChange,
  onSelectSuggestion,
  disabled,
  excludeKeys,
  placement = "bottom",
}: {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  onSelectSuggestion?: (suggestion: MerchantAliasSuggestion) => void;
  disabled?: boolean;
  excludeKeys?: Set<string>;
  placement?: "top" | "bottom";
}) {
  const { t } = useT();
  const { formatCurrency } = useFormatters();
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const listId = `${inputId}-suggestions`;
  const query = value.trim();
  const [debouncedQuery, setDebouncedQuery] = useState(query);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => setDebouncedQuery(query), 200);
    return () => window.clearTimeout(timeoutId);
  }, [query]);

  const suggestionsQuery = useQuery<MerchantAliasSuggestion[]>({
    queryKey: queryKeys.merchants.suggestions(debouncedQuery),
    queryFn: () => api.merchantAliasSuggestions(debouncedQuery),
    enabled: debouncedQuery.length > 0,
  });
  const suggestions = (suggestionsQuery.data ?? []).filter(
    (suggestion) => !excludeKeys?.has(suggestion.alias_key),
  );
  const isWaiting = query !== debouncedQuery;

  const selectSuggestion = (suggestion: MerchantAliasSuggestion) => {
    if (onSelectSuggestion) onSelectSuggestion(suggestion);
    else onChange(suggestion.alias_label);
    setOpen(false);
    setActiveIndex(-1);
  };

  return (
    <div className="relative">
      <ClearableInput
        id={inputId}
        value={value}
        onValueChange={(nextValue) => {
          onChange(nextValue);
          setOpen(Boolean(nextValue.trim()));
          setActiveIndex(-1);
        }}
        placeholder={t("merchants.aliasPlaceholder")}
        clearLabel={t("common.clear")}
        disabled={disabled}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open && query.length > 0}
        aria-controls={listId}
        onFocus={() => setOpen(Boolean(query))}
        onBlur={() => {
          setOpen(false);
          setActiveIndex(-1);
        }}
        onKeyDown={(event) => {
          if (!open || suggestions.length === 0) {
            if (event.key === "ArrowDown" && query) setOpen(true);
            return;
          }
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setActiveIndex((current) =>
              current >= suggestions.length - 1 ? 0 : current + 1,
            );
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            setActiveIndex((current) =>
              current <= 0 ? suggestions.length - 1 : current - 1,
            );
          } else if (event.key === "Enter" && activeIndex >= 0) {
            event.preventDefault();
            selectSuggestion(suggestions[activeIndex]);
          } else if (event.key === "Escape") {
            setOpen(false);
            setActiveIndex(-1);
          }
        }}
      />
      {open && query.length > 0 && !disabled ? (
        <div
          id={listId}
          role="listbox"
          className={cn(
            "select-scrollbar absolute z-20 max-h-64 w-full overflow-auto rounded-md border bg-popover p-1 shadow-md",
            placement === "top" ? "bottom-full mb-1" : "mt-1",
          )}
        >
          {isWaiting || suggestionsQuery.isLoading ? (
            <div className="px-2 py-2 text-xs text-muted-foreground">
              {t("common.loading")}
            </div>
          ) : suggestions.length === 0 ? (
            <div className="px-2 py-2 text-xs text-muted-foreground">
              {t("merchants.aliasSuggestionsEmpty")}
            </div>
          ) : (
            suggestions.map((suggestion, index) => (
              <button
                key={suggestion.alias_key}
                type="button"
                role="option"
                aria-selected={index === activeIndex}
                className={cn(
                  "flex w-full min-w-0 items-center justify-between gap-3 rounded-sm px-2 py-2 text-left text-sm hover:bg-muted",
                  index === activeIndex && "bg-muted",
                )}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => selectSuggestion(suggestion)}
              >
                <span className="min-w-0">
                  <span className="block truncate font-medium">
                    {suggestion.alias_label}
                  </span>
                </span>
                <span className="shrink-0 text-right text-xs text-muted-foreground">
                  {t("merchants.aliasSuggestionMeta", {
                    count: suggestion.count,
                    amount: formatCurrency(
                      Number(suggestion.total_amount),
                      suggestion.base_currency,
                    ),
                  })}
                </span>
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
