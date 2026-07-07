"use client";

import { useState } from "react";
import { Loader2, Plus, Save, Store, Trash2 } from "lucide-react";

import type { MerchantAlias, MerchantAliasGroup } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { Input } from "@/components/ui/input";
import { AliasSuggestionInput } from "./alias-suggestion-input";

export function AliasGroupsPanel({
  groups,
  labelPendingKey,
  deletePendingId,
  addPendingKey,
  onUpdateLabel,
  onAddAlias,
  onDeleteAlias,
}: {
  groups: MerchantAliasGroup[];
  labelPendingKey: string | null;
  deletePendingId: number | null;
  addPendingKey: string | null;
  onUpdateLabel: (canonicalKey: string, canonicalLabel: string) => void;
  onAddAlias: (canonicalKey: string, canonicalLabel: string, alias: string) => void;
  onDeleteAlias: (alias: MerchantAlias) => void;
}) {
  const { t } = useT();
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [newAliases, setNewAliases] = useState<Record<string, string>>({});

  if (groups.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("merchants.savedTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState title={t("merchants.savedEmpty")} icon={Store} />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t("merchants.savedTitle")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {groups.map((group) => {
          const labelValue = labels[group.canonical_key] ?? group.canonical_label;
          const newAlias = newAliases[group.canonical_key] ?? "";
          const labelChanged = labelValue.trim() !== group.canonical_label;
          return (
            <details
              key={group.canonical_key}
              className="group rounded-lg border"
            >
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">
                    {group.canonical_label}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {group.aliases.slice(0, 4).map((alias) => (
                      <Badge key={alias.id} variant="muted" className="text-[10px]">
                        {alias.alias_label}
                      </Badge>
                    ))}
                    {group.aliases.length > 4 ? (
                      <Badge variant="outline" className="text-[10px]">
                        +{group.aliases.length - 4}
                      </Badge>
                    ) : null}
                  </div>
                </div>
                <Badge variant="secondary" className="shrink-0">
                  {t("merchants.aliasCount", { count: group.aliases.length })}
                </Badge>
              </summary>

              <div className="border-t p-3">
                <div className="grid gap-3 lg:grid-cols-[1fr_auto] lg:items-start">
                  <div className="space-y-2">
                    <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                      <Input
                        value={labelValue}
                        onChange={(event) =>
                          setLabels((prev) => ({
                            ...prev,
                            [group.canonical_key]: event.target.value,
                          }))
                        }
                        aria-label={t("merchants.displayLabel")}
                      />
                      <Button
                        variant="outline"
                        disabled={
                          !labelChanged ||
                          !labelValue.trim() ||
                          labelPendingKey === group.canonical_key
                        }
                        onClick={() =>
                          onUpdateLabel(group.canonical_key, labelValue.trim())
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
                    <div className="text-xs text-muted-foreground">
                      {group.canonical_key}
                    </div>
                  </div>
                </div>

                <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                  {group.aliases.map((alias) => (
                    <div
                      key={alias.id}
                      className="flex min-w-0 items-center justify-between gap-2 rounded-md bg-muted/40 p-2"
                    >
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium">{alias.alias_label}</div>
                        <div className="text-xs text-muted-foreground">
                          {alias.alias_key}
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        disabled={deletePendingId === alias.id}
                        onClick={() => onDeleteAlias(alias)}
                        aria-label={t("common.delete")}
                      >
                        {deletePendingId === alias.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4 text-destructive" />
                        )}
                      </Button>
                    </div>
                  ))}
                </div>

                <div className="mt-3 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                  <AliasSuggestionInput
                    value={newAlias}
                    onChange={(value) =>
                      setNewAliases((prev) => ({
                        ...prev,
                        [group.canonical_key]: value,
                      }))
                    }
                    onSelectSuggestion={(suggestion) => {
                      onAddAlias(
                        group.canonical_key,
                        labelValue.trim() || group.canonical_label,
                        suggestion.alias_label,
                      );
                      setNewAliases((prev) => ({
                        ...prev,
                        [group.canonical_key]: "",
                      }));
                    }}
                    disabled={addPendingKey === group.canonical_key}
                    placement="top"
                  />
                  <Button
                    variant="outline"
                    disabled={!newAlias.trim() || addPendingKey === group.canonical_key}
                    onClick={() => {
                      onAddAlias(
                        group.canonical_key,
                        labelValue.trim() || group.canonical_label,
                        newAlias.trim(),
                      );
                      setNewAliases((prev) => ({
                        ...prev,
                        [group.canonical_key]: "",
                      }));
                    }}
                  >
                    {addPendingKey === group.canonical_key ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Plus className="mr-2 h-4 w-4" />
                    )}
                    {t("merchants.addToGroup")}
                  </Button>
                </div>
              </div>
            </details>
          );
        })}
      </CardContent>
    </Card>
  );
}
