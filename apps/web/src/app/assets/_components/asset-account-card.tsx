"use client";

import { useState } from "react";
import {
  Archive,
  ArchiveRestore,
  Banknote,
  Bitcoin,
  ChartPie,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Edit3,
  FileText,
  Gem,
  HandCoins,
  History,
  Landmark,
  Layers3,
  MoreHorizontal,
  Package,
  PiggyBank,
  Plus,
  RefreshCw,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";
import type { AssetAccount, AssetItem, AssetType } from "@/lib/api";
import { HelpTooltip } from "@/components/help-tooltip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useFormatters, useT } from "@/lib/i18n";
import {
  accountKindKey,
  assetTypeKey,
  wrapperKey,
} from "../_lib/asset-options";
import type { HistoryTarget } from "./asset-valuation-history-dialog";
import type { ValuationTarget } from "./asset-valuation-dialog";
import { AssetDetailsSheet } from "./asset-details-sheet";

const ASSET_TYPE_ICONS: Record<AssetType, LucideIcon> = {
  cash: Banknote,
  savings_account: Landmark,
  deposit: PiggyBank,
  bond: FileText,
  stock: TrendingUp,
  etf: ChartPie,
  fund: Layers3,
  crypto: Bitcoin,
  precious_metal: Gem,
  loan_receivable: HandCoins,
  other: Package,
};

export function AssetAccountCard({
  account,
  asOf,
  showAssetType = true,
  onAddItem,
  onUpdate,
  onHistory,
  onArchiveAccount,
  onArchiveItem,
  onEditAccount,
  onEditItem,
  onRestoreAccount,
  onRestoreItem,
}: {
  account: AssetAccount;
  asOf: string;
  showAssetType?: boolean;
  onAddItem?: (account: AssetAccount) => void;
  onUpdate?: (target: ValuationTarget) => void;
  onHistory: (target: HistoryTarget) => void;
  onArchiveAccount?: (account: AssetAccount) => void;
  onArchiveItem?: (item: AssetItem) => void;
  onEditAccount?: (account: AssetAccount) => void;
  onEditItem?: (account: AssetAccount, item: AssetItem) => void;
  onRestoreAccount?: (account: AssetAccount) => void;
  onRestoreItem?: (item: AssetItem) => void;
}) {
  const { t, locale } = useT();
  const { formatCurrency, formatDate } = useFormatters();
  const [expanded, setExpanded] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const aggregate = account.tracking_mode === "aggregate";
  const archived = Boolean(account.archived_at);
  const valuationAgeDays = account.valuation_date
    ? Math.max(
        0,
        Math.round(
          (Date.parse(asOf) - Date.parse(account.valuation_date)) / 86_400_000,
        ),
      )
    : null;
  const valuationAge =
    valuationAgeDays != null
      ? new Intl.RelativeTimeFormat(locale, { numeric: "auto" }).format(
          -valuationAgeDays,
          "day",
        )
      : null;
  const valuationAgeClassName =
    account.stale_count > 0 ? "text-warning" : undefined;
  const issueCount =
    account.unconverted_count +
    (aggregate ? 0 : account.missing_valuation_count);

  const valuationTarget: ValuationTarget | null =
    aggregate && account.valuation_item_id
      ? {
          itemId: account.valuation_item_id,
          itemName: account.name,
          assetType: account.aggregate_asset_type ?? "other",
          currency: account.native_currency ?? account.default_currency,
          currentNativeValue: account.native_value,
        }
      : null;
  const AssetIcon =
    ASSET_TYPE_ICONS[account.aggregate_asset_type ?? "other"];

  return (
    <article className={aggregate ? undefined : "px-2"}>
      <div
        className="group/row -mx-2 flex items-start gap-3 rounded-md px-2 py-3.5 transition-colors hover:bg-accent/60"
      >
        {!aggregate ? (
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-expanded={expanded}
            aria-controls={`asset-items-${account.id}`}
            aria-label={`${account.name}: ${expanded ? t("common.collapse") : t("common.expand")}`}
          >
            {expanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </button>
        ) : null}
        {aggregate ? (
          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/8 text-primary">
            <AssetIcon className="h-4 w-4" aria-hidden="true" />
          </div>
        ) : null}
        <div className="min-w-0 flex-1">
          <div
            className={
              aggregate
                ? "flex items-start justify-between gap-3"
                : "flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"
            }
          >
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h3
                  className={
                    aggregate
                      ? "min-w-0 break-words text-sm font-medium [overflow-wrap:anywhere]"
                      : "truncate text-sm font-semibold"
                  }
                >
                  {aggregate ? (
                    <button
                      type="button"
                      className="max-w-full whitespace-normal break-words rounded-sm text-left underline-offset-4 transition-colors hover:text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      title={t("assets.assetDetails")}
                      onClick={() => setDetailsOpen(true)}
                    >
                      {account.name}
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setDetailsOpen(true)}
                      className="rounded-sm text-left underline-offset-4 transition-colors hover:text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      title={t("assets.portfolioDetails")}
                    >
                      {account.name}
                    </button>
                  )}
                </h3>
                {aggregate ? (
                  showAssetType ? (
                    <Badge variant="muted">
                      {t(assetTypeKey(account.aggregate_asset_type ?? "other"))}
                    </Badge>
                  ) : null
                ) : (
                  <Badge variant="secondary" className="py-0 font-medium">
                    {account.items.length}
                  </Badge>
                )}
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground empty:hidden">
                {account.institution && !aggregate ? (
                  <span>{account.institution}</span>
                ) : null}
                {!aggregate ? (
                  <span>
                    {t(accountKindKey(account.kind))}
                    {account.wrapper !== "standard"
                      ? `, ${t(wrapperKey(account.wrapper))}`
                      : ""}
                  </span>
                ) : null}
                {account.projected ? (
                  <HelpTooltip content={t("assets.estimatedHint")}>
                    <Badge variant="info" className="py-0">
                      {t("assets.estimated")}
                    </Badge>
                  </HelpTooltip>
                ) : null}
                {archived ? (
                  <Badge variant="muted">{t("assets.archived")}</Badge>
                ) : null}
              </div>
              {aggregate ? (
                <p className="mt-1 flex flex-wrap items-center gap-x-2 text-xs">
                  <span className="text-muted-foreground">
                    {account.valuation_date
                      ? t("assets.valuedOn", {
                          date: formatDate(account.valuation_date),
                        })
                      : t("assets.noValuation")}
                  </span>
                  {valuationAge ? (
                    <>
                      {valuationAgeClassName ? (
                        <HelpTooltip content={t("assets.staleHint")}>
                          <span className={`font-medium ${valuationAgeClassName}`}>
                            {valuationAge}
                          </span>
                        </HelpTooltip>
                      ) : (
                        <span className="font-medium text-foreground/70">
                          {valuationAge}
                        </span>
                      )}
                    </>
                  ) : null}
                </p>
              ) : null}

              {account.matured_count > 0 ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  {t("assets.matured")}
                </p>
              ) : null}
            </div>
            <div
              className={
                aggregate
                  ? "flex w-[40%] max-w-36 shrink-0 flex-col items-end gap-1.5 sm:w-auto sm:max-w-none sm:flex-row sm:items-center"
                  : "flex shrink-0 items-center justify-end gap-0.5"
              }
            >
              <div
                className={
                  aggregate
                    ? "text-right sm:min-w-28 sm:pr-2"
                    : "min-w-28 pr-2 text-right"
                }
              >
                <p
                  className={
                    aggregate
                      ? "whitespace-nowrap text-sm font-semibold tabular-nums leading-5"
                      : "whitespace-nowrap text-sm font-semibold tabular-nums leading-5"
                  }
                >
                  {aggregate &&
                  (account.missing_valuation_count > 0 ||
                    account.unconverted_count > 0)
                    ? "—"
                    : formatCurrency(Number(account.amount_pln), "PLN")}
                </p>
                {aggregate &&
                account.native_currency !== "PLN" &&
                account.native_value != null ? (
                  <p className="text-xs tabular-nums text-muted-foreground">
                    {formatCurrency(
                      Number(account.native_value),
                      account.native_currency ?? account.default_currency,
                    )}
                  </p>
                ) : null}
              </div>
              <div
                className={
                  aggregate
                    ? "flex w-full items-center justify-end gap-0.5 text-muted-foreground sm:w-auto"
                    : "contents"
                }
              >
                {!archived && valuationTarget && onUpdate ? (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-muted-foreground group-hover/row:text-foreground group-focus-within/row:text-foreground hover:bg-primary/10 hover:text-primary sm:w-auto sm:px-2"
                    aria-label={t("assets.updateValue")}
                    onClick={() => onUpdate(valuationTarget)}
                  >
                    <RefreshCw className="h-4 w-4" />
                    <span className="hidden text-xs font-normal sm:inline">
                      {t("assets.updateValue")}
                    </span>
                  </Button>
                ) : null}
                {!aggregate && !archived && onAddItem ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 text-muted-foreground group-hover/row:text-foreground group-focus-within/row:text-foreground hover:bg-primary/10 hover:text-primary"
                    onClick={() => onAddItem(account)}
                  >
                    <Plus className="h-4 w-4" />
                    {t("assets.addItem")}
                  </Button>
                ) : null}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-muted-foreground/80 group-hover/row:text-foreground group-focus-within/row:text-foreground hover:bg-primary/10 hover:text-primary"
                      aria-label={t("common.actions")}
                    >
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {valuationTarget ? (
                      <DropdownMenuItem
                        onSelect={() =>
                          onHistory({ ...valuationTarget, readOnly: archived })
                        }
                      >
                        <History className="h-4 w-4" />
                        {t("assets.history")}
                      </DropdownMenuItem>
                    ) : null}
                    {archived && onRestoreAccount ? (
                      <DropdownMenuItem
                        onSelect={() => onRestoreAccount(account)}
                      >
                        <ArchiveRestore className="h-4 w-4" />
                        {t("assets.restoreAccount")}
                      </DropdownMenuItem>
                    ) : (
                      <>
                        {onEditAccount ? (
                          <DropdownMenuItem
                            onSelect={() => onEditAccount(account)}
                          >
                            <Edit3 className="h-4 w-4" />
                            {t(
                              aggregate
                                ? "assets.editHolding"
                                : "assets.editAccount",
                            )}
                          </DropdownMenuItem>
                        ) : null}
                        {onArchiveAccount ? (
                          <DropdownMenuItem
                            onSelect={() => onArchiveAccount(account)}
                          >
                            <Archive className="h-4 w-4" />
                            {t("assets.archiveAccount")}
                          </DropdownMenuItem>
                        ) : null}
                      </>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          </div>
          {issueCount > 0 ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {account.unconverted_count ? (
                <Badge variant="destructive">
                  {t("assets.unconvertedCount", {
                    count: account.unconverted_count,
                  })}
                </Badge>
              ) : null}
              {!aggregate && account.missing_valuation_count ? (
                <Badge variant="muted">
                  {t("assets.missingCount", {
                    count: account.missing_valuation_count,
                  })}
                </Badge>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>

      {!aggregate && expanded ? (
        <div id={`asset-items-${account.id}`} className="pb-2 pl-11">
          <div className="space-y-3">
            {account.items.length ? (
              <div className="space-y-0.5">
                {account.items.map((item) => (
                  <AssetItemRow
                    key={item.id}
                    item={item}
                    onUpdate={onUpdate}
                    onHistory={onHistory}
                    onArchive={onArchiveItem}
                    onRestore={onRestoreItem}
                    onEdit={
                      onEditItem
                        ? (item) => onEditItem(account, item)
                        : undefined
                    }
                    parentArchived={archived}
                    asOf={asOf}
                    formatCurrency={formatCurrency}
                    formatDate={formatDate}
                  />
                ))}
              </div>
            ) : (
              <div className="flex items-center gap-3 py-3 text-sm text-muted-foreground">
                <CircleAlert className="h-4 w-4 shrink-0" />
                {t("assets.noItems")}
              </div>
            )}
          </div>
        </div>
      ) : null}

      <AssetDetailsSheet
        account={account}
        open={detailsOpen}
        onOpenChange={setDetailsOpen}
        valuationTarget={valuationTarget}
        onAddItem={onAddItem}
        onUpdate={onUpdate}
        onHistory={onHistory}
        onEdit={onEditAccount}
      />
    </article>
  );
}

function AssetItemRow({
  item,
  onUpdate,
  onHistory,
  onArchive,
  onRestore,
  onEdit,
  parentArchived,
  asOf,
  formatCurrency,
  formatDate,
}: {
  item: AssetItem;
  onUpdate?: (target: ValuationTarget) => void;
  onHistory: (target: HistoryTarget) => void;
  onArchive?: (item: AssetItem) => void;
  onRestore?: (item: AssetItem) => void;
  onEdit?: (item: AssetItem) => void;
  parentArchived: boolean;
  asOf: string;
  formatCurrency: (amount: number, currency?: string) => string;
  formatDate: (value: string | Date) => string;
}) {
  const { t, locale } = useT();
  const value = item.current_value;
  const archived = Boolean(item.archived_at);
  const ItemIcon = ASSET_TYPE_ICONS[item.asset_type];
  const valuationAgeDays = value.valuation_date
    ? Math.max(
        0,
        Math.round(
          (Date.parse(asOf) - Date.parse(value.valuation_date)) / 86_400_000,
        ),
      )
    : null;
  const valuationAge =
    valuationAgeDays != null
      ? new Intl.RelativeTimeFormat(locale, { numeric: "auto" }).format(
          -valuationAgeDays,
          "day",
        )
      : null;
  return (
    <div className="group/item -mx-2 flex items-start gap-3 rounded-md px-2 py-3 transition-colors hover:bg-accent/60">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/8 text-primary">
        <ItemIcon className="h-4 w-4" aria-hidden="true" />
      </div>
      <div className="min-w-0 flex-1 flex-col gap-3 sm:flex sm:flex-row sm:items-center">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate text-sm font-medium">{item.name}</p>
            <Badge variant="secondary">
              {t(assetTypeKey(item.asset_type))}
            </Badge>
            {value.projected ? (
              <HelpTooltip content={t("assets.estimatedHint")}>
                <Badge variant="info">{t("assets.estimated")}</Badge>
              </HelpTooltip>
            ) : null}
            {value.stale ? (
              <HelpTooltip content={t("assets.staleHint")}>
                <Badge variant="muted">{t("assets.stale")}</Badge>
              </HelpTooltip>
            ) : null}
            {value.matured ? (
              <HelpTooltip content={t("assets.maturedHint")}>
                <Badge variant="muted">{t("assets.matured")}</Badge>
              </HelpTooltip>
            ) : null}
            {value.unconverted ? (
              <HelpTooltip content={t("assets.unconvertedHint")}>
                <Badge variant="destructive">{t("assets.unconverted")}</Badge>
              </HelpTooltip>
            ) : null}
            {archived ? (
              <Badge variant="muted">{t("assets.archived")}</Badge>
            ) : null}
          </div>
          <p className="mt-1 flex flex-wrap items-center gap-x-2 text-xs">
            <span className="text-muted-foreground">
              {value.valuation_date
                ? t("assets.valuedOn", {
                    date: formatDate(value.valuation_date),
                  })
                : t("assets.noValuation")}
              {item.symbol ? ` – ${item.symbol}` : ""}
            </span>
            {valuationAge ? (
              value.stale ? (
                <HelpTooltip content={t("assets.staleHint")}>
                  <span className="font-medium text-warning">
                    {valuationAge}
                  </span>
                </HelpTooltip>
              ) : (
                <span className="font-medium text-foreground/70">
                  {valuationAge}
                </span>
              )
            ) : null}
          </p>
        </div>
        <div className="mt-3 flex items-center justify-between gap-0.5 sm:mt-0 sm:justify-end">
          <div className="min-w-28 pr-2 text-right">
            <p className="text-sm font-semibold tabular-nums">
              {value.amount_pln != null
                ? formatCurrency(Number(value.amount_pln), "PLN")
                : "—"}
            </p>
            {value.native_value != null && value.currency !== "PLN" ? (
              <p className="text-xs tabular-nums text-muted-foreground">
                {formatCurrency(Number(value.native_value), value.currency)}
              </p>
            ) : null}
          </div>
          {!archived && !parentArchived && onUpdate ? (
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground group-hover/item:text-foreground group-focus-within/item:text-foreground hover:bg-primary/10 hover:text-primary sm:w-auto sm:px-2"
              aria-label={t("assets.updateValue")}
              onClick={() =>
                onUpdate({
                  itemId: item.id,
                  itemName: item.name,
                  assetType: item.asset_type,
                  currency: item.currency,
                  currentNativeValue: value.native_value,
                })
              }
            >
              <RefreshCw className="h-4 w-4" />
              <span className="hidden text-xs font-normal sm:inline">
                {t("assets.updateValue")}
              </span>
            </Button>
          ) : null}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-muted-foreground/80 group-hover/item:text-foreground group-focus-within/item:text-foreground hover:bg-primary/10 hover:text-primary"
                aria-label={t("common.actions")}
              >
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {!archived && !parentArchived && (onEdit || onUpdate) ? (
                <>
                  {onEdit ? (
                    <DropdownMenuItem onSelect={() => onEdit(item)}>
                      <Edit3 className="h-4 w-4" />
                      {t("assets.editItem")}
                    </DropdownMenuItem>
                  ) : null}
                </>
              ) : null}
              <DropdownMenuItem
                onSelect={() =>
                  onHistory({
                    itemId: item.id,
                    itemName: item.name,
                    assetType: item.asset_type,
                    currency: item.currency,
                    readOnly: archived || parentArchived,
                  })
                }
              >
                <History className="h-4 w-4" />
                {t("assets.history")}
              </DropdownMenuItem>
              {!parentArchived ? (
                archived && onRestore ? (
                  <DropdownMenuItem onSelect={() => onRestore(item)}>
                    <ArchiveRestore className="h-4 w-4" />
                    {t("assets.restoreItem")}
                  </DropdownMenuItem>
                ) : !archived && onArchive ? (
                  <DropdownMenuItem onSelect={() => onArchive(item)}>
                    <Archive className="h-4 w-4" />
                    {t("assets.archiveItem")}
                  </DropdownMenuItem>
                ) : null
              ) : null}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </div>
  );
}
