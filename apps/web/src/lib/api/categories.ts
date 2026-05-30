import { request } from "./client";
import type { CategoryDef } from "./types";

export const categoriesApi = {
  listCategories: () => request<CategoryDef[]>("/categories"),
  createCategory: (payload: { name: string; color?: string | null; icon?: string | null }) =>
    request<CategoryDef>("/categories", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  patchCategoryDef: (id: number, payload: { color?: string | null; icon?: string | null }) =>
    request<CategoryDef>(`/categories/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteCategory: (id: number) => request<void>(`/categories/${id}`, { method: "DELETE" }),
};
