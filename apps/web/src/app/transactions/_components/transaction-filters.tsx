"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, type Direction } from "@/lib/api";
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
  includeTransfers: boolean;
  suggestionCount: number;
  acceptPending: boolean;
  onSearchChange: (value: string) => void;
  onCategoryChange: (value: string) => void;
  onDirectionChange: (value: Direction) => void;
  onTransactionTypeChange: (value: string) => void;
  onMinConfidenceChange: (value: string) => void;
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
  includeTransfers,
  suggestionCount,
  acceptPending,
  onSearchChange,
  onCategoryChange,
  onDirectionChange,
  onTransactionTypeChange,
  onMinConfidenceChange,
  onIncludeTransfersChange,
  onAcceptSuggestions,
}: TransactionFiltersProps) {
  const { t } = useT();
  const confidenceFilter = minConfidence ? Number(minConfidence) : undefined;

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
          <Input
            placeholder={t("transactions.filterCategory")}
            value={category}
            onChange={(e) => onCategoryChange(e.target.value)}
            className="max-w-xs"
          />
          <select
            value={direction}
            onChange={(e) => onDirectionChange(e.target.value as Direction)}
            className="h-9 rounded-md border border-input bg-transparent px-3 text-sm"
            aria-label={t("transactions.filterDirection")}
          >
            <option value="all">{t("transactions.filterDirection.all")}</option>
            <option value="debit">{t("transactions.filterDirection.debit")}</option>
            <option value="credit">{t("transactions.filterDirection.credit")}</option>
          </select>
          <select
            value={transactionType}
            onChange={(e) => onTransactionTypeChange(e.target.value)}
            className="h-9 rounded-md border border-input bg-transparent px-3 text-sm"
            aria-label={t("transactions.filterType")}
          >
            <option value="">{t("transactions.filterType.all")}</option>
            {TRANSACTION_TYPE_OPTIONS.map((type) => (
              <option key={type} value={type}>
                {tTransactionType(t, type)}
              </option>
            ))}
          </select>
          <select
            value={minConfidence}
            onChange={(e) => onMinConfidenceChange(e.target.value)}
            className="h-9 rounded-md border border-input bg-transparent px-3 text-sm"
            aria-label={t("transactions.filterConfidence")}
          >
            <option value="">{t("transactions.filterConfidence.all")}</option>
            <option value="0.55">{t("transactions.filterConfidence.55")}</option>
            <option value="0.75">{t("transactions.filterConfidence.75")}</option>
            <option value="0.9">{t("transactions.filterConfidence.90")}</option>
          </select>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <input
              type="checkbox"
              checked={includeTransfers}
              onChange={(e) => onIncludeTransfersChange(e.target.checked)}
              className="h-4 w-4"
            />
            {t("transactions.includeTransfers")}
          </label>
          <a
            href={api.exportTransactionsUrl({
              include_transfers: includeTransfers,
              category_state: reviewMode ? "needs_review" : "all",
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
