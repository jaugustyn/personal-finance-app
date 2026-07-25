"use client";

import type { ReactNode } from "react";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { TableHead } from "@/components/ui/table";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export interface TableSortState<T extends string = string> {
  id: T;
  dir: "asc" | "desc";
}

export function SortableTableHead<T extends string>({
  id,
  sort,
  onSort,
  children,
  className,
  align = "left",
}: {
  id: T;
  sort: TableSortState | null;
  onSort: (id: T) => void;
  children: ReactNode;
  className?: string;
  align?: "left" | "right" | "center";
}) {
  const { t } = useT();
  const active = sort?.id === id;

  return (
    <TableHead
      aria-sort={
        active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"
      }
      className={cn(
        align === "right" && "text-right",
        align === "center" && "text-center",
        className,
      )}
    >
      <button
        type="button"
        onClick={() => onSort(id)}
        title={t("table.sort")}
        className={cn(
          "inline-flex items-center gap-1 transition-colors hover:text-foreground",
          active && "text-foreground",
          align === "right" && "ml-auto flex-row-reverse",
          align === "center" && "mx-auto",
        )}
      >
        {children}
        {active ? (
          sort.dir === "asc" ? (
            <ArrowUp className="h-3.5 w-3.5" />
          ) : (
            <ArrowDown className="h-3.5 w-3.5" />
          )
        ) : (
          <ChevronsUpDown className="h-3.5 w-3.5 opacity-50" />
        )}
      </button>
    </TableHead>
  );
}
