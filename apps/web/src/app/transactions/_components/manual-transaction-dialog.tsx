/* eslint-disable react-hooks/set-state-in-effect -- reset the form for each opened record */
"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";

import { CategorySelect } from "@/components/category-select";
import { DatePicker } from "@/components/date-range-picker";
import { FilterSelect } from "@/components/filter-select";
import { TransactionTypeCombobox } from "@/components/transaction-type-combobox";
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
import type { ManualTransactionInput } from "@/lib/api";
import { useT } from "@/lib/i18n";

interface ManualTransactionForm {
  bookingDate: string;
  amount: string;
  direction: "debit" | "credit";
  merchant: string;
  title: string;
  transactionType: string;
  category: string;
  notes: string;
}

interface ManualTransactionDialogProps {
  open: boolean;
  mode?: "create" | "edit";
  initialValue?: Partial<ManualTransactionInput>;
  pending: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (payload: ManualTransactionInput) => void;
}

function localDateValue() {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formFromInitial(
  initialValue?: Partial<ManualTransactionInput>,
): ManualTransactionForm {
  return {
    bookingDate: initialValue?.booking_date ?? localDateValue(),
    amount:
      initialValue?.amount == null
        ? ""
        : String(Math.abs(Number(initialValue.amount))).replace(".", ","),
    direction: initialValue?.direction ?? "debit",
    merchant: initialValue?.merchant ?? "",
    title: initialValue?.title ?? "",
    transactionType: initialValue?.transaction_type ?? "",
    category: initialValue?.category ?? "",
    notes: initialValue?.notes ?? "",
  };
}

function categoryType(direction: "debit" | "credit") {
  return direction === "credit" ? "refund" : "expense";
}

const TYPES_BY_DIRECTION = {
  debit: [
    "expense",
    "own_transfer",
    "cash_withdrawal",
    "debt_payment",
    "asset_allocation",
    "other",
  ],
  credit: ["salary", "income", "refund", "own_transfer", "other"],
} as const;

export function ManualTransactionDialog({
  open,
  mode = "create",
  initialValue,
  pending,
  onOpenChange,
  onSubmit,
}: ManualTransactionDialogProps) {
  const { t } = useT();
  const [form, setForm] = useState(() => formFromInitial(initialValue));

  useEffect(() => {
    if (open) setForm(formFromInitial(initialValue));
  }, [initialValue, open]);

  const parsedAmount = useMemo(
    () => Number(form.amount.trim().replace(",", ".")),
    [form.amount],
  );
  const canSubmit =
    form.bookingDate !== "" &&
    Number.isFinite(parsedAmount) &&
    parsedAmount > 0 &&
    Boolean(form.merchant.trim() || form.title.trim());

  const submit = () => {
    if (!canSubmit) return;
    onSubmit({
      booking_date: form.bookingDate,
      amount: parsedAmount,
      direction: form.direction,
      merchant: form.merchant.trim(),
      title: form.title.trim(),
      transaction_type: form.transactionType || null,
      category: form.category || null,
      notes: form.notes.trim() || null,
    });
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!pending) onOpenChange(next);
      }}
    >
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {t(
              mode === "edit"
                ? "transactions.manual.editTitle"
                : "transactions.manual.addTitle",
            )}
          </DialogTitle>
          <DialogDescription>
            {t("transactions.manual.description")}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-1 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label>{t("transactions.manual.date")}</Label>
            <DatePicker
              value={form.bookingDate}
              onChange={(bookingDate) =>
                setForm((current) => ({ ...current, bookingDate }))
              }
              ariaLabel={t("transactions.manual.date")}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="manual-transaction-amount">
              {t("transactions.manual.amount")}
            </Label>
            <div className="relative">
              <Input
                id="manual-transaction-amount"
                inputMode="decimal"
                value={form.amount}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    amount: event.target.value,
                  }))
                }
                placeholder="0,00"
                className="pr-12"
              />
              <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
                PLN
              </span>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>{t("transactions.manual.direction")}</Label>
            <FilterSelect
              value={form.direction}
              onValueChange={(value) => {
                const direction = value as "debit" | "credit";
                setForm((current) => ({
                  ...current,
                  direction,
                  transactionType: current.category
                    ? categoryType(direction)
                    : TYPES_BY_DIRECTION[direction].some(
                          (value) => value === current.transactionType,
                        )
                      ? current.transactionType
                      : "",
                }));
              }}
              options={[
                {
                  value: "debit",
                  label: t("transactions.filterDirection.debit"),
                },
                {
                  value: "credit",
                  label: t("transactions.filterDirection.credit"),
                },
              ]}
            />
          </div>
          <div className="space-y-1.5">
            <Label>{t("transactions.manual.type")}</Label>
            <TransactionTypeCombobox
              value={form.transactionType}
              onChange={(transactionType) =>
                setForm((current) => ({
                  ...current,
                  transactionType,
                  category:
                    current.category &&
                    transactionType !== categoryType(current.direction)
                      ? ""
                      : current.category,
                }))
              }
              size="md"
              includeEmpty
              emptyLabel={t("transactions.manual.typeAutomatic")}
              allowedValues={TYPES_BY_DIRECTION[form.direction]}
              ariaLabel={t("transactions.manual.type")}
            />
          </div>

          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="manual-transaction-merchant">
              {t("transactions.manual.merchant")}
            </Label>
            <Input
              id="manual-transaction-merchant"
              value={form.merchant}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  merchant: event.target.value,
                }))
              }
            />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="manual-transaction-title">
              {t("transactions.manual.transactionTitle")}
            </Label>
            <Input
              id="manual-transaction-title"
              value={form.title}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  title: event.target.value,
                }))
              }
            />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label>{t("transactions.manual.category")}</Label>
            <CategorySelect
              value={form.category}
              onChange={(category) =>
                setForm((current) => ({
                  ...current,
                  category,
                  transactionType: category
                    ? categoryType(current.direction)
                    : current.transactionType,
                }))
              }
              allLabel={t("subscriptions.fixed.noCategory")}
              className="w-full"
            />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="manual-transaction-notes">
              {t("transactions.manual.notes")}
            </Label>
            <Input
              id="manual-transaction-notes"
              value={form.notes}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  notes: event.target.value,
                }))
              }
            />
          </div>
        </div>

        <p className="text-xs text-muted-foreground">
          {t("transactions.manual.identityHint")}
        </p>

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
            onClick={submit}
            disabled={!canSubmit || pending}
          >
            {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {t(mode === "edit" ? "common.save" : "transactions.manual.add")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
