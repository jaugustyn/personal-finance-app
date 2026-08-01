"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Landmark, MoreHorizontal, Receipt, Trash2 } from "lucide-react";

import { api, type ImportHistoryRow } from "@/lib/api";
import { useFormatters, useT } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";
import { invalidateImportData, queryKeys } from "@/lib/query-keys";
import { transactionsHref } from "@/lib/transaction-links";
import { useConfirm } from "@/components/confirm-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { AccountSelect } from "@/components/account-select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export function ImportsHistory() {
  const { t } = useT();
  const { formatDateTime } = useFormatters();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [accountTarget, setAccountTarget] = useState<ImportHistoryRow | null>(null);
  const [accountId, setAccountId] = useState<number | null>(null);
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
  const accountMut = useMutation({
    mutationFn: () => api.changeImportAccount(accountTarget!.id, accountId!),
    onSuccess: () => {
      void invalidateImportData(qc);
      setAccountTarget(null);
      toast.success(t("toast.saved"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const onDelete = async (row: ImportHistoryRow) => {
    const ok = await confirm({
      title: t("imports.history.deleteTitle"),
      description: t("imports.history.deleteDescription"),
      details: [
        {
          label: t("imports.history.deleteFileLabel"),
          value: row.filename,
        },
        {
          label: t("imports.history.deleteTransactionsLabel"),
          value: String(row.inserted),
        },
      ],
      confirmLabel: t("imports.history.deleteAction"),
      destructive: true,
    });
    if (ok) deleteMut.mutate(row.id);
  };
  const sourceLabel = (source: string) => {
    const normalized = source.trim().toLowerCase();
    if (!normalized || normalized === "unknown" || normalized === "generic") {
      return t("imports.customFormat");
    }
    if (normalized === "pekao") return "Pekao";
    if (normalized === "revolut") return "Revolut";
    return source;
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
      id: "account",
      header: t("imports.history.account"),
      sortValue: (row) => row.account_name,
      cell: (row) => row.account_name,
    },
    {
      id: "source",
      header: t("imports.history.source"),
      sortValue: (row) => sourceLabel(row.source),
      cell: (row) => <Badge variant="outline">{sourceLabel(row.source)}</Badge>,
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
      align: "center",
      headerClassName: "w-14",
      className: "w-14",
      cell: (row) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8"
              aria-label={t("common.actions")}
            >
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem
              onSelect={() => {
                setAccountTarget(row);
                setAccountId(row.account_id);
              }}
            >
              <Landmark className="h-4 w-4" />
              {t("imports.history.changeAccount")}
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href={transactionsHref({ import_id: row.id })}>
                <Receipt className="h-4 w-4" />
                {t("imports.history.openTransactions")}
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="text-destructive focus:text-destructive"
              onSelect={() => void onDelete(row)}
              disabled={deleteMut.isPending}
            >
              <Trash2 className="h-4 w-4" />
              {t("imports.history.deleteAction")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ];

  return (
    <>
      <section className="space-y-3">
        <div className="flex min-h-9 items-center gap-2">
          <h2 className="text-base font-semibold">
            {t("imports.history.title")}
          </h2>
          {!isLoading && !isError ? (
            <Badge variant="secondary" className="tabular-nums">
              {imports.length}
            </Badge>
          ) : null}
        </div>
        <DataTable
          columns={columns}
          data={imports}
          rowKey={(row) => row.id}
          isLoading={isLoading}
          isError={isError}
          onRetry={() => void refetch()}
          emptyTitle={t("imports.history.empty")}
          initialSort={{ id: "created_at", dir: "desc" }}
          pagination={{ mode: "client" }}
          className="rounded-xl"
        />
      </section>
      <Dialog
        open={accountTarget !== null}
        onOpenChange={(open) => {
          if (!open && !accountMut.isPending) setAccountTarget(null);
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{t("imports.history.changeAccountTitle")}</DialogTitle>
          </DialogHeader>
          <AccountSelect
            value={accountId}
            onChange={setAccountId}
            disabled={accountMut.isPending}
            quickCreate={false}
          />
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setAccountTarget(null)}
              disabled={accountMut.isPending}
            >
              {t("common.cancel")}
            </Button>
            <Button
              onClick={() => accountMut.mutate()}
              disabled={
                accountId === null ||
                accountId === accountTarget?.account_id ||
                accountMut.isPending
              }
            >
              {t("common.save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
