export const SUBSCRIPTION_QUERY_KEYS = {
  list: (includeRejected: boolean) => ["subscriptions", includeRejected] as const,
  allLists: ["subscriptions"] as const,
  overview: ["subscriptions-overview"] as const,
  fixedCharges: ["fixed-charges"] as const,
  fixedChargeTransactions: (chargeId: number | null) =>
    ["fixed-charge-transactions", chargeId] as const,
};
