"use client";

import { useState } from "react";
import {
  Archive,
  ArchiveRestore,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Edit3,
  History,
  MoreHorizontal,
  Plus,
  RefreshCw,
} from "lucide-react";
import type { AssetAccount, AssetItem } from "@/lib/api";
import { HelpTooltip } from "@/components/help-tooltip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
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

export function AssetAccountCard({
  account,
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
  const { t } = useT();
  const { formatCurrency, formatDate } = useFormatters();
  const [expanded, setExpanded] = useState(false);
  const aggregate = account.tracking_mode === "aggregate";
  const archived = Boolean(account.archived_at);
  const issueCount =
    account.stale_count +
    account.matured_count +
    account.unconverted_count +
    account.missing_valuation_count;

  return (
    <Card className={archived ? "overflow-hidden border-dashed" : "overflow-hidden"}>
      <div className="flex items-start gap-4 p-5">
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md border bg-muted/25 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label={expanded ? t("common.collapse") : t("common.expand")}
        >
          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="truncate font-semibold">{account.name}</h3>
              <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                {account.institution ? <span>{account.institution}</span> : null}
                {account.institution ? <span aria-hidden="true">·</span> : null}
                <span>{t(accountKindKey(account.kind))}</span>
                {account.wrapper !== "standard" ? (
                  <Badge variant="secondary" className="py-0">{t(wrapperKey(account.wrapper))}</Badge>
                ) : null}
                {archived ? <Badge variant="muted">{t("assets.archived")}</Badge> : null}
              </div>
            </div>
            <div className="flex items-start gap-2">
              <div className="text-right">
                <p className="text-lg font-semibold tabular-nums">{formatCurrency(Number(account.amount_pln), "PLN")}</p>
                <p className="text-xs text-muted-foreground">{t("assets.estimatedValue")}</p>
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" aria-label={t("common.actions")}>
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {archived && onRestoreAccount ? (
                    <DropdownMenuItem onSelect={() => onRestoreAccount(account)}>
                      <ArchiveRestore className="h-4 w-4" />
                      {t("assets.restoreAccount")}
                    </DropdownMenuItem>
                  ) : (
                    <>
                      {onEditAccount ? (
                        <DropdownMenuItem onSelect={() => onEditAccount(account)}>
                          <Edit3 className="h-4 w-4" />
                          {t("assets.editAccount")}
                        </DropdownMenuItem>
                      ) : null}
                      {onArchiveAccount ? (
                        <DropdownMenuItem onSelect={() => onArchiveAccount(account)}>
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
          {issueCount > 0 ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {account.stale_count ? <Badge variant="warning">{t("assets.staleCount", { count: account.stale_count })}</Badge> : null}
              {account.matured_count ? <Badge variant="warning">{t("assets.maturedCount", { count: account.matured_count })}</Badge> : null}
              {account.unconverted_count ? <Badge variant="destructive">{t("assets.unconvertedCount", { count: account.unconverted_count })}</Badge> : null}
              {account.missing_valuation_count ? <Badge variant="muted">{t("assets.missingCount", { count: account.missing_valuation_count })}</Badge> : null}
            </div>
          ) : null}
        </div>
      </div>

      {expanded ? (
        <div className="border-t bg-muted/10 px-5 py-4">
          {aggregate && account.valuation_item_id ? (
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="space-y-1 text-sm">
                {account.native_value != null && account.native_currency ? (
                  <p>
                    <span className="text-muted-foreground">{t("assets.sourceValue")}: </span>
                    <span className="font-medium tabular-nums">{formatCurrency(Number(account.native_value), account.native_currency)}</span>
                  </p>
                ) : null}
                <p className="text-xs text-muted-foreground">{t("assets.aggregateAccountHint")}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onHistory({
                    itemId: account.valuation_item_id!,
                    itemName: account.name,
                    assetType: account.aggregate_asset_type ?? "other",
                    currency: account.native_currency ?? account.default_currency,
                    readOnly: archived,
                  })}
                >
                  <History className="h-4 w-4" />
                  {t("assets.history")}
                </Button>
                {!archived && onUpdate ? (
                  <Button
                    size="sm"
                    onClick={() => onUpdate({
                      itemId: account.valuation_item_id!,
                      itemName: account.name,
                      assetType: account.aggregate_asset_type ?? "other",
                      currency: account.native_currency ?? account.default_currency,
                      currentNativeValue: account.native_value,
                    })}
                  >
                    <RefreshCw className="h-4 w-4" />
                    {t("assets.updateValue")}
                  </Button>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {account.items.length ? (
                <div className="divide-y rounded-lg border bg-card">
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
                      formatCurrency={formatCurrency}
                      formatDate={formatDate}
                    />
                  ))}
                </div>
              ) : (
                <div className="flex items-center gap-3 rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                  <CircleAlert className="h-4 w-4 shrink-0" />
                  {t("assets.noItems")}
                </div>
              )}
              {!archived && onAddItem ? (
                <Button variant="outline" size="sm" onClick={() => onAddItem(account)}>
                  <Plus className="h-4 w-4" />
                  {t("assets.addItem")}
                </Button>
              ) : null}
            </div>
          )}
        </div>
      ) : null}
    </Card>
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
  formatCurrency: (amount: number, currency?: string) => string;
  formatDate: (value: string | Date) => string;
}) {
  const { t } = useT();
  const value = item.current_value;
  const archived = Boolean(item.archived_at);
  return (
    <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="truncate text-sm font-medium">{item.name}</p>
          <Badge variant="secondary">{t(assetTypeKey(item.asset_type))}</Badge>
          {value.projected ? (
            <HelpTooltip content={t("assets.estimatedHint")}>
              <Badge variant="info">{t("assets.estimated")}</Badge>
            </HelpTooltip>
          ) : null}
          {value.stale ? (
            <HelpTooltip content={t("assets.staleHint")}>
              <Badge variant="warning">{t("assets.stale")}</Badge>
            </HelpTooltip>
          ) : null}
          {value.matured ? (
            <HelpTooltip content={t("assets.maturedHint")}>
              <Badge variant="warning">{t("assets.matured")}</Badge>
            </HelpTooltip>
          ) : null}
          {value.unconverted ? (
            <HelpTooltip content={t("assets.unconvertedHint")}>
              <Badge variant="destructive">{t("assets.unconverted")}</Badge>
            </HelpTooltip>
          ) : null}
          {archived ? <Badge variant="muted">{t("assets.archived")}</Badge> : null}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          {value.valuation_date
            ? t("assets.valuedOn", { date: formatDate(value.valuation_date) })
            : t("assets.noValuation")}
          {item.symbol ? ` · ${item.symbol}` : ""}
        </p>
      </div>
      <div className="flex items-center justify-between gap-3 sm:justify-end">
        <div className="text-right">
          <p className="text-sm font-semibold tabular-nums">
            {value.amount_pln != null ? formatCurrency(Number(value.amount_pln), "PLN") : "—"}
          </p>
          {value.native_value != null && value.currency !== "PLN" ? (
            <p className="text-xs tabular-nums text-muted-foreground">{formatCurrency(Number(value.native_value), value.currency)}</p>
          ) : null}
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" aria-label={t("common.actions")}><MoreHorizontal className="h-4 w-4" /></Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {!archived && !parentArchived && (onEdit || onUpdate) ? (
              <>
                {onEdit ? (
                  <DropdownMenuItem onSelect={() => onEdit(item)}>
                    <Edit3 className="h-4 w-4" />{t("assets.editItem")}
                  </DropdownMenuItem>
                ) : null}
                {onUpdate ? (
                  <DropdownMenuItem onSelect={() => onUpdate({
                    itemId: item.id,
                    itemName: item.name,
                    assetType: item.asset_type,
                    currency: item.currency,
                    currentNativeValue: value.native_value,
                  })}>
                    <RefreshCw className="h-4 w-4" />{t("assets.updateValue")}
                  </DropdownMenuItem>
                ) : null}
              </>
            ) : null}
            <DropdownMenuItem onSelect={() => onHistory({
              itemId: item.id,
              itemName: item.name,
              assetType: item.asset_type,
              currency: item.currency,
              readOnly: archived || parentArchived,
            })}>
              <History className="h-4 w-4" />{t("assets.history")}
            </DropdownMenuItem>
            {!parentArchived ? (
              archived && onRestore ? (
                <DropdownMenuItem onSelect={() => onRestore(item)}>
                  <ArchiveRestore className="h-4 w-4" />{t("assets.restoreItem")}
                </DropdownMenuItem>
              ) : !archived && onArchive ? (
                <DropdownMenuItem onSelect={() => onArchive(item)}>
                  <Archive className="h-4 w-4" />{t("assets.archiveItem")}
                </DropdownMenuItem>
              ) : null
            ) : null}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}
