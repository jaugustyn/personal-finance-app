"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ArchiveRestore } from "lucide-react";
import { toast } from "sonner";
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
    <div className="space-y-5">
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
              <Card className="divide-y overflow-hidden">
                {archivedAccounts.map((account) => (
                  <div
                    key={account.id}
                    className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{account.name}</p>
                      <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                        {account.institution ? <span>{account.institution}</span> : null}
                        {account.institution ? <span aria-hidden="true">·</span> : null}
                        <span>{t(accountKindKey(account.kind))}</span>
                        {account.wrapper !== "standard" ? (
                          <Badge variant="secondary" className="py-0">
                            {t(wrapperKey(account.wrapper))}
                          </Badge>
                        ) : null}
                        <span aria-hidden="true">·</span>
                        <span>
                          {t("assets.archivedOn", {
                            date: formatDate(account.archived_at!),
                          })}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between gap-4 sm:justify-end">
                      <span className="font-semibold tabular-nums">
                        {formatCurrency(Number(account.amount_pln), "PLN")}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={restoreAccount.isPending}
                        onClick={() => restoreAccount.mutate(account.id)}
                      >
                        <ArchiveRestore className="h-4 w-4" />
                        {t("assets.restoreAccount")}
                      </Button>
                    </div>
                  </div>
                ))}
              </Card>
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
              <Card className="divide-y overflow-hidden">
                {archivedItems.map(({ account, item }) => (
                  <div
                    key={item.id}
                    className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-sm font-medium">{item.name}</p>
                        <Badge variant="secondary">
                          {t(assetTypeKey(item.asset_type))}
                        </Badge>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {account.name}
                        <span aria-hidden="true"> · </span>
                        {t("assets.archivedOn", {
                          date: formatDate(item.archived_at!),
                        })}
                      </p>
                    </div>
                    <div className="flex items-center justify-between gap-4 sm:justify-end">
                      <span className="font-semibold tabular-nums">
                        {item.current_value.amount_pln == null
                          ? "—"
                          : formatCurrency(
                              Number(item.current_value.amount_pln),
                              "PLN",
                            )}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={restoreItem.isPending}
                        onClick={() => restoreItem.mutate(item.id)}
                      >
                        <ArchiveRestore className="h-4 w-4" />
                        {t("assets.restoreItem")}
                      </Button>
                    </div>
                  </div>
                ))}
              </Card>
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
