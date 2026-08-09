"use client";

import Link from "next/link";
import { useState } from "react";
import {
  ChevronDown,
  Loader2,
  MoreHorizontal,
  Plus,
  Save,
  Unlink,
} from "lucide-react";

import type { MerchantAlias, MerchantAliasGroup } from "@/lib/api";
import { useFormatters, useT } from "@/lib/i18n";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { transactionsHref } from "@/lib/transaction-links";
import { EmptyState } from "@/components/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";
import { AliasSuggestionInput } from "./alias-suggestion-input";

export function AliasGroupsPanel({
  groups,
  isLoading,
  isFiltered,
  labelPendingKey,
  deletePendingId,
  addPendingKey,
  onAddManual,
  onUpdateLabel,
  onAddAlias,
  onDeleteAlias,
}: {
  groups: MerchantAliasGroup[];
  isLoading: boolean;
  isFiltered: boolean;
  labelPendingKey: string | null;
  deletePendingId: number | null;
  addPendingKey: string | null;
  onAddManual: () => void;
  onUpdateLabel: (canonicalKey: string, canonicalLabel: string) => void;
  onAddAlias: (canonicalKey: string, canonicalLabel: string, alias: string) => void;
  onDeleteAlias: (alias: MerchantAlias) => void;
}) {
  const { t, locale } = useT();
  const { formatCurrency } = useFormatters();
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [newAliases, setNewAliases] = useState<Record<string, string>>({});

  return (
    <section className="space-y-3">
      <div className="flex min-h-9 items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold">
            {t("merchants.savedTitle")}
          </h2>
          <Badge variant="secondary">{groups.length}</Badge>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={onAddManual}
        >
          <Plus className="mr-2 h-4 w-4" />
          {t("merchants.addAlias")}
        </Button>
      </div>
      {isLoading ? (
        <div className="rounded-xl border bg-card p-3">
          <TableSkeleton rows={3} />
        </div>
      ) : groups.length === 0 ? (
        <EmptyState
          title={
            isFiltered
              ? t("merchants.savedSearchEmpty")
              : t("merchants.savedEmpty")
          }
          className="bg-card py-8"
        />
      ) : (
        <div className="divide-y rounded-xl border bg-card">
          {groups.map((group) => {
            const labelValue =
              labels[group.canonical_key] ?? group.canonical_label;
            const newAlias = newAliases[group.canonical_key] ?? "";
            const labelChanged = labelValue.trim() !== group.canonical_label;

            return (
              <details key={group.canonical_key} className="group">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3.5 transition-colors hover:bg-muted/40 group-open:bg-primary/5 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
                  <div className="flex min-w-0 items-center gap-3">
                    <ChevronDown className="h-4 w-4 shrink-0 -rotate-90 text-muted-foreground transition-all group-open:rotate-0 group-open:text-primary" />
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">
                        {group.canonical_label}
                      </div>
                      <div className="mt-1 flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
                        <span className="truncate">
                          {group.aliases
                            .slice(0, 3)
                            .map((alias) => alias.alias_label)
                            .join(" · ")}
                        </span>
                        {group.aliases.length > 3 ? (
                          <span className="shrink-0">
                            +{group.aliases.length - 3}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <span className="hidden whitespace-nowrap text-xs text-muted-foreground sm:inline">
                      {t("merchants.totalExpenses")}: {" "}
                      <span className="font-medium tabular-nums text-foreground">
                        {formatCurrency(
                          group.total_expenses,
                          group.base_currency,
                        )}
                      </span>
                    </span>
                    <Badge variant="secondary">
                      {t("merchants.aliasCount", {
                        count: group.aliases.length,
                      })}
                    </Badge>
                  </div>
                </summary>

                <div className="border-t bg-muted/10 px-4 py-5">
                  <div className="grid gap-6 lg:grid-cols-[32rem_minmax(0,1fr)] lg:items-start">
                    <div className="space-y-5">
                      <div className="grid gap-2">
                        <Label
                          htmlFor={`merchant-label-${group.canonical_key}`}
                        >
                          {t("merchants.displayLabel")}
                        </Label>
                        <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                          <Input
                            id={`merchant-label-${group.canonical_key}`}
                            value={labelValue}
                            onChange={(event) =>
                              setLabels((previous) => ({
                                ...previous,
                                [group.canonical_key]: event.target.value,
                              }))
                            }
                          />
                          <Button
                            variant="outline"
                            disabled={
                              !labelChanged ||
                              !labelValue.trim() ||
                              labelPendingKey === group.canonical_key
                            }
                            onClick={() =>
                              onUpdateLabel(
                                group.canonical_key,
                                labelValue.trim(),
                              )
                            }
                          >
                            {labelPendingKey === group.canonical_key ? (
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                              <Save className="mr-2 h-4 w-4" />
                            )}
                            {t("common.save")}
                          </Button>
                        </div>
                      </div>

                      <div className="grid gap-2">
                        <Label
                          htmlFor={`merchant-alias-${group.canonical_key}`}
                        >
                          {t("merchants.addAlias")}
                        </Label>
                        <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                          <AliasSuggestionInput
                            id={`merchant-alias-${group.canonical_key}`}
                            value={newAlias}
                            onChange={(value) =>
                              setNewAliases((previous) => ({
                                ...previous,
                                [group.canonical_key]: value,
                              }))
                            }
                            onSelectSuggestion={(suggestion) =>
                              setNewAliases((previous) => ({
                                ...previous,
                                [group.canonical_key]: suggestion.alias_label,
                              }))
                            }
                            disabled={addPendingKey === group.canonical_key}
                          />
                          <Button
                            variant="outline"
                            disabled={
                              !newAlias.trim() ||
                              addPendingKey === group.canonical_key
                            }
                            onClick={() => {
                              onAddAlias(
                                group.canonical_key,
                                labelValue.trim() || group.canonical_label,
                                newAlias.trim(),
                              );
                              setNewAliases((previous) => ({
                                ...previous,
                                [group.canonical_key]: "",
                              }));
                            }}
                          >
                            {addPendingKey === group.canonical_key ? (
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                              <Plus className="mr-2 h-4 w-4" />
                            )}
                            {t("common.add")}
                          </Button>
                        </div>
                      </div>
                    </div>

                    <div className="grid gap-2">
                      <p className="text-sm font-medium leading-none">
                        {t("merchants.savedVariants")}
                      </p>
                      <div className="grid grid-cols-[repeat(auto-fill,minmax(15rem,1fr))] gap-2">
                        {group.aliases.map((alias) => (
                          <div
                            key={alias.id}
                            className="flex min-w-0 items-start justify-between gap-3 rounded-lg border bg-card px-3 py-2.5 transition-colors hover:bg-muted/25"
                          >
                            <div className="min-w-0">
                              <span className="block truncate text-sm font-medium">
                                {alias.alias_label}
                              </span>
                              {alias.usage_count > 0 ? (
                                <Link
                                  href={transactionsHref({
                                    search: alias.alias_label
                                      .trim()
                                      .replace(/\s+/g, " "),
                                  })}
                                  className="mt-1 block w-fit text-xs tabular-nums text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
                                >
                                  {t(
                                    aliasUsageCountKey(
                                      locale,
                                      alias.usage_count,
                                    ),
                                    { count: alias.usage_count },
                                  )}
                                </Link>
                              ) : (
                                <span className="mt-1 block text-xs text-muted-foreground/70">
                                  {t("merchants.aliasNoTransactions")}
                                </span>
                              )}
                            </div>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-7 w-7"
                                  disabled={deletePendingId === alias.id}
                                  aria-label={t("merchants.aliasActions", {
                                    alias: alias.alias_label,
                                  })}
                                >
                                  {deletePendingId === alias.id ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                  ) : (
                                    <MoreHorizontal className="h-4 w-4" />
                                  )}
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem
                                  onSelect={() => onDeleteAlias(alias)}
                                >
                                  <Unlink className="h-4 w-4" />
                                  {t("merchants.detachAlias")}
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </details>
            );
          })}
        </div>
      )}
    </section>
  );
}

function aliasUsageCountKey(
  locale: "pl" | "en",
  count: number,
):
  | "merchants.aliasTransactionsOne"
  | "merchants.aliasTransactionsFew"
  | "merchants.aliasTransactionsMany" {
  if (count === 1) return "merchants.aliasTransactionsOne";
  if (locale === "pl") {
    const lastDigit = count % 10;
    const lastTwoDigits = count % 100;
    if (
      lastDigit >= 2 &&
      lastDigit <= 4 &&
      (lastTwoDigits < 12 || lastTwoDigits > 14)
    ) {
      return "merchants.aliasTransactionsFew";
    }
  }
  return "merchants.aliasTransactionsMany";
}
