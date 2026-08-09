"use client";

import type { ReactNode } from "react";
import { Check, ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export const DEFAULT_TABLE_PAGE_SIZE = 10;
export const TABLE_PAGE_SIZE_OPTIONS = [10, 25, 50, 100] as const;

export interface TablePaginationProps {
  page: number;
  pageSize: number;
  currentCount: number;
  total?: number;
  hasNext?: boolean;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  pageSizeOptions?: readonly number[];
  alwaysVisible?: boolean;
  leadingContent?: ReactNode;
  className?: string;
}

export function TablePagination({
  page,
  pageSize,
  currentCount,
  total,
  hasNext,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = TABLE_PAGE_SIZE_OPTIONS,
  alwaysVisible = false,
  leadingContent,
  className,
}: TablePaginationProps) {
  const { t } = useT();
  const smallestPageSize = Math.min(...pageSizeOptions);
  const hasAnyRows = total !== undefined ? total > 0 : currentCount > 0;
  const showPagination =
    (alwaysVisible && hasAnyRows) ||
    page > 0 ||
    (total !== undefined
      ? total > smallestPageSize
      : currentCount >= pageSize);

  if (!showPagination && !leadingContent) return null;

  const canGoNext =
    hasNext ??
    (total !== undefined
      ? (page + 1) * pageSize < total
      : currentCount >= pageSize);
  const totalPages =
    total !== undefined ? Math.max(1, Math.ceil(total / pageSize)) : undefined;
  const pageLabel =
    totalPages !== undefined
      ? `${Math.min(page + 1, totalPages)} / ${totalPages}`
      : t("pagination.page", { n: page + 1 });
  const paginationMeta = showPagination ? (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 gap-1.5 px-2 font-normal text-muted-foreground"
          aria-label={t("pagination.rowsPerPage")}
        >
          {t("pagination.perPage", { n: pageSize })}
          <ChevronDown className="h-3.5 w-3.5 opacity-60" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="min-w-32">
        {pageSizeOptions.map((option) => (
          <DropdownMenuItem
            key={option}
            onSelect={() => onPageSizeChange(option)}
          >
            <span>{option}</span>
            {option === pageSize ? (
              <Check className="ml-auto h-4 w-4 text-primary" />
            ) : null}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  ) : null;
  const navigation = showPagination ? (
    <div className="ml-auto flex shrink-0 items-center gap-1">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        disabled={page === 0}
        onClick={() => onPageChange(Math.max(0, page - 1))}
        title={t("pagination.previous")}
        aria-label={t("pagination.previous")}
      >
        <ChevronLeft className="h-4 w-4" />
      </Button>
      <span className="min-w-14 text-center tabular-nums text-foreground/80">
        {pageLabel}
      </span>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        disabled={!canGoNext}
        onClick={() => onPageChange(page + 1)}
        title={t("pagination.next")}
        aria-label={t("pagination.next")}
      >
        <ChevronRight className="h-4 w-4" />
      </Button>
    </div>
  ) : null;

  return (
    <div
      className={cn(
        "flex min-h-11 flex-wrap items-center gap-x-6 gap-y-1.5 border-t px-3 py-1 text-xs text-muted-foreground",
        className,
      )}
    >
      {paginationMeta}
      {leadingContent ? (
        <div className="order-3 flex w-full min-w-0 justify-center sm:order-none sm:w-auto sm:flex-1">
          {leadingContent}
        </div>
      ) : (
        <div className="min-w-0 flex-1" aria-hidden="true" />
      )}
      {navigation}
    </div>
  );
}
