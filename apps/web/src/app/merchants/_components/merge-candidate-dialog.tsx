"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, Save } from "lucide-react";

import type { MerchantAliasSuggestion, MerchantCandidate } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { cn, formatCurrency } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
  const [label, setLabel] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [extraAliasInput, setExtraAliasInput] = useState("");
  const [extraAliases, setExtraAliases] = useState<MerchantAliasSuggestion[]>([]);
  const variants = useMemo(
    () => (candidate ? candidateVariants(candidate) : []),
    [candidate],
  );

  useEffect(() => {
    if (!candidate || !open) return;
    setLabel(candidate.canonical_label);
    setSelected(new Set(candidateVariants(candidate).map((variant) => variant.alias_key)));
    setExtraAliasInput("");
    setExtraAliases([]);
  }, [candidate, open]);

  const selectedVariants = variants.filter((variant) => selected.has(variant.alias_key));
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
  const selectedCount = selectedVariants.length + extraAliases.length;
  const canSave = Boolean(candidate && label.trim() && selectedCount > 0);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t("merchants.mergeDialogTitle")}</DialogTitle>
          <DialogDescription>
            {t("merchants.mergeDialogDescription")}
          </DialogDescription>
        </DialogHeader>

        {candidate ? (
          <div className="space-y-4">
            <label className="space-y-1 text-sm">
              <span>{t("merchants.displayLabel")}</span>
              <Input
                value={label}
                onChange={(event) => setLabel(event.target.value)}
              />
            </label>

            <div className="max-h-80 space-y-2 overflow-y-auto rounded-lg border p-3">
              {variants.map((variant) => {
                const checked = selected.has(variant.alias_key);
                return (
                  <label
                    key={variant.alias_key}
                    className={cn(
                      "flex cursor-pointer items-start gap-3 rounded-md p-2",
                      checked ? "bg-muted" : "hover:bg-muted/60",
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
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">
                        {variant.alias_label}
                      </div>
                      <div className="truncate text-xs text-muted-foreground">
                        {variant.alias_key}
                      </div>
                    </div>
                    <div className="text-right text-xs text-muted-foreground">
                      <div className="tabular-nums">{variant.count}</div>
                      <div className="tabular-nums">
                        {formatCurrency(Number(variant.total_debit))}
                      </div>
                    </div>
                  </label>
                );
              })}
            </div>

            <div className="space-y-2">
              <div className="text-sm font-medium">
                {t("merchants.mergeAdditionalAliases")}
              </div>
              <AliasSuggestionInput
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
                        className="rounded-sm px-1 text-muted-foreground hover:text-foreground"
                        onClick={() =>
                          setExtraAliases((prev) =>
                            prev.filter((item) => item.alias_key !== alias.alias_key),
                          )
                        }
                        aria-label={t("common.delete")}
                      >
                        x
                      </button>
                    </Badge>
                  ))}
                </div>
              ) : null}
            </div>

            <div className="rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">
              {t("merchants.mergeSummary", {
                count: selectedCount,
                amount: formatCurrency(total),
              })}
            </div>
          </div>
        ) : null}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("common.cancel")}
          </Button>
          <Button
            disabled={!canSave || isPending}
            onClick={() =>
              candidate &&
              onSave({
                canonical_key: candidate.canonical_key,
                canonical_label: label.trim(),
                aliases: [
                  ...selectedVariants.map((variant) => variant.alias_label),
                  ...extraAliases.map((alias) => alias.alias_label),
                ],
              })
            }
          >
            {isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            {t("merchants.saveAliases")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
