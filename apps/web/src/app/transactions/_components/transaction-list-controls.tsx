"use client";

import { useQuery } from "@tanstack/react-query";
import { Download, Plus, RotateCcw, SlidersHorizontal } from "lucide-react";

import { CategorySelect } from "@/components/category-select";
import { ClearableInput } from "@/components/ui/clearable-input";
import { DateRangePicker } from "@/components/date-range-picker";
import { DirectionFilterSelect } from "@/components/direction-filter-select";
import { FilterSelect } from "@/components/filter-select";
import { TransactionTypeFilterSelect } from "@/components/transaction-type-filter-select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import { TableHead, TableRow } from "@/components/ui/table";
import {
  api,
  type Direction,
  type FilterSummary,
} from "@/lib/api";
import { useT } from "@/lib/i18n";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";

export interface TransactionListControlsProps {
  search: string;
  category: string;
  minAmount: string;
  maxAmount: string;
  direction: Direction;
  transactionType: string;
  dateFrom: string;
  dateTo: string;
  importId?: number;
  accountId?: number;
  includeTransfers: boolean;
  hasActiveFilters: boolean;
  filterSummary?: FilterSummary;
  onAddManualTransaction?: () => void;
  onSearchChange: (value: string) => void;
  onCategoryChange: (value: string) => void;
  onMinAmountChange: (value: string) => void;
  onMaxAmountChange: (value: string) => void;
  onDirectionChange: (value: Direction) => void;
  onTransactionTypeChange: (value: string) => void;
  onDateFromChange: (value: string) => void;
  onDateToChange: (value: string) => void;
  onImportIdChange: (value: number | undefined) => void;
  onAccountIdChange: (value: number | undefined) => void;
  onIncludeTransfersChange: (value: boolean) => void;
  onClearFilters: () => void;
}

export interface TransactionCategoryReviewControlsProps {
  search: string;
  category: string;
  minAmount: string;
  maxAmount: string;
  direction: Direction;
  dateFrom: string;
  dateTo: string;
  hasActiveFilters: boolean;
  onSearchChange: (value: string) => void;
  onCategoryChange: (value: string) => void;
  onMinAmountChange: (value: string) => void;
  onMaxAmountChange: (value: string) => void;
  onDirectionChange: (value: Direction) => void;
  onDateFromChange: (value: string) => void;
  onDateToChange: (value: string) => void;
  onClearFilters: () => void;
}

export function TransactionListToolbar({
  search,
  category,
  minAmount,
  maxAmount,
  direction,
  transactionType,
  dateFrom,
  dateTo,
  importId,
  accountId,
  includeTransfers,
  onAddManualTransaction,
  onImportIdChange,
  onAccountIdChange,
  onIncludeTransfersChange,
}: TransactionListControlsProps) {
  const { t } = useT();
  const importsQuery = useQuery({
    queryKey: queryKeys.imports.history,
    queryFn: api.listImports,
    enabled: importId !== undefined,
  });
  const accountsQuery = useQuery({
    queryKey: queryKeys.accounts.list(true),
    queryFn: () => api.accounts(true),
  });
  const activeImport = importsQuery.data?.find((row) => row.id === importId);
  const exportHref = api.exportTransactionsUrl({
    search: search.trim() || undefined,
    direction: direction === "all" ? undefined : direction,
    category: category || undefined,
    min_amount: amountFilterValue(minAmount),
    max_amount: amountFilterValue(maxAmount),
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    import_id: importId,
    account_id: accountId,
    include_transfers: includeTransfers,
    category_state: category ? "categorized" : "all",
    transaction_type: transactionType || undefined,
  });

  return (
    <div className="flex flex-wrap items-end justify-between gap-4 px-1 py-2">
      <div className="flex flex-wrap items-end gap-4">
        <div className="min-w-0">
          <div className="mb-1.5 flex items-center px-0.5 text-xs font-medium text-muted-foreground">
            {t("transactions.filterAccount")}
          </div>
          <FilterSelect
            value={accountId === undefined ? "all" : String(accountId)}
            onValueChange={(value) =>
              onAccountIdChange(value === "all" ? undefined : Number(value))
            }
            options={[
              {
                value: "all",
                label: t("transactions.filterAccountAll"),
              },
              ...(accountsQuery.data ?? []).map((account) => ({
                value: String(account.id),
                label: account.archived_at
                  ? `${account.name} (${t("accounts.archivedLabel")})`
                  : account.name,
              })),
            ]}
            ariaLabel={t("transactions.filterAccount")}
            className={cn(
              "h-9 w-60 border-border/80 bg-card shadow-sm hover:border-foreground/20",
              accountId !== undefined && "border-primary/40",
            )}
            disabled={accountsQuery.isLoading || accountsQuery.isError}
          />
        </div>

        <div className="min-w-0">
          <div className="mb-1.5 flex items-center px-0.5 text-xs font-medium text-muted-foreground">
            {t("transactions.includeTransfers")}
          </div>
          <div className="flex h-9 items-center px-1">
            <Switch
              checked={includeTransfers}
              onCheckedChange={onIncludeTransfersChange}
              aria-label={t("transactions.includeTransfers")}
            />
          </div>
        </div>

        {importId !== undefined ? (
          <div className="min-w-0">
            <div className="mb-1.5 flex items-center px-0.5 text-xs font-medium text-muted-foreground">
              {t("transactions.filterImport")}
            </div>
            <FilterSelect
              value={String(importId)}
              onValueChange={(value) =>
                onImportIdChange(value === "all" ? undefined : Number(value))
              }
              options={[
                {
                  value: "all",
                  label: t("transactions.filterImportAll"),
                },
                ...(importsQuery.data ?? []).map((row) => ({
                  value: String(row.id),
                  label: `${row.filename} · ${row.source}`,
                })),
                ...(!activeImport && !importsQuery.isLoading
                  ? [
                      {
                        value: String(importId),
                        label: t("transactions.filterImportNumber", {
                          id: importId,
                        }),
                      },
                    ]
                  : []),
              ]}
              ariaLabel={t("transactions.filterImport")}
              className="h-9 w-64 max-w-[35vw] border-border/80 bg-card shadow-sm hover:border-foreground/20"
              disabled={importsQuery.isLoading || importsQuery.isError}
            />
          </div>
        ) : null}
      </div>

      <div className="flex items-center gap-2.5 pl-2">
        {onAddManualTransaction ? (
          <Button size="sm" onClick={onAddManualTransaction}>
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            {t("transactions.manual.add")}
          </Button>
        ) : null}
        <Button size="sm" variant="outline" asChild>
          <a href={exportHref} title={t("transactions.exportCsvHint")}>
            <Download className="mr-1.5 h-3.5 w-3.5" />
            {t("transactions.exportCsv")}
          </a>
        </Button>
      </div>
    </div>
  );
}

export function TransactionColumnFiltersRow({
  search,
  category,
  minAmount,
  maxAmount,
  direction,
  transactionType,
  dateFrom,
  dateTo,
  hasActiveFilters,
  onSearchChange,
  onCategoryChange,
  onMinAmountChange,
  onMaxAmountChange,
  onDirectionChange,
  onTransactionTypeChange,
  onDateFromChange,
  onDateToChange,
  onClearFilters,
}: TransactionListControlsProps) {
  const { t } = useT();
  const clearDateRange = () => {
    onDateFromChange("");
    onDateToChange("");
  };

  return (
    <TableRow className="bg-muted/10 hover:bg-muted/10">
      <TableHead className="h-11 w-10 border-r border-border/60 p-0" />
      <TableHead className="h-11 w-[10rem] border-r border-border/50 p-0">
        <DateRangePicker
          from={dateFrom}
          to={dateTo}
          onFromChange={onDateFromChange}
          onToChange={onDateToChange}
          onClear={clearDateRange}
          ariaLabel={t("transactions.filterDateRange")}
          compactLabel
          showIcon={false}
          triggerClassName={cn(
            TRANSACTION_INLINE_FILTER_CONTROL_CLASS,
            (dateFrom || dateTo) && TRANSACTION_INLINE_FILTER_ACTIVE_CLASS,
            "h-11 justify-start text-xs",
          )}
        />
      </TableHead>
      <TableHead className="h-11 border-r border-border/50 p-0">
        <ClearableInput
          placeholder={t("transactions.search")}
          value={search}
          onValueChange={onSearchChange}
          clearLabel={t("common.clear")}
          className="w-full"
          inputClassName={cn(
            TRANSACTION_INLINE_FILTER_CONTROL_CLASS,
            search && TRANSACTION_INLINE_FILTER_ACTIVE_CLASS,
            "h-11 text-xs",
          )}
        />
      </TableHead>
      <TableHead className="h-11 w-52 border-r border-border/50 p-0">
        <TransactionTypeFilterSelect
          value={transactionType}
          onChange={onTransactionTypeChange}
          allLabel={t("transactions.filterType.all")}
          ariaLabel={t("transactions.filterType")}
          className={cn(
            TRANSACTION_INLINE_FILTER_CONTROL_CLASS,
            transactionType && TRANSACTION_INLINE_FILTER_ACTIVE_CLASS,
            "relative h-11 w-full justify-start pr-8 text-xs [&>svg]:absolute [&>svg]:right-3",
          )}
        />
      </TableHead>
      <TableHead className="h-11 w-52 border-r border-border/50 p-0">
        <CategorySelect
          value={category}
          onChange={onCategoryChange}
          allLabel={t("transactions.filterCategoryAll")}
          ariaLabel={t("transactions.filterCategory")}
          className={cn(
            TRANSACTION_INLINE_FILTER_CONTROL_CLASS,
            category && TRANSACTION_INLINE_FILTER_ACTIVE_CLASS,
            "relative h-11 w-full justify-start pr-8 text-xs [&>svg]:absolute [&>svg]:right-3",
          )}
        />
      </TableHead>
      <TableHead className="h-11 w-52 border-r border-border/50 p-0 tabular-nums">
        <AmountAndDirectionFilter
          minAmount={minAmount}
          maxAmount={maxAmount}
          direction={direction}
          onMinAmountChange={onMinAmountChange}
          onMaxAmountChange={onMaxAmountChange}
          onDirectionChange={onDirectionChange}
        />
      </TableHead>
      <TableHead className="h-11 w-12 p-0 text-center">
        <ClearFiltersButton
          active={hasActiveFilters}
          onClear={onClearFilters}
        />
      </TableHead>
    </TableRow>
  );
}

export function TransactionCategoryReviewFiltersRow({
  search,
  category,
  minAmount,
  maxAmount,
  direction,
  dateFrom,
  dateTo,
  hasActiveFilters,
  onSearchChange,
  onCategoryChange,
  onMinAmountChange,
  onMaxAmountChange,
  onDirectionChange,
  onDateFromChange,
  onDateToChange,
  onClearFilters,
}: TransactionCategoryReviewControlsProps) {
  const { t } = useT();
  const clearDateRange = () => {
    onDateFromChange("");
    onDateToChange("");
  };

  return (
    <TableRow className="bg-muted/10 hover:bg-muted/10">
      <TableHead className="h-11 w-10 border-r border-border/60 p-0" />
      <TableHead className="h-11 w-[10rem] border-r border-border/40 p-0">
        <DateRangePicker
          from={dateFrom}
          to={dateTo}
          onFromChange={onDateFromChange}
          onToChange={onDateToChange}
          onClear={clearDateRange}
          ariaLabel={t("transactions.filterDateRange")}
          compactLabel
          showIcon={false}
          triggerClassName={cn(
            TRANSACTION_INLINE_FILTER_CONTROL_CLASS,
            (dateFrom || dateTo) && TRANSACTION_INLINE_FILTER_ACTIVE_CLASS,
            "h-11 justify-start text-xs",
          )}
        />
      </TableHead>
      <TableHead className="h-11 border-r border-border/40 p-0">
        <ClearableInput
          placeholder={t("transactions.search")}
          value={search}
          onValueChange={onSearchChange}
          clearLabel={t("common.clear")}
          className="w-full"
          inputClassName={cn(
            TRANSACTION_INLINE_FILTER_CONTROL_CLASS,
            search && TRANSACTION_INLINE_FILTER_ACTIVE_CLASS,
            "h-11 text-xs",
          )}
        />
      </TableHead>
      <TableHead className="h-11 w-52 border-r border-border/40 p-0 tabular-nums">
        <AmountAndDirectionFilter
          minAmount={minAmount}
          maxAmount={maxAmount}
          direction={direction}
          onMinAmountChange={onMinAmountChange}
          onMaxAmountChange={onMaxAmountChange}
          onDirectionChange={onDirectionChange}
        />
      </TableHead>
      <TableHead className="h-11 w-52 border-r border-border/40 p-0">
        <CategorySelect
          value={category}
          onChange={onCategoryChange}
          allLabel={t("transactions.filterSuggestedCategoryAll")}
          ariaLabel={t("transactions.filterSuggestedCategory")}
          className={cn(
            TRANSACTION_INLINE_FILTER_CONTROL_CLASS,
            category && TRANSACTION_INLINE_FILTER_ACTIVE_CLASS,
            "relative h-11 w-full justify-start pr-8 text-xs [&>svg]:absolute [&>svg]:right-3",
          )}
        />
      </TableHead>
      <TableHead className="h-11 w-20 p-0 text-center">
        <ClearFiltersButton
          active={hasActiveFilters}
          onClear={onClearFilters}
        />
      </TableHead>
    </TableRow>
  );
}

function ClearFiltersButton({
  active,
  onClear,
}: {
  active: boolean;
  onClear: () => void;
}) {
  const { t } = useT();

  return (
    <Button
      type="button"
      size="icon"
      variant="ghost"
      className="h-8 w-8 text-muted-foreground"
      disabled={!active}
      onClick={onClear}
      title={t("transactions.clearFilters")}
      aria-label={t("transactions.clearFilters")}
    >
      <RotateCcw className="h-3.5 w-3.5" />
    </Button>
  );
}

export function AmountAndDirectionFilter({
  minAmount,
  maxAmount,
  direction,
  onMinAmountChange,
  onMaxAmountChange,
  onDirectionChange,
}: Pick<
  TransactionListControlsProps,
  | "minAmount"
  | "maxAmount"
  | "direction"
  | "onMinAmountChange"
  | "onMaxAmountChange"
  | "onDirectionChange"
>) {
  const { t } = useT();
  const hasAmount = Boolean(minAmount || maxAmount);
  const active = hasAmount || direction !== "all";
  const amountLabel = hasAmount
    ? `${minAmount || "0"} - ${maxAmount || "∞"} zł`
    : "";
  const directionLabel =
    direction === "all"
      ? ""
      : t(`transactions.filterDirection.${direction}`);
  const triggerLabel =
    [amountLabel, directionLabel].filter(Boolean).join(" · ") ||
    t("transactions.filterDirection.all");

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className={cn(
            TRANSACTION_INLINE_FILTER_CONTROL_CLASS,
            "relative h-11 w-full justify-start pr-8 font-normal tabular-nums",
            active && TRANSACTION_INLINE_FILTER_ACTIVE_CLASS,
          )}
          aria-label={`${t("transactions.filterAmount")}, ${t(
            "transactions.filterDirection",
          )}`}
        >
          <span className="truncate">{triggerLabel}</span>
          <SlidersHorizontal className="absolute right-3 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 space-y-4 p-4">
        <div className="space-y-2">
          <Label>{t("transactions.filterDirection")}</Label>
          <DirectionFilterSelect
            value={direction}
            onChange={onDirectionChange}
            ariaLabel={t("transactions.filterDirection")}
            className="w-full"
          />
        </div>
        <div className="space-y-2">
          <Label>{t("transactions.filterAmount")}</Label>
          <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2">
            <Input
              type="number"
              min="0"
              step="0.01"
              inputMode="decimal"
              value={minAmount}
              onChange={(event) => onMinAmountChange(event.target.value)}
              placeholder="0,00"
              aria-label={t("transactions.filterAmountFrom")}
              className="text-right tabular-nums [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
            />
            <span className="text-sm text-muted-foreground" aria-hidden="true">
              -
            </span>
            <Input
              type="number"
              min="0"
              step="0.01"
              inputMode="decimal"
              value={maxAmount}
              onChange={(event) => onMaxAmountChange(event.target.value)}
              placeholder="∞"
              aria-label={t("transactions.filterAmountTo")}
              className="text-right tabular-nums [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
            />
          </div>
        </div>
        {active ? (
          <div className="flex justify-end">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => {
                onMinAmountChange("");
                onMaxAmountChange("");
                onDirectionChange("all");
              }}
            >
              <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
              {t("common.clear")}
            </Button>
          </div>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}

export const TRANSACTION_INLINE_FILTER_CONTROL_CLASS =
  "rounded-none border-0 bg-transparent px-3 shadow-none hover:bg-muted/30 focus-visible:bg-background/40 focus-visible:ring-0 focus-visible:ring-offset-0 focus-visible:shadow-[inset_0_-2px_0_hsl(var(--primary))]";

export const TRANSACTION_INLINE_FILTER_ACTIVE_CLASS =
  "text-foreground shadow-[inset_0_-2px_0_hsl(var(--primary))]";

function amountFilterValue(value: string): number | undefined {
  if (value.trim() === "") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined;
}
