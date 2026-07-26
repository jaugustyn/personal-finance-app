"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, MoreHorizontal, Pencil, Plus, RotateCcw } from "lucide-react";
import { toast } from "sonner";

import { DataTable, type DataTableColumn } from "@/components/data-table";
import { FilterSelect } from "@/components/filter-select";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  api,
  type TransactionAccount,
  type TransactionAccountKind,
} from "@/lib/api";
import { useFormatters, useT } from "@/lib/i18n";
import { queryKeys } from "@/lib/query-keys";
import { showErrorToast } from "@/lib/toasts";
import { transactionsHref } from "@/lib/transaction-links";

const ACCOUNT_KINDS: TransactionAccountKind[] = [
  "bank",
  "savings",
  "credit_card",
  "cash",
  "other",
];

export default function AccountsPage() {
  const { t } = useT();
  const { formatDate } = useFormatters();
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
    <div className="space-y-6">
      <PageHeader
        title={t("accounts.title")}
        description={t("accounts.description")}
        actions={
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4" />
            {t("accounts.add")}
          </Button>
        }
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

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>
              {t(edited ? "accounts.editTitle" : "accounts.addTitle")}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-1">
            <div className="space-y-1.5">
              <Label htmlFor="account-name">{t("accounts.name")}</Label>
              <Input
                id="account-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder={t("accounts.namePlaceholder")}
                autoFocus
              />
            </div>
            <div className="space-y-1.5">
              <Label>{t("accounts.kind")}</Label>
              <FilterSelect
                value={kind}
                onValueChange={(next) => setKind(next as TransactionAccountKind)}
                options={ACCOUNT_KINDS.map((item) => ({
                  value: item,
                  label: t(`accounts.kind.${item}`),
                }))}
                ariaLabel={t("accounts.kind")}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDialogOpen(false)}
              disabled={saveMutation.isPending}
            >
              {t("common.cancel")}
            </Button>
            <Button
              onClick={() => saveMutation.mutate()}
              disabled={!name.trim() || saveMutation.isPending}
            >
              {t("common.save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
