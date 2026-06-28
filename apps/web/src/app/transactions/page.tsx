/* eslint-disable react-hooks/set-state-in-effect */
"use client";

import { useEffect, useState } from "react";
import { useT } from "@/lib/i18n";
import type { CategoryState, Direction } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { useLocalStorageState } from "@/hooks/use-local-storage-state";
import { GroupsView } from "./_components/groups-view";
import { ListView, type TransactionInitialFilters } from "./_components/list-view";
import { ViewSwitcher } from "./_components/view-switcher";
import type { TransactionsView } from "./_lib/constants";

export default function TransactionsPage() {
  const { t } = useT();
  const [view, setView] = useLocalStorageState<TransactionsView>(
    "finance.transactions.view",
    "list",
  );
  const [initialFilters, setInitialFilters] =
    useState<TransactionInitialFilters>({ key: "" });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlView = parseView(params.get("view"));
    if (urlView) setView(urlView);
    else if (hasTransactionFilterParams(params)) setView("list");
    setInitialFilters({
      key: window.location.search,
      search: valueOrUndefined(params.get("search")),
      category: valueOrUndefined(params.get("category")),
      direction: parseDirection(params.get("direction")),
      transactionType: valueOrUndefined(params.get("transaction_type")),
      dateFrom: valueOrUndefined(params.get("date_from")),
      dateTo: valueOrUndefined(params.get("date_to")),
      importId: parseNumber(params.get("import_id")),
      reviewState:
        parseReviewState(params.get("category_state")) ??
        (urlView === "review" ? "assignable" : undefined),
      includeTransfers: parseIncludeTransfers(params.get("include_transfers")),
    });
  }, [setView]);

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("transactions.title")}
        actions={<ViewSwitcher value={view} onChange={setView} />}
      />

      {view === "groups" ? (
        <GroupsView />
      ) : (
        <ListView
          key={`${view}:${initialFilters.key}`}
          reviewMode={view === "review"}
          initialFilters={initialFilters}
        />
      )}
    </div>
  );
}

function valueOrUndefined(value: string | null): string | undefined {
  return value ?? undefined;
}

function parseView(value: string | null): TransactionsView | null {
  return value === "review" || value === "groups" || value === "list"
    ? value
    : null;
}

function hasTransactionFilterParams(params: URLSearchParams): boolean {
  return [
    "search",
    "category",
    "direction",
    "transaction_type",
    "date_from",
    "date_to",
    "import_id",
    "category_state",
    "include_transfers",
  ].some((key) => params.has(key));
}

function parseDirection(value: string | null): Direction | undefined {
  return value === "debit" || value === "credit" || value === "all"
    ? value
    : undefined;
}

function parseReviewState(value: string | null): CategoryState | undefined {
  return value === "all" ||
    value === "categorized" ||
    value === "uncategorized" ||
    value === "suggested" ||
    value === "assignable" ||
    value === "needs_review" ||
    value === "rejected"
    ? value
    : undefined;
}

function parseIncludeTransfers(value: string | null): boolean | undefined {
  if (value === "false") return false;
  if (value === "true") return true;
  return undefined;
}

function parseNumber(value: string | null): number | undefined {
  if (!value) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}
