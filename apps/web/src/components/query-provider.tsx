"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { isApiError } from "@/lib/api";

function shouldRetry(failureCount: number, error: unknown) {
  if (failureCount >= 2) return false;
  if (!isApiError(error)) return error instanceof TypeError;

  return error.status === 408 || error.status === 429 || error.status >= 500;
}

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            retry: shouldRetry,
            retryDelay: (attempt, error) =>
              isApiError(error) && error.retryAfter
                ? Math.min(error.retryAfter * 1000, 30_000)
                : Math.min(1000 * 2 ** attempt, 8000),
          },
          mutations: { retry: 0 },
        },
      }),
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
