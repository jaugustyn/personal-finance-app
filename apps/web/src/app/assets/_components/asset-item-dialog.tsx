"use client";

import { FormEvent, useState } from "react";
import { Loader2 } from "lucide-react";
import { CurrencyCombobox } from "@/components/currency-combobox";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  pageTabsListClassName,
  pageTabTriggerClassName,
} from "@/components/page-tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectSeparator,
  SelectLabel,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  AssetAccount,
  AssetItem,
  AssetItemInput,
  AssetType,
} from "@/lib/api";
import { useT } from "@/lib/i18n";
import {
  ASSET_TYPE_GROUPS,
  REVIEW_INTERVAL_OPTIONS,
  assetTypeCapabilities,
  assetTypeKey,
} from "../_lib/asset-options";
import {
  AssetGrowthFields,
  AssetValuationFields,
  emptyValuationDraft,
  isValuationValid,
  valuationPayload,
  valuationDraftIsEmpty,
  type ValuationDraft,
} from "./asset-valuation-fields";

interface ItemDraft {
  name: string;
  assetType: AssetType;
  currency: string;
  symbol: string;
  isin: string;
  reviewInterval: string;
  notes: string;
  valuation: ValuationDraft;
}

function initialDraft(currency: string, item?: AssetItem | null): ItemDraft {
  const assetType = item?.asset_type ?? "etf";
  return {
    name: item?.name ?? "",
    assetType,
    currency: item?.currency ?? currency,
    symbol: item?.symbol ?? "",
    isin: item?.isin ?? "",
    reviewInterval: item
      ? item.review_interval_days == null
        ? "never"
        : String(item.review_interval_days)
      : "never",
    notes: item?.notes ?? "",
    valuation: emptyValuationDraft(
      assetTypeCapabilities(assetType).defaultInputMode,
    ),
  };
}

export function AssetItemDialog({
  account,
  item,
  open,
  onOpenChange,
  onSubmit,
  pending,
}: {
  account: AssetAccount | null;
  item?: AssetItem | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (accountId: number, payload: AssetItemInput) => Promise<void>;
  pending: boolean;
}) {
  const { t } = useT();
  const editing = Boolean(item);
  const [draft, setDraft] = useState<ItemDraft>(() =>
    initialDraft(account?.default_currency ?? "PLN", item),
  );
  const [tab, setTab] = useState("basic");
  const capabilities = assetTypeCapabilities(draft.assetType);
  const showInstrumentData =
    capabilities.supportsInstrumentIdentifiers ||
    Boolean(draft.symbol.trim() || draft.isin.trim());
  const canSave = Boolean(
    account &&
    draft.name.trim() &&
    (editing || isValuationValid(draft.valuation)),
  );
  const update = <K extends keyof ItemDraft>(key: K, value: ItemDraft[K]) =>
    setDraft((current) => ({ ...current, [key]: value }));

  const updateAssetType = (assetType: AssetType) => {
    setDraft((current) => {
      const currentCapabilities = assetTypeCapabilities(current.assetType);
      const nextCapabilities = assetTypeCapabilities(assetType);
      const followsInputDefault =
        valuationDraftIsEmpty(current.valuation) &&
        current.valuation.inputMode === currentCapabilities.defaultInputMode;
      return {
        ...current,
        assetType,
        valuation: followsInputDefault
          ? {
              ...current.valuation,
              inputMode: nextCapabilities.defaultInputMode,
            }
          : current.valuation,
      };
    });
  };

  const close = () => {
    if (pending) return;
    setDraft(initialDraft(account?.default_currency ?? "PLN", item));
    setTab("basic");
    onOpenChange(false);
  };

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!account || !canSave) return;
    const reviewInterval =
      draft.reviewInterval === "never"
        ? null
        : (Number(draft.reviewInterval) as 7 | 30 | 90 | 180);
    await onSubmit(account.id, {
      name: draft.name.trim(),
      asset_type: draft.assetType,
      currency: draft.currency,
      symbol: draft.symbol.trim() || null,
      isin: draft.isin.trim() || null,
      review_interval_days: reviewInterval,
      notes: draft.notes.trim() || null,
      initial_valuation: editing ? null : valuationPayload(draft.valuation),
    });
    setDraft(initialDraft(account.default_currency, item));
    setTab("basic");
    onOpenChange(false);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => (next ? onOpenChange(true) : close())}
    >
      <DialogContent className="max-h-[90dvh] max-w-5xl overflow-hidden p-0 md:top-[10dvh] md:translate-y-0">
        <form onSubmit={submit} className="flex max-h-[80dvh] min-h-0 flex-col">
          <DialogHeader className="shrink-0 px-6 pt-8 sm:px-8">
            <DialogTitle>
              {editing ? t("assets.editItem") : t("assets.addItem")}
            </DialogTitle>
            <DialogDescription className="sr-only">
              {account ? account.name : t("assets.addItemDescription")}
            </DialogDescription>
          </DialogHeader>
          <Tabs
            value={tab}
            onValueChange={setTab}
            className="flex min-h-0 flex-col"
          >
            <div className="shrink-0 px-6 pt-6 sm:px-8">
              <TabsList className={pageTabsListClassName}>
                <TabsTrigger value="basic" className={pageTabTriggerClassName}>
                  {t("assets.basicData")}
                </TabsTrigger>
                <TabsTrigger
                  value="details"
                  className={pageTabTriggerClassName}
                >
                  {t("assets.detailsTab")}
                </TabsTrigger>
              </TabsList>
            </div>
            <div className="min-h-0 overflow-y-auto px-6 py-8 sm:px-8">
              <TabsContent
                value="basic"
                className="grid gap-8 data-[state=inactive]:hidden md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]"
              >
                <div className="space-y-8">
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="asset-item-name">
                      {t("assets.itemName")}
                    </Label>
                    <Input
                      id="asset-item-name"
                      value={draft.name}
                      onChange={(event) => update("name", event.target.value)}
                      placeholder={t("assets.itemNamePlaceholder")}
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label>{t("assets.assetType")}</Label>
                    <Select
                      value={draft.assetType}
                      onValueChange={updateAssetType}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {ASSET_TYPE_GROUPS.map((group, index) => (
                          <SelectGroup key={group.label}>
                            {index > 0 ? <SelectSeparator /> : null}
                            <SelectLabel className="px-2 py-2 text-sm font-medium text-muted-foreground">
                              {t(group.label)}
                            </SelectLabel>
                            {group.types.map((type) => (
                              <SelectItem
                                key={type}
                                value={type}
                                indicatorPosition="right"
                              >
                                {t(assetTypeKey(type))}
                              </SelectItem>
                            ))}
                          </SelectGroup>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="space-y-8 md:border-l md:pl-8">
                  {editing ? (
                    <div className="flex flex-col gap-2">
                      <Label>{t("assets.currency")}</Label>
                      <Input value={draft.currency} disabled />
                    </div>
                  ) : null}
                  {!editing ? (
                    <>
                      <AssetValuationFields
                        value={draft.valuation}
                        onChange={(value) => update("valuation", value)}
                        currency={draft.currency}
                        currencyControl={
                          <div className="flex flex-col gap-2">
                            <Label>{t("assets.currency")}</Label>
                            <CurrencyCombobox
                              value={draft.currency}
                              onChange={(value) => update("currency", value)}
                            />
                          </div>
                        }
                        showInputMode={
                          capabilities.defaultInputMode === "unit_price"
                        }
                        showGrowth={false}
                      />
                    </>
                  ) : null}
                </div>
              </TabsContent>
              <TabsContent
                value="details"
                className="grid gap-8 data-[state=inactive]:hidden md:grid-cols-2"
              >
                <div className="space-y-8">
                  <div className="flex flex-col gap-2">
                    <Label>{t("assets.reviewInterval")}</Label>
                    <Select
                      value={draft.reviewInterval}
                      onValueChange={(value) => update("reviewInterval", value)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {REVIEW_INTERVAL_OPTIONS.map((option) => (
                          <SelectItem
                            key={option.value}
                            value={option.value}
                            indicatorPosition="right"
                          >
                            {t(option.key)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="asset-item-notes">
                      {t("assets.notes")}
                    </Label>
                    <textarea
                      id="asset-item-notes"
                      value={draft.notes}
                      onChange={(event) => update("notes", event.target.value)}
                      className="min-h-20 w-full resize-y rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      placeholder={t("common.optional")}
                    />
                  </div>
                </div>
                {showInstrumentData ? (
                  <section>
                    <h3 className="text-sm font-medium">
                      {t("assets.instrumentData")}
                    </h3>
                    <div className="mt-4 grid gap-6 sm:grid-cols-2">
                      <div className="flex flex-col gap-2">
                        <Label htmlFor="asset-symbol">
                          {t("assets.symbol")}
                        </Label>
                        <Input
                          id="asset-symbol"
                          value={draft.symbol}
                          onChange={(event) =>
                            update("symbol", event.target.value)
                          }
                        />
                      </div>
                      <div className="flex flex-col gap-2">
                        <Label htmlFor="asset-isin">ISIN</Label>
                        <Input
                          id="asset-isin"
                          value={draft.isin}
                          onChange={(event) =>
                            update("isin", event.target.value)
                          }
                          maxLength={12}
                        />
                      </div>
                    </div>
                  </section>
                ) : null}
                {!editing ? (
                  <div className="border-t pt-6 md:col-span-2">
                    <AssetGrowthFields
                      value={draft.valuation}
                      onChange={(value) => update("valuation", value)}
                    />
                  </div>
                ) : null}
              </TabsContent>
            </div>
          </Tabs>
          <DialogFooter className="shrink-0 border-t px-6 py-5 sm:px-8">
            <Button
              type="button"
              variant="outline"
              onClick={close}
              disabled={pending}
            >
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={!canSave || pending}>
              {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {editing ? t("common.save") : t("assets.addItem")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
