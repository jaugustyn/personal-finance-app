"use client";

import { Loader2 } from "lucide-react";

import { FilterSelect } from "@/components/filter-select";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { TransactionAccountKind } from "@/lib/api";
import { useT } from "@/lib/i18n";

const ACCOUNT_KINDS: TransactionAccountKind[] = [
  "bank",
  "savings",
  "credit_card",
  "cash",
  "other",
];

export function AccountFormDialog({
  open,
  onOpenChange,
  mode,
  name,
  onNameChange,
  kind,
  onKindChange,
  pending,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "edit";
  name: string;
  onNameChange: (name: string) => void;
  kind: TransactionAccountKind;
  onKindChange: (kind: TransactionAccountKind) => void;
  pending: boolean;
  onSubmit: () => void;
}) {
  const { t } = useT();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>
            {t(mode === "edit" ? "accounts.editTitle" : "accounts.addTitle")}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-5">
          <div className="grid gap-2">
            <Label htmlFor="account-form-name">{t("accounts.name")}</Label>
            <Input
              id="account-form-name"
              value={name}
              onChange={(event) => onNameChange(event.target.value)}
              placeholder={t("accounts.namePlaceholder")}
              autoFocus
            />
          </div>
          <div className="grid gap-2">
            <Label>{t("accounts.kind")}</Label>
            <FilterSelect
              value={kind}
              onValueChange={(next) =>
                onKindChange(next as TransactionAccountKind)
              }
              options={ACCOUNT_KINDS.map((item) => ({
                value: item,
                label: t(`accounts.kind.${item}`),
              }))}
              ariaLabel={t("accounts.kind")}
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={pending}
          >
            {t("common.cancel")}
          </Button>
          <Button
            type="button"
            onClick={onSubmit}
            disabled={!name.trim() || pending}
          >
            {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {t("common.save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
