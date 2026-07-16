"use client";

import Link from "next/link";
import { useState } from "react";
import {
  ChevronDown,
  Loader2,
  MoreHorizontal,
  Plus,
  ReceiptText,
  Save,
  Unlink,
} from "lucide-react";

import type { MerchantAlias, MerchantAliasGroup } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { transactionsHref } from "@/lib/transaction-links";
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
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [newAliases, setNewAliases] = useState<Record<string, string>>({});

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle className="flex items-center gap-2 text-base">
          {t("merchants.savedTitle")}
          <Badge variant="secondary">{groups.length}</Badge>
        </CardTitle>
        <Button size="sm" onClick={onAddManual}>
          <Plus className="mr-2 h-4 w-4" />
          {t("merchants.addAlias")}
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex h-24 items-center justify-center text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : groups.length === 0 ? (
          <div className="rounded-lg border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">
            {isFiltered
              ? t("merchants.savedSearchEmpty")
              : t("merchants.savedEmpty")}
          </div>
        ) : (
          <div className="space-y-2">
            {groups.map((group) => {
              const labelValue =
                labels[group.canonical_key] ?? group.canonical_label;
              const newAlias = newAliases[group.canonical_key] ?? "";
              const labelChanged = labelValue.trim() !== group.canonical_label;

              return (
                <details
                  key={group.canonical_key}
                  className="group overflow-hidden rounded-lg border transition-colors open:bg-muted/10"
                >
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 transition-colors hover:bg-muted/40 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
                    <div className="flex min-w-0 items-center gap-3">
                      <ChevronDown className="h-4 w-4 shrink-0 -rotate-90 text-muted-foreground transition-transform group-open:rotate-0" />
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
                    <Badge variant="secondary" className="shrink-0">
                      {t("merchants.aliasCount", {
                        count: group.aliases.length,
                      })}
                    </Badge>
                  </summary>

                  <div className="space-y-4 border-t p-4">
                    <div className="space-y-2">
                      <Label htmlFor={`merchant-label-${group.canonical_key}`}>
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

                    <div className="space-y-2">
                      <Label>{t("merchants.savedVariants")}</Label>
                      <div className="divide-y overflow-hidden rounded-lg border bg-card">
                        {group.aliases.map((alias) => (
                          <div
                            key={alias.id}
                            className="grid min-h-10 grid-cols-[minmax(0,1fr)_8.5rem_2rem] items-center gap-3 px-3 py-1.5"
                          >
                            <span className="truncate text-sm">
                              {alias.alias_label}
                            </span>
                            <span className="text-right text-xs tabular-nums text-muted-foreground">
                              {alias.usage_count > 0
                                ? t(aliasUsageCountKey(locale, alias.usage_count), {
                                    count: alias.usage_count,
                                  })
                                : t("merchants.aliasNoTransactions")}
                            </span>
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
                                {alias.usage_count > 0 ? (
                                  <DropdownMenuItem asChild>
                                    <Link
                                      href={transactionsHref({
                                        search: alias.alias_label
                                          .trim()
                                          .replace(/\s+/g, " "),
                                      })}
                                    >
                                      <ReceiptText className="h-4 w-4" />
                                      {t("merchants.showTransactions")}
                                    </Link>
                                  </DropdownMenuItem>
                                ) : (
                                  <DropdownMenuItem disabled>
                                    <ReceiptText className="h-4 w-4" />
                                    {t("merchants.showTransactions")}
                                  </DropdownMenuItem>
                                )}
                                <DropdownMenuSeparator />
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

                    <div className="space-y-2">
                      <Label htmlFor={`merchant-alias-${group.canonical_key}`}>
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
                          onSelectSuggestion={(suggestion) => {
                            onAddAlias(
                              group.canonical_key,
                              labelValue.trim() || group.canonical_label,
                              suggestion.alias_label,
                            );
                            setNewAliases((previous) => ({
                              ...previous,
                              [group.canonical_key]: "",
                            }));
                          }}
                          disabled={addPendingKey === group.canonical_key}
                          placement="top"
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
                </details>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
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
