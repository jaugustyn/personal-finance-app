"use client";

import { useState } from "react";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { CategoryCombobox } from "@/components/category-combobox";
import { FilterField } from "@/components/filter-panel";
import { FilterSelect } from "@/components/filter-select";
import { DEFAULT_TABLE_PAGE_SIZE } from "@/components/table-pagination";
import {
  DataTable,
  type DataTableColumn,
  type DataTableSortState,
} from "@/components/data-table";
import { Button } from "@/components/ui/button";
import { TableSkeleton } from "@/components/ui/skeleton";
import {
  api,
  type MerchantGroup,
  type MerchantGroupSortBy,
  type TransactionSortDirection,
} from "@/lib/api";
import { useFormatters, useT } from "@/lib/i18n";
import { invalidateTransactionData, queryKeys } from "@/lib/query-keys";
import { showErrorToast } from "@/lib/toasts";

export function GroupsView() {
  const { t } = useT();
  const { formatCurrency } = useFormatters();
  const qc = useQueryClient();
  const [onlyUncat, setOnlyUncat] = useState(true);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(DEFAULT_TABLE_PAGE_SIZE);
  const [sort, setSort] = useState<Exclude<DataTableSortState, null>>({
    id: "count",
    dir: "desc",
  });
  const [pickers, setPickers] = useState<Record<string, string | null>>({});

  const query = useQuery<MerchantGroup[]>({
    queryKey: queryKeys.transactions.groups({
      onlyUncategorized: onlyUncat,
      minCount: 2,
      page,
      pageSize,
      sortBy: sort.id,
      sortDirection: sort.dir,
    }),
    queryFn: () =>
      api.merchantGroups({
        only_uncategorized: onlyUncat,
        min_count: 2,
        limit: pageSize + 1,
        offset: page * pageSize,
        sort_by: sort.id as MerchantGroupSortBy,
        sort_direction: sort.dir as TransactionSortDirection,
      }),
    placeholderData: keepPreviousData,
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
      void invalidateTransactionData(qc);
      setPickers((p) => {
        const next = { ...p };
        delete next[vars.merchantCanonicalKey];
        return next;
      });
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });
  const groupNet = (g: MerchantGroup) => {
    const debit = Math.abs(Number(g.total_debit) || 0);
    const credit = Math.abs(Number(g.total_credit) || 0);
    return credit - debit;
  };
  const rows = (query.data ?? []).slice(0, pageSize);
  const hasNextPage = (query.data?.length ?? 0) > pageSize;
  const columns: DataTableColumn<MerchantGroup>[] = [
    {
      id: "merchant",
      header: t("transactions.column.merchant"),
      sortable: true,
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
      sortable: true,
      align: "right",
      headerClassName: "w-36",
      className: "w-36 tabular-nums",
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
      sortable: true,
      align: "right",
      headerClassName: "w-16",
      className: "w-16 tabular-nums text-muted-foreground",
      cell: (g) => g.count,
    },
    {
      id: "category",
      header: t("transactions.column.category"),
      sortable: true,
      headerClassName: "w-64",
      className: "w-64",
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
      align: "center",
      headerClassName: "w-28",
      className: "w-28",
      cell: (g) => {
        const picked =
          g.merchant_canonical_key in pickers
            ? pickers[g.merchant_canonical_key]
            : (g.common_category ?? null);
        return (
          <div className="flex justify-center">
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
          </div>
        );
      },
    },
  ];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-3 rounded-lg border bg-card p-3 shadow-sm">
        <FilterField
          label={t("transactions.groups.scopeLabel")}
          className="w-[14rem] shrink-0"
        >
          <FilterSelect
            value={onlyUncat ? "unassigned" : "all"}
            onValueChange={(value) => {
              setOnlyUncat(value === "unassigned");
              setPage(0);
            }}
            ariaLabel={t("transactions.groups.scopeLabel")}
            options={[
              {
                value: "all",
                label: t("transactions.groups.scopeAll"),
                muted: true,
              },
              {
                value: "unassigned",
                label: t("transactions.groups.scopeUnassigned"),
              },
            ]}
          />
        </FilterField>
      </div>

      {query.isLoading ? (
        <div className="rounded-lg border bg-card p-3">
          <TableSkeleton rows={6} />
        </div>
      ) : query.isError ? (
        <DataTable
          key={onlyUncat ? "unassigned" : "all"}
          columns={columns}
          data={undefined}
          rowKey={(g) => g.merchant_canonical_key}
          isError
          onRetry={() => void query.refetch()}
        />
      ) : rows.length === 0 && page === 0 ? (
        <div className="flex h-40 items-center justify-center rounded-lg border bg-card text-sm text-muted-foreground">
          <p>
            {t(
              onlyUncat
                ? "transactions.groups.empty"
                : "transactions.groups.emptyAll",
            )}
          </p>
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={rows}
          rowKey={(g) => g.merchant_canonical_key}
          tableClassName="min-w-[760px] table-fixed"
          sort={sort}
          onSortChange={(nextSort) => {
            setSort(nextSort);
            setPage(0);
          }}
          pagination={{
            mode: "server",
            page,
            pageSize,
            hasNext: hasNextPage,
            onPageChange: setPage,
            onPageSizeChange: (nextPageSize) => {
              setPageSize(nextPageSize);
              setPage(0);
            },
          }}
        />
      )}
    </div>
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
