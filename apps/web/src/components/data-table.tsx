"use client";

import * as React from "react";
import { ArrowDown, ArrowUp, ChevronsUpDown, Loader2 } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { cn } from "@/lib/utils";
import { useFormatters, useT } from "@/lib/i18n";

export interface DataTableColumn<T> {
  id: string;
  header: React.ReactNode;
  cell: (row: T) => React.ReactNode;
  /** Value used for client-side sorting. Omit to make the column non-sortable. */
  sortValue?: (row: T) => string | number | null | undefined;
  /** Marks a column as sortable when sorting is handled by the caller. */
  sortable?: boolean;
  align?: "left" | "right" | "center";
  className?: string;
  headerClassName?: string;
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  data: T[] | undefined;
  rowKey: (row: T) => string | number;
  isLoading?: boolean;
  isError?: boolean;
  onRetry?: () => void;
  initialSort?: SortState;
  sort?: SortState;
  onSortChange?: (sort: Exclude<SortState, null>) => void;
  /** Rendered when data is loaded but empty. */
  emptyTitle?: string;
  emptyDescription?: string;
  onRowClick?: (row: T) => void;
  getRowClassName?: (row: T) => string | undefined;
  /** Sticky header keeps the head visible while scrolling. */
  stickyHeader?: boolean;
  className?: string;
  tableClassName?: string;
  toolbar?: React.ReactNode;
  toolbarPosition?: "top" | "bottom";
  rowCountLabel?: string;
}

export type DataTableSortState = {
  id: string;
  dir: "asc" | "desc";
} | null;

type SortState = DataTableSortState;

const alignClass = {
  left: "text-left",
  right: "text-right",
  center: "text-center",
} as const;

export function DataTable<T>({
  columns,
  data,
  rowKey,
  isLoading,
  isError,
  onRetry,
  initialSort = null,
  sort: controlledSort,
  onSortChange,
  emptyTitle,
  emptyDescription,
  onRowClick,
  getRowClassName,
  stickyHeader,
  className,
  tableClassName,
  toolbar,
  toolbarPosition = "top",
  rowCountLabel,
}: DataTableProps<T>) {
  const { t } = useT();
  const { compare } = useFormatters();
  const [internalSort, setInternalSort] = React.useState<SortState>(initialSort);
  const activeSort = onSortChange ? (controlledSort ?? null) : internalSort;

  const sorted = React.useMemo(() => {
    if (!data || !activeSort || onSortChange) return data;
    const col = columns.find((c) => c.id === activeSort.id);
    if (!col?.sortValue) return data;
    const factor = activeSort.dir === "asc" ? 1 : -1;
    return [...data].sort((a, b) => {
      const av = col.sortValue!(a);
      const bv = col.sortValue!(b);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "number" && typeof bv === "number") {
        return (av - bv) * factor;
      }
      return compare(String(av), String(bv)) * factor;
    });
  }, [activeSort, columns, compare, data, onSortChange]);

  const toggleSort = (id: string) => {
    if (onSortChange) {
      onSortChange({
        id,
        dir:
          activeSort?.id === id && activeSort.dir === "asc" ? "desc" : "asc",
      });
      return;
    }
    setInternalSort((prev) => {
      if (prev?.id !== id) return { id, dir: "asc" };
      if (prev.dir === "asc") return { id, dir: "desc" };
      return null;
    });
  };

  if (isLoading) {
    return (
      <div className="flex h-48 items-center justify-center text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
    );
  }

  const tableToolbar =
    toolbar || rowCountLabel ? (
      <div
        className={cn(
          "flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-xs text-muted-foreground",
          toolbarPosition === "top" ? "border-b" : "border-t",
        )}
      >
        {rowCountLabel ? <div>{rowCountLabel}</div> : null}
        {toolbar}
      </div>
    ) : null;

  if (isError) {
    return (
      <ErrorState
        variant="compact"
        onRetry={onRetry}
        className={cn("min-h-40", className)}
      />
    );
  }

  if (!sorted || sorted.length === 0) {
    if (tableToolbar) {
      return (
        <div className={cn("overflow-hidden rounded-lg border", className)}>
          {toolbarPosition === "top" ? tableToolbar : null}
          <EmptyState
            title={emptyTitle ?? t("common.empty")}
            description={emptyDescription}
            className="rounded-none border-0"
          />
          {toolbarPosition === "bottom" ? tableToolbar : null}
        </div>
      );
    }
    return (
      <EmptyState
        title={emptyTitle ?? t("common.empty")}
        description={emptyDescription}
      />
    );
  }

  return (
    <div className={cn("overflow-x-auto rounded-lg border", className)}>
      {toolbarPosition === "top" ? tableToolbar : null}
      <Table className={tableClassName}>
        <TableHeader
          className={cn(stickyHeader && "sticky top-0 z-10 bg-card")}
        >
          <TableRow className="hover:bg-transparent">
            {columns.map((col) => {
              const sortable = Boolean(
                col.sortValue || (onSortChange && col.sortable),
              );
              const active = activeSort?.id === col.id;
              return (
                <TableHead
                  key={col.id}
                  aria-sort={
                    active
                      ? activeSort!.dir === "asc"
                        ? "ascending"
                        : "descending"
                      : sortable
                        ? "none"
                        : undefined
                  }
                  className={cn(
                    alignClass[col.align ?? "left"],
                    col.headerClassName,
                  )}
                >
                  {sortable ? (
                    <button
                      type="button"
                      onClick={() => toggleSort(col.id)}
                      title={t("table.sort")}
                      className={cn(
                        "inline-flex items-center gap-1 transition-colors hover:text-foreground",
                        active && "text-foreground",
                        col.align === "right" && "flex-row-reverse",
                      )}
                    >
                      {col.header}
                      {active ? (
                        activeSort?.dir === "asc" ? (
                          <ArrowUp className="h-3.5 w-3.5" />
                        ) : (
                          <ArrowDown className="h-3.5 w-3.5" />
                        )
                      ) : (
                        <ChevronsUpDown className="h-3.5 w-3.5 opacity-50" />
                      )}
                    </button>
                  ) : (
                    col.header
                  )}
                </TableHead>
              );
            })}
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((row) => (
            <TableRow
              key={rowKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={cn(
                onRowClick && "cursor-pointer",
                getRowClassName?.(row),
              )}
            >
              {columns.map((col) => (
                <TableCell
                  key={col.id}
                  className={cn(alignClass[col.align ?? "left"], col.className)}
                >
                  {col.cell(row)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {toolbarPosition === "bottom" ? tableToolbar : null}
    </div>
  );
}
