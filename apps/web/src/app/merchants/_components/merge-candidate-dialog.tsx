"use client";

import { useMemo, useState } from "react";
import { Loader2, X } from "lucide-react";

import type { MerchantAliasSuggestion, MerchantCandidate } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { cn, formatCurrency } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  candidateVariants,
  type MerchantAliasPayload,
} from "../_lib/merchant-aliases";
import { AliasSuggestionInput } from "./alias-suggestion-input";

export function MergeCandidateDialog({
  candidate,
  open,
  isPending,
  onOpenChange,
  onSave,
}: {
  candidate: MerchantCandidate | null;
  open: boolean;
  isPending: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (payload: MerchantAliasPayload) => void;
}) {
  const { t } = useT();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t("merchants.mergeDialogTitle")}</DialogTitle>
        </DialogHeader>

        {candidate ? (
          <MergeCandidateForm
            key={candidate.canonical_key}
            candidate={candidate}
            isPending={isPending}
            onOpenChange={onOpenChange}
            onSave={onSave}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function MergeCandidateForm({
  candidate,
  isPending,
  onOpenChange,
  onSave,
}: {
  candidate: MerchantCandidate;
  isPending: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (payload: MerchantAliasPayload) => void;
}) {
  const { t } = useT();
  const [label, setLabel] = useState(() => candidate.canonical_label);
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(candidateVariants(candidate).map((variant) => variant.alias_key)),
  );
  const [extraAliasInput, setExtraAliasInput] = useState("");
  const [extraAliases, setExtraAliases] = useState<MerchantAliasSuggestion[]>([]);
  const variants = useMemo(() => candidateVariants(candidate), [candidate]);

  const selectedVariants = variants.filter((variant) =>
    selected.has(variant.alias_key),
  );
  const excludedAliasKeys = new Set([
    ...variants.map((variant) => variant.alias_key),
    ...extraAliases.map((alias) => alias.alias_key),
  ]);
  const total = selectedVariants.reduce(
    (sum, variant) => sum + Number(variant.total_debit || 0),
    0,
  ) + extraAliases.reduce(
    (sum, alias) => sum + Number(alias.total_amount || 0),
    0,
  );
  const selectedVariantCount = selectedVariants.length + extraAliases.length;
  const transactionCount = selectedVariants.reduce(
    (sum, variant) => sum + variant.count,
    0,
  ) + extraAliases.reduce((sum, alias) => sum + alias.count, 0);
  const canSave = Boolean(label.trim() && selectedVariantCount > 0);

  return (
    <form
      className="space-y-5"
      onSubmit={(event) => {
        event.preventDefault();
        if (!canSave || isPending) return;
        onSave({
          canonical_key: candidate.canonical_key,
          canonical_label: label.trim(),
          aliases: [
            ...selectedVariants.map((variant) => variant.alias_label),
            ...extraAliases.map((alias) => alias.alias_label),
          ],
        });
      }}
    >
      <div className="space-y-2">
        <Label htmlFor="merchant-merge-label">
          {t("merchants.displayLabel")}
        </Label>
        <Input
          id="merchant-merge-label"
          value={label}
          onChange={(event) => setLabel(event.target.value)}
        />
      </div>

      <div className="space-y-2">
        <Label>{t("merchants.mergeVariantsLabel")}</Label>
        <div className="select-scrollbar max-h-80 divide-y overflow-y-auto rounded-lg border">
          {variants.map((variant) => {
            const checked = selected.has(variant.alias_key);
            return (
              <label
                key={variant.alias_key}
                className={cn(
                  "flex cursor-pointer items-center gap-3 px-3 py-2.5 transition-colors",
                  checked ? "bg-muted/60" : "hover:bg-muted/40",
                )}
              >
                <Checkbox
                  checked={checked}
                  onCheckedChange={(value) => {
                    setSelected((prev) => {
                      const next = new Set(prev);
                      if (value) next.add(variant.alias_key);
                      else next.delete(variant.alias_key);
                      return next;
                    });
                  }}
                />
                <div className="min-w-0 flex-1 truncate text-sm font-medium">
                  {variant.alias_label}
                </div>
                <div className="shrink-0 text-right text-xs text-muted-foreground">
                  <div className="tabular-nums">
                    {t("merchants.transactionCount", {
                      count: variant.count,
                    })}
                  </div>
                  <div className="tabular-nums">
                    {formatCurrency(
                      Number(variant.total_debit),
                      variant.base_currency,
                    )}
                  </div>
                </div>
              </label>
            );
          })}
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="merchant-extra-alias">
          {t("merchants.addVariant")}
        </Label>
        <AliasSuggestionInput
          id="merchant-extra-alias"
          value={extraAliasInput}
          onChange={setExtraAliasInput}
          excludeKeys={excludedAliasKeys}
          onSelectSuggestion={(suggestion) => {
            setExtraAliases((prev) =>
              prev.some((alias) => alias.alias_key === suggestion.alias_key)
                ? prev
                : [...prev, suggestion],
            );
            setExtraAliasInput("");
          }}
        />
        {extraAliases.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {extraAliases.map((alias) => (
              <Badge
                key={alias.alias_key}
                variant="secondary"
                className="gap-2 pr-1"
              >
                <span className="max-w-52 truncate">{alias.alias_label}</span>
                <button
                  type="button"
                  className="rounded-sm p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                  onClick={() =>
                    setExtraAliases((prev) =>
                      prev.filter((item) => item.alias_key !== alias.alias_key),
                    )
                  }
                  aria-label={t("common.delete")}
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </Badge>
            ))}
          </div>
        ) : null}
      </div>

      <div className="border-t pt-3 text-sm text-muted-foreground">
        {t("merchants.mergeSummary", {
          variants: selectedVariantCount,
          transactions: transactionCount,
          amount: formatCurrency(total, candidate.base_currency),
        })}
      </div>

      <DialogFooter className="pt-1">
        <Button
          type="button"
          variant="outline"
          disabled={isPending}
          onClick={() => onOpenChange(false)}
        >
          {t("common.cancel")}
        </Button>
        <Button type="submit" disabled={!canSave || isPending}>
          {isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : null}
          {t("merchants.saveAliases")}
        </Button>
      </DialogFooter>
    </form>
  );
}
