"use client";

import * as React from "react";
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
import { SortableTableHead } from "@/components/sortable-table-head";
import { TableSkeleton } from "@/components/ui/skeleton";
import {
  DEFAULT_TABLE_PAGE_SIZE,
  TablePagination,
} from "@/components/table-pagination";
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
  /** Text and dates use left; numbers right; actions and compact controls center. */
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
  pagination?: DataTablePagination;
}

export type DataTablePagination =
  | {
      mode: "client";
      defaultPageSize?: number;
      pageSizeOptions?: readonly number[];
    }
  | {
      mode: "server";
      page: number;
      pageSize: number;
      total?: number;
      hasNext?: boolean;
      onPageChange: (page: number) => void;
      onPageSizeChange: (pageSize: number) => void;
      pageSizeOptions?: readonly number[];
    };

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
  pagination,
}: DataTableProps<T>) {
  const { t } = useT();
  const { compare } = useFormatters();
  const [internalSort, setInternalSort] = React.useState<SortState>(initialSort);
  const [clientPage, setClientPage] = React.useState(0);
  const [clientPageSize, setClientPageSize] = React.useState(
    pagination?.mode === "client"
      ? (pagination.defaultPageSize ?? DEFAULT_TABLE_PAGE_SIZE)
      : DEFAULT_TABLE_PAGE_SIZE,
  );
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
    if (pagination?.mode === "client") setClientPage(0);
    if (onSortChange) {
      onSortChange({
        id,
        dir:
          activeSort?.id === id && activeSort.dir === "asc" ? "desc" : "asc",
      });
      return;
    }
    setInternalSort((prev) => {
      if (prev?.id === id && prev.dir === "asc") {
        return { id, dir: "desc" };
      }
      return { id, dir: "asc" };
    });
  };

  const clientTotal = sorted?.length ?? 0;
  const clientMaxPage = Math.max(0, Math.ceil(clientTotal / clientPageSize) - 1);
  const effectiveClientPage = Math.min(clientPage, clientMaxPage);
  const visibleRows =
    pagination?.mode === "client" && sorted
      ? sorted.slice(
          effectiveClientPage * clientPageSize,
          (effectiveClientPage + 1) * clientPageSize,
        )
      : sorted;
  const paginationFooter =
    pagination?.mode === "client" ? (
      <TablePagination
        page={effectiveClientPage}
        pageSize={clientPageSize}
        currentCount={visibleRows?.length ?? 0}
        total={clientTotal}
        pageSizeOptions={pagination.pageSizeOptions}
        onPageChange={setClientPage}
        onPageSizeChange={(nextPageSize) => {
          setClientPageSize(nextPageSize);
          setClientPage(0);
        }}
      />
    ) : pagination?.mode === "server" ? (
      <TablePagination
        page={pagination.page}
        pageSize={pagination.pageSize}
        currentCount={visibleRows?.length ?? 0}
        total={pagination.total}
        hasNext={pagination.hasNext}
        pageSizeOptions={pagination.pageSizeOptions}
        onPageChange={pagination.onPageChange}
        onPageSizeChange={pagination.onPageSizeChange}
      />
    ) : null;

  if (isLoading) {
    return (
      <div
        className={cn(
          "overflow-hidden rounded-lg border bg-card p-3",
          className,
        )}
      >
        <TableSkeleton rows={6} />
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

  if (!visibleRows || visibleRows.length === 0) {
    if (tableToolbar || paginationFooter) {
      return (
        <div
          className={cn("overflow-hidden rounded-lg border bg-card", className)}
        >
          {toolbarPosition === "top" ? tableToolbar : null}
          <EmptyState
            title={emptyTitle ?? t("common.empty")}
            description={emptyDescription}
            className="rounded-none border-0"
          />
          {toolbarPosition === "bottom" ? tableToolbar : null}
          {paginationFooter}
        </div>
      );
    }
    return (
      <EmptyState
        title={emptyTitle ?? t("common.empty")}
        description={emptyDescription}
        className={cn("bg-card", className)}
      />
    );
  }

  return (
    <div
      className={cn("overflow-hidden rounded-lg border bg-card", className)}
    >
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
              return (
                sortable ? (
                  <SortableTableHead
                    key={col.id}
                    id={col.id}
                    sort={activeSort}
                    onSort={toggleSort}
                    align={col.align}
                    className={col.headerClassName}
                  >
                    {col.header}
                  </SortableTableHead>
                ) : (
                  <TableHead
                    key={col.id}
                    className={cn(
                      alignClass[col.align ?? "left"],
                      col.headerClassName,
                    )}
                  >
                    {col.header}
                  </TableHead>
                )
              );
            })}
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleRows.map((row) => (
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
      {paginationFooter}
    </div>
  );
}
