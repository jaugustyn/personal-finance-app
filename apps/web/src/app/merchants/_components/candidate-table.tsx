"use client";

import { ChevronRight, Loader2 } from "lucide-react";

import type { MerchantCandidate } from "@/lib/api";
import { useFormatters, useT } from "@/lib/i18n";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { HelpTooltip } from "@/components/help-tooltip";
import { candidateVariants } from "../_lib/merchant-aliases";

export type MerchantCandidateSort = {
  id: "suggested_label" | "variants" | "count" | "total_debit";
  dir: "asc" | "desc";
};

export function CandidateTable({
  candidates,
  isLoading,
  isUpdating,
  sort,
  pendingKey,
  onOpen,
  onSortChange,
}: {
  candidates: MerchantCandidate[];
  isLoading: boolean;
  isUpdating: boolean;
  sort: MerchantCandidateSort;
  pendingKey: string | null;
  onOpen: (candidate: MerchantCandidate) => void;
  onSortChange: (sort: MerchantCandidateSort) => void;
}) {
  const { t } = useT();
  const { formatCurrency } = useFormatters();
  const columns: DataTableColumn<MerchantCandidate>[] = [
    {
      id: "suggested_label",
      header: t("merchants.candidate"),
      sortable: true,
      headerClassName: "w-64",
      className: "w-64",
      cell: (row) => (
        <div className="font-medium">{row.suggested_label}</div>
      ),
    },
    {
      id: "variants",
      header: t("merchants.variants"),
      sortable: true,
      headerClassName: "w-[26rem]",
      className: "w-[26rem]",
      cell: (row) => {
        const variants = candidateVariants(row);
        return (
          <div className="flex flex-wrap gap-1">
            {variants.slice(0, 6).map((variant) => (
              <Badge key={variant.alias_key} variant="muted">
                {variant.alias_label}
              </Badge>
            ))}
            {variants.length > 6 ? (
              <Badge variant="outline">+{variants.length - 6}</Badge>
            ) : null}
          </div>
        );
      },
    },
    {
      id: "count",
      header: t("merchants.transactionsCount"),
      sortable: true,
      headerClassName: "w-32 min-w-32 max-w-32",
      className: "w-32 min-w-32 max-w-32 tabular-nums",
      cell: (row) => row.count,
    },
    {
      id: "total_debit",
      header: t("merchants.totalExpenses"),
      sortable: true,
      headerClassName: "w-32 min-w-32 max-w-32",
      className: "w-32 min-w-32 max-w-32 tabular-nums",
      cell: (row) =>
        formatCurrency(Number(row.total_debit), row.base_currency),
    },
    {
      id: "actions",
      header: "",
      align: "center",
      headerClassName: "w-28 min-w-28 max-w-28",
      className: "w-28 min-w-28 max-w-28 px-2",
      cell: (row) => (
        <div className="flex justify-center">
          <Button
            size="sm"
            variant="outline"
            className="px-2.5"
            disabled={pendingKey === row.canonical_key}
            onClick={() => onOpen(row)}
          >
            {pendingKey === row.canonical_key ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : null}
            {t("merchants.reviewMerge")}
            {pendingKey !== row.canonical_key ? (
              <ChevronRight className="h-4 w-4" />
            ) : null}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <section className="space-y-3">
      <div className="flex min-h-9 items-center gap-2">
        <HelpTooltip content={t("merchants.candidatesHelp")}>
          <h2 className="text-base font-semibold">
            {t("merchants.candidatesTitle")}
          </h2>
        </HelpTooltip>
        <Badge variant="secondary">{candidates.length}</Badge>
        {isUpdating ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
        ) : null}
      </div>
      <DataTable
        columns={columns}
        data={candidates}
        isLoading={isLoading}
        rowKey={(row) => row.canonical_key}
        emptyTitle={t("merchants.candidatesEmpty")}
        className="bg-card [&_tbody_tr]:divide-x [&_tbody_tr]:divide-border/40 [&_thead_tr]:divide-x [&_thead_tr]:divide-border/40 [&_thead_tr]:bg-muted/30 [&_thead_tr:hover]:bg-muted/30"
        tableClassName="min-w-[1104px] table-fixed"
        sort={sort}
        onSortChange={(nextSort) =>
          onSortChange({
            id: nextSort.id as MerchantCandidateSort["id"],
            dir: nextSort.dir,
          })
        }
      />
    </section>
  );
}
