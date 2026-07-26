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
      accountId?: number | null;
    } = {},
  ) => {
    const fd = new FormData();
    fd.append("file", file);
    if (opts.source) fd.append("source", opts.source);
    if (opts.columnMap) fd.append("column_map", JSON.stringify(opts.columnMap));
    if (opts.fxMode) fd.append("fx_mode", opts.fxMode);
    if (opts.accountId) fd.append("account_id", String(opts.accountId));
    return requestMultipart<ImportPreview>("/imports/preview", fd);
  },
  uploadImport: (
    file: File,
    opts: {
      source?: string | null;
      columnMap?: Record<string, string> | null;
      skipCategories?: boolean;
      accountId: number;
    },
  ) => {
    const fd = new FormData();
    fd.append("file", file);
    if (opts.source) fd.append("source", opts.source);
    if (opts.columnMap) fd.append("column_map", JSON.stringify(opts.columnMap));
    if (opts.skipCategories !== undefined) {
      fd.append("skip_categories", String(opts.skipCategories));
    }
    fd.append("account_id", String(opts.accountId));
    return requestMultipart<ImportSummary>("/imports", fd);
  },
  changeImportAccount: (id: number, accountId: number) =>
    request<ImportHistoryRow>(`/imports/${id}/account`, {
      method: "PATCH",
      body: JSON.stringify({ account_id: accountId }),
    }),
};
