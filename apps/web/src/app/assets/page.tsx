"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Loader2,
  Plus,
  RefreshCw,
  WalletCards,
} from "lucide-react";
import { toast } from "sonner";
import {
  api,
  type AssetAccount,
  type AssetAccountInput,
  type AssetItem,
  type AssetItemInput,
  type AssetValuation,
  type AssetValuationInput,
} from "@/lib/api";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { useConfirm } from "@/components/confirm-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useFormatters, useT } from "@/lib/i18n";
import { invalidateAssetData, queryKeys } from "@/lib/query-keys";
import { showErrorToast } from "@/lib/toasts";
import { AssetAccountCard } from "./_components/asset-account-card";
import { AssetAccountDialog } from "./_components/asset-account-dialog";
import { AssetItemDialog } from "./_components/asset-item-dialog";
import { AssetSectionTabs } from "./_components/asset-section-tabs";
import {
  AssetValuationDialog,
  type ValuationTarget,
} from "./_components/asset-valuation-dialog";
import { todayIso } from "./_components/asset-valuation-fields";
import {
  AssetValuationHistoryDialog,
  type HistoryTarget,
} from "./_components/asset-valuation-history-dialog";

export default function AssetsPage() {
  const { t } = useT();
  const { formatCurrency, formatDate } = useFormatters();
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [accountDialogOpen, setAccountDialogOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<AssetAccount | null>(null);
  const [itemAccount, setItemAccount] = useState<AssetAccount | null>(null);
  const [editingItem, setEditingItem] = useState<{
    account: AssetAccount;
    item: AssetItem;
  } | null>(null);
  const [valuationTarget, setValuationTarget] = useState<ValuationTarget | null>(null);
  const [historyTarget, setHistoryTarget] = useState<HistoryTarget | null>(null);

  const overviewQuery = useQuery({
    queryKey: queryKeys.assets.overview,
    queryFn: api.assetOverview,
  });
  const accountsQuery = useQuery({
    queryKey: queryKeys.assets.accounts(false),
    queryFn: () => api.assetAccounts(false),
  });
  const refresh = () => invalidateAssetData(queryClient);
  const createAccount = useMutation({
    mutationFn: api.createAssetAccount,
    onSuccess: () => {
      toast.success(t("assets.accountAdded"));
      void refresh();
    },
    onError: (error) => showErrorToast(error, t("assets.saveError")),
  });
  const createItem = useMutation({
    mutationFn: ({ accountId, payload }: { accountId: number; payload: AssetItemInput }) =>
      api.createAssetItem(accountId, payload),
    onSuccess: () => {
      toast.success(t("assets.itemAdded"));
      void refresh();
    },
    onError: (error) => showErrorToast(error, t("assets.saveError")),
  });
  const updateAccount = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<AssetAccountInput> }) =>
      api.updateAssetAccount(id, payload),
    onSuccess: () => {
      toast.success(t("assets.accountUpdated"));
      void refresh();
    },
    onError: (error) => showErrorToast(error, t("assets.saveError")),
  });
  const updateItem = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<AssetItemInput> }) =>
      api.updateAssetItem(id, payload),
    onSuccess: () => {
      toast.success(t("assets.itemUpdated"));
      void refresh();
    },
    onError: (error) => showErrorToast(error, t("assets.saveError")),
  });
  const saveValuation = useMutation({
    mutationFn: ({
      itemId,
      payload,
      valuationId,
    }: {
      itemId: number;
      payload: AssetValuationInput;
      valuationId?: number;
    }) =>
      valuationId
        ? api.updateAssetValuation(valuationId, payload)
        : api.createAssetValuation(itemId, payload),
    onSuccess: () => {
      toast.success(t("assets.valuationSaved"));
      void refresh();
    },
    onError: (error) => showErrorToast(error, t("assets.saveError")),
  });
  const archiveAccount = useMutation({
    mutationFn: api.archiveAssetAccount,
    onSuccess: () => {
      toast.success(t("assets.accountArchived"));
      void refresh();
    },
    onError: (error) => showErrorToast(error, t("assets.saveError")),
  });
  const archiveItem = useMutation({
    mutationFn: api.archiveAssetItem,
    onSuccess: () => {
      toast.success(t("assets.itemArchived"));
      void refresh();
    },
    onError: (error) => showErrorToast(error, t("assets.saveError")),
  });
  const deleteValuation = useMutation({
    mutationFn: api.deleteAssetValuation,
    onSuccess: () => {
      toast.success(t("assets.valuationDeleted"));
      void refresh();
    },
    onError: (error) => showErrorToast(error, t("assets.saveError")),
  });
  const recomputeFx = useMutation({
    mutationFn: api.recomputeAssetFx,
    onSuccess: (result) => {
      toast.success(
        t("assets.fxRecomputed", {
          updated: result.updated,
          missing: result.missing,
        }),
      );
      void refresh();
    },
    onError: (error) => showErrorToast(error, t("assets.saveError")),
  });

  const loading = overviewQuery.isLoading || accountsQuery.isLoading;
  const failed = overviewQuery.isError || accountsQuery.isError;
  const overview = overviewQuery.data;
  const accounts = accountsQuery.data ?? [];

  async function confirmArchiveAccount(account: AssetAccount) {
    const accepted = await confirm({
      title: t("assets.archiveAccount"),
      description: t("assets.archiveAccountConfirm", { name: account.name }),
      confirmLabel: t("assets.archive"),
    });
    if (accepted) archiveAccount.mutate(account.id);
  }

  async function confirmArchiveItem(item: AssetItem) {
    const accepted = await confirm({
      title: t("assets.archiveItem"),
      description: t("assets.archiveItemConfirm", { name: item.name }),
      confirmLabel: t("assets.archive"),
    });
    if (accepted) archiveItem.mutate(item.id);
  }

  async function confirmDeleteValuation(valuation: AssetValuation) {
    const accepted = await confirm({
      title: t("assets.deleteValuation"),
      description: t("assets.deleteValuationConfirm", {
        date: formatDate(valuation.valuation_date),
      }),
      confirmLabel: t("common.delete"),
      destructive: true,
    });
    if (accepted) deleteValuation.mutate(valuation.id);
  }

  async function openValuationUpdate(target: ValuationTarget) {
    try {
      const valuations = await queryClient.fetchQuery({
        queryKey: queryKeys.assets.valuations(target.itemId),
        queryFn: () => api.assetValuations(target.itemId),
      });
      const today = todayIso();
      const latest =
        valuations.find((row) => row.valuation_date <= today) ?? null;
      const editsToday = latest?.valuation_date === today;
      setValuationTarget({
        ...target,
        valuation: editsToday ? latest : null,
        prefillValuation: editsToday ? null : latest,
      });
    } catch (error) {
      showErrorToast(error, t("assets.valuationLoadError"));
    }
  }

  if (failed) {
    return (
      <div className="space-y-5">
        <PageHeader title={t("assets.title")} />
        <AssetSectionTabs />
        <ErrorState
          title={t("assets.loadError")}
          onRetry={() => {
            void overviewQuery.refetch();
            void accountsQuery.refetch();
          }}
        />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader title={t("assets.title")} />
      <AssetSectionTabs />

      {loading ? (
        <AssetsSkeleton />
      ) : overview ? (
        <>
          <section className="rounded-lg border bg-card px-5 py-4">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-sm text-muted-foreground">
                  {t("assets.totalAssetsValue")}
                </p>
                <p className="mt-1 text-3xl font-semibold tracking-tight tabular-nums">
                  {formatCurrency(Number(overview.total_pln), overview.base_currency)}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {t("assets.asOf", { date: formatDate(overview.as_of) })}
                </p>
              </div>
              <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
                <SummaryValue label={t("assets.accountCount")} value={overview.account_count} />
                <SummaryValue label={t("assets.components")} value={overview.item_count} />
                <SummaryValue
                  label={t("assets.needReview")}
                  value={overview.stale_count + overview.matured_count + overview.missing_valuation_count}
                  warning={overview.stale_count + overview.matured_count + overview.missing_valuation_count > 0}
                />
              </div>
            </div>
          </section>

          {overview.unconverted_count > 0 ? (
            <section className="flex flex-col gap-4 rounded-lg border border-warning/35 bg-warning/5 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex gap-3">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
                <div>
                  <p className="text-sm font-medium">{t("assets.unconvertedAlert", { count: overview.unconverted_count })}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{t("assets.unconvertedHint")}</p>
                </div>
              </div>
              <Button variant="outline" onClick={() => recomputeFx.mutate()} disabled={recomputeFx.isPending}>
                {recomputeFx.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                {t("assets.retryFx")}
              </Button>
            </section>
          ) : null}

          <section className="space-y-3">
            <div className="flex min-h-9 flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold">{t("assets.accounts")}</h2>
                <Badge variant="secondary">{accounts.length}</Badge>
              </div>
              {accounts.length ? (
                <Button
                  size="sm"
                  onClick={() => {
                    setEditingAccount(null);
                    setAccountDialogOpen(true);
                  }}
                >
                  <Plus className="h-4 w-4" />
                  {t("assets.addAccount")}
                </Button>
              ) : null}
            </div>
            {accounts.length ? (
              <div className="grid items-start gap-4 2xl:grid-cols-2">
                {accounts.map((account) => (
                  <AssetAccountCard
                    key={account.id}
                    account={account}
                    onAddItem={setItemAccount}
                    onUpdate={(target) => void openValuationUpdate(target)}
                    onHistory={setHistoryTarget}
                    onArchiveAccount={(row) => void confirmArchiveAccount(row)}
                    onArchiveItem={(row) => void confirmArchiveItem(row)}
                    onEditAccount={(row) => {
                      setEditingAccount(row);
                      setAccountDialogOpen(true);
                    }}
                    onEditItem={(accountRow, item) =>
                      setEditingItem({ account: accountRow, item })
                    }
                  />
                ))}
              </div>
            ) : (
              <EmptyState
                icon={WalletCards}
                title={t("assets.emptyTitle")}
                description={t("assets.emptyDescription")}
                action={
                  <Button
                    onClick={() => {
                      setEditingAccount(null);
                      setAccountDialogOpen(true);
                    }}
                  >
                    <Plus className="h-4 w-4" />
                    {t("assets.addAccount")}
                  </Button>
                }
              />
            )}
          </section>
        </>
      ) : null}

      <AssetAccountDialog
        key={editingAccount?.id ?? "new-account"}
        account={editingAccount}
        open={accountDialogOpen}
        onOpenChange={(open) => {
          setAccountDialogOpen(open);
          if (!open) setEditingAccount(null);
        }}
        pending={createAccount.isPending || updateAccount.isPending}
        onSubmit={async (payload: AssetAccountInput) => {
          if (editingAccount) {
            await updateAccount.mutateAsync({
              id: editingAccount.id,
              payload: {
                name: payload.name,
                institution: payload.institution,
                kind: payload.kind,
                wrapper: payload.wrapper,
                default_currency: payload.default_currency,
                notes: payload.notes,
                aggregate_asset_type:
                  editingAccount.tracking_mode === "aggregate"
                    ? payload.aggregate_asset_type
                    : undefined,
                review_interval_days:
                  editingAccount.tracking_mode === "aggregate"
                    ? payload.review_interval_days
                    : undefined,
              },
            });
          } else {
            const created = await createAccount.mutateAsync(payload);
            if (created.tracking_mode === "detailed") {
              setItemAccount(created);
            }
          }
        }}
      />
      <AssetItemDialog
        key={editingItem ? `edit-${editingItem.item.id}` : `new-${itemAccount?.id ?? "none"}`}
        account={editingItem?.account ?? itemAccount}
        item={editingItem?.item}
        open={Boolean(itemAccount || editingItem)}
        onOpenChange={(open) => {
          if (!open) {
            setItemAccount(null);
            setEditingItem(null);
          }
        }}
        pending={createItem.isPending || updateItem.isPending}
        onSubmit={async (accountId, payload) => {
          if (editingItem) {
            await updateItem.mutateAsync({
              id: editingItem.item.id,
              payload: {
                name: payload.name,
                asset_type: payload.asset_type,
                currency: payload.currency,
                symbol: payload.symbol,
                isin: payload.isin,
                review_interval_days: payload.review_interval_days,
                notes: payload.notes,
              },
            });
          } else {
            await createItem.mutateAsync({ accountId, payload });
          }
        }}
      />
      {valuationTarget ? (
        <AssetValuationDialog
          key={`${valuationTarget.itemId}-${valuationTarget.valuation?.id ?? valuationTarget.prefillValuation?.id ?? "new"}`}
          target={valuationTarget}
          open
          onOpenChange={(open) => !open && setValuationTarget(null)}
          pending={saveValuation.isPending}
          onSubmit={async (itemId, payload, valuationId) => {
            await saveValuation.mutateAsync({ itemId, payload, valuationId });
          }}
        />
      ) : null}
      <AssetValuationHistoryDialog
        target={historyTarget}
        open={Boolean(historyTarget)}
        onOpenChange={(open) => !open && setHistoryTarget(null)}
        onEdit={(target, valuation) => {
          setHistoryTarget(null);
          setValuationTarget({
            itemId: target.itemId,
            itemName: target.itemName,
            assetType: target.assetType,
            currency: target.currency,
            valuation,
          });
        }}
        onDelete={(valuation) => void confirmDeleteValuation(valuation)}
      />
    </div>
  );
}

function SummaryValue({
  label,
  value,
  warning = false,
}: {
  label: string;
  value: number;
  warning?: boolean;
}) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={warning ? "font-semibold tabular-nums text-warning" : "font-semibold tabular-nums"}>{value}</p>
    </div>
  );
}

function AssetsSkeleton() {
  return (
    <div className="space-y-5">
      <Skeleton className="h-28 w-full" />
      <div className="grid gap-4 2xl:grid-cols-2">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    </div>
  );
}
