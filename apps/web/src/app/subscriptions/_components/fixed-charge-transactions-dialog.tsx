"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link2, Loader2, Plus, Unlink } from "lucide-react";
import { toast } from "sonner";

import { ErrorState } from "@/components/error-state";
import { Money } from "@/components/money";
import { ManualTransactionDialog } from "@/app/transactions/_components/manual-transaction-dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  api,
  type FixedCharge,
  type FixedChargeTransaction,
  type ManualTransactionInput,
} from "@/lib/api";
import { useFormatters, useT } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";
import {
  invalidateSubscriptionData,
  invalidateTransactionData,
  queryKeys,
} from "@/lib/query-keys";
import { cn } from "@/lib/utils";


export function FixedChargeTransactionsDialog({
  charge,
  open,
  onOpenChange,
}: {
  charge: FixedCharge | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useT();
  const { formatCurrency, formatDate } = useFormatters();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<number[]>([]);
  const [manualOpen, setManualOpen] = useState(false);
  const detailsKey = queryKeys.fixedCharges.transactions(charge?.id ?? null);
  const query = useQuery({
    queryKey: detailsKey,
    queryFn: () => api.fixedChargeTransactions(charge!.id),
    enabled: open && charge !== null,
  });

  const refresh = () => invalidateSubscriptionData(queryClient);

  const linkMutation = useMutation({
    mutationFn: () =>
      api.linkFixedChargeTransactions(charge!.id, {
        transaction_ids: selected,
        scheduled_due_date: query.data!.current_due_date,
      }),
    onSuccess: () => {
      setSelected([]);
      void refresh();
      toast.success(t("subscriptions.fixed.transactions.linked"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const unlinkMutation = useMutation({
    mutationFn: (transactionId: number) =>
      api.unlinkFixedChargeTransaction(charge!.id, transactionId),
    onSuccess: () => {
      void refresh();
      toast.success(t("subscriptions.fixed.transactions.unlinked"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const manualInitialValue = useMemo<
    Partial<ManualTransactionInput> | undefined
  >(
    () =>
      charge && query.data
        ? {
            booking_date: query.data.current_due_date,
            amount: charge.amount,
            direction: "debit",
            merchant: charge.name,
            title: "",
            transaction_type: "expense",
            category: charge.category,
            notes: null,
          }
        : undefined,
    [charge, query.data],
  );

  const createManualMutation = useMutation({
    mutationFn: (payload: ManualTransactionInput) =>
      api.createFixedChargeManualPayment(charge!.id, {
        ...payload,
        scheduled_due_date: query.data!.current_due_date,
      }),
    onSuccess: () => {
      setManualOpen(false);
      void invalidateTransactionData(queryClient);
      toast.success(t("subscriptions.fixed.transactions.linked"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const toggle = (transactionId: number) => {
    setSelected((current) =>
      current.includes(transactionId)
        ? current.filter((id) => id !== transactionId)
        : [...current, transactionId],
    );
  };

  return (
    <>
      <Dialog
        open={open}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) {
            setSelected([]);
            setManualOpen(false);
          }
          onOpenChange(nextOpen);
        }}
      >
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>
            {t("subscriptions.fixed.transactions.title")}
          </DialogTitle>
          <DialogDescription>
            {charge
              ? `${charge.name} · ${formatCurrency(charge.amount, charge.currency)}`
              : ""}
          </DialogDescription>
        </DialogHeader>

        {query.isLoading ? (
          <div className="flex min-h-48 items-center justify-center text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : query.isError ? (
          <ErrorState
            title={t("subscriptions.fixed.transactions.error")}
            onRetry={() => void query.refetch()}
          />
        ) : query.data ? (
          <div className="max-h-[min(65vh,36rem)] space-y-5 overflow-y-auto pr-1">
            <section className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-medium">
                  {t("subscriptions.fixed.transactions.candidates")}
                </h3>
                <span className="text-xs text-muted-foreground">
                  {t("subscriptions.fixed.transactions.dueDate", {
                    date: formatDate(query.data.current_due_date),
                  })}
                </span>
              </div>
              {query.data.candidates.length === 0 ? (
                <p className="rounded-lg border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
                  {t("subscriptions.fixed.transactions.noCandidates")}
                </p>
              ) : (
                <div className="overflow-hidden rounded-lg border">
                  {query.data.candidates.map((transaction, index) => (
                    <CandidateRow
                      key={transaction.transaction_id}
                      transaction={transaction}
                      checked={selected.includes(transaction.transaction_id)}
                      divided={index > 0}
                      onToggle={() => toggle(transaction.transaction_id)}
                    />
                  ))}
                </div>
              )}
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="w-full border-dashed"
                onClick={() => setManualOpen(true)}
              >
                <Plus className="h-4 w-4" />
                {t("subscriptions.fixed.transactions.addManual")}
              </Button>
            </section>

            <section className="space-y-2">
              <h3 className="text-sm font-medium">
                {t("subscriptions.fixed.transactions.history")}
              </h3>
              {query.data.linked.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  {t("subscriptions.fixed.transactions.noHistory")}
                </p>
              ) : (
                <div className="overflow-hidden rounded-lg border">
                  {query.data.linked.map((transaction, index) => (
                    <LinkedRow
                      key={transaction.transaction_id}
                      transaction={transaction}
                      divided={index > 0}
                      pending={unlinkMutation.isPending}
                      onUnlink={() =>
                        unlinkMutation.mutate(transaction.transaction_id)
                      }
                    />
                  ))}
                </div>
              )}
            </section>
          </div>
        ) : null}

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            {t("common.cancel")}
          </Button>
          {query.data && query.data.candidates.length > 0 ? (
            <Button
              type="button"
              disabled={selected.length === 0 || linkMutation.isPending}
              onClick={() => linkMutation.mutate()}
            >
              {linkMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Link2 className="h-4 w-4" />
              )}
              {t("subscriptions.fixed.transactions.assign", {
                count: selected.length,
              })}
            </Button>
          ) : null}
        </DialogFooter>
        </DialogContent>
      </Dialog>
      <ManualTransactionDialog
        open={manualOpen}
        initialValue={manualInitialValue}
        pending={createManualMutation.isPending}
        onOpenChange={setManualOpen}
        onSubmit={(payload) => createManualMutation.mutate(payload)}
      />
    </>
  );
}

function CandidateRow({
  transaction,
  checked,
  divided,
  onToggle,
}: {
  transaction: FixedChargeTransaction;
  checked: boolean;
  divided: boolean;
  onToggle: () => void;
}) {
  return (
    <label
      className={cn(
        "flex cursor-pointer items-center gap-3 px-3 py-2.5 transition-colors hover:bg-muted/50",
        divided && "border-t",
      )}
    >
      <Checkbox checked={checked} onCheckedChange={onToggle} />
      <TransactionIdentity transaction={transaction} />
      <Money
        amount={transaction.amount_base}
        currency={transaction.base_currency}
        direction="debit"
        className="ml-auto shrink-0 text-sm font-medium"
      />
    </label>
  );
}

function LinkedRow({
  transaction,
  divided,
  pending,
  onUnlink,
}: {
  transaction: FixedChargeTransaction;
  divided: boolean;
  pending: boolean;
  onUnlink: () => void;
}) {
  const { t } = useT();
  return (
    <div
      className={cn(
        "flex items-center gap-3 px-3 py-2.5",
        divided && "border-t",
      )}
    >
      <TransactionIdentity transaction={transaction} />
      <Money
        amount={transaction.amount_base}
        currency={transaction.base_currency}
        direction="debit"
        className="ml-auto shrink-0 text-sm font-medium"
      />
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-8 w-8 shrink-0"
        disabled={pending}
        onClick={onUnlink}
        aria-label={t("subscriptions.fixed.transactions.unlink")}
      >
        <Unlink className="h-4 w-4" />
      </Button>
    </div>
  );
}

function TransactionIdentity({
  transaction,
}: {
  transaction: FixedChargeTransaction;
}) {
  const { t } = useT();
  const { formatDate } = useFormatters();
  const label = transaction.merchant || transaction.title;
  return (
    <div className="min-w-0">
      <div className="truncate text-sm font-medium" title={label}>
        {label}
      </div>
      <div className="mt-0.5 text-xs text-muted-foreground">
        {transaction.scheduled_due_date
          ? t("subscriptions.fixed.transactions.historyDate", {
              booking: formatDate(transaction.booking_date),
              due: formatDate(transaction.scheduled_due_date),
            })
          : formatDate(transaction.booking_date)}
      </div>
    </div>
  );
}
