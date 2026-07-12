"use client";

import { Button } from "@/components/ui/button";
import { ClearableInput } from "@/components/ui/clearable-input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { CategorySelect } from "@/components/category-select";
import { DateRangePicker } from "@/components/date-range-picker";
import { TransactionTypeCombobox } from "@/components/transaction-type-combobox";
import { FilterField } from "@/components/filter-panel";
import {
  api,
  type CategoryState,
  type Direction,
  type FilterSummary,
} from "@/lib/api";
import { useT } from "@/lib/i18n";
import { formatCurrency } from "@/lib/utils";
import {
  ArrowDownRight,
  ArrowUpRight,
  Download,
  RotateCcw,
  Scale,
} from "lucide-react";

interface TransactionFiltersProps {
  reviewMode: boolean;
  search: string;
  category: string;
  direction: Direction;
  transactionType: string;
  dateFrom: string;
  dateTo: string;
  importId?: number;
  minConfidence: string;
  reviewState: CategoryState;
  includeTransfers: boolean;
  suggestionCount: number;
  acceptPending: boolean;
  hasActiveFilters: boolean;
  filterSummary?: FilterSummary;
  onSearchChange: (value: string) => void;
  onCategoryChange: (value: string) => void;
  onDirectionChange: (value: Direction) => void;
  onTransactionTypeChange: (value: string) => void;
  onDateFromChange: (value: string) => void;
  onDateToChange: (value: string) => void;
  onMinConfidenceChange: (value: string) => void;
  onReviewStateChange: (value: CategoryState) => void;
  onIncludeTransfersChange: (value: boolean) => void;
  onAcceptSuggestions: () => void;
  onClearFilters: () => void;
}

export function TransactionFilters({
  reviewMode,
  search,
  category,
  direction,
  transactionType,
  dateFrom,
  dateTo,
  importId,
  minConfidence,
  reviewState,
  includeTransfers,
  suggestionCount,
  acceptPending,
  hasActiveFilters,
  filterSummary,
  onSearchChange,
  onCategoryChange,
  onDirectionChange,
  onTransactionTypeChange,
  onDateFromChange,
  onDateToChange,
  onMinConfidenceChange,
  onReviewStateChange,
  onIncludeTransfersChange,
  onAcceptSuggestions,
  onClearFilters,
}: TransactionFiltersProps) {
  const { t } = useT();
  const confidenceFilter = minConfidence ? Number(minConfidence) : undefined;
  const searchFilter = search.trim() || undefined;
  const directionFilter = direction === "all" ? undefined : direction;
  const categoryFilter = category || undefined;
  const exportHref = api.exportTransactionsUrl({
    search: searchFilter,
    direction: directionFilter,
    category: categoryFilter,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    import_id: importId,
    include_transfers: includeTransfers,
    category_state: reviewMode ? reviewState : "all",
    min_confidence: reviewMode ? confidenceFilter : undefined,
    transaction_type: transactionType || undefined,
    review_priority: reviewMode,
  });

  const clearDateRange = () => {
    onDateFromChange("");
    onDateToChange("");
  };

  return (
    <section className="space-y-3">
      <div className="overflow-hidden rounded-lg border bg-card">
        <div className="flex flex-wrap items-end gap-3 p-3">
          <FilterField
            label={t("transactions.filterSearch")}
            className="min-w-[18rem] flex-1 basis-[24rem]"
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
            className="w-[17rem] shrink-0"
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
            className="min-w-[13rem] basis-[14rem]"
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
            label={t("transactions.filterDirection")}
            className="min-w-[10rem] basis-[10rem]"
          >
            <Select
              value={direction}
              onValueChange={(v) => onDirectionChange(v as Direction)}
            >
              <SelectTrigger
                className="w-full"
                aria-label={t("transactions.filterDirection")}
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">
                  {t("transactions.filterDirection.all")}
                </SelectItem>
                <SelectItem value="debit">
                  {t("transactions.filterDirection.debit")}
                </SelectItem>
                <SelectItem value="credit">
                  {t("transactions.filterDirection.credit")}
                </SelectItem>
              </SelectContent>
            </Select>
          </FilterField>

          <FilterField
            label={t("transactions.filterType")}
            className="min-w-[13rem] basis-[14rem]"
          >
            <TransactionTypeCombobox
              value={transactionType || "all"}
              onChange={(v) => onTransactionTypeChange(v === "all" ? "" : v)}
              includeEmpty
              emptyValue="all"
              emptyLabel={t("transactions.filterType.all")}
              ariaLabel={t("transactions.filterType")}
              size="md"
            />
          </FilterField>

          <div className="ml-auto flex min-h-9 flex-wrap items-center justify-end gap-2">
            <label className="flex h-9 items-center gap-2 rounded-md px-2 text-sm text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground">
              <Checkbox
                checked={includeTransfers}
                onCheckedChange={(c) => onIncludeTransfersChange(c === true)}
              />
              {t("transactions.includeTransfers")}
            </label>
            {hasActiveFilters && (
              <Button size="sm" variant="ghost" onClick={onClearFilters}>
                <RotateCcw className="mr-2 h-4 w-4" />
                {t("transactions.clearFilters")}
              </Button>
            )}
          </div>
        </div>

        {reviewMode && (
          <div className="border-t bg-muted/20 p-3">
            <div className="flex flex-wrap items-end gap-3">
              <FilterField
                label={t("transactions.reviewQueue")}
                className="min-w-[13rem] basis-[14rem]"
              >
                <Select
                  value={reviewState}
                  onValueChange={(v) => onReviewStateChange(v as CategoryState)}
                >
                  <SelectTrigger
                    className="w-full"
                    aria-label={t("transactions.reviewQueue")}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="assignable">
                      {t("transactions.reviewQueue.assignable")}
                    </SelectItem>
                    <SelectItem value="needs_review">
                      {t("transactions.reviewQueue.needsReview")}
                    </SelectItem>
                    <SelectItem value="rejected">
                      {t("transactions.reviewQueue.rejected")}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </FilterField>

              <FilterField
                label={t("transactions.filterConfidence")}
                className="min-w-[11rem] basis-[12rem]"
              >
                <Select
                  value={minConfidence || "all"}
                  onValueChange={(v) =>
                    onMinConfidenceChange(v === "all" ? "" : v)
                  }
                >
                  <SelectTrigger
                    className="w-full"
                    aria-label={t("transactions.filterConfidence")}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">
                      {t("transactions.filterConfidence.all")}
                    </SelectItem>
                    <SelectItem value="0.55">
                      {t("transactions.filterConfidence.55")}
                    </SelectItem>
                    <SelectItem value="0.75">
                      {t("transactions.filterConfidence.75")}
                    </SelectItem>
                    <SelectItem value="0.9">
                      {t("transactions.filterConfidence.90")}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </FilterField>

              <Button
                size="sm"
                variant="outline"
                className="ml-auto"
                disabled={suggestionCount === 0 || acceptPending}
                onClick={onAcceptSuggestions}
              >
                {t("transactions.acceptSuggestions", { n: suggestionCount })}
              </Button>
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border bg-background px-3 py-2 text-sm">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          {filterSummary ? (
            <>
              <span className="font-medium text-muted-foreground">
                {t("transactions.filterSummary.count", {
                  n: filterSummary.count,
                })}
              </span>
              <span className="inline-flex items-center gap-1 text-positive">
                <ArrowUpRight className="h-3.5 w-3.5" />
                {formatCurrency(filterSummary.total_income, "PLN")}
              </span>
              <span className="inline-flex items-center gap-1 text-negative">
                <ArrowDownRight className="h-3.5 w-3.5" />
                {formatCurrency(filterSummary.total_expenses, "PLN")}
              </span>
              <span className="inline-flex items-center gap-1 font-medium">
                <Scale className="h-3.5 w-3.5" />
                <span
                  className={
                    filterSummary.net >= 0 ? "text-positive" : "text-negative"
                  }
                >
                  {filterSummary.net >= 0 ? "+" : "−"}
                  {formatCurrency(Math.abs(filterSummary.net), "PLN")}
                </span>
              </span>
            </>
          ) : (
            <span className="text-muted-foreground">
              {t("transactions.filterSummary.loading")}
            </span>
          )}
        </div>
        <Button size="sm" variant="outline" asChild>
          <a href={exportHref}>
            <Download className="mr-2 h-4 w-4" />
            {t("transactions.exportCsv")}
          </a>
        </Button>
      </div>
    </section>
  );
}
