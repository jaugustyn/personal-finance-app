import type { CategoryState, Direction } from "@/lib/api";
import type {
  TransactionsSubject,
  TransactionsView,
} from "@/app/transactions/_lib/constants";
import { buildQuery } from "@/lib/api/query";

export function transactionsHref(
  params: {
    view?: TransactionsView;
    subject?: TransactionsSubject;
    search?: string | null;
    category?: string | null;
    direction?: Direction | null;
    transaction_type?: string | null;
    category_state?: CategoryState | null;
    date_from?: string | null;
    date_to?: string | null;
    import_id?: number | null;
    account_id?: number | null;
    include_transfers?: boolean | null;
  } = {},
): string {
  const categoryState =
    params.category_state ??
    (params.view === "review" && params.subject !== "transaction_type"
      ? "assignable"
      : null);
  const qs = buildQuery({
    view: params.view && params.view !== "list" ? params.view : undefined,
    subject: params.subject,
    search: params.search?.trim(),
    category: params.category,
    direction:
      params.direction && params.direction !== "all" ? params.direction : undefined,
    transaction_type: params.transaction_type,
    category_state:
      categoryState && categoryState !== "all" ? categoryState : undefined,
    date_from: params.date_from,
    date_to: params.date_to,
    import_id: params.import_id,
    account_id: params.account_id,
    include_transfers: params.include_transfers === false ? false : undefined,
  });
  return `/transactions${qs ? `?${qs}` : ""}`;
}
