"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Loader2,
  Layers3,
  Plus,
  RefreshCw,
  Search,
  WalletCards,
} from "lucide-react";
import { toast } from "sonner";
import {
  api,
  type AssetAccount,
  type AssetAccountInput,
  type AssetTrackingMode,
  type AssetItem,
  type AssetItemInput,
  type AssetValuation,
  type AssetValuationInput,
} from "@/lib/api";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { HelpTooltip } from "@/components/help-tooltip";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { useConfirm } from "@/components/confirm-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { useFormatters, useT } from "@/lib/i18n";
import { invalidateAssetData, queryKeys } from "@/lib/query-keys";
import { showErrorToast } from "@/lib/toasts";
import { ASSET_TYPES, assetTypeKey } from "./_lib/asset-options";
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
  const [search, setSearch] = useState("");
  const [currency, setCurrency] = useState("all");
  const [createMode, setCreateMode] = useState<AssetTrackingMode>("aggregate");
  const [accountDialogOpen, setAccountDialogOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<AssetAccount | null>(
    null,
  );
  const [itemAccount, setItemAccount] = useState<AssetAccount | null>(null);
  const [editingItem, setEditingItem] = useState<{
    account: AssetAccount;
    item: AssetItem;
  } | null>(null);
  const [valuationTarget, setValuationTarget] =
    useState<ValuationTarget | null>(null);
  const [historyTarget, setHistoryTarget] = useState<HistoryTarget | null>(
    null,
  );

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
    onSuccess: async () => {
      setSearch("");
      setCurrency("all");
      await refresh();
      toast.success(t("assets.accountAdded"));
    },
    onError: (error) => showErrorToast(error, t("assets.saveError")),
  });
  const createItem = useMutation({
    mutationFn: ({
      accountId,
      payload,
    }: {
      accountId: number;
      payload: AssetItemInput;
    }) => api.createAssetItem(accountId, payload),
    onSuccess: async () => {
      setSearch("");
      setCurrency("all");
      await refresh();
      toast.success(t("assets.itemAdded"));
    },
    onError: (error) => showErrorToast(error, t("assets.saveError")),
  });
  const updateAccount = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: number;
      payload: Partial<AssetAccountInput>;
    }) => api.updateAssetAccount(id, payload),
    onSuccess: () => {
      toast.success(t("assets.accountUpdated"));
      void refresh();
    },
    onError: (error) => showErrorToast(error, t("assets.saveError")),
  });
  const updateItem = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: number;
      payload: Partial<AssetItemInput>;
    }) => api.updateAssetItem(id, payload),
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
  const query = search.trim().toLocaleLowerCase();
  const currencies = [
    ...new Set(
      accounts.flatMap((account) =>
        account.tracking_mode === "aggregate"
          ? [account.native_currency ?? account.default_currency]
          : account.items.length
            ? account.items.map((item) => item.currency)
            : [account.default_currency],
      ),
    ),
  ].sort();
  const filtered = Boolean(query) || currency !== "all";
  const matchesCurrency = (account: AssetAccount) =>
    currency === "all" ||
    (account.tracking_mode === "aggregate"
      ? (account.native_currency ?? account.default_currency) === currency
      : account.items.length
        ? account.items.some((item) => item.currency === currency)
        : account.default_currency === currency);
  const currencyScopedAccounts = accounts.filter(matchesCurrency);
  const visibleAccounts = accounts.filter((account) => {
    const matchingItems = account.items.filter(
      (item) => currency === "all" || item.currency === currency,
    );
    return (
      matchesCurrency(account) &&
      [
        account.name,
        account.institution,
        ...matchingItems.map((item) => item.name),
      ].some((value) => value?.toLocaleLowerCase().includes(query))
    );
  });
  const currencyValues = accounts.flatMap((account) => {
    if (account.tracking_mode === "aggregate") {
      if ((account.native_currency ?? account.default_currency) !== currency)
        return [];
      return [
        account.unconverted_count || account.missing_valuation_count
          ? null
          : account.amount_pln,
      ];
    }
    return account.items
      .filter((item) => item.currency === currency)
      .map((item) =>
        item.current_value.unconverted ? null : item.current_value.amount_pln,
      );
  });
  const convertedValues = currencyValues.filter((value) => value != null);
  const currencyTotal = convertedValues.reduce<number>(
    (sum, value) => sum + Number(value),
    0,
  );
  const currencyTotalMissing = convertedValues.length < currencyValues.length;
  const summaryCounts = [
    {
      label: t("assets.individualAssets"),
      count: currencyScopedAccounts.filter(
        (account) => account.tracking_mode === "aggregate",
      ).length,
    },
    {
      label: t("assets.summaryPortfolios"),
      count: currencyScopedAccounts.filter(
        (account) => account.tracking_mode === "detailed",
      ).length,
    },
    {
      label: t("assets.summaryHoldings"),
      count: currencyScopedAccounts
        .filter((account) => account.tracking_mode === "detailed")
        .reduce(
          (sum, account) =>
            sum +
            account.items.filter(
              (item) => currency === "all" || item.currency === currency,
            ).length,
          0,
        ),
    },
  ];
  const groups = [
    ...ASSET_TYPES.map((type) => ({
      key: type,
      label: t(assetTypeKey(type)),
      accounts: visibleAccounts.filter(
        (account) =>
          account.tracking_mode === "aggregate" &&
          (account.aggregate_asset_type ?? "other") === type,
      ),
    })),
    {
      key: "portfolios",
      label: t("assets.portfolios"),
      accounts: visibleAccounts.filter(
        (account) => account.tracking_mode === "detailed",
      ),
    },
  ].filter((group) => group.accounts.length > 0);

  const panels = [
    {
      key: "assets",
      label: t("assets.individualAssets"),
      icon: WalletCards,
      groups: groups.filter((group) => group.key !== "portfolios"),
      empty: t("assets.noIndividualAssets"),
    },
    {
      key: "portfolios",
      label: t("assets.portfolios"),
      icon: Layers3,
      groups: groups.filter((group) => group.key === "portfolios"),
      empty: t("assets.noPortfolios"),
    },
  ];

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

  function openCreate(mode: AssetTrackingMode) {
    setCreateMode(mode);
    setEditingAccount(null);
    setAccountDialogOpen(true);
  }

  const addMenu = (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size="sm">
          <Plus className="h-4 w-4" />
          {t("assets.addAccount")}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-72">
        <DropdownMenuItem
          onSelect={() => openCreate("aggregate")}
          className="gap-3 px-3 py-2"
        >
          <WalletCards className="h-4 w-4 shrink-0" />
          {t("assets.addHolding")}
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={() => openCreate("detailed")}
          className="gap-3 px-3 py-2"
        >
          <Layers3 className="h-4 w-4 shrink-0" />
          {t("assets.addPortfolio")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );

  if (failed) {
    return (
      <div className="space-y-6">
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
    <div className="space-y-6">
      <PageHeader title={t("assets.title")} />
      <AssetSectionTabs />

      {loading ? (
        <AssetsSkeleton />
      ) : overview ? (
        <>
          <section className="border-b pb-4 pt-1">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:gap-10">
              <div className="lg:w-72 lg:shrink-0">
                <HelpTooltip content={t("assets.estimateBasis")}>
                  <p className="w-fit text-sm text-muted-foreground">
                    {currency === "all"
                      ? t("assets.totalAssetsValue")
                      : t("assets.currencyTotal", { currency })}
                  </p>
                </HelpTooltip>
                <p className="mt-1 text-3xl font-semibold tracking-tight tabular-nums">
                  {currency !== "all" &&
                  currencyValues.length > 0 &&
                  !convertedValues.length
                    ? "—"
                    : formatCurrency(
                        currency === "all"
                          ? Number(overview.total_pln)
                          : currencyTotal,
                        overview.base_currency,
                      )}
                  {currency !== "all" && currencyTotalMissing ? (
                    <HelpTooltip content={t("assets.partialGroupTotal")}>
                      <AlertTriangle
                        className="ml-2 inline h-4 w-4 text-warning"
                        aria-label={t("assets.partialGroupTotal")}
                      />
                    </HelpTooltip>
                  ) : null}
                </p>
              </div>
              <dl className="flex gap-6 border-t pt-3 sm:gap-8 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
                {summaryCounts.map(({ label, count }) => (
                  <div
                    key={label}
                    className="flex min-w-14 flex-col items-center gap-2 text-center"
                  >
                    <dt className="text-xs text-muted-foreground">{label}</dt>
                    <dd className="text-lg font-semibold tabular-nums">
                      {count}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          </section>

          {overview.unconverted_count > 0 ? (
            <section className="flex flex-col gap-4 rounded-lg border border-warning/35 bg-warning/5 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex gap-3">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
                <div>
                  <p className="text-sm font-medium">
                    {t("assets.unconvertedAlert", {
                      count: overview.unconverted_count,
                    })}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {t("assets.unconvertedHint")}
                  </p>
                </div>
              </div>
              <Button
                variant="outline"
                onClick={() => recomputeFx.mutate()}
                disabled={recomputeFx.isPending}
              >
                {recomputeFx.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
                {t("assets.retryFx")}
              </Button>
            </section>
          ) : null}

          <section className="space-y-5">
            {accounts.length > 0 ? (
              <div className="space-y-2">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                  <div className="relative w-full sm:max-w-lg">
                    <Search
                      className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                      aria-hidden="true"
                    />
                    <Input
                      value={search}
                      onChange={(event) => setSearch(event.target.value)}
                      placeholder={t("assets.search")}
                      aria-label={t("assets.search")}
                      className="pl-9"
                    />
                  </div>
                  <Select value={currency} onValueChange={setCurrency}>
                    <SelectTrigger
                      className="w-full sm:w-48 sm:shrink-0"
                      aria-label={t("assets.filterCurrency")}
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">
                        {t("assets.allCurrencies")}
                      </SelectItem>
                      {currencies.map((code) => (
                        <SelectItem key={code} value={code}>
                          {code}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {filtered ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="shrink-0"
                      onClick={() => {
                        setSearch("");
                        setCurrency("all");
                      }}
                    >
                      {t("assets.clearFilters")}
                    </Button>
                  ) : null}
                </div>
              </div>
            ) : null}

            {accounts.length ? (
              <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
                {panels.map((panel) => (
                  <section
                    key={panel.key}
                    className="min-w-0 overflow-hidden rounded-lg border bg-card"
                    aria-label={panel.label}
                  >
                    <div className="flex flex-wrap items-center gap-2.5 border-b bg-muted/20 px-5 py-4">
                      <panel.icon className="h-5 w-5 text-muted-foreground" />
                      <h2 className="text-base font-semibold">{panel.label}</h2>
                      <Badge variant="secondary">
                        {panel.groups.reduce(
                          (count, group) => count + group.accounts.length,
                          0,
                        )}
                      </Badge>
                      <Button
                        size="sm"
                        variant="outline"
                        className="ml-auto shrink-0"
                        onClick={() =>
                          openCreate(
                            panel.key === "assets" ? "aggregate" : "detailed",
                          )
                        }
                      >
                        <Plus className="h-4 w-4" />
                        {t(
                          panel.key === "assets"
                            ? "assets.addHolding"
                            : "assets.createAccount",
                        )}
                      </Button>
                    </div>
                    <div className="px-5 py-2">
                      {panel.groups.length ? (
                        panel.groups.map((group) => {
                          const valuedAccounts = group.accounts.filter(
                            (account) =>
                              account.unconverted_count === 0 &&
                              account.missing_valuation_count === 0,
                          );
                          const partial =
                            valuedAccounts.length < group.accounts.length;
                          const groupTotal = valuedAccounts.reduce(
                            (sum, account) => sum + Number(account.amount_pln),
                            0,
                          );
                          return (
                            <div
                              key={group.key}
                              className={
                                panel.key === "assets"
                                  ? "-mx-5 border-t border-border px-5 pb-3 pt-4 first:border-t-0 first:pt-2"
                                  : "py-2"
                              }
                            >
                              {panel.key === "assets" ? (
                                <div className="flex min-h-12 flex-wrap items-center justify-between gap-x-4 gap-y-2 pb-3 text-base font-semibold">
                                  <h3 className="flex min-w-0 items-center gap-2">
                                    {group.label}
                                    <Badge
                                      variant="secondary"
                                      className="font-medium"
                                    >
                                      {group.accounts.length}
                                    </Badge>
                                  </h3>
                                  <div className="ml-auto flex shrink-0 items-center gap-1.5 tabular-nums">
                                    <span>
                                      {valuedAccounts.length
                                        ? formatCurrency(groupTotal, "PLN")
                                        : "—"}
                                    </span>
                                    {partial ? (
                                      <HelpTooltip
                                        content={t("assets.partialGroupTotal")}
                                      >
                                        <AlertTriangle
                                          className="h-3.5 w-3.5 text-warning"
                                          aria-label={t(
                                            "assets.partialGroupTotal",
                                          )}
                                        />
                                      </HelpTooltip>
                                    ) : null}
                                  </div>
                                </div>
                              ) : null}
                              <div
                                className={
                                  panel.key === "assets"
                                    ? "space-y-0.5"
                                    : "ml-1 space-y-0.5 pl-1"
                                }
                              >
                                {group.accounts.map((account) => (
                                  <AssetAccountCard
                                    key={account.id}
                                    account={account}
                                    asOf={overview.as_of}
                                    showAssetType={false}
                                    onAddItem={setItemAccount}
                                    onUpdate={(target) =>
                                      void openValuationUpdate(target)
                                    }
                                    onHistory={setHistoryTarget}
                                    onArchiveAccount={(row) =>
                                      void confirmArchiveAccount(row)
                                    }
                                    onArchiveItem={(row) =>
                                      void confirmArchiveItem(row)
                                    }
                                    onEditAccount={(row) => {
                                      setEditingAccount(row);
                                      setAccountDialogOpen(true);
                                    }}
                                    onEditItem={(accountRow, item) =>
                                      setEditingItem({
                                        account: accountRow,
                                        item,
                                      })
                                    }
                                  />
                                ))}
                              </div>
                            </div>
                          );
                        })
                      ) : (
                        <p className="py-8 text-sm text-muted-foreground">
                          {filtered ? t("assets.noSearchResults") : panel.empty}
                        </p>
                      )}
                    </div>
                  </section>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={WalletCards}
                title={t("assets.emptyTitle")}
                description={t("assets.emptyDescription")}
                action={addMenu}
              />
            )}
          </section>
        </>
      ) : null}

      <AssetAccountDialog
        key={editingAccount?.id ?? `new-${createMode}`}
        mode={editingAccount?.tracking_mode ?? createMode}
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
        key={
          editingItem
            ? `edit-${editingItem.item.id}`
            : `new-${itemAccount?.id ?? "none"}`
        }
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

function AssetsSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-28 w-full" />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    </div>
  );
}
