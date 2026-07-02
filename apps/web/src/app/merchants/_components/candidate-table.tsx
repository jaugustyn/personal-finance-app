"use client";

import { CheckCircle2, Loader2, Store } from "lucide-react";

import type { MerchantCandidate } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { formatCurrency } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { candidateVariants } from "../_lib/merchant-aliases";

export function CandidateTable({
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
