"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  CheckCircle2,
  Loader2,
  Plus,
  Save,
  Search,
  Store,
  Trash2,
} from "lucide-react";
import {
  api,
  type MerchantAlias,
  type MerchantAliasGroup,
  type MerchantAliasSuggestion,
  type MerchantCandidate,
  type MerchantCandidateVariant,
} from "@/lib/api";
import { useT } from "@/lib/i18n";
import { cn, formatCurrency } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { ClearableInput } from "@/components/ui/clearable-input";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/page-header";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CardGridSkeleton } from "@/components/ui/skeleton";
import { useConfirm } from "@/components/confirm-dialog";

const ALIASES_KEY = ["merchantAliases"] as const;
const CANDIDATES_KEY = ["merchantAliasCandidates"] as const;
const NEW_GROUP = "__new__";

function groupAliases(aliases: MerchantAlias[]): MerchantAliasGroup[] {
  const groups = new Map<string, MerchantAliasGroup>();
  for (const alias of aliases) {
    const existing = groups.get(alias.canonical_key);
    if (existing) {
      existing.aliases.push(alias);
    } else {
      groups.set(alias.canonical_key, {
        canonical_key: alias.canonical_key,
        canonical_label: alias.canonical_label,
        aliases: [alias],
      });
    }
  }
  return Array.from(groups.values())
    .map((group) => ({
      ...group,
      aliases: [...group.aliases].sort((a, b) =>
        a.alias_label.localeCompare(b.alias_label, "pl", { sensitivity: "base" }),
      ),
    }))
    .sort((a, b) =>
      a.canonical_label.localeCompare(b.canonical_label, "pl", {
        sensitivity: "base",
      }),
    );
}

function candidateVariants(
  candidate: MerchantCandidate,
): MerchantCandidateVariant[] {
  if ((candidate.variants ?? []).length > 0) return candidate.variants;
  return candidate.aliases.map((alias) => ({
    alias_key: alias,
    alias_label: alias,
    count: 0,
    total_debit: 0,
  }));
}

function invalidateMerchantQueries(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ALIASES_KEY });
  qc.invalidateQueries({ queryKey: CANDIDATES_KEY });
  qc.invalidateQueries({ queryKey: ["merchantAliasSuggestions"] });
  qc.invalidateQueries({ queryKey: ["overview"] });
  qc.invalidateQueries({ queryKey: ["topMerchants"] });
  qc.invalidateQueries({ queryKey: ["transactions"] });
  qc.invalidateQueries({ queryKey: ["review-summary"] });
  qc.invalidateQueries({ queryKey: ["review-queue"] });
  qc.invalidateQueries({ queryKey: ["ml"] });
  qc.invalidateQueries({ queryKey: ["recap"] });
  qc.invalidateQueries({ queryKey: ["anomalies"] });
  qc.invalidateQueries({ queryKey: ["subscriptions"] });
}

export default function MerchantsPage() {
  const { t } = useT();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [search, setSearch] = useState("");
  const [mergeCandidate, setMergeCandidate] = useState<MerchantCandidate | null>(
    null,
  );

  useEffect(() => {
    setSearch(new URLSearchParams(window.location.search).get("search") ?? "");
  }, []);

  const aliasesQuery = useQuery<MerchantAlias[]>({
    queryKey: ALIASES_KEY,
    queryFn: () => api.merchantAliases(),
  });
  const candidatesQuery = useQuery<MerchantCandidate[]>({
    queryKey: CANDIDATES_KEY,
    queryFn: () => api.merchantAliasCandidates(),
  });

  const groups = useMemo(
    () => groupAliases(aliasesQuery.data ?? []),
    [aliasesQuery.data],
  );
  const normalizedSearch = search.trim().toLowerCase();
  const filteredGroups = useMemo(() => {
    if (!normalizedSearch) return groups;
    return groups.filter((group) => {
      const haystack = [
        group.canonical_key,
        group.canonical_label,
        ...group.aliases.flatMap((alias) => [alias.alias_key, alias.alias_label]),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(normalizedSearch);
    });
  }, [groups, normalizedSearch]);
  const filteredCandidates = useMemo(() => {
    const candidates = candidatesQuery.data ?? [];
    if (!normalizedSearch) return candidates;
    return candidates.filter((candidate) => {
      const haystack = [
        candidate.canonical_key,
        candidate.suggested_label,
        ...candidateVariants(candidate).flatMap((variant) => [
          variant.alias_key,
          variant.alias_label,
        ]),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(normalizedSearch);
    });
  }, [candidatesQuery.data, normalizedSearch]);
  const aliasCount = filteredGroups.reduce(
    (sum, group) => sum + group.aliases.length,
    0,
  );
  const candidateCount = filteredCandidates.length;

  const createAliases = useMutation({
    mutationFn: (payload: {
      canonical_label: string;
      canonical_key?: string | null;
      aliases: string[];
    }) => api.createMerchantAliases(payload),
    onSuccess: () => {
      invalidateMerchantQueries(qc);
      toast.success(t("toast.saved"));
      setMergeCandidate(null);
    },
    onError: () => toast.error(t("toast.error")),
  });

  const updateLabel = useMutation({
    mutationFn: (payload: { canonical_key: string; canonical_label: string }) =>
      api.updateMerchantAliasGroupLabel(payload),
    onSuccess: () => {
      invalidateMerchantQueries(qc);
      toast.success(t("toast.saved"));
    },
    onError: () => toast.error(t("toast.error")),
  });

  const deleteAlias = useMutation({
    mutationFn: (id: number) => api.deleteMerchantAlias(id),
    onSuccess: () => {
      invalidateMerchantQueries(qc);
      toast.success(t("toast.deleted"));
    },
    onError: () => toast.error(t("toast.error")),
  });

  const handleDeleteAlias = async (alias: MerchantAlias) => {
    const ok = await confirm({
      title: t("merchants.deleteAliasTitle"),
      description: t("merchants.deleteAliasDescription", {
        alias: alias.alias_label,
      }),
      confirmLabel: t("common.delete"),
      destructive: true,
    });
    if (ok) deleteAlias.mutate(alias.id);
  };

  const isLoading = aliasesQuery.isLoading || candidatesQuery.isLoading;
  const isError = aliasesQuery.isError || candidatesQuery.isError;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("merchants.title")}
        description={t("merchants.subtitle")}
      />

      {isLoading ? (
        <CardGridSkeleton />
      ) : isError ? (
        <ErrorState
          onRetry={() => {
            aliasesQuery.refetch();
            candidatesQuery.refetch();
          }}
        />
      ) : (
        <>
          <div className="grid items-stretch gap-3 sm:grid-cols-3 lg:grid-cols-[minmax(18rem,2fr)_repeat(3,minmax(7rem,1fr))]">
            <ClearableInput
              value={search}
              onValueChange={setSearch}
              placeholder={t("common.search")}
              clearLabel={t("common.clear")}
              className="h-14 sm:col-span-3 lg:col-span-1"
              inputClassName="h-full"
              leftIcon={<Search className="h-4 w-4" />}
            />
            <MetricCard
              label={t("merchants.metricCandidates")}
              value={candidateCount}
            />
            <MetricCard label={t("merchants.metricGroups")} value={filteredGroups.length} />
            <MetricCard label={t("merchants.metricAliases")} value={aliasCount} />
          </div>

          <ManualAliasCard
            groups={groups}
            isPending={createAliases.isPending}
            onCreate={(payload) => createAliases.mutate(payload)}
          />

          <CandidateTable
            candidates={filteredCandidates}
            pendingKey={
              createAliases.isPending
                ? createAliases.variables?.canonical_key ?? mergeCandidate?.canonical_key ?? null
                : null
            }
            onOpen={setMergeCandidate}
            onAccept={(candidate) =>
              createAliases.mutate({
                canonical_key: candidate.canonical_key,
                canonical_label: candidate.suggested_label,
                aliases: candidateVariants(candidate).map((variant) => variant.alias_key),
              })
            }
          />

          <AliasGroupsPanel
            groups={filteredGroups}
            labelPendingKey={
              updateLabel.isPending
                ? updateLabel.variables?.canonical_key ?? null
                : null
            }
            deletePendingId={
              deleteAlias.isPending ? deleteAlias.variables ?? null : null
            }
            addPendingKey={
              createAliases.isPending
                ? createAliases.variables?.canonical_key ?? null
                : null
            }
            onUpdateLabel={(canonical_key, canonical_label) =>
              updateLabel.mutate({ canonical_key, canonical_label })
            }
            onAddAlias={(canonical_key, canonical_label, alias) =>
              createAliases.mutate({
                canonical_key,
                canonical_label,
                aliases: [alias],
              })
            }
            onDeleteAlias={handleDeleteAlias}
          />

          <MergeCandidateDialog
            candidate={mergeCandidate}
            open={mergeCandidate !== null}
            isPending={createAliases.isPending}
            onOpenChange={(open) => !open && setMergeCandidate(null)}
            onSave={(payload) => createAliases.mutate(payload)}
          />
        </>
      )}
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <Card className="h-14">
      <CardContent className="flex h-full flex-col justify-center px-3 py-2">
        <div className="truncate text-[11px] leading-4 text-muted-foreground">{label}</div>
        <div className="text-lg font-semibold leading-6 tabular-nums">{value}</div>
      </CardContent>
    </Card>
  );
}

function ManualAliasCard({
  groups,
  isPending,
  onCreate,
}: {
  groups: MerchantAliasGroup[];
  isPending: boolean;
  onCreate: (payload: {
    canonical_label: string;
    canonical_key?: string | null;
    aliases: string[];
  }) => void;
}) {
  const { t } = useT();
  const [aliasLabel, setAliasLabel] = useState("");
  const [groupKey, setGroupKey] = useState(NEW_GROUP);
  const selectedGroup = groups.find((group) => group.canonical_key === groupKey);
  const [canonicalLabel, setCanonicalLabel] = useState("");

  useEffect(() => {
    if (selectedGroup) setCanonicalLabel(selectedGroup.canonical_label);
  }, [selectedGroup]);

  const canSave = aliasLabel.trim() && canonicalLabel.trim();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Plus className="h-4 w-4 text-muted-foreground" />
          {t("merchants.manualTitle")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 lg:grid-cols-[1.3fr_1fr_1.3fr_auto]">
          <Input
            value={aliasLabel}
            onChange={(event) => setAliasLabel(event.target.value)}
            placeholder={t("merchants.aliasPlaceholder")}
          />
          <Select
            value={groupKey}
            onValueChange={(value) => {
              setGroupKey(value);
              const group = groups.find((item) => item.canonical_key === value);
              setCanonicalLabel(group?.canonical_label ?? "");
            }}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NEW_GROUP}>{t("merchants.newGroup")}</SelectItem>
              {groups.map((group) => (
                <SelectItem key={group.canonical_key} value={group.canonical_key}>
                  {group.canonical_label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            value={canonicalLabel}
            onChange={(event) => setCanonicalLabel(event.target.value)}
            placeholder={t("merchants.displayLabelPlaceholder")}
          />
          <Button
            disabled={!canSave || isPending}
            onClick={() => {
              onCreate({
                canonical_key: selectedGroup?.canonical_key,
                canonical_label: canonicalLabel.trim(),
                aliases: [aliasLabel.trim()],
              });
              setAliasLabel("");
              if (!selectedGroup) setCanonicalLabel("");
            }}
          >
            {isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Plus className="mr-2 h-4 w-4" />
            )}
            {t("common.add")}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function CandidateTable({
  candidates,
  pendingKey,
  onOpen,
  onAccept,
}: {
  candidates: MerchantCandidate[];
  pendingKey: string | null;
  onOpen: (candidate: MerchantCandidate) => void;
  onAccept: (candidate: MerchantCandidate) => void;
}) {
  const { t } = useT();
  const columns: DataTableColumn<MerchantCandidate>[] = [
    {
      id: "suggested_label",
      header: t("merchants.candidate"),
      sortValue: (row) => row.suggested_label,
      cell: (row) => (
        <div>
          <div className="font-medium">{row.suggested_label}</div>
          <div className="text-xs text-muted-foreground">{row.canonical_key}</div>
        </div>
      ),
    },
    {
      id: "variants",
      header: t("merchants.variants"),
      sortValue: (row) => candidateVariants(row).length,
      cell: (row) => (
        <div className="flex flex-wrap gap-1">
          {candidateVariants(row)
            .slice(0, 6)
            .map((variant) => (
              <Badge key={variant.alias_key} variant="muted">
                {variant.alias_label}
              </Badge>
            ))}
        </div>
      ),
    },
    {
      id: "count",
      header: t("review.count"),
      align: "right",
      className: "tabular-nums",
      sortValue: (row) => row.count,
      cell: (row) => row.count,
    },
    {
      id: "total_debit",
      header: t("transactions.column.amount"),
      align: "right",
      className: "tabular-nums",
      sortValue: (row) => Number(row.total_debit),
      cell: (row) => formatCurrency(Number(row.total_debit)),
    },
    {
      id: "actions",
      header: "",
      align: "right",
      headerClassName: "w-52",
      className: "w-52",
      cell: (row) => (
        <div className="flex justify-end gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={pendingKey === row.canonical_key}
            onClick={() => onOpen(row)}
          >
            {pendingKey === row.canonical_key ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle2 className="mr-2 h-4 w-4" />
            )}
            {t("merchants.reviewMerge")}
          </Button>
          <Button
            size="sm"
            disabled={pendingKey === row.canonical_key}
            onClick={() => onAccept(row)}
          >
            {pendingKey === row.canonical_key ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle2 className="mr-2 h-4 w-4" />
            )}
            {t("merchants.acceptMerge")}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Store className="h-4 w-4 text-muted-foreground" />
          {t("merchants.candidatesTitle")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <DataTable
          columns={columns}
          data={candidates}
          rowKey={(row) => row.canonical_key}
          emptyTitle={t("merchants.candidatesEmpty")}
          initialSort={{ id: "count", dir: "desc" }}
        />
      </CardContent>
    </Card>
  );
}

function AliasGroupsPanel({
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

  useEffect(() => {
    setLabels(
      Object.fromEntries(
        groups.map((group) => [group.canonical_key, group.canonical_label]),
      ),
    );
  }, [groups]);

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

function AliasSuggestionInput({
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
    queryKey: ["merchantAliasSuggestions", query],
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

function MergeCandidateDialog({
  candidate,
  open,
  isPending,
  onOpenChange,
  onSave,
}: {
  candidate: MerchantCandidate | null;
  open: boolean;
  isPending: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (payload: {
    canonical_label: string;
    canonical_key?: string | null;
    aliases: string[];
  }) => void;
}) {
  const { t } = useT();
  const [label, setLabel] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [extraAliasInput, setExtraAliasInput] = useState("");
  const [extraAliases, setExtraAliases] = useState<MerchantAliasSuggestion[]>([]);
  const variants = useMemo(
    () => (candidate ? candidateVariants(candidate) : []),
    [candidate],
  );

  useEffect(() => {
    if (!candidate || !open) return;
    setLabel(candidate.suggested_label);
    setSelected(new Set(candidateVariants(candidate).map((variant) => variant.alias_key)));
    setExtraAliasInput("");
    setExtraAliases([]);
  }, [candidate, open]);

  const selectedVariants = variants.filter((variant) => selected.has(variant.alias_key));
  const excludedAliasKeys = new Set([
    ...variants.map((variant) => variant.alias_key),
    ...extraAliases.map((alias) => alias.alias_key),
  ]);
  const total = selectedVariants.reduce(
    (sum, variant) => sum + Number(variant.total_debit || 0),
    0,
  ) + extraAliases.reduce(
    (sum, alias) => sum + Number(alias.total_amount || 0),
    0,
  );
  const selectedCount = selectedVariants.length + extraAliases.length;
  const canSave = Boolean(candidate && label.trim() && selectedCount > 0);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t("merchants.mergeDialogTitle")}</DialogTitle>
          <DialogDescription>
            {t("merchants.mergeDialogDescription")}
          </DialogDescription>
        </DialogHeader>

        {candidate ? (
          <div className="space-y-4">
            <label className="space-y-1 text-sm">
              <span>{t("merchants.displayLabel")}</span>
              <Input
                value={label}
                onChange={(event) => setLabel(event.target.value)}
              />
            </label>

            <div className="max-h-80 space-y-2 overflow-y-auto rounded-lg border p-3">
              {variants.map((variant) => {
                const checked = selected.has(variant.alias_key);
                return (
                  <label
                    key={variant.alias_key}
                    className={cn(
                      "flex cursor-pointer items-start gap-3 rounded-md p-2",
                      checked ? "bg-muted" : "hover:bg-muted/60",
                    )}
                  >
                    <Checkbox
                      checked={checked}
                      onCheckedChange={(value) => {
                        setSelected((prev) => {
                          const next = new Set(prev);
                          if (value) next.add(variant.alias_key);
                          else next.delete(variant.alias_key);
                          return next;
                        });
                      }}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">
                        {variant.alias_label}
                      </div>
                      <div className="truncate text-xs text-muted-foreground">
                        {variant.alias_key}
                      </div>
                    </div>
                    <div className="text-right text-xs text-muted-foreground">
                      <div className="tabular-nums">{variant.count}</div>
                      <div className="tabular-nums">
                        {formatCurrency(Number(variant.total_debit))}
                      </div>
                    </div>
                  </label>
                );
              })}
            </div>

            <div className="space-y-2">
              <div className="text-sm font-medium">
                {t("merchants.mergeAdditionalAliases")}
              </div>
              <AliasSuggestionInput
                value={extraAliasInput}
                onChange={setExtraAliasInput}
                excludeKeys={excludedAliasKeys}
                onSelectSuggestion={(suggestion) => {
                  setExtraAliases((prev) =>
                    prev.some((alias) => alias.alias_key === suggestion.alias_key)
                      ? prev
                      : [...prev, suggestion],
                  );
                  setExtraAliasInput("");
                }}
              />
              {extraAliases.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {extraAliases.map((alias) => (
                    <Badge
                      key={alias.alias_key}
                      variant="secondary"
                      className="gap-2 pr-1"
                    >
                      <span className="max-w-52 truncate">{alias.alias_label}</span>
                      <button
                        type="button"
                        className="rounded-sm px-1 text-muted-foreground hover:text-foreground"
                        onClick={() =>
                          setExtraAliases((prev) =>
                            prev.filter((item) => item.alias_key !== alias.alias_key),
                          )
                        }
                        aria-label={t("common.delete")}
                      >
                        x
                      </button>
                    </Badge>
                  ))}
                </div>
              ) : null}
            </div>

            <div className="rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">
              {t("merchants.mergeSummary", {
                count: selectedCount,
                amount: formatCurrency(total),
              })}
            </div>
          </div>
        ) : null}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("common.cancel")}
          </Button>
          <Button
            disabled={!canSave || isPending}
            onClick={() =>
              candidate &&
              onSave({
                canonical_key: candidate.canonical_key,
                canonical_label: label.trim(),
                aliases: [
                  ...selectedVariants.map((variant) => variant.alias_label),
                  ...extraAliases.map((alias) => alias.alias_label),
                ],
              })
            }
          >
            {isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            {t("merchants.saveAliases")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
