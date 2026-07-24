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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { AssetAccount, AssetItem, AssetItemInput, AssetType } from "@/lib/api";
import { useT } from "@/lib/i18n";
import {
  ASSET_TYPES,
  REVIEW_INTERVAL_OPTIONS,
  assetTypeCapabilities,
  assetTypeKey,
} from "../_lib/asset-options";
import {
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
      : "30",
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
    onOpenChange(false);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => (next ? onOpenChange(true) : close())}
    >
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>
              {editing ? t("assets.editItem") : t("assets.addItem")}
            </DialogTitle>
            <DialogDescription>
              {account ? account.name : t("assets.addItemDescription")}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-5 py-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="asset-item-name">{t("assets.itemName")}</Label>
                <Input
                  id="asset-item-name"
                  value={draft.name}
                  onChange={(event) => update("name", event.target.value)}
                  placeholder={t("assets.itemNamePlaceholder")}
                  autoFocus
                />
              </div>
              <div className="space-y-2">
                <Label>{t("assets.assetType")}</Label>
                <Select value={draft.assetType} onValueChange={updateAssetType}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {ASSET_TYPES.map((type) => (
                      <SelectItem key={type} value={type} indicatorPosition="right">
                        {t(assetTypeKey(type))}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>{t("assets.currency")}</Label>
                {editing ? (
                  <Input value={draft.currency} disabled />
                ) : (
                  <CurrencyCombobox value={draft.currency} onChange={(value) => update("currency", value)} />
                )}
              </div>
              <div className="space-y-2">
                <Label>{t("assets.reviewInterval")}</Label>
                <Select value={draft.reviewInterval} onValueChange={(value) => update("reviewInterval", value)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {REVIEW_INTERVAL_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value} indicatorPosition="right">
                        {t(option.key)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            {showInstrumentData ? (
              <details className="rounded-lg border px-4 py-3">
                <summary className="cursor-pointer text-sm font-medium">
                  {t("assets.instrumentData")}
                </summary>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
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
                  <div className="space-y-2">
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
              </details>
            ) : null}
            {!editing ? (
              <>
                <div className="space-y-1 border-t pt-5">
                  <h3 className="text-sm font-semibold">{t("assets.initialValuation")}</h3>
                  <p className="text-xs text-muted-foreground">{t("assets.initialValuationHint")}</p>
                </div>
                <AssetValuationFields
                  value={draft.valuation}
                  onChange={(value) => update("valuation", value)}
                  currency={draft.currency}
                  showGrowth={
                    capabilities.supportsFixedGrowth ||
                    draft.valuation.growthMode !== "none"
                  }
                />
              </>
            ) : null}
            <div className="space-y-2">
              <Label htmlFor="asset-item-notes">{t("assets.notes")}</Label>
              <textarea
                id="asset-item-notes"
                value={draft.notes}
                onChange={(event) => update("notes", event.target.value)}
                className="min-h-20 w-full resize-y rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder={t("common.optional")}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={close} disabled={pending}>{t("common.cancel")}</Button>
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
