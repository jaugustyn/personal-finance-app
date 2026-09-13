"use client";

import { Edit3, History, Layers3, Plus, RefreshCw, WalletCards } from "lucide-react";
import type { AssetAccount } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { useFormatters, useT } from "@/lib/i18n";
import {
  accountKindKey,
  assetTypeKey,
  wrapperKey,
} from "../_lib/asset-options";
import type { HistoryTarget } from "./asset-valuation-history-dialog";
import type { ValuationTarget } from "./asset-valuation-dialog";

interface AssetDetailsSheetProps {
  account: AssetAccount;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  valuationTarget: ValuationTarget | null;
  onAddItem?: (account: AssetAccount) => void;
  onUpdate?: (target: ValuationTarget) => void;
  onHistory: (target: HistoryTarget) => void;
  onEdit?: (account: AssetAccount) => void;
}

export function AssetDetailsSheet({
  account,
  open,
  onOpenChange,
  valuationTarget,
  onAddItem,
  onUpdate,
  onHistory,
  onEdit,
}: AssetDetailsSheetProps) {
  const { t } = useT();
  const { formatCurrency, formatDate } = useFormatters();
  const archived = Boolean(account.archived_at);
  const aggregate = account.tracking_mode === "aggregate";
  const incomplete =
    account.missing_valuation_count > 0 || account.unconverted_count > 0;
  const reviewInterval = account.review_interval_days;
  const reviewLabel =
    reviewInterval === 7 ||
    reviewInterval === 30 ||
    reviewInterval === 90 ||
    reviewInterval === 180
      ? t(`assets.review.${reviewInterval}`)
      : t("assets.review.never");

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        className="flex w-full max-w-2xl flex-col overflow-hidden sm:w-[42rem] lg:w-[46rem]"
        aria-describedby={undefined}
      >
        <SheetHeader className="px-5 py-5">
          <SheetTitle>
            {t(aggregate ? "assets.assetDetails" : "assets.portfolioDetails")}
          </SheetTitle>
        </SheetHeader>

        <div className="flex-1 space-y-5 overflow-y-auto px-5 pb-6">
          <div className="flex items-center gap-4 border-b pb-5">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
              {aggregate ? (
                <WalletCards className="h-5 w-5" />
              ) : (
                <Layers3 className="h-5 w-5" />
              )}
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="break-words text-lg font-semibold [overflow-wrap:anywhere]">
                  {account.name}
                </h2>
                {archived ? (
                  <Badge variant="muted">{t("assets.archived")}</Badge>
                ) : null}
              </div>
              <p className="mt-1 text-2xl font-semibold tracking-tight tabular-nums">
                {incomplete
                  ? "—"
                  : formatCurrency(Number(account.amount_pln), "PLN")}
              </p>
              {account.native_currency !== "PLN" &&
              account.native_value != null ? (
                <p className="mt-0.5 text-sm text-muted-foreground tabular-nums">
                  {formatCurrency(
                    Number(account.native_value),
                    account.native_currency ?? account.default_currency,
                  )}
                </p>
              ) : null}
            </div>
          </div>

          <DetailsSection title={t("assets.basicData")}>
            {aggregate ? (
              <Detail label={t("assets.assetType")}>
                {t(assetTypeKey(account.aggregate_asset_type ?? "other"))}
              </Detail>
            ) : null}
            <Detail label={t("assets.institution")}>
              {account.institution || t("assets.notProvided")}
            </Detail>
            <Detail label={t("assets.accountProfile")}>
              {t(accountKindKey(account.kind))}
            </Detail>
            {account.wrapper !== "standard" ? (
              <Detail label={t("assets.accountWrapper")}>
                {t(wrapperKey(account.wrapper))}
              </Detail>
            ) : null}
            <Detail label={t("assets.currency")}>
              {aggregate
                ? (account.native_currency ?? account.default_currency)
                : account.default_currency}
            </Detail>
            {!aggregate ? (
              <Detail label={t("assets.summaryHoldings")}>
                {account.items.length}
              </Detail>
            ) : null}
          </DetailsSection>

          {aggregate ? (
            <DetailsSection title={t("assets.valuations")}>
              <Detail label={t("assets.valuationDate")}>
                {account.valuation_date
                  ? formatDate(account.valuation_date)
                  : t("assets.noValuation")}
              </Detail>
              <Detail label={t("assets.reviewInterval")}>{reviewLabel}</Detail>
            </DetailsSection>
          ) : null}

          {account.notes ? (
            <DetailsSection title={t("assets.notes")}>
              <p className="whitespace-pre-wrap break-words text-sm leading-6">
                {account.notes}
              </p>
            </DetailsSection>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-2 border-t px-6 py-4">
          {!aggregate && !archived && onAddItem ? (
            <Button
              variant="outline"
              className="flex-1"
              onClick={() => onAddItem(account)}
            >
              <Plus className="h-4 w-4" />
              {t("assets.addItem")}
            </Button>
          ) : null}
          {valuationTarget ? (
            <Button
              variant="outline"
              className="flex-1"
              onClick={() =>
                onHistory({ ...valuationTarget, readOnly: archived })
              }
            >
              <History className="h-4 w-4" />
              {t("assets.history")}
            </Button>
          ) : null}
          {!archived && valuationTarget && onUpdate ? (
            <Button
              variant="outline"
              className="flex-1"
              onClick={() => onUpdate(valuationTarget)}
            >
              <RefreshCw className="h-4 w-4" />
              {t("assets.updateValue")}
            </Button>
          ) : null}
          {!archived && onEdit ? (
            <Button
              className="flex-1"
              onClick={() => onEdit(account)}
            >
              <Edit3 className="h-4 w-4" />
              {t("common.edit")}
            </Button>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function DetailsSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3 border-b pb-5 last:border-b-0">
      <h3 className="text-sm font-semibold">{title}</h3>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-4 text-sm">
      <p className="text-muted-foreground">{label}</p>
      <p className="break-words font-medium [overflow-wrap:anywhere]">
        {children}
      </p>
    </div>
  );
}
