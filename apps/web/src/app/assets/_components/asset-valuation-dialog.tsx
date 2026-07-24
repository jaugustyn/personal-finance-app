"use client";

import { FormEvent, useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type {
  AssetType,
  AssetValuation,
  AssetValuationInput,
} from "@/lib/api";
import { useT } from "@/lib/i18n";
import { assetTypeCapabilities } from "../_lib/asset-options";
import {
  AssetValuationFields,
  emptyValuationDraft,
  isValuationValid,
  valuationDraft,
  valuationDraftForUpdate,
  valuationPayload,
} from "./asset-valuation-fields";

export interface ValuationTarget {
  itemId: number;
  itemName: string;
  assetType: AssetType;
  currency: string;
  valuation?: AssetValuation | null;
  prefillValuation?: AssetValuation | null;
  currentNativeValue?: number | string | null;
}

export function AssetValuationDialog({
  target,
  open,
  onOpenChange,
  onSubmit,
  pending,
}: {
  target: ValuationTarget | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (
    itemId: number,
    payload: AssetValuationInput,
    valuationId?: number,
  ) => Promise<void>;
  pending: boolean;
}) {
  const { t } = useT();
  const [draft, setDraft] = useState(() => {
    if (target?.valuation) return valuationDraft(target.valuation);
    if (target?.prefillValuation) {
      return valuationDraftForUpdate(
        target.prefillValuation,
        target.currentNativeValue,
      );
    }
    return emptyValuationDraft();
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!target || !isValuationValid(draft)) return;
    await onSubmit(
      target.itemId,
      valuationPayload(draft),
      target.valuation?.id,
    );
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !pending && onOpenChange(next)}>
      <DialogContent className="max-h-[90vh] max-w-xl overflow-y-auto">
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>
              {target?.valuation
                ? t("assets.editValuation")
                : t("assets.updateValuation")}
            </DialogTitle>
            <DialogDescription>{target?.itemName}</DialogDescription>
          </DialogHeader>
          <div className="py-5">
            <AssetValuationFields
              value={draft}
              onChange={setDraft}
              currency={target?.currency ?? "PLN"}
              showGrowth={Boolean(
                target &&
                  (assetTypeCapabilities(target.assetType).supportsFixedGrowth ||
                    draft.growthMode !== "none"),
              )}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={pending}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={!target || !isValuationValid(draft) || pending}>
              {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {t("common.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
