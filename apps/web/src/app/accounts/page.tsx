"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  MoreHorizontal,
  Pencil,
  Plus,
  RotateCcw,
  Upload,
} from "lucide-react";
import { toast } from "sonner";

import { AccountFormDialog } from "@/components/account-form-dialog";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  api,
  type TransactionAccount,
  type TransactionAccountKind,
} from "@/lib/api";
import { useFormatters, useT } from "@/lib/i18n";
import { queryKeys } from "@/lib/query-keys";
import { showErrorToast } from "@/lib/toasts";
import { transactionsHref } from "@/lib/transaction-links";

export default function AccountsPage() {
  const { t } = useT();
  const { formatDate, formatDateTime } = useFormatters();
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [edited, setEdited] = useState<TransactionAccount | null>(null);
  const [name, setName] = useState("");
  const [kind, setKind] = useState<TransactionAccountKind>("bank");
  const accountsQuery = useQuery({
    queryKey: queryKeys.accounts.list(true),
    queryFn: () => api.accounts(true),
  });
  const saveMutation = useMutation({
    mutationFn: () =>
      edited
        ? api.updateAccount(edited.id, { name: name.trim(), kind })
        : api.createAccount({ name: name.trim(), kind }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
      setDialogOpen(false);
      toast.success(t("toast.saved"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });
  const statusMutation = useMutation({
    mutationFn: (account: TransactionAccount) =>
      account.archived_at
        ? api.restoreAccount(account.id)
        : api.archiveAccount(account.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
      toast.success(t("toast.saved"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const openCreate = () => {
    setEdited(null);
    setName("");
    setKind("bank");
    setDialogOpen(true);
  };
  const openEdit = (account: TransactionAccount) => {
    setEdited(account);
    setName(account.name);
    setKind(account.kind);
    setDialogOpen(true);
  };
  const active = (accountsQuery.data ?? []).filter((row) => !row.archived_at);
  const archived = (accountsQuery.data ?? []).filter((row) => row.archived_at);

  const columns: DataTableColumn<TransactionAccount>[] = [
    {
      id: "name",
      header: t("accounts.name"),
      sortValue: (row) => row.name,
      className: "font-medium",
      cell: (row) => row.name,
    },
    {
      id: "kind",
      header: t("accounts.kind"),
      sortValue: (row) => t(`accounts.kind.${row.kind}`),
      cell: (row) => t(`accounts.kind.${row.kind}`),
    },
    {
      id: "currencies",
      header: t("accounts.currencies"),
      sortValue: (row) => row.currencies.join(","),
      cell: (row) => row.currencies.join(", ") || "—",
    },
    {
      id: "transactions",
      header: t("accounts.transactions"),
      align: "right",
      sortValue: (row) => row.transaction_count,
      cell: (row) => (
        <Button variant="link" className="h-auto p-0 tabular-nums" asChild>
          <Link href={transactionsHref({ account_id: row.id })}>
            {row.transaction_count}
          </Link>
        </Button>
      ),
    },
    {
      id: "lastTransaction",
      header: t("accounts.lastTransaction"),
      sortValue: (row) => row.last_transaction_date,
      className: "whitespace-nowrap text-muted-foreground",
      cell: (row) =>
        row.last_transaction_date ? formatDate(row.last_transaction_date) : "—",
    },
    {
      id: "lastImport",
      header: t("accounts.lastImport"),
      sortValue: (row) => row.last_imported_at,
      className: "whitespace-nowrap text-muted-foreground",
      cell: (row) =>
        row.last_imported_at ? formatDateTime(row.last_imported_at) : "—",
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
            <Button variant="ghost" size="icon" aria-label={t("common.actions")}>
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {!row.archived_at ? (
              <DropdownMenuItem asChild>
                <Link href={`/imports?account_id=${row.id}`}>
                  <Upload className="h-4 w-4" />
                  {t("accounts.importData")}
                </Link>
              </DropdownMenuItem>
            ) : null}
            <DropdownMenuItem onClick={() => openEdit(row)}>
              <Pencil className="h-4 w-4" />
              {t("common.edit")}
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => statusMutation.mutate(row)}
              disabled={statusMutation.isPending}
            >
              {row.archived_at ? (
                <RotateCcw className="h-4 w-4" />
              ) : (
                <Archive className="h-4 w-4" />
              )}
              {t(row.archived_at ? "accounts.restore" : "accounts.archive")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ];

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("accounts.title")}
        description={t("accounts.description")}
      />

      <DataTable
        columns={columns}
        data={active}
        rowKey={(row) => row.id}
        isLoading={accountsQuery.isLoading}
        isError={accountsQuery.isError}
        onRetry={() => void accountsQuery.refetch()}
        emptyTitle={t("accounts.empty")}
        initialSort={{ id: "name", dir: "asc" }}
        pagination={{ mode: "client" }}
        toolbarPosition="bottom"
        toolbar={
          <button
            type="button"
            onClick={openCreate}
            className="-mx-3 -my-2 flex w-[calc(100%+1.5rem)] items-center gap-2 px-3 py-2.5 text-left text-sm font-medium text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
          >
            <Plus className="h-4 w-4" />
            {t("accounts.add")}
          </button>
        }
      />

      {archived.length > 0 ? (
        <details className="group">
          <summary className="cursor-pointer list-none text-sm font-medium text-muted-foreground hover:text-foreground">
            {t("accounts.archived", { count: archived.length })}
          </summary>
          <DataTable
            columns={columns}
            data={archived}
            rowKey={(row) => row.id}
            initialSort={{ id: "name", dir: "asc" }}
            className="mt-3"
          />
        </details>
      ) : null}

      <AccountFormDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        mode={edited ? "edit" : "create"}
        name={name}
        onNameChange={setName}
        kind={kind}
        onKindChange={setKind}
        pending={saveMutation.isPending}
        onSubmit={() => saveMutation.mutate()}
      />
    </div>
  );
}
