"use client";

import { useState } from "react";
import { Loader2, Plus } from "lucide-react";

import type { MerchantAliasGroup } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { NEW_GROUP, type MerchantAliasPayload } from "../_lib/merchant-aliases";

export function ManualAliasCard({
  groups,
  isPending,
  onCreate,
}: {
  groups: MerchantAliasGroup[];
  isPending: boolean;
  onCreate: (payload: MerchantAliasPayload) => void;
}) {
  const { t } = useT();
  const [aliasLabel, setAliasLabel] = useState("");
  const [groupKey, setGroupKey] = useState(NEW_GROUP);
  const [customCanonicalLabel, setCustomCanonicalLabel] = useState<string | null>(
    null,
  );
  const selectedGroup = groups.find((group) => group.canonical_key === groupKey);
  const canonicalLabel =
    customCanonicalLabel ?? selectedGroup?.canonical_label ?? "";

  const canSave = aliasLabel.trim() && canonicalLabel.trim();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Plus className="h-4 w-4 text-muted-foreground" />
          {t("merchants.manualTitle")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 lg:grid-cols-[1.3fr_1fr_1.3fr_auto]">
          <Input
            value={aliasLabel}
            onChange={(event) => setAliasLabel(event.target.value)}
            placeholder={t("merchants.aliasPlaceholder")}
          />
          <Select
            value={groupKey}
            onValueChange={(value) => {
              setGroupKey(value);
              setCustomCanonicalLabel(null);
            }}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NEW_GROUP}>{t("merchants.newGroup")}</SelectItem>
              {groups.map((group) => (
                <SelectItem key={group.canonical_key} value={group.canonical_key}>
                  {group.canonical_label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            value={canonicalLabel}
            onChange={(event) => setCustomCanonicalLabel(event.target.value)}
            placeholder={t("merchants.displayLabelPlaceholder")}
          />
          <Button
            disabled={!canSave || isPending}
            onClick={() => {
              onCreate({
                canonical_key: selectedGroup?.canonical_key,
                canonical_label: canonicalLabel.trim(),
                aliases: [aliasLabel.trim()],
              });
              setAliasLabel("");
              if (!selectedGroup) setCustomCanonicalLabel("");
            }}
          >
            {isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Plus className="mr-2 h-4 w-4" />
            )}
            {t("common.add")}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
