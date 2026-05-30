"use client";

import { useState } from "react";
import { CategoryCombobox } from "@/components/category-combobox";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { TableSkeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Transaction } from "@/lib/api";
import { tCategory, tTransactionType, useT } from "@/lib/i18n";
import { formatCurrency, formatDate } from "@/lib/utils";
import { ArrowLeftRight, Ban, Check, Pencil, Trash2, X } from "lucide-react";
import { PAGE_SIZE, hasCategorySuggestion } from "../_lib/constants";

interface TransactionsTableProps {
  rows: Transaction[];
  fetchedCount: number;
  isLoading: boolean;
  page: number;
  selected: Set<number>;
  acceptPending: boolean;
  rejectPending: boolean;
  onToggleAll: () => void;
  onToggleOne: (id: number) => void;
  onPatchCategory: (id: number, value: string | null, rememberRule?: boolean) => void;
  onAcceptSuggestion: (id: number) => void;
  onRejectSuggestion: (id: number) => void;
  onDeleteOne: (id: number) => void;
  onPreviousPage: () => void;
  onNextPage: () => void;
}

export function TransactionsTable({
  rows,
  fetchedCount,
  isLoading,
  page,
  selected,
  acceptPending,
  rejectPending,
  onToggleAll,
  onToggleOne,
  onPatchCategory,
  onAcceptSuggestion,
  onRejectSuggestion,
  onDeleteOne,
  onPreviousPage,
  onNextPage,
}: TransactionsTableProps) {
  const { t } = useT();
  const [editing, setEditing] = useState<number | null>(null);
  const allOnPageSelected = rows.length > 0 && rows.every((r) => selected.has(r.id));

  return (
    <Card>
      <CardContent className="pt-6">
        {isLoading ? (
          <TableSkeleton />
        ) : rows.length === 0 ? (
          <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
            {t("transactions.empty")}
          </div>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8">
                    <input
                      type="checkbox"
                      checked={allOnPageSelected}
                      onChange={onToggleAll}
                      className="h-4 w-4"
                      aria-label="select all"
                    />
                  </TableHead>
                  <TableHead>{t("transactions.column.date")}</TableHead>
                  <TableHead>{t("transactions.column.merchant")}</TableHead>
                  <TableHead>{t("transactions.column.category")}</TableHead>
                  <TableHead className="text-right">
                    {t("transactions.column.amount")}
                  </TableHead>
                  <TableHead className="w-24" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((tx) => (
                  <TransactionRow
                    key={tx.id}
                    tx={tx}
                    selected={selected.has(tx.id)}
                    editing={editing === tx.id}
                    acceptPending={acceptPending}
                    rejectPending={rejectPending}
                    onToggle={() => onToggleOne(tx.id)}
                    onEdit={() => setEditing(tx.id)}
                    onCancelEdit={() => setEditing(null)}
                    onPatchCategory={(value, rememberRule) => {
                      onPatchCategory(tx.id, value, rememberRule);
                      setEditing(null);
                    }}
                    onAcceptSuggestion={() => onAcceptSuggestion(tx.id)}
                    onRejectSuggestion={() => onRejectSuggestion(tx.id)}
                    onDelete={() => onDeleteOne(tx.id)}
                  />
                ))}
              </TableBody>
            </Table>
            <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
              <span>
                {t("pagination.page", { n: page + 1 })} · {rows.length} / {fetchedCount}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 0}
                  onClick={onPreviousPage}
                >
                  {t("pagination.previous")}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={fetchedCount < PAGE_SIZE}
                  onClick={onNextPage}
                >
                  {t("pagination.next")}
                </Button>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

interface TransactionRowProps {
  tx: Transaction;
  selected: boolean;
  editing: boolean;
  acceptPending: boolean;
  rejectPending: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onCancelEdit: () => void;
  onPatchCategory: (value: string | null, rememberRule?: boolean) => void;
  onAcceptSuggestion: () => void;
  onRejectSuggestion: () => void;
  onDelete: () => void;
}

function TransactionRow({
  tx,
  selected,
  editing,
  acceptPending,
  rejectPending,
  onToggle,
  onEdit,
  onCancelEdit,
  onPatchCategory,
  onAcceptSuggestion,
  onRejectSuggestion,
  onDelete,
}: TransactionRowProps) {
  const { t } = useT();
  const hasSuggestion = hasCategorySuggestion(tx);
  const [rememberRule, setRememberRule] = useState(false);

  return (
    <TableRow className={selected ? "bg-primary/5" : ""}>
      <TableCell>
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggle}
          className="h-4 w-4"
          aria-label={`select ${tx.id}`}
        />
      </TableCell>
      <TableCell className="text-muted-foreground">
        {formatDate(tx.booking_date)}
      </TableCell>
      <TableCell className="font-medium">
        <div className="flex items-center gap-2">
          {tx.merchant || tx.title}
          {tx.is_transfer && (
            <Badge
              variant="outline"
              className="text-[10px]"
              title={t("transactions.transfer")}
            >
              <ArrowLeftRight className="mr-1 h-3 w-3" />
              {t("transactions.transfer")}
            </Badge>
          )}
          {!tx.is_transfer && tx.transaction_type !== "purchase" && (
            <Badge variant="outline" className="text-[10px]">
              {tTransactionType(t, tx.transaction_type)}
            </Badge>
          )}
        </div>
        {tx.merchant && tx.title && tx.merchant !== tx.title && (
          <div className="text-xs text-muted-foreground">{tx.title}</div>
        )}
      </TableCell>
      <TableCell>
        {editing ? (
          <div className="space-y-2">
            <CategoryCombobox
              value={tx.category}
              onChange={(value) => onPatchCategory(value, rememberRule)}
              autoFocus
            />
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={rememberRule}
                onChange={(event) => setRememberRule(event.target.checked)}
                className="h-3.5 w-3.5"
              />
              {t("transactions.rememberRule")}
            </label>
          </div>
        ) : tx.category ? (
          <Badge variant="secondary">{tCategory(t, tx.category)}</Badge>
        ) : tx.category_predicted ? (
          <div className="flex flex-col items-start gap-1">
            <Badge variant="outline" title={t("transactions.suggestion")}>
              {tCategory(t, tx.category_predicted)}
            </Badge>
            {tx.category_confidence !== null && (
              <span className="text-xs text-muted-foreground">
                {t("transactions.suggestion")} ·{" "}
                {(tx.category_confidence * 100).toFixed(0)}%
              </span>
            )}
          </div>
        ) : tx.category_suggestion_rejected ? (
          <Badge variant="outline">{t("transactions.suggestionRejected")}</Badge>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell
        className={`text-right tabular-nums ${
          tx.direction === "debit"
            ? "text-red-600 dark:text-red-400"
            : "text-emerald-600 dark:text-emerald-400"
        }`}
      >
        {tx.direction === "debit" ? "-" : "+"}
        {formatCurrency(Math.abs(Number(tx.amount)), tx.currency)}
      </TableCell>
      <TableCell className="text-right">
        {editing ? (
          <Button size="icon" variant="ghost" onClick={onCancelEdit}>
            <X className="h-4 w-4" />
          </Button>
        ) : (
          <div className="flex justify-end">
            {hasSuggestion && (
              <>
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={onAcceptSuggestion}
                  disabled={acceptPending}
                  aria-label={t("transactions.acceptOne")}
                >
                  <Check className="h-4 w-4 text-emerald-600" />
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={onRejectSuggestion}
                  disabled={rejectPending}
                  aria-label={t("transactions.rejectOne")}
                >
                  <Ban className="h-4 w-4 text-muted-foreground" />
                </Button>
              </>
            )}
            <Button
              size="icon"
              variant="ghost"
              onClick={onEdit}
              aria-label={t("transactions.editCategory")}
            >
              <Pencil className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              onClick={onDelete}
              aria-label={t("common.delete")}
            >
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          </div>
        )}
      </TableCell>
    </TableRow>
  );
}
