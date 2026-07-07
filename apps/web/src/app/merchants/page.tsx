"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import type { MerchantCandidate } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { ErrorState } from "@/components/error-state";
import { ClearableInput } from "@/components/ui/clearable-input";
import { PageHeader } from "@/components/page-header";
import { CardGridSkeleton } from "@/components/ui/skeleton";
import { AliasGroupsPanel } from "./_components/alias-groups-panel";
import { CandidateTable } from "./_components/candidate-table";
import { ManualAliasCard } from "./_components/manual-alias-card";
import { MergeCandidateDialog } from "./_components/merge-candidate-dialog";
import { MetricCard } from "./_components/metric-card";
import { candidateVariants, groupAliases } from "./_lib/merchant-aliases";
import { useMerchantAliases } from "./_lib/use-merchant-aliases";

export default function MerchantsPage() {
  const { t } = useT();
  const [search, setSearch] = useState(() => {
    if (typeof window === "undefined") return "";
    return new URLSearchParams(window.location.search).get("search") ?? "";
  });
  const [mergeCandidate, setMergeCandidate] = useState<MerchantCandidate | null>(
    null,
  );
  const {
    aliasesQuery,
    candidatesQuery,
    createAliases,
    updateLabel,
    deleteAlias,
    handleDeleteAlias,
  } = useMerchantAliases({
    onCreateSuccess: () => setMergeCandidate(null),
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
                canonical_label: candidate.canonical_label,
                aliases: candidateVariants(candidate).map((variant) => variant.alias_label),
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
