"use client";

import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import type { MerchantCandidate } from "@/lib/api";
import { useFormatters, useT } from "@/lib/i18n";
import { ErrorState } from "@/components/error-state";
import { FilterField, FilterPanel } from "@/components/filter-panel";
import { ClearableInput } from "@/components/ui/clearable-input";
import { PageHeader } from "@/components/page-header";
import { AliasGroupsPanel } from "./_components/alias-groups-panel";
import {
  CandidateTable,
  type MerchantCandidateSort,
} from "./_components/candidate-table";
import { ManualAliasDialog } from "./_components/manual-alias-dialog";
import { MergeCandidateDialog } from "./_components/merge-candidate-dialog";
import { groupAliases } from "./_lib/merchant-aliases";
import { useMerchantAliases } from "./_lib/use-merchant-aliases";

function updateSearchUrl(value: string) {
  const url = new URL(window.location.href);
  if (value.trim()) url.searchParams.set("search", value.trim());
  else url.searchParams.delete("search");
  window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

export default function MerchantsPage() {
  const { t } = useT();
  const { compare } = useFormatters();
  const [search, setSearch] = useState("");
  const [candidateSearch, setCandidateSearch] = useState(search.trim());
  const [candidateSort, setCandidateSort] = useState<MerchantCandidateSort>({
    id: "count",
    dir: "desc",
  });
  const [mergeCandidate, setMergeCandidate] = useState<MerchantCandidate | null>(
    null,
  );
  const [manualAliasOpen, setManualAliasOpen] = useState(false);

  useEffect(() => {
    const initialSearch =
      new URLSearchParams(window.location.search).get("search") ?? "";
    // eslint-disable-next-line react-hooks/set-state-in-effect -- URL state is client-only and must not affect hydration
    setSearch(initialSearch);
    setCandidateSearch(initialSearch.trim());
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(
      () => setCandidateSearch(search.trim()),
      250,
    );
    return () => window.clearTimeout(timeoutId);
  }, [search]);

  const {
    aliasesQuery,
    candidatesQuery,
    createAliases,
    updateLabel,
    deleteAlias,
    handleDeleteAlias,
  } = useMerchantAliases({
    candidateSearch,
    candidateSort,
    onCreateSuccess: () => {
      setMergeCandidate(null);
      setManualAliasOpen(false);
    },
  });

  const groups = useMemo(
    () => groupAliases(aliasesQuery.data ?? [], compare),
    [aliasesQuery.data, compare],
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
  return (
    <div className="space-y-5">
      <PageHeader
        title={t("merchants.title")}
        description={t("merchants.subtitle")}
      />

      <FilterPanel gridClassName="md:grid-cols-[minmax(18rem,30rem)] xl:grid-cols-[minmax(18rem,30rem)]">
        <FilterField label={t("common.search")}>
          <ClearableInput
            value={search}
            onValueChange={(value) => {
              setSearch(value);
              updateSearchUrl(value);
            }}
            placeholder={t("merchants.searchPlaceholder")}
            clearLabel={t("common.clear")}
            leftIcon={<Search className="h-4 w-4" />}
          />
        </FilterField>
      </FilterPanel>

      {candidatesQuery.isError ? (
        <ErrorState onRetry={() => candidatesQuery.refetch()} />
      ) : (
        <CandidateTable
          key={candidateSearch}
          candidates={candidatesQuery.data ?? []}
          isLoading={candidatesQuery.isLoading}
          isUpdating={candidatesQuery.isFetching && !candidatesQuery.isLoading}
          sort={candidateSort}
          pendingKey={
            createAliases.isPending
              ? createAliases.variables?.canonical_key ??
                mergeCandidate?.canonical_key ??
                null
              : null
          }
          onOpen={setMergeCandidate}
          onSortChange={setCandidateSort}
        />
      )}

      {aliasesQuery.isError ? (
        <ErrorState onRetry={() => aliasesQuery.refetch()} />
      ) : (
        <AliasGroupsPanel
          groups={filteredGroups}
          isLoading={aliasesQuery.isLoading}
          isFiltered={Boolean(normalizedSearch)}
          onAddManual={() => setManualAliasOpen(true)}
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
      )}

      {manualAliasOpen ? (
        <ManualAliasDialog
          open
          groups={groups}
          isPending={createAliases.isPending}
          onOpenChange={setManualAliasOpen}
          onCreate={(payload) => createAliases.mutate(payload)}
        />
      ) : null}

      <MergeCandidateDialog
        candidate={mergeCandidate}
        open={mergeCandidate !== null}
        isPending={createAliases.isPending}
        onOpenChange={(open) => !open && setMergeCandidate(null)}
        onSave={(payload) => createAliases.mutate(payload)}
      />
    </div>
  );
}
