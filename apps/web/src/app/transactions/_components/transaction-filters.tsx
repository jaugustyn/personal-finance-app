"use client";

import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ClearableInput } from "@/components/ui/clearable-input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { CategorySelect } from "@/components/category-select";
import { DateRangePicker } from "@/components/date-range-picker";
import { DirectionFilterSelect } from "@/components/direction-filter-select";
import { TransactionTypeFilterSelect } from "@/components/transaction-type-filter-select";
import { FilterSelect } from "@/components/filter-select";
import { FilterField } from "@/components/filter-panel";
import {
  api,
  type CategoryState,
  type Direction,
  type FilterSummary,
} from "@/lib/api";
import { useT } from "@/lib/i18n";
import { cn, formatCurrency } from "@/lib/utils";
import { Download, RotateCcw } from "lucide-react";

interface TransactionFiltersProps {
  reviewMode: boolean;
  search: string;
  category: string;
  minAmount: string;
  maxAmount: string;
  direction: Direction;
  transactionType: string;
  dateFrom: string;
  dateTo: string;
  importId?: number;
  reviewState: CategoryState;
  includeTransfers: boolean;
  hasActiveFilters: boolean;
  filterSummary?: FilterSummary;
  onSearchChange: (value: string) => void;
  onCategoryChange: (value: string) => void;
  onMinAmountChange: (value: string) => void;
  onMaxAmountChange: (value: string) => void;
  onDirectionChange: (value: Direction) => void;
  onTransactionTypeChange: (value: string) => void;
  onDateFromChange: (value: string) => void;
  onDateToChange: (value: string) => void;
  onImportIdChange: (value: number | undefined) => void;
  onReviewStateChange: (value: CategoryState) => void;
  onIncludeTransfersChange: (value: boolean) => void;
  onClearFilters: () => void;
}

export function TransactionFilters({
  reviewMode,
  search,
  category,
  minAmount,
  maxAmount,
  direction,
  transactionType,
  dateFrom,
  dateTo,
  importId,
  reviewState,
  includeTransfers,
  hasActiveFilters,
  filterSummary,
  onSearchChange,
  onCategoryChange,
  onMinAmountChange,
  onMaxAmountChange,
  onDirectionChange,
  onTransactionTypeChange,
  onDateFromChange,
  onDateToChange,
  onImportIdChange,
  onReviewStateChange,
  onIncludeTransfersChange,
  onClearFilters,
}: TransactionFiltersProps) {
  const { t } = useT();
  const importsQuery = useQuery({
    queryKey: ["imports", "history"],
    queryFn: api.listImports,
    enabled: !reviewMode && importId !== undefined,
  });
  const activeImport = importsQuery.data?.find((row) => row.id === importId);
  const minAmountFilter = amountFilterValue(minAmount);
  const maxAmountFilter = amountFilterValue(maxAmount);
  const searchFilter = search.trim() || undefined;
  const directionFilter = direction === "all" ? undefined : direction;
  const categoryFilter = category || undefined;
  const exportHref = api.exportTransactionsUrl({
    search: searchFilter,
    direction: directionFilter,
    category: categoryFilter,
    min_amount: minAmountFilter,
    max_amount: maxAmountFilter,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    import_id: importId,
    include_transfers: includeTransfers,
    category_state: reviewMode ? reviewState : "all",
    transaction_type: transactionType || undefined,
    review_priority: reviewMode,
  });

  const clearDateRange = () => {
    onDateFromChange("");
    onDateToChange("");
  };

  if (reviewMode) {
    return (
      <section>
        <div className="overflow-hidden rounded-lg border bg-card shadow-sm">
          <div className="flex flex-wrap items-end gap-3 p-3">
            <FilterField
              label={t("transactions.filterSearch")}
              className="w-full sm:w-[26rem]"
            >
              <ClearableInput
                placeholder={t("transactions.search")}
                value={search}
                onValueChange={onSearchChange}
                clearLabel={t("common.clear")}
                className="w-full"
              />
            </FilterField>

            <FilterField
              label={t("transactions.filterSuggestedCategory")}
              className="w-[14rem] shrink-0"
            >
              <CategorySelect
                value={category}
                onChange={onCategoryChange}
                allLabel={t("transactions.filterSuggestedCategoryAll")}
                ariaLabel={t("transactions.filterSuggestedCategory")}
                className="w-full"
              />
            </FilterField>

            <FilterField
              label={t("transactions.reviewQueue")}
              className="w-[12rem] shrink-0"
            >
              <FilterSelect
                value={reviewState}
                onValueChange={(value) =>
                  onReviewStateChange(value as CategoryState)
                }
                ariaLabel={t("transactions.reviewQueue")}
                options={[
                  {
                    value: "needs_review",
                    label: t("transactions.reviewQueue.needsReview"),
                  },
                  {
                    value: "rejected",
                    label: t("transactions.reviewQueue.rejected"),
                  },
                ]}
              />
            </FilterField>

            {hasActiveFilters ? (
              <div className="ml-auto flex min-h-9 items-center">
                <Button size="sm" variant="ghost" onClick={onClearFilters}>
                  <RotateCcw className="mr-2 h-4 w-4" />
                  {t("transactions.clearFilters")}
                </Button>
              </div>
            ) : null}
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="space-y-3">
      <div className="overflow-hidden rounded-lg border bg-card shadow-sm">
        <div className="flex flex-wrap items-end gap-3 p-3">
          <FilterField
            label={t("transactions.filterSearch")}
            className="w-full sm:w-[26rem]"
          >
            <ClearableInput
              placeholder={t("transactions.search")}
              value={search}
              onValueChange={onSearchChange}
              clearLabel={t("common.clear")}
              className="w-full"
            />
          </FilterField>

          <FilterField
            label={t("transactions.filterDateRange")}
            className="w-[16rem] shrink-0"
          >
            <DateRangePicker
              from={dateFrom}
              to={dateTo}
              onFromChange={onDateFromChange}
              onToChange={onDateToChange}
              onClear={clearDateRange}
              ariaLabel={t("transactions.filterDateRange")}
            />
          </FilterField>

          <FilterField
            label={t("transactions.filterCategory")}
            className="w-[13.5rem] shrink-0"
          >
            <CategorySelect
              value={category}
              onChange={onCategoryChange}
              allLabel={t("transactions.filterCategoryAll")}
              ariaLabel={t("transactions.filterCategory")}
              className="w-full"
            />
          </FilterField>

          <FilterField
            label={t("transactions.filterAmount")}
            className="min-w-[14rem] basis-[15rem]"
          >
            <div className="grid grid-cols-2 gap-2">
              <Input
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                value={minAmount}
                onChange={(event) => onMinAmountChange(event.target.value)}
                placeholder={t("transactions.filterAmountFrom")}
                aria-label={t("transactions.filterAmountFrom")}
              />
              <Input
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                value={maxAmount}
                onChange={(event) => onMaxAmountChange(event.target.value)}
                placeholder={t("transactions.filterAmountTo")}
                aria-label={t("transactions.filterAmountTo")}
              />
            </div>
          </FilterField>

          <FilterField
            label={t("transactions.filterDirection")}
            className="min-w-[10rem] basis-[10rem]"
          >
            <DirectionFilterSelect
              value={direction}
              onChange={onDirectionChange}
              ariaLabel={t("transactions.filterDirection")}
            />
          </FilterField>

          <FilterField
            label={t("transactions.filterType")}
            className="min-w-[13rem] basis-[14rem]"
          >
            <TransactionTypeFilterSelect
              value={transactionType}
              onChange={onTransactionTypeChange}
              allLabel={t("transactions.filterType.all")}
              ariaLabel={t("transactions.filterType")}
            />
          </FilterField>

          <FilterField
            label={t("transactions.includeTransfers")}
            className="shrink-0"
          >
            <div className="flex h-9 items-center px-1">
              <Switch
                checked={includeTransfers}
                onCheckedChange={onIncludeTransfersChange}
                aria-label={t("transactions.includeTransfers")}
              />
            </div>
          </FilterField>

          {importId !== undefined ? (
            <FilterField
              label={t("transactions.filterImport")}
              className="min-w-[15rem] basis-[18rem]"
            >
              <Select
                value={String(importId)}
                onValueChange={(value) =>
                  onImportIdChange(value === "all" ? undefined : Number(value))
                }
              >
                <SelectTrigger
                  className="w-full"
                  aria-label={t("transactions.filterImport")}
                >
                  <SelectValue>
                    {activeImport
                      ? `${activeImport.filename} · ${activeImport.source}`
                      : t("transactions.filterImportNumber", { id: importId })}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all" indicatorPosition="right">
                    {t("transactions.filterImportAll")}
                  </SelectItem>
                  {(importsQuery.data ?? []).map((row) => (
                    <SelectItem
                      key={row.id}
                      value={String(row.id)}
                      indicatorPosition="right"
                    >
                      {row.filename} · {row.source}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FilterField>
          ) : null}

          <div className="ml-auto flex min-h-9 flex-wrap items-center justify-end gap-2">
            {hasActiveFilters && (
              <Button size="sm" variant="ghost" onClick={onClearFilters}>
                <RotateCcw className="mr-2 h-4 w-4" />
                {t("transactions.clearFilters")}
              </Button>
            )}
          </div>
        </div>

        <div className="flex min-h-[3.25rem] flex-wrap items-center justify-between gap-3 border-t px-3 py-2.5 text-sm">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 tabular-nums">
            {filterSummary ? (
              <>
                <SummaryValue
                  label={t("transactions.filterSummary.results")}
                  value={String(filterSummary.count)}
                />
                <SummaryValue
                  label={t("transactions.filterSummary.income")}
                  value={formatCurrency(filterSummary.total_income, "PLN")}
                  valueClassName="text-positive"
                />
                <SummaryValue
                  label={t("transactions.filterSummary.outflow")}
                  value={formatCurrency(filterSummary.total_expenses, "PLN")}
                  valueClassName="text-negative"
                />
                <SummaryValue
                  label={t("transactions.filterSummary.balance")}
                  value={`${filterSummary.net >= 0 ? "+" : "−"}${formatCurrency(
                    Math.abs(filterSummary.net),
                    "PLN",
                  )}`}
                  valueClassName={
                    filterSummary.net >= 0 ? "text-positive" : "text-negative"
                  }
                />
                {filterSummary.unconverted_count > 0 ? (
                  <SummaryValue
                    label={t("transactions.filterSummary.unconverted")}
                    value={String(filterSummary.unconverted_count)}
                    valueClassName="text-warning"
                  />
                ) : null}
              </>
            ) : (
              <span className="text-muted-foreground">
                {t("transactions.filterSummary.loading")}
              </span>
            )}
          </div>
          <Button size="sm" variant="outline" asChild>
            <a href={exportHref} title={t("transactions.exportCsvHint")}>
              <Download className="mr-2 h-4 w-4" />
              {t("transactions.exportCsv")}
            </a>
          </Button>
        </div>
      </div>
    </section>
  );
}

function SummaryValue({
  label,
  value,
  valueClassName,
}: {
  label: string;
  value: string;
  valueClassName?: string;
}) {
  return (
    <span className="inline-flex items-baseline gap-1.5 whitespace-nowrap">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("font-medium text-foreground", valueClassName)}>
        {value}
      </span>
    </span>
  );
}

function amountFilterValue(value: string): number | undefined {
  if (value.trim() === "") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined;
}
