"use client";

import { Check, ChevronDown } from "lucide-react";
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
  className,
}: TablePaginationProps) {
  const { t } = useT();
  const smallestPageSize = Math.min(...pageSizeOptions);
  const showPagination =
    page > 0 ||
    (total !== undefined
      ? total > smallestPageSize
      : currentCount >= pageSize);

  if (!showPagination) return null;

  const firstRow = currentCount > 0 ? page * pageSize + 1 : 0;
  const lastRow = currentCount > 0 ? page * pageSize + currentCount : 0;
  const canGoNext =
    hasNext ??
    (total !== undefined
      ? (page + 1) * pageSize < total
      : currentCount >= pageSize);

  return (
    <div
      className={cn(
        "flex min-h-12 flex-wrap items-center justify-between gap-2 border-t px-3 py-1.5 text-xs text-muted-foreground",
        className,
      )}
    >
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className="tabular-nums">
          {total !== undefined
            ? t("pagination.range", {
                from: firstRow,
                to: lastRow,
                total,
              })
            : `${t("pagination.page", { n: page + 1 })} · ${currentCount}`}
        </span>
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
      </div>
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          className="h-8 px-2.5 text-xs"
          disabled={page === 0}
          onClick={() => onPageChange(Math.max(0, page - 1))}
        >
          {t("pagination.previous")}
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="h-8 px-2.5 text-xs"
          disabled={!canGoNext}
          onClick={() => onPageChange(page + 1)}
        >
          {t("pagination.next")}
        </Button>
      </div>
    </div>
  );
}
