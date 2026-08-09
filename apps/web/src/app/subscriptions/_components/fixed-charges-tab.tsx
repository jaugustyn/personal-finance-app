"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Clock,
  Edit3,
  Loader2,
  MoreHorizontal,
  Pause,
  Play,
  Plus,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { CategoryCompactAccent } from "@/components/category-accent";
import { CategorySelect } from "@/components/category-select";
import { useConfirm } from "@/components/confirm-dialog";
import { DatePicker } from "@/components/date-range-picker";
import { ErrorState } from "@/components/error-state";
import { useCategories } from "@/hooks/use-categories";
import {
  api,
  type FixedCharge,
  type FixedChargeCadence,
  type FixedChargeCreateInput,
  type FixedChargeSummary as FixedChargeSummaryType,
} from "@/lib/api";
import { tCategory, useFormatters, useT, type TranslationKey } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";
import { invalidateSubscriptionData, queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CardGridSkeleton } from "@/components/ui/skeleton";
import { FixedChargeTransactionsDialog } from "./fixed-charge-transactions-dialog";

const CADENCES: FixedChargeCadence[] = [
  "monthly",
  "quarterly",
  "semiannual",
  "yearly",
];
const CADENCE_LABELS: Record<FixedChargeCadence, TranslationKey> = {
  monthly: "subscriptions.fixed.cadence.monthly",
  quarterly: "subscriptions.fixed.cadence.quarterly",
  semiannual: "subscriptions.fixed.cadence.semiannual",
  yearly: "subscriptions.fixed.cadence.yearly",
};
const PAYMENT_STATUS_LABELS: Record<
  FixedCharge["payment_status"],
  TranslationKey
> = {
  pending: "subscriptions.fixed.status.pending",
  paid: "subscriptions.fixed.status.paid",
  overdue: "subscriptions.fixed.status.overdue",
  paused: "subscriptions.fixed.status.paused",
};

interface FormState {
  name: string;
  amount: string;
  cadence: FixedChargeCadence;
  anchorDate: string;
  category: string;
}

function localDateValue() {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function localDate(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function formatDueDate(value: string, localeTag: string): string {
  return new Intl.DateTimeFormat(localeTag, {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(localDate(value));
}

function formatRelativeDueDate(value: string, localeTag: string): string {
  const due = localDate(value);
  const today = new Date();
  const difference = Math.round(
    (Date.UTC(due.getFullYear(), due.getMonth(), due.getDate()) -
      Date.UTC(today.getFullYear(), today.getMonth(), today.getDate())) /
      86_400_000,
  );
  return new Intl.RelativeTimeFormat(localeTag, {
    numeric: "auto",
  }).format(difference, "day");
}

function emptyForm(): FormState {
  return {
    name: "",
    amount: "",
    cadence: "monthly",
    anchorDate: localDateValue(),
    category: "",
  };
}

export function FixedChargesTab() {
  const { t } = useT();
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [edited, setEdited] = useState<FixedCharge | null>(null);
  const [transactionsTarget, setTransactionsTarget] =
    useState<FixedCharge | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm);

  const query = useQuery({
    queryKey: queryKeys.fixedCharges.list,
    queryFn: api.fixedCharges,
  });

  const refresh = () => invalidateSubscriptionData(queryClient);

  const saveMutation = useMutation({
    mutationFn: (payload: FixedChargeCreateInput) =>
      edited
        ? api.updateFixedCharge(edited.id, payload)
        : api.createFixedCharge(payload),
    onSuccess: () => {
      void refresh();
      setDialogOpen(false);
      setEdited(null);
      setForm(emptyForm());
      toast.success(t("toast.saved"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const stateMutation = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) =>
      api.updateFixedCharge(id, { active }),
    onSuccess: (_result, variables) => {
      void refresh();
      toast.success(
        t(
          variables.active
            ? "subscriptions.fixed.resumed"
            : "subscriptions.fixed.paused",
        ),
      );
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const deleteMutation = useMutation({
    mutationFn: api.deleteFixedCharge,
    onSuccess: () => {
      void refresh();
      toast.success(t("toast.deleted"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const active = query.data?.items.filter((item) => item.active) ?? [];
  const paused = query.data?.items.filter((item) => !item.active) ?? [];

  const openCreate = () => {
    setEdited(null);
    setForm(emptyForm());
    setDialogOpen(true);
  };

  const openEdit = (charge: FixedCharge) => {
    setEdited(charge);
    setForm({
      name: charge.name,
      amount: String(charge.amount),
      cadence: charge.cadence,
      anchorDate: charge.anchor_date,
      category: charge.category ?? "",
    });
    setDialogOpen(true);
  };

  const remove = async (charge: FixedCharge) => {
    const accepted = await confirm({
      title: t("subscriptions.fixed.deleteConfirm", { name: charge.name }),
      destructive: true,
    });
    if (accepted) deleteMutation.mutate(charge.id);
  };

  if (query.isError) {
    return (
      <ErrorState
        title={t("subscriptions.fixed.error")}
        onRetry={() => void query.refetch()}
      />
    );
  }

  return (
    <div className="space-y-5">
      {query.isLoading ? (
        <>
          <FixedChargeSummarySkeleton />
          <CardGridSkeleton />
        </>
      ) : (
        <>
          <FixedChargeSummary summary={query.data!.summary} />

          <FixedChargeGrid
            charges={active}
            pending={stateMutation.isPending || deleteMutation.isPending}
            onEdit={openEdit}
            onStateChange={(charge) =>
              stateMutation.mutate({ id: charge.id, active: false })
            }
            onDelete={remove}
            onTransactions={setTransactionsTarget}
            onAdd={openCreate}
          />

          {paused.length > 0 ? (
            <details className="group rounded-lg border bg-card">
              <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 text-sm font-medium">
                <span>{t("subscriptions.fixed.pausedSection")}</span>
                <Badge variant="secondary">{paused.length}</Badge>
              </summary>
              <div className="border-t p-3">
                <FixedChargeGrid
                  charges={paused}
                  pending={stateMutation.isPending || deleteMutation.isPending}
                  onEdit={openEdit}
                  onStateChange={(charge) =>
                    stateMutation.mutate({ id: charge.id, active: true })
                  }
                  onDelete={remove}
                  onTransactions={setTransactionsTarget}
                />
              </div>
            </details>
          ) : null}
        </>
      )}

      <FixedChargeDialog
        open={dialogOpen}
        edited={edited}
        form={form}
        pending={saveMutation.isPending}
        onFormChange={setForm}
        onOpenChange={(open) => {
          if (saveMutation.isPending) return;
          setDialogOpen(open);
          if (!open) setEdited(null);
        }}
        onSubmit={() => {
          const amount = Number(form.amount.replace(",", "."));
          if (!form.name.trim() || !Number.isFinite(amount) || amount <= 0) {
            return;
          }
          saveMutation.mutate({
            name: form.name.trim(),
            amount,
            cadence: form.cadence,
            anchor_date: form.anchorDate,
            category: form.category || null,
          });
        }}
      />
      <FixedChargeTransactionsDialog
        charge={transactionsTarget}
        open={transactionsTarget !== null}
        onOpenChange={(open) => {
          if (!open) setTransactionsTarget(null);
        }}
      />
    </div>
  );
}

function FixedChargeSummary({
  summary,
}: {
  summary: FixedChargeSummaryType;
}) {
  const { t } = useT();
  const { formatCurrency } = useFormatters();
  const items = [
    {
      label: t("subscriptions.fixed.monthly"),
      value: formatCurrency(summary.monthly_total, summary.base_currency),
    },
    {
      label: t("subscriptions.fixed.yearly"),
      value: formatCurrency(summary.yearly_total, summary.base_currency),
    },
    {
      label: t("subscriptions.fixed.next30"),
      value: formatCurrency(summary.next_30_days_total, summary.base_currency),
    },
    {
      label: t("subscriptions.fixed.activeCount"),
      value: String(summary.active_count),
    },
  ];
  return (
    <section className="grid min-w-0 flex-1 overflow-hidden rounded-lg border bg-card sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item, index) => (
        <div
          key={item.label}
          className={cn(
            "min-w-0 px-4 py-3.5",
            index > 0 && "border-t sm:border-t-0",
            index % 2 === 1 && "sm:border-l",
            index >= 2 && "sm:border-t xl:border-t-0",
            index > 0 && "xl:border-l",
          )}
        >
          <div className="truncate text-xs text-muted-foreground">
            {item.label}
          </div>
          <div className="mt-1 truncate text-lg font-semibold tabular-nums">
            {item.value}
          </div>
        </div>
      ))}
    </section>
  );
}

function FixedChargeSummarySkeleton() {
  return <div className="h-[74px] animate-pulse rounded-lg border bg-muted/40" />;
}

function FixedChargeGrid({
  charges,
  pending,
  onEdit,
  onStateChange,
  onDelete,
  onTransactions,
  onAdd,
}: {
  charges: FixedCharge[];
  pending: boolean;
  onEdit: (charge: FixedCharge) => void;
  onStateChange: (charge: FixedCharge) => void;
  onDelete: (charge: FixedCharge) => void;
  onTransactions: (charge: FixedCharge) => void;
  onAdd?: () => void;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {charges.map((charge) => (
        <FixedChargeCard
          key={charge.id}
          charge={charge}
          pending={pending}
          onEdit={() => onEdit(charge)}
          onStateChange={() => onStateChange(charge)}
          onDelete={() => onDelete(charge)}
          onTransactions={() => onTransactions(charge)}
        />
      ))}
      {onAdd ? <FixedChargeAddCard onClick={onAdd} /> : null}
    </div>
  );
}

function FixedChargeAddCard({ onClick }: { onClick: () => void }) {
  const { t } = useT();
  return (
    <button
      type="button"
      className="group flex min-h-48 flex-col items-center justify-center rounded-lg border border-dashed bg-card/40 p-5 text-center transition-colors hover:border-primary/45 hover:bg-accent/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      onClick={onClick}
    >
      <span className="flex h-9 w-9 items-center justify-center rounded-full border bg-background text-muted-foreground transition-colors group-hover:border-primary/35 group-hover:text-primary">
        <Plus className="h-4 w-4" />
      </span>
      <span className="mt-3 text-sm font-medium">
        {t("subscriptions.fixed.add")}
      </span>
      <span className="mt-1 text-xs text-muted-foreground">
        {t("subscriptions.fixed.addDescription")}
      </span>
    </button>
  );
}

function FixedChargeCard({
  charge,
  pending,
  onEdit,
  onStateChange,
  onDelete,
  onTransactions,
}: {
  charge: FixedCharge;
  pending: boolean;
  onEdit: () => void;
  onStateChange: () => void;
  onDelete: () => void;
  onTransactions: () => void;
}) {
  const { t } = useT();
  const { formatCurrency, localeTag } = useFormatters();
  const { data: categories = [] } = useCategories();
  const category = categories.find((item) => item.name === charge.category);
  const actionLabel =
    charge.payment_status === "paid"
      ? t("subscriptions.fixed.transactions.viewPayment")
      : charge.payment_status === "paused"
        ? t("subscriptions.fixed.transactions.viewHistory")
        : t("subscriptions.fixed.transactions.assignPayment");
  const paymentDetail =
    charge.payment_status === "paid"
      ? t("subscriptions.fixed.payment.assignedAmount", {
          amount: formatCurrency(
            charge.current_paid_amount,
            charge.currency,
          ),
        })
      : charge.payment_status === "paused"
        ? t("subscriptions.fixed.payment.pausedHelp")
        : t("subscriptions.fixed.payment.unassigned");
  return (
    <Card
      className={cn(
        "overflow-hidden transition-colors hover:border-foreground/15",
        !charge.active && "opacity-75",
      )}
    >
      <CardContent className="flex h-full flex-col gap-4 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="truncate font-medium" title={charge.name}>
              {charge.name}
            </div>
            {charge.category ? (
              <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
                <CategoryCompactAccent color={category?.color} />
                {tCategory(t, charge.category)}
              </div>
            ) : null}
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="-mr-2 -mt-2 h-8 w-8"
                disabled={pending}
                aria-label={t("common.actions")}
              >
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={onEdit}>
                <Edit3 className="mr-2 h-4 w-4" />
                {t("common.edit")}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={onStateChange}>
                {charge.active ? (
                  <Pause className="mr-2 h-4 w-4" />
                ) : (
                  <Play className="mr-2 h-4 w-4" />
                )}
                {t(
                  charge.active
                    ? "subscriptions.fixed.pause"
                    : "subscriptions.fixed.resume",
                )}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onClick={onDelete}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                {t("common.delete")}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div className="flex items-end justify-between gap-5">
          <div className="min-w-0">
            <div className="truncate text-2xl font-semibold tabular-nums">
              {formatCurrency(charge.amount, charge.currency)}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {t(CADENCE_LABELS[charge.cadence])}
            </div>
          </div>
          <div className="min-w-0 text-right">
            <div className="truncate text-base font-semibold">
              {charge.current_due_date
                ? formatDueDate(charge.current_due_date, localeTag)
                : t("subscriptions.fixed.pausedLabel")}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {charge.current_due_date
                ? t("subscriptions.fixed.relativeDue", {
                    relative: formatRelativeDueDate(
                      charge.current_due_date,
                      localeTag,
                    ),
                  })
                : t("subscriptions.fixed.noActiveDue")}
            </div>
          </div>
        </div>

        <div className="mt-auto flex min-h-12 items-center justify-between gap-3 pt-1">
          <div className="flex min-w-0 items-start gap-2.5">
            <PaymentStatusIcon status={charge.payment_status} />
            <div className="min-w-0">
              <div className="text-sm font-medium">
                {t(PAYMENT_STATUS_LABELS[charge.payment_status])}
              </div>
              <div className="mt-0.5 truncate text-xs text-muted-foreground">
                {paymentDetail}
              </div>
            </div>
          </div>
          <button
            type="button"
            className="flex shrink-0 items-center gap-1 text-sm font-medium transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onClick={onTransactions}
          >
            <span>{actionLabel}</span>
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>
      </CardContent>
    </Card>
  );
}

function PaymentStatusIcon({
  status,
}: {
  status: FixedCharge["payment_status"];
}) {
  if (status === "paid") {
    return <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-positive" />;
  }
  if (status === "overdue") {
    return <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />;
  }
  if (status === "paused") {
    return <Pause className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />;
  }
  return <Clock className="mt-0.5 h-4 w-4 shrink-0 text-warning" />;
}

function FixedChargeDialog({
  open,
  edited,
  form,
  pending,
  onFormChange,
  onOpenChange,
  onSubmit,
}: {
  open: boolean;
  edited: FixedCharge | null;
  form: FormState;
  pending: boolean;
  onFormChange: (form: FormState) => void;
  onOpenChange: (open: boolean) => void;
  onSubmit: () => void;
}) {
  const { t } = useT();
  const amount = Number(form.amount.replace(",", "."));
  const valid =
    Boolean(form.name.trim()) &&
    Boolean(form.anchorDate) &&
    Number.isFinite(amount) &&
    amount > 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>
            {t(
              edited
                ? "subscriptions.fixed.edit"
                : "subscriptions.fixed.add",
            )}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {t("subscriptions.fixed.formDescription")}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="fixed-charge-name">
              {t("subscriptions.fixed.name")}
            </Label>
            <Input
              id="fixed-charge-name"
              value={form.name}
              maxLength={128}
              onChange={(event) =>
                onFormChange({ ...form, name: event.target.value })
              }
              autoFocus
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="fixed-charge-amount">
                {t("subscriptions.fixed.amount")}
              </Label>
              <div className="relative">
                <Input
                  id="fixed-charge-amount"
                  type="number"
                  inputMode="decimal"
                  min="0.01"
                  step="0.01"
                  value={form.amount}
                  className="pr-12 tabular-nums"
                  onChange={(event) =>
                    onFormChange({ ...form, amount: event.target.value })
                  }
                />
                <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-muted-foreground">
                  PLN
                </span>
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="fixed-charge-cadence">
                {t("subscriptions.fixed.cadence")}
              </Label>
              <Select
                value={form.cadence}
                onValueChange={(value) =>
                  onFormChange({
                    ...form,
                    cadence: value as FixedChargeCadence,
                  })
                }
              >
                <SelectTrigger id="fixed-charge-cadence">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CADENCES.map((cadence) => (
                    <SelectItem
                      key={cadence}
                      value={cadence}
                      indicatorPosition="right"
                    >
                      {t(CADENCE_LABELS[cadence])}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="fixed-charge-anchor-date">
              {t("subscriptions.fixed.anchorDate")}
            </Label>
            <DatePicker
              id="fixed-charge-anchor-date"
              value={form.anchorDate}
              onChange={(anchorDate) => onFormChange({ ...form, anchorDate })}
              ariaLabel={t("subscriptions.fixed.anchorDate")}
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="fixed-charge-category">
              {t("subscriptions.fixed.category")}
            </Label>
            <CategorySelect
              id="fixed-charge-category"
              value={form.category}
              onChange={(category) => onFormChange({ ...form, category })}
              allLabel={t("subscriptions.fixed.noCategory")}
              ariaLabel={t("subscriptions.fixed.category")}
              className="w-full"
            />
          </div>
        </div>

        <DialogFooter className="mt-1">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={pending}
          >
            {t("common.cancel")}
          </Button>
          <Button type="button" onClick={onSubmit} disabled={!valid || pending}>
            {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {t("common.save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
