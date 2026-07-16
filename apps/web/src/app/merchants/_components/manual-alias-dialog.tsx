"use client";

import { useState } from "react";
import { Loader2, Plus } from "lucide-react";

import type { MerchantAliasGroup } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { FilterSelect } from "@/components/filter-select";
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
import { NEW_GROUP, type MerchantAliasPayload } from "../_lib/merchant-aliases";
import { AliasSuggestionInput } from "./alias-suggestion-input";

export function ManualAliasDialog({
  open,
  groups,
  isPending,
  onOpenChange,
  onCreate,
}: {
  open: boolean;
  groups: MerchantAliasGroup[];
  isPending: boolean;
  onOpenChange: (open: boolean) => void;
  onCreate: (payload: MerchantAliasPayload) => void;
}) {
  const { t } = useT();
  const [aliasLabel, setAliasLabel] = useState("");
  const [groupKey, setGroupKey] = useState(NEW_GROUP);
  const [canonicalLabel, setCanonicalLabel] = useState("");
  const selectedGroup = groups.find((group) => group.canonical_key === groupKey);
  const displayLabel = selectedGroup?.canonical_label ?? canonicalLabel;
  const canSave = Boolean(aliasLabel.trim() && displayLabel.trim());

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!isPending) onOpenChange(nextOpen);
      }}
    >
      <DialogContent className="max-w-lg">
        <form
          className="space-y-5"
          onSubmit={(event) => {
            event.preventDefault();
            if (!canSave || isPending) return;
            onCreate({
              canonical_key: selectedGroup?.canonical_key,
              canonical_label: displayLabel.trim(),
              aliases: [aliasLabel.trim()],
            });
          }}
        >
          <DialogHeader>
            <DialogTitle>{t("merchants.manualTitle")}</DialogTitle>
            <DialogDescription>
              {t("merchants.manualDescription")}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label htmlFor="merchant-alias">{t("merchants.aliasLabel")}</Label>
            <AliasSuggestionInput
              id="merchant-alias"
              value={aliasLabel}
              onChange={setAliasLabel}
              onSelectSuggestion={(suggestion) =>
                setAliasLabel(suggestion.alias_label)
              }
              disabled={isPending}
            />
          </div>

          <div className="space-y-2">
            <Label>{t("merchants.groupLabel")}</Label>
            <FilterSelect
              value={groupKey}
              onValueChange={setGroupKey}
              ariaLabel={t("merchants.groupLabel")}
              options={[
                { value: NEW_GROUP, label: t("merchants.newGroup") },
                ...groups.map((group) => ({
                  value: group.canonical_key,
                  label: group.canonical_label,
                })),
              ]}
            />
          </div>

          {!selectedGroup ? (
            <div className="space-y-2">
              <Label htmlFor="merchant-display-label">
                {t("merchants.displayLabel")}
              </Label>
              <Input
                id="merchant-display-label"
                value={canonicalLabel}
                onChange={(event) => setCanonicalLabel(event.target.value)}
                placeholder={t("merchants.displayLabelPlaceholder")}
                disabled={isPending}
              />
            </div>
          ) : null}

          <DialogFooter>
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
              ) : (
                <Plus className="mr-2 h-4 w-4" />
              )}
              {t("merchants.addAlias")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
