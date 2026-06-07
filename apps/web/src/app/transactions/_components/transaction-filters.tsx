"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import { api, type CategoryState, type Direction } from "@/lib/api";
import { tTransactionType, useT } from "@/lib/i18n";
import { Download } from "lucide-react";
import { TRANSACTION_TYPE_OPTIONS } from "../_lib/constants";

interface TransactionFiltersProps {
  reviewMode: boolean;
  search: string;
  category: string;
  direction: Direction;
  transactionType: string;
  minConfidence: string;
  reviewState: CategoryState;
  includeTransfers: boolean;
  suggestionCount: number;
  acceptPending: boolean;
  onSearchChange: (value: string) => void;
  onCategoryChange: (value: string) => void;
  onDirectionChange: (value: Direction) => void;
  onTransactionTypeChange: (value: string) => void;
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
  minConfidence,
  reviewState,
  includeTransfers,
  suggestionCount,
  acceptPending,
  onSearchChange,
  onCategoryChange,
  onDirectionChange,
  onTransactionTypeChange,
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
    <Card>
      <CardContent className="pt-6">
        <div className="flex flex-wrap items-center gap-3">
          <Input
            placeholder={t("transactions.search")}
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="max-w-xs"
          />
          {reviewMode && (
            <Select
              value={reviewState}
              onValueChange={(v) => onReviewStateChange(v as CategoryState)}
            >
              <SelectTrigger
                className="w-auto min-w-40"
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
          )}
          <CategorySelect
            value={category}
            onChange={onCategoryChange}
            allLabel={t("transactions.filterCategoryAll")}
            ariaLabel={t("transactions.filterCategory")}
          />
          <Select
            value={direction}
            onValueChange={(v) => onDirectionChange(v as Direction)}
          >
            <SelectTrigger
              className="w-auto min-w-36"
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
          <Select
            value={transactionType || "all"}
            onValueChange={(v) => onTransactionTypeChange(v === "all" ? "" : v)}
          >
            <SelectTrigger
              className="w-auto min-w-36"
              aria-label={t("transactions.filterType")}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">
                {t("transactions.filterType.all")}
              </SelectItem>
              {TRANSACTION_TYPE_OPTIONS.map((type) => (
                <SelectItem key={type} value={type}>
                  {tTransactionType(t, type)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={minConfidence || "all"}
            onValueChange={(v) => onMinConfidenceChange(v === "all" ? "" : v)}
          >
            <SelectTrigger
              className="w-auto min-w-36"
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
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <Checkbox
              checked={includeTransfers}
              onCheckedChange={(c) => onIncludeTransfersChange(c === true)}
            />
            {t("transactions.includeTransfers")}
          </label>
          <a
            href={api.exportTransactionsUrl({
              search: searchFilter,
              direction: directionFilter,
              category: categoryFilter,
              include_transfers: includeTransfers,
              category_state: reviewMode ? reviewState : "all",
              min_confidence: confidenceFilter,
              transaction_type: transactionType || undefined,
              review_priority: reviewMode,
            })}
            className="ml-auto"
          >
            <Button size="sm" variant="outline" asChild={false}>
              <Download className="mr-2 h-4 w-4" />
              {t("transactions.exportCsv")}
            </Button>
          </a>
          <Button
            size="sm"
            variant="outline"
            disabled={suggestionCount === 0 || acceptPending}
            onClick={onAcceptSuggestions}
          >
            {t("transactions.acceptSuggestions", { n: suggestionCount })}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
