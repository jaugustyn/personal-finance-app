import type { CategoryState, Direction } from "@/lib/api";
import type { TransactionsView } from "@/app/transactions/_lib/constants";

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
    include_transfers?: boolean | null;
  } = {},
): string {
  const q = new URLSearchParams();
  if (params.view && params.view !== "list") q.set("view", params.view);
  const categoryState =
    params.category_state ?? (params.view === "review" ? "assignable" : null);
  if (params.search?.trim()) q.set("search", params.search.trim());
  if (params.category) q.set("category", params.category);
  if (params.direction && params.direction !== "all") {
    q.set("direction", params.direction);
  }
  if (params.transaction_type) q.set("transaction_type", params.transaction_type);
  if (categoryState && categoryState !== "all") {
    q.set("category_state", categoryState);
  }
  if (params.date_from) q.set("date_from", params.date_from);
  if (params.date_to) q.set("date_to", params.date_to);
  if (params.import_id != null) q.set("import_id", String(params.import_id));
  if (params.include_transfers === false) q.set("include_transfers", "false");
  const qs = q.toString();
  return `/transactions${qs ? `?${qs}` : ""}`;
}
