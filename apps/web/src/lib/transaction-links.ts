import type { CategoryState, Direction } from "@/lib/api";
import type { TransactionsView } from "@/app/transactions/_lib/constants";
import { buildQuery } from "@/lib/api/query";

export function transactionsHref(
  params: {
    view?: TransactionsView;
    search?: string | null;
    category?: string | null;
    direction?: Direction | null;
    transaction_type?: string | null;
    category_state?: CategoryState | null;
    date_from?: string | null;
    date_to?: string | null;
    import_id?: number | null;
    merchant_canonical_key?: string | null;
    include_transfers?: boolean | null;
  } = {},
): string {
  const categoryState =
    params.category_state ?? (params.view === "review" ? "assignable" : null);
  const qs = buildQuery({
    view: params.view && params.view !== "list" ? params.view : undefined,
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
    merchant_canonical_key: params.merchant_canonical_key,
    include_transfers: params.include_transfers === false ? false : undefined,
  });
  return `/transactions${qs ? `?${qs}` : ""}`;
}
