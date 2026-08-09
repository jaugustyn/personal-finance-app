"use client";

import { useMemo, useState } from "react";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Check } from "lucide-react";
import { CategoryCompactAccent } from "@/components/category-accent";
import { CategoryCombobox } from "@/components/category-combobox";
import { SegmentedControl } from "@/components/segmented-control";
import { DEFAULT_TABLE_PAGE_SIZE } from "@/components/table-pagination";
import {
  DataTable,
  type DataTableColumn,
  type DataTableSortState,
} from "@/components/data-table";
import { Button } from "@/components/ui/button";
import { useCategories } from "@/hooks/use-categories";
import {
  api,
  type MerchantGroup,
  type MerchantGroupPage,
  type MerchantGroupSortBy,
  type TransactionSortDirection,
} from "@/lib/api";
import { tCategory, useFormatters, useT } from "@/lib/i18n";
import { invalidateTransactionData, queryKeys } from "@/lib/query-keys";
import { showErrorToast } from "@/lib/toasts";
import { AssignmentValue } from "./assignment-value";
import { EmptyCategoryValue } from "./transaction-category-cell";

export function GroupsView() {
  const { t } = useT();
  const { formatCurrency } = useFormatters();
  const { data: categories = [] } = useCategories();
  const categoryColors = useMemo(
    () => new Map(categories.map((category) => [category.name, category.color])),
    [categories],
  );
  const qc = useQueryClient();
  const [onlyUncat, setOnlyUncat] = useState(true);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(DEFAULT_TABLE_PAGE_SIZE);
  const [sort, setSort] = useState<Exclude<DataTableSortState, null>>({
    id: "count",
    dir: "desc",
  });
  const [pickers, setPickers] = useState<Record<string, string | null>>({});

  const query = useQuery<MerchantGroupPage>({
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
        limit: pageSize,
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
  const rows = query.data?.items ?? [];
  const total = query.data?.total;
  const hasNextPage =
    total !== undefined && (page + 1) * pageSize < total;
  const columns: DataTableColumn<MerchantGroup>[] = [
    {
      id: "merchant",
      header: t("transactions.column.merchant"),
      sortable: true,
      headerClassName: "border-r border-border/50",
      className: "border-r border-border/50 font-medium",
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
      headerClassName: "w-52 border-r border-border/50",
      className: "w-52 border-r border-border/50 tabular-nums",
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
      align: "center",
      headerClassName: "w-16 border-r border-border/50",
      className:
        "w-16 border-r border-border/50 tabular-nums text-muted-foreground",
      cell: (g) => g.count,
    },
    {
      id: "category",
      header: t("transactions.column.category"),
      sortable: true,
      headerClassName: "w-52 border-r border-border/50",
      className: "w-52 border-r border-border/50",
      cell: (g) => {
        const hasPendingChoice = g.merchant_canonical_key in pickers;
        const picked =
          hasPendingChoice
            ? pickers[g.merchant_canonical_key]
            : (g.common_category ?? null);
        if (hasPendingChoice) {
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
              autoFocus
              size="sm"
              className="mx-auto"
            />
          );
        }
        if (g.common_category) {
          return (
            <AssignmentValue
              label={tCategory(t, g.common_category)}
              icon={
                <CategoryCompactAccent
                  color={categoryColors.get(g.common_category) ?? null}
                />
              }
              onEdit={() =>
                setPickers((current) => ({
                  ...current,
                  [g.merchant_canonical_key]: g.common_category,
                }))
              }
              title={t("transactions.editCategory")}
            />
          );
        }
        return (
          <EmptyCategoryValue
            applicable
            onAssign={() =>
              setPickers((current) => ({
                ...current,
                [g.merchant_canonical_key]: null,
              }))
            }
          />
        );
      },
    },
    {
      id: "actions",
      header: "",
      align: "center",
      headerClassName: "w-12",
      className: "w-12 px-1",
      cell: (g) => {
        const hasPendingChoice = g.merchant_canonical_key in pickers;
        const picked =
          hasPendingChoice
            ? pickers[g.merchant_canonical_key]
            : (g.common_category ?? null);
        return (
          <div className="flex justify-center">
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-positive hover:text-positive"
              disabled={apply.isPending || !hasPendingChoice || !picked}
              onClick={() =>
                apply.mutate({
                  merchantCanonicalKey: g.merchant_canonical_key,
                  category: picked,
                })
              }
              title={t("transactions.groups.assignHint", { n: g.count })}
              aria-label={t("transactions.groups.assignHint", { n: g.count })}
            >
              <Check className="h-4 w-4" />
            </Button>
          </div>
        );
      },
    },
  ];

  return (
    <div className="space-y-5">
      <div className="flex min-h-12 flex-wrap items-center gap-4 px-1 py-2">
        <SegmentedControl
          value={onlyUncat ? "unassigned" : "all"}
          onValueChange={(value) => {
            setOnlyUncat(value === "unassigned");
            setPage(0);
          }}
          ariaLabel={t("transactions.groups.scopeLabel")}
          options={[
            {
              value: "unassigned",
              label: t("transactions.groups.scopeUnassigned"),
            },
            {
              value: "all",
              label: t("transactions.groups.scopeAll"),
            },
          ]}
        />
      </div>

      <DataTable
        columns={columns}
        data={query.isLoading ? undefined : rows}
        rowKey={(g) => g.merchant_canonical_key}
        isLoading={query.isLoading}
        isError={query.isError}
        onRetry={() => void query.refetch()}
        emptyTitle={t(
          onlyUncat
            ? "transactions.groups.empty"
            : "transactions.groups.emptyAll",
        )}
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
          total,
          hasNext: hasNextPage,
          onPageChange: setPage,
          onPageSizeChange: (nextPageSize) => {
            setPageSize(nextPageSize);
            setPage(0);
          },
          alwaysVisible: true,
        }}
      />
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
