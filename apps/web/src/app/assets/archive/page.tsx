"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ArchiveRestore, Layers3, Trash2, WalletCards } from "lucide-react";
import { toast } from "sonner";
import { useConfirm } from "@/components/confirm-dialog";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type AssetAccount, type AssetItem } from "@/lib/api";
import { useFormatters, useT } from "@/lib/i18n";
import { invalidateAssetData, queryKeys } from "@/lib/query-keys";
import { showErrorToast } from "@/lib/toasts";
import { AssetSectionTabs } from "../_components/asset-section-tabs";
import {
  accountKindKey,
  assetTypeKey,
  wrapperKey,
} from "../_lib/asset-options";

interface ArchivedItem {
  account: AssetAccount;
  item: AssetItem;
}

export default function AssetArchivePage() {
  const { t } = useT();
  const { formatCurrency, formatDate } = useFormatters();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const accountsQuery = useQuery({
    queryKey: queryKeys.assets.accounts(true),
    queryFn: () => api.assetAccounts(true),
  });
  const refresh = () => invalidateAssetData(queryClient);
  const restoreAccount = useMutation({
    mutationFn: api.restoreAssetAccount,
    onSuccess: () => {
      toast.success(t("assets.accountRestored"));
      void refresh();
    },
    onError: (error) => showErrorToast(error, t("assets.saveError")),
  });
  const restoreItem = useMutation({
    mutationFn: api.restoreAssetItem,
    onSuccess: () => {
      toast.success(t("assets.itemRestored"));
      void refresh();
    },
    onError: (error) => showErrorToast(error, t("assets.saveError")),
  });

  const deleteEntry = useMutation({
    mutationFn: ({ id, kind }: { id: number; kind: "account" | "item" }) =>
      kind === "account" ? api.deleteAssetAccount(id) : api.deleteAssetItem(id),
    onSuccess: () => {
      toast.success(t("assets.deleted"));
      void refresh();
    },
    onError: (error) => showErrorToast(error, t("assets.saveError")),
  });
  async function remove(id: number, name: string, kind: "account" | "item") {
    if (
      await confirm({
        title: t("assets.deletePermanently"),
        description: t(
          kind === "account"
            ? "assets.deleteAccountConfirm"
            : "assets.deleteItemConfirm",
          { name },
        ),
        confirmLabel: t("common.delete"),
        destructive: true,
      })
    )
      deleteEntry.mutate({ id, kind });
  }

  const accounts = accountsQuery.data ?? [];
  const archivedAccounts = accounts.filter((account) => account.archived_at);
  const archivedItems: ArchivedItem[] = accounts
    .filter((account) => !account.archived_at)
    .flatMap((account) =>
      account.items
        .filter((item) => item.archived_at)
        .map((item) => ({ account, item })),
    );
  const empty = archivedAccounts.length === 0 && archivedItems.length === 0;

  return (
    <div className="space-y-6">
      <PageHeader title={t("assets.title")} />
      <AssetSectionTabs />

      {accountsQuery.isError ? (
        <ErrorState
          title={t("assets.loadError")}
          onRetry={() => void accountsQuery.refetch()}
        />
      ) : accountsQuery.isLoading ? (
        <ArchiveSkeleton />
      ) : empty ? (
        <EmptyState icon={Archive} title={t("assets.archiveEmpty")} />
      ) : (
        <div className="space-y-6">
          {archivedAccounts.length ? (
            <section className="space-y-3">
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold">
                  {t("assets.archivedAccounts")}
                </h2>
                <Badge variant="secondary">{archivedAccounts.length}</Badge>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                {archivedAccounts.map((account) => (
                  <Card key={account.id} className="flex min-w-0 flex-col p-4">
                    <div className="flex min-w-0 items-start gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                        <WalletCards className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold">
                          {account.name}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {t(accountKindKey(account.kind))}
                          {account.wrapper !== "standard"
                            ? `, ${t(wrapperKey(account.wrapper))}`
                            : ""}
                        </p>
                        {account.institution ? (
                          <p className="mt-1 truncate text-xs text-muted-foreground">
                            {account.institution}
                          </p>
                        ) : null}
                      </div>
                      <div className="hidden shrink-0 text-right sm:block">
                        <p className="text-xs text-muted-foreground">
                          {t("assets.value")}
                        </p>
                        <p className="mt-1 text-sm font-semibold tabular-nums">
                          {formatCurrency(Number(account.amount_pln), "PLN")}
                        </p>
                      </div>
                    </div>
                    <div className="mt-auto flex flex-wrap items-center justify-between gap-x-3 gap-y-2 pt-4">
                      <p className="w-full text-xs text-muted-foreground sm:w-auto">
                        {t("assets.archivedOn", {
                          date: formatDate(account.archived_at!),
                        })}
                      </p>
                      <span className="text-sm font-semibold tabular-nums sm:hidden">
                        {formatCurrency(Number(account.amount_pln), "PLN")}
                      </span>
                      <div className="ml-auto flex items-center gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={
                            restoreAccount.isPending || deleteEntry.isPending
                          }
                          onClick={() => restoreAccount.mutate(account.id)}
                        >
                          <ArchiveRestore className="h-4 w-4" />
                          {t("assets.restoreAccount")}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive"
                          aria-label={t("assets.deletePermanently")}
                          disabled={
                            deleteEntry.isPending || restoreAccount.isPending
                          }
                          onClick={() =>
                            void remove(account.id, account.name, "account")
                          }
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </section>
          ) : null}

          {archivedItems.length ? (
            <section className="space-y-3">
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold">
                  {t("assets.archivedItems")}
                </h2>
                <Badge variant="secondary">{archivedItems.length}</Badge>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                {archivedItems.map(({ account, item }) => (
                  <Card key={item.id} className="flex min-w-0 flex-col p-4">
                    <div className="flex min-w-0 items-start gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                        <Layers3 className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="truncate text-sm font-semibold">
                            {item.name}
                          </p>
                          <Badge variant="secondary">
                            {t(assetTypeKey(item.asset_type))}
                          </Badge>
                        </div>
                        <p className="mt-1 truncate text-xs text-muted-foreground">
                          {account.name}
                        </p>
                      </div>
                      <div className="hidden shrink-0 text-right sm:block">
                        <p className="text-xs text-muted-foreground">
                          {t("assets.value")}
                        </p>
                        <p className="mt-1 text-sm font-semibold tabular-nums">
                          {item.current_value.amount_pln == null
                            ? "—"
                            : formatCurrency(
                                Number(item.current_value.amount_pln),
                                "PLN",
                              )}
                        </p>
                      </div>
                    </div>
                    <div className="mt-auto flex flex-wrap items-center justify-between gap-x-3 gap-y-2 pt-4">
                      <p className="w-full text-xs text-muted-foreground sm:w-auto">
                        {t("assets.archivedOn", {
                          date: formatDate(item.archived_at!),
                        })}
                      </p>
                      <span className="text-sm font-semibold tabular-nums sm:hidden">
                        {item.current_value.amount_pln == null
                          ? "—"
                          : formatCurrency(
                              Number(item.current_value.amount_pln),
                              "PLN",
                            )}
                      </span>
                      <div className="ml-auto flex items-center gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={
                            restoreItem.isPending || deleteEntry.isPending
                          }
                          onClick={() => restoreItem.mutate(item.id)}
                        >
                          <ArchiveRestore className="h-4 w-4" />
                          {t("assets.restoreItem")}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive"
                          aria-label={t("assets.deletePermanently")}
                          disabled={
                            deleteEntry.isPending || restoreItem.isPending
                          }
                          onClick={() => void remove(item.id, item.name, "item")}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </section>
          ) : null}
        </div>
      )}
    </div>
  );
}

function ArchiveSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-5 w-40" />
      <Skeleton className="h-40 w-full" />
      <Skeleton className="h-5 w-32" />
      <Skeleton className="h-28 w-full" />
    </div>
  );
}
