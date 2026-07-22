"use client";

import { useQuery } from "@tanstack/react-query";
import { api, type CategoryDef } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

export function useCategories() {
  return useQuery<CategoryDef[]>({
    queryKey: queryKeys.categories.list,
    queryFn: () => api.listCategories(),
    staleTime: 60_000,
  });
}
