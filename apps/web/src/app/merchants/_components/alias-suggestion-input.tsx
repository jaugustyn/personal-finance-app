"use client";

import { useQuery } from "@tanstack/react-query";

import type { MerchantAliasSuggestion } from "@/lib/api";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { cn, formatCurrency } from "@/lib/utils";
import { ClearableInput } from "@/components/ui/clearable-input";
import { MERCHANT_QUERY_KEYS } from "../_lib/query-keys";

export function AliasSuggestionInput({
  value,
  onChange,
  onSelectSuggestion,
  disabled,
  excludeKeys,
  placement = "bottom",
}: {
  value: string;
  onChange: (value: string) => void;
  onSelectSuggestion?: (suggestion: MerchantAliasSuggestion) => void;
  disabled?: boolean;
  excludeKeys?: Set<string>;
  placement?: "top" | "bottom";
}) {
  const { t } = useT();
  const query = value.trim();
  const suggestionsQuery = useQuery<MerchantAliasSuggestion[]>({
    queryKey: MERCHANT_QUERY_KEYS.suggestions(query),
    queryFn: () => api.merchantAliasSuggestions(query),
    enabled: query.length > 0,
  });
  const suggestions = (suggestionsQuery.data ?? []).filter(
    (suggestion) => !excludeKeys?.has(suggestion.alias_key),
  );

  return (
    <div className="relative">
      <ClearableInput
        value={value}
        onValueChange={onChange}
        placeholder={t("merchants.aliasPlaceholder")}
        clearLabel={t("common.clear")}
        disabled={disabled}
      />
      {query.length > 0 && !disabled ? (
        <div
          className={cn(
            "absolute z-20 max-h-64 w-full overflow-auto rounded-md border bg-popover p-1 shadow-md",
            placement === "top" ? "bottom-full mb-1" : "mt-1",
          )}
        >
          {suggestionsQuery.isLoading ? (
            <div className="px-2 py-2 text-xs text-muted-foreground">
              {t("common.loading")}
            </div>
          ) : suggestions.length === 0 ? (
            <div className="px-2 py-2 text-xs text-muted-foreground">
              {t("merchants.aliasSuggestionsEmpty")}
            </div>
          ) : (
            suggestions.map((suggestion) => (
              <button
                key={suggestion.alias_key}
                type="button"
                className="flex w-full min-w-0 items-center justify-between gap-3 rounded-sm px-2 py-2 text-left text-sm hover:bg-muted"
                onClick={() =>
                  onSelectSuggestion
                    ? onSelectSuggestion(suggestion)
                    : onChange(suggestion.alias_label)
                }
              >
                <span className="min-w-0">
                  <span className="block truncate font-medium">
                    {suggestion.alias_label}
                  </span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {suggestion.alias_key}
                  </span>
                </span>
                <span className="shrink-0 text-right text-xs text-muted-foreground">
                  {t("merchants.aliasSuggestionMeta", {
                    count: suggestion.count,
                    amount: formatCurrency(Number(suggestion.total_amount), "PLN"),
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
