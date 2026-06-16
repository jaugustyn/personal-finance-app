"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { CategorySelect } from "@/components/category-select";
import { TransactionTypeCombobox } from "@/components/transaction-type-combobox";
import { FilterField, FilterPanel } from "@/components/filter-panel";
import { api, type CategoryState, type Direction } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { Download } from "lucide-react";

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
}: TransactionFiltersProps) {
  const { t } = useT();
  const confidenceFilter = minConfidence ? Number(minConfidence) : undefined;
  const searchFilter = search.trim() || undefined;
  const directionFilter = direction === "all" ? undefined : direction;
  const categoryFilter = category || undefined;

  return (
    <FilterPanel
      hint={reviewMode ? t("transactions.reviewHint") : undefined}
      actions={
        <>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <Checkbox
              checked={includeTransfers}
              onCheckedChange={(c) => onIncludeTransfersChange(c === true)}
            />
            {t("transactions.includeTransfers")}
          </label>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <Button size="sm" variant="outline" asChild>
              <a
                href={api.exportTransactionsUrl({
                  search: searchFilter,
                  direction: directionFilter,
                  category: categoryFilter,
                  date_from: dateFrom || undefined,
                  date_to: dateTo || undefined,
                  import_id: importId,
                  include_transfers: includeTransfers,
                  category_state: reviewMode ? reviewState : "all",
                  min_confidence: confidenceFilter,
                  transaction_type: transactionType || undefined,
                  review_priority: reviewMode,
                })}
              >
                <Download className="mr-2 h-4 w-4" />
                {t("transactions.exportCsv")}
              </a>
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={suggestionCount === 0 || acceptPending}
              onClick={onAcceptSuggestions}
            >
              {t("transactions.acceptSuggestions", { n: suggestionCount })}
            </Button>
          </div>
        </>
      }
    >
      <FilterField
        label={t("transactions.filterSearch")}
        className="md:col-span-2 xl:col-span-2"
      >
        <Input
          placeholder={t("transactions.search")}
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-full"
        />
      </FilterField>
      {reviewMode && (
        <FilterField label={t("transactions.reviewQueue")}>
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
              <SelectItem value="needs_review">
                {t("transactions.reviewQueue.needsReview")}
              </SelectItem>
              <SelectItem value="rejected">
                {t("transactions.reviewQueue.rejected")}
              </SelectItem>
            </SelectContent>
          </Select>
        </FilterField>
      )}
      <FilterField label={t("transactions.filterDateRange")} className="md:col-span-2">
        <div className="grid grid-cols-2 gap-2">
          <Input
            type="date"
            value={dateFrom}
            onChange={(e) => onDateFromChange(e.target.value)}
            aria-label={t("transactions.filterDateFrom")}
          />
          <Input
            type="date"
            value={dateTo}
            onChange={(e) => onDateToChange(e.target.value)}
            aria-label={t("transactions.filterDateTo")}
          />
        </div>
      </FilterField>
      <FilterField label={t("transactions.filterCategory")}>
        <CategorySelect
          value={category}
          onChange={onCategoryChange}
          allLabel={t("transactions.filterCategoryAll")}
          ariaLabel={t("transactions.filterCategory")}
          className="w-full"
        />
      </FilterField>
      <FilterField label={t("transactions.filterDirection")}>
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
      <FilterField label={t("transactions.filterType")}>
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
      {reviewMode && (
        <FilterField label={t("transactions.filterConfidence")}>
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
      )}
    </FilterPanel>
  );
}
