"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus } from "lucide-react";

import { FilterSelect } from "@/components/filter-select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, type TransactionAccountKind } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { queryKeys } from "@/lib/query-keys";
import { showErrorToast } from "@/lib/toasts";
import { cn } from "@/lib/utils";

const ACCOUNT_KINDS: TransactionAccountKind[] = [
  "bank",
  "savings",
  "credit_card",
  "cash",
  "other",
];

export function AccountSelect({
  value,
  onChange,
  id,
  disabled,
  quickCreate = true,
  allowedArchivedAccountId,
  className,
}: {
  value: number | null;
  onChange: (value: number) => void;
  id?: string;
  disabled?: boolean;
  quickCreate?: boolean;
  allowedArchivedAccountId?: number;
  className?: string;
}) {
  const { t } = useT();
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [kind, setKind] = useState<TransactionAccountKind>("bank");
  const includeArchived = allowedArchivedAccountId !== undefined;
  const accountsQuery = useQuery({
    queryKey: queryKeys.accounts.list(includeArchived),
    queryFn: () => api.accounts(includeArchived),
  });
  const createMutation = useMutation({
    mutationFn: () => api.createAccount({ name: name.trim(), kind }),
    onSuccess: (account) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
      setName("");
      setKind("bank");
      setCreating(false);
      onChange(account.id);
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });
  const accounts = (accountsQuery.data ?? []).filter(
    (account) =>
      account.archived_at === null || account.id === allowedArchivedAccountId,
  );

  return (
    <div className={cn("space-y-2", className)}>
      <FilterSelect
        id={id}
        value={value === null ? "" : String(value)}
        onValueChange={(next) => onChange(Number(next))}
        options={accounts.map((account) => ({
          value: String(account.id),
          label: account.archived_at
            ? `${account.name} (${t("accounts.archivedLabel")})`
            : account.name,
        }))}
        placeholder={
          accountsQuery.isLoading
            ? t("common.loading")
            : t("accounts.selectPlaceholder")
        }
        ariaLabel={t("accounts.selectLabel")}
        disabled={disabled || accountsQuery.isLoading || accountsQuery.isError}
      />

      {accountsQuery.isError ? (
        <div className="flex items-center justify-between gap-2 text-xs text-destructive">
          <span>{t("accounts.loadError")}</span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7"
            onClick={() => void accountsQuery.refetch()}
          >
            {t("common.retry")}
          </Button>
        </div>
      ) : null}

      {quickCreate && !creating ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 px-1.5 text-muted-foreground"
          disabled={disabled}
          onClick={() => setCreating(true)}
        >
          <Plus className="h-4 w-4" />
          {t("accounts.quickCreate")}
        </Button>
      ) : null}

      {quickCreate && creating ? (
        <div className="grid gap-3 rounded-lg border border-dashed bg-muted/20 p-3 sm:grid-cols-[minmax(0,1fr)_12rem_auto] sm:items-end">
          <div className="space-y-1.5">
            <Label htmlFor={`${id ?? "account"}-new-name`}>
              {t("accounts.name")}
            </Label>
            <Input
              id={`${id ?? "account"}-new-name`}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={t("accounts.namePlaceholder")}
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <Label>{t("accounts.kind")}</Label>
            <FilterSelect
              value={kind}
              onValueChange={(next) => setKind(next as TransactionAccountKind)}
              options={ACCOUNT_KINDS.map((item) => ({
                value: item,
                label: t(`accounts.kind.${item}`),
              }))}
              ariaLabel={t("accounts.kind")}
            />
          </div>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setCreating(false)}
              disabled={createMutation.isPending}
            >
              {t("common.cancel")}
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={!name.trim() || createMutation.isPending}
              onClick={() => createMutation.mutate()}
            >
              {createMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : null}
              {t("common.add")}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
