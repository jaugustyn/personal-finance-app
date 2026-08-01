"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";

import { AccountFormDialog } from "@/components/account-form-dialog";
import { FilterSelect } from "@/components/filter-select";
import { Button } from "@/components/ui/button";
import { api, type TransactionAccountKind } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { queryKeys } from "@/lib/query-keys";
import { showErrorToast } from "@/lib/toasts";
import { cn } from "@/lib/utils";

const CREATE_ACCOUNT_VALUE = "__create_account__";

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
        onValueChange={(next) => {
          if (next === CREATE_ACCOUNT_VALUE) {
            setName("");
            setKind("bank");
            setCreating(true);
            return;
          }
          onChange(Number(next));
        }}
        options={[
          ...accounts.map((account) => ({
            value: String(account.id),
            label: account.archived_at
              ? `${account.name} (${t("accounts.archivedLabel")})`
              : account.name,
          })),
          ...(quickCreate
            ? [
                {
                  value: CREATE_ACCOUNT_VALUE,
                  label: t("accounts.quickCreate"),
                  leading: <Plus className="h-4 w-4" />,
                  separatorBefore: accounts.length > 0,
                },
              ]
            : []),
        ]}
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

      {quickCreate ? (
        <AccountFormDialog
          open={creating}
          onOpenChange={setCreating}
          mode="create"
          name={name}
          onNameChange={setName}
          kind={kind}
          onKindChange={setKind}
          pending={createMutation.isPending}
          onSubmit={() => createMutation.mutate()}
        />
      ) : null}
    </div>
  );
}
