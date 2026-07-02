"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CategoryCombobox } from "@/components/category-combobox";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TableSkeleton } from "@/components/ui/skeleton";
import { api, type MerchantGroup } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { formatCurrency } from "@/lib/utils";
import { transactionQueryKeys } from "../_lib/query-keys";

export function GroupsView() {
  const { t } = useT();
  const qc = useQueryClient();
  const [onlyUncat, setOnlyUncat] = useState(true);
  const [pickers, setPickers] = useState<Record<string, string | null>>({});

  const query = useQuery<MerchantGroup[]>({
    queryKey: transactionQueryKeys.groups({ onlyUncategorized: onlyUncat }),
    queryFn: () =>
      api.merchantGroups({ only_uncategorized: onlyUncat, min_count: 2 }),
  });

  const apply = useMutation({
    mutationFn: (vars: {
      merchantCanonicalKey: string;
      category: string | null;
    }) =>
      api.bulkCategorize({
        merchant_canonical_key: vars.merchantCanonicalKey,
        category: vars.category,
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: transactionQueryKeys.all });
      setPickers((p) => {
        const next = { ...p };
        delete next[vars.merchantCanonicalKey];
        return next;
      });
    },
  });
  const groupNet = (g: MerchantGroup) => {
    const debit = Math.abs(Number(g.total_debit) || 0);
    const credit = Math.abs(Number(g.total_credit) || 0);
    return credit - debit;
  };
  const columns: DataTableColumn<MerchantGroup>[] = [
    {
      id: "merchant",
      header: t("transactions.column.merchant"),
      sortValue: (g) => g.merchant,
      className: "font-medium",
      cell: (g) => {
        const merchantDisplay = g.merchant_display || g.merchant;
        const rawMerchants = (g.sample_merchants ?? []).filter(
          (merchant) => !sameDisplayText(merchant, merchantDisplay),
        );
        return (
          <>
            <div className="truncate">{merchantDisplay}</div>
            {rawMerchants.length > 0 ? (
              <div className="line-clamp-1 text-xs font-normal text-muted-foreground">
                {t("transactions.originalMerchant", {
                  value: rawMerchants.slice(0, 3).join(" · "),
                })}
              </div>
            ) : null}
            {g.sample_titles.length > 0 ? (
              <div className="line-clamp-1 text-xs text-muted-foreground">
                {t("transactions.sourceTitle", {
                  value: g.sample_titles.slice(0, 2).join(" · "),
                })}
              </div>
            ) : null}
          </>
        );
      },
    },
    {
      id: "amount",
      header: t("transactions.column.amount"),
      align: "right",
      headerClassName: "w-36",
      className: "w-36 tabular-nums",
      sortValue: groupNet,
      cell: (g) => {
        const net = groupNet(g);
        return (
          <span
            className={
              net < 0
                ? "text-red-600 dark:text-red-400"
                : "text-emerald-600 dark:text-emerald-400"
            }
          >
            {formatCurrency(net, "PLN")}
          </span>
        );
      },
    },
    {
      id: "count",
      header: "#",
      align: "center",
      headerClassName: "w-16",
      className: "w-16 text-muted-foreground",
      sortValue: (g) => g.count,
      cell: (g) => g.count,
    },
    {
      id: "category",
      header: t("transactions.column.category"),
      headerClassName: "w-64",
      className: "w-64",
      sortValue: (g) => g.common_category ?? "",
      cell: (g) => {
        const picked =
          g.merchant_canonical_key in pickers
            ? pickers[g.merchant_canonical_key]
            : (g.common_category ?? null);
        return (
          <CategoryCombobox
            value={picked}
            onChange={(sel) =>
              setPickers((p) => ({
                ...p,
                [g.merchant_canonical_key]: sel.category,
              }))
            }
            groupsOnly
            size="md"
            className="w-60"
          />
        );
      },
    },
    {
      id: "actions",
      header: "",
      headerClassName: "w-28",
      className: "w-28",
      cell: (g) => {
        const picked =
          g.merchant_canonical_key in pickers
            ? pickers[g.merchant_canonical_key]
            : (g.common_category ?? null);
        return (
          <Button
            size="sm"
            disabled={apply.isPending || !picked}
            onClick={() =>
              apply.mutate({
                merchantCanonicalKey: g.merchant_canonical_key,
                category: picked,
              })
            }
          >
            {t("transactions.groups.apply")}
          </Button>
        );
      },
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          {t("transactions.groups.title")}
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          {t("transactions.groups.help")}
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={onlyUncat}
            onChange={(e) => setOnlyUncat(e.target.checked)}
            className="h-4 w-4"
          />
          {t("transactions.groups.onlyUncategorized")}
        </label>

        {query.isLoading ? (
          <TableSkeleton rows={6} />
        ) : (query.data ?? []).length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            {t("transactions.groups.empty")}
          </p>
        ) : (
          <DataTable
            columns={columns}
            data={query.data ?? []}
            rowKey={(g) => g.merchant_canonical_key}
            initialSort={{ id: "count", dir: "desc" }}
            tableClassName="min-w-[760px] table-fixed"
          />
        )}
      </CardContent>
    </Card>
  );
}

function sameDisplayText(
  left: string | null | undefined,
  right: string | null | undefined,
) {
  return normalizeDisplayText(left) === normalizeDisplayText(right);
}

function normalizeDisplayText(value: string | null | undefined) {
  return (value ?? "").trim().replace(/\s+/g, " ").toLocaleLowerCase("pl");
}
