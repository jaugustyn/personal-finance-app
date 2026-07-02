import type { QueryClient } from "@tanstack/react-query";

export const MERCHANT_QUERY_KEYS = {
  aliases: ["merchantAliases"] as const,
  candidates: ["merchantAliasCandidates"] as const,
  suggestions: (query?: string) =>
    query ? (["merchantAliasSuggestions", query] as const) : (["merchantAliasSuggestions"] as const),
};

export function invalidateMerchantQueries(queryClient: QueryClient) {
  queryClient.invalidateQueries({ queryKey: MERCHANT_QUERY_KEYS.aliases });
  queryClient.invalidateQueries({ queryKey: MERCHANT_QUERY_KEYS.candidates });
  queryClient.invalidateQueries({ queryKey: MERCHANT_QUERY_KEYS.suggestions() });
  queryClient.invalidateQueries({ queryKey: ["overview"] });
  queryClient.invalidateQueries({ queryKey: ["topMerchants"] });
  queryClient.invalidateQueries({ queryKey: ["transactions"] });
  queryClient.invalidateQueries({ queryKey: ["review-summary"] });
  queryClient.invalidateQueries({ queryKey: ["review-queue"] });
  queryClient.invalidateQueries({ queryKey: ["ml"] });
  queryClient.invalidateQueries({ queryKey: ["recap"] });
  queryClient.invalidateQueries({ queryKey: ["anomalies"] });
  queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
}
