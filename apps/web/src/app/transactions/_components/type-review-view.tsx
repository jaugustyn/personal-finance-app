"use client";

import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { ErrorState } from "@/components/error-state";
import { Money } from "@/components/money";
import { TransactionTypeCombobox } from "@/components/transaction-type-combobox";
import { TransactionTypeFilterSelect } from "@/components/transaction-type-filter-select";
import { FilterField } from "@/components/filter-panel";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { ClearableInput } from "@/components/ui/clearable-input";
import { TableSkeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, apiErrorMessage } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { formatDate } from "@/lib/utils";
import { transactionQueryKeys } from "../_lib/query-keys";
import { useTransactionMutations } from "../_lib/use-transaction-mutations";

const PAGE_SIZE = 50;

export function TypeReviewView() {
  const { t } = useT();
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [type, setType] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkType, setBulkType] = useState("");
  const filters = {
    search: search.trim() || undefined,
    transaction_type: type || undefined,
    transaction_type_state: "needs_review" as const,
  };
  const query = useQuery({
    queryKey: transactionQueryKeys.list(page, filters),
    queryFn: () =>
      api.transactions({
        ...filters,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  });
  const summary = useQuery({
    queryKey: transactionQueryKeys.filterSummary(filters),
    queryFn: () => api.filterSummary(filters),
    placeholderData: keepPreviousData,
  });
  const clearSelection = () => setSelected(new Set());
  const mutations = useTransactionMutations({
    clearSelection,
    clearBulkCategory: () => undefined,
    clearBulkType: () => setBulkType(""),
  });
  const rows = query.data ?? [];
  const allSelected = rows.length > 0 && rows.every((row) => selected.has(row.id));
  const reset = () => {
    setPage(0);
    clearSelection();
  };
  const dropSelection = (id: number) =>
    setSelected((current) => {
      const next = new Set(current);
      next.delete(id);
      return next;
    });
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3 rounded-lg border bg-card p-3 shadow-sm">
        <FilterField
          label={t("transactions.filterSearch")}
          className="w-full sm:w-[26rem]"
        >
          <ClearableInput
            value={search}
            onValueChange={(value) => {
              setSearch(value);
              reset();
            }}
            placeholder={t("transactions.search")}
            clearLabel={t("common.clear")}
          />
        </FilterField>
        <FilterField
          label={t("transactions.typeReview.proposed")}
          className="w-[14rem] shrink-0"
        >
          <TransactionTypeFilterSelect
            value={type}
            onChange={(value) => {
              setType(value);
              reset();
            }}
            allLabel={t("transactions.filterType.all")}
            ariaLabel={t("transactions.typeReview.proposed")}
          />
        </FilterField>
      </div>

      {selected.size > 0 ? (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-muted/30 p-3">
          <span className="mr-auto text-sm font-medium">
            {t("common.selected", { n: selected.size })}
          </span>
          <div className="w-56">
            <TransactionTypeCombobox
              value={bulkType || "none"}
              onChange={(value) => setBulkType(value === "none" ? "" : value)}
              includeEmpty
              emptyValue="none"
              emptyLabel={t("transactions.bulkType")}
              size="md"
            />
          </div>
          <Button
            variant="outline"
            disabled={!bulkType || mutations.bulkSetType.isPending}
            onClick={() =>
              mutations.bulkSetType.mutate({
                ids: [...selected],
                transactionType: bulkType,
              })
            }
          >
            {t("transactions.bulkSetType")}
          </Button>
          <Button
            disabled={mutations.acceptTypeSuggestions.isPending}
            onClick={() => mutations.acceptTypeSuggestions.mutate([...selected])}
          >
            <Check className="mr-2 h-4 w-4" />
            {t("transactions.typeReview.confirmSelected")}
          </Button>
          <Button variant="ghost" onClick={clearSelection}>
            {t("common.cancel")}
          </Button>
        </div>
      ) : null}

      {query.isError ? (
        <ErrorState
          description={apiErrorMessage(query.error)}
          onRetry={() => query.refetch()}
        />
      ) : query.isLoading ? (
        <div className="rounded-lg border bg-card p-3">
          <TableSkeleton rows={8} />
        </div>
      ) : rows.length === 0 ? (
        <div className="flex h-40 items-center justify-center rounded-lg border bg-card text-sm text-muted-foreground">
          {t("transactions.typeReview.empty")}
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border bg-card">
          <Table className="min-w-[800px] table-fixed">
            <TableHeader>
              <TableRow className="divide-x divide-border/40 bg-muted/30 hover:bg-muted/30">
                <TableHead className="w-10">
                  <Checkbox
                    checked={allSelected}
                    onCheckedChange={() =>
                      setSelected(
                        allSelected ? new Set() : new Set(rows.map((row) => row.id)),
                      )
                    }
                  />
                </TableHead>
                <TableHead>{t("transactions.column.merchant")}</TableHead>
                <TableHead className="w-32 text-right">
                  {t("transactions.column.amount")}
                </TableHead>
                <TableHead className="w-56">
                  {t("transactions.typeReview.proposed")}
                </TableHead>
                <TableHead className="w-44 text-center">
                  {t("transactions.column.actions")}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => {
                return (
                  <TableRow key={row.id} className="divide-x divide-border/40">
                    <TableCell>
                      <Checkbox
                        checked={selected.has(row.id)}
                        onCheckedChange={() =>
                          setSelected((current) => {
                            const next = new Set(current);
                            if (next.has(row.id)) next.delete(row.id);
                            else next.add(row.id);
                            return next;
                          })
                        }
                      />
                    </TableCell>
                    <TableCell>
                      <div className="truncate font-medium">
                        {row.merchant_display || row.merchant || row.title}
                      </div>
                      <div className="truncate text-xs text-muted-foreground">
                        {formatDate(row.booking_date)} · {row.title}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <Money
                        amount={Number(row.amount)}
                        currency={row.currency}
                        direction={row.direction}
                      />
                    </TableCell>
                    <TableCell>
                      <TransactionTypeCombobox
                        value={row.transaction_type_effective || "expense"}
                        onChange={(value) => {
                          dropSelection(row.id);
                          mutations.patchType.mutate({ id: row.id, value });
                        }}
                        size="md"
                      />
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-1">
                        <Button
                          size="sm"
                          className="w-full text-xs"
                          disabled={mutations.acceptTypeSuggestion.isPending}
                          onClick={() => {
                            dropSelection(row.id);
                            mutations.acceptTypeSuggestion.mutate(row.id);
                          }}
                        >
                          <Check className="mr-1.5 h-4 w-4" />
                          {t("transactions.typeReview.confirm")}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
          <div className="flex min-h-14 items-center justify-between border-t px-3 py-2 text-sm text-muted-foreground">
            <span>
              {t("pagination.page", { n: page + 1 })} · {rows.length} /{" "}
              {summary.data?.count ?? rows.length}
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 0}
                onClick={() => setPage((value) => Math.max(0, value - 1))}
              >
                {t("pagination.previous")}
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={rows.length < PAGE_SIZE}
                onClick={() => setPage((value) => value + 1)}
              >
                {t("pagination.next")}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
