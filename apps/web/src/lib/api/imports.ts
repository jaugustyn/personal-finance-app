import { request, requestMultipart } from "./client";
import type { ImportHistoryRow, ImportPreview, ImportSummary } from "./types";

export const importsApi = {
  listImports: () => request<ImportHistoryRow[]>("/imports"),
  deleteImport: (id: number) =>
    request<{ deleted_transactions: number; import_id: number }>(`/imports/${id}`, {
      method: "DELETE",
    }),
  previewImport: (
    file: File,
    opts: {
      source?: string | null;
      columnMap?: Record<string, string> | null;
      fxMode?: "require_existing" | "prefetch_missing";
    } = {},
  ) => {
    const fd = new FormData();
    fd.append("file", file);
    if (opts.source) fd.append("source", opts.source);
    if (opts.columnMap) fd.append("column_map", JSON.stringify(opts.columnMap));
    if (opts.fxMode) fd.append("fx_mode", opts.fxMode);
    return requestMultipart<ImportPreview>("/imports/preview", fd);
  },
  uploadImport: (
    file: File,
    opts: {
      source?: string | null;
      columnMap?: Record<string, string> | null;
      skipCategories?: boolean;
    } = {},
  ) => {
    const fd = new FormData();
    fd.append("file", file);
    if (opts.source) fd.append("source", opts.source);
    if (opts.columnMap) fd.append("column_map", JSON.stringify(opts.columnMap));
    if (opts.skipCategories !== undefined) {
      fd.append("skip_categories", String(opts.skipCategories));
    }
    return requestMultipart<ImportSummary>("/imports", fd);
  },
};
