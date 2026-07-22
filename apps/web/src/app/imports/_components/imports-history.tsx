"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { History, Receipt, Trash2 } from "lucide-react";

import { api, type ImportHistoryRow } from "@/lib/api";
import { useFormatters, useT } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";
import { invalidateImportData, queryKeys } from "@/lib/query-keys";
import { transactionsHref } from "@/lib/transaction-links";
import { useConfirm } from "@/components/confirm-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable, type DataTableColumn } from "@/components/data-table";

export function ImportsHistory() {
  const { t } = useT();
  const { formatDateTime } = useFormatters();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const {
    data: imports = [],
    isLoading,
    isError,
    refetch,
  } = useQuery<ImportHistoryRow[]>({
    queryKey: queryKeys.imports.history,
    queryFn: () => api.listImports(),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => api.deleteImport(id),
    onSuccess: () => {
      void invalidateImportData(qc);
      toast.success(t("toast.deleted"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const onDelete = async (row: ImportHistoryRow) => {
    const ok = await confirm({
      title: t("imports.history.deleteConfirm", {
        filename: row.filename,
        n: row.inserted,
      }),
      destructive: true,
    });
    if (ok) deleteMut.mutate(row.id);
  };
  const columns: DataTableColumn<ImportHistoryRow>[] = [
    {
      id: "created_at",
      header: t("imports.history.created"),
      sortValue: (row) => new Date(row.created_at).getTime(),
      className: "text-xs whitespace-nowrap text-muted-foreground",
      cell: (row) => formatDateTime(row.created_at),
    },
    {
      id: "filename",
      header: t("imports.history.filename"),
      sortValue: (row) => row.filename,
      className: "font-medium",
      cell: (row) => row.filename,
    },
    {
      id: "source",
      header: t("imports.history.source"),
      sortValue: (row) => row.source,
      cell: (row) => <Badge variant="outline">{row.source}</Badge>,
    },
    {
      id: "total_rows",
      header: t("imports.history.totalRows"),
      align: "right",
      className: "tabular-nums",
      sortValue: (row) => row.total_rows,
      cell: (row) => row.total_rows,
    },
    {
      id: "inserted",
      header: t("imports.history.inserted"),
      align: "right",
      className: "tabular-nums text-positive",
      sortValue: (row) => row.inserted,
      cell: (row) => row.inserted,
    },
    {
      id: "duplicates",
      header: t("imports.history.duplicates"),
      align: "right",
      className: "tabular-nums text-muted-foreground",
      sortValue: (row) => row.duplicates,
      cell: (row) => row.duplicates,
    },
    {
      id: "actions",
      header: "",
      align: "right",
      headerClassName: "w-24",
      className: "w-24",
      cell: (row) => (
        <div className="flex justify-end gap-1">
          <Button
            size="icon"
            variant="ghost"
            asChild
            aria-label={t("imports.history.openTransactions")}
          >
            <Link href={transactionsHref({ import_id: row.id })}>
              <Receipt className="h-4 w-4" />
            </Link>
          </Button>
          <Button
            size="icon"
            variant="ghost"
            onClick={() => onDelete(row)}
            disabled={deleteMut.isPending}
            aria-label={t("common.delete")}
          >
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <History className="h-4 w-4" /> {t("imports.history.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <DataTable
          columns={columns}
          data={imports}
          rowKey={(row) => row.id}
          isLoading={isLoading}
          isError={isError}
          onRetry={() => void refetch()}
          emptyTitle={t("imports.history.empty")}
          initialSort={{ id: "created_at", dir: "desc" }}
          className="rounded-none border-0"
        />
      </CardContent>
    </Card>
  );
}
