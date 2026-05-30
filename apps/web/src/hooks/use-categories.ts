"use client";

import { useQuery } from "@tanstack/react-query";
import { api, type CategoryDef } from "@/lib/api";

/** Shared cache key — invalidated whenever a category is added/removed. */
export const CATEGORIES_QUERY_KEY = ["categories"] as const;

export function useCategories() {
  return useQuery<CategoryDef[]>({
    queryKey: CATEGORIES_QUERY_KEY,
    queryFn: () => api.listCategories(),
    staleTime: 60_000,
  });
}
