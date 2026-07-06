"use client";

import { useMemo, useState } from "react";
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  FileSpreadsheet,
  HelpCircle,
  Loader2,
  Upload,
} from "lucide-react";
import type { ImportPreview, ImportSummary } from "@/lib/api";
import { useT, type TranslationKey } from "@/lib/i18n";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ImportQualityPanel } from "./import-quality-panel";
import { SuccessBox } from "./success-box";
import {
  buildCustomWarnings,
  fieldHintKey,
  fieldSpecsFromPreview,
  type FieldKey,
} from "../_lib/import-fields";

export function ImportPreviewDialog({
  open,
  onOpenChange,
  file,
  preview,
  mapping,
  skipCategories,
  previewPending,
  previewError,
  qualityPending,
  qualityError,
  uploadPending,
  uploadError,
  uploadData,
  canCommit,
  onMappingChange,
  onSkipCategoriesChange,
  onCommit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  file: File | null;
  preview: ImportPreview | null;
  mapping: Record<FieldKey, string>;
  skipCategories: boolean;
  previewPending: boolean;
  previewError: unknown;
  qualityPending: boolean;
  qualityError: unknown;
  uploadPending: boolean;
  uploadError: unknown;
  uploadData: ImportSummary | undefined;
  canCommit: boolean;
  onMappingChange: (key: FieldKey, value: string) => void;
  onSkipCategoriesChange: (checked: boolean) => void;
  onCommit: () => void;
}) {
  const { t } = useT();
  const customWarnings = preview ? buildCustomWarnings(mapping, t) : [];
  const busy = previewPending || qualityPending || uploadPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[92vh] w-[calc(100vw-1.5rem)] max-w-7xl flex-col gap-0 overflow-hidden p-0">
        <DialogHeader className="shrink-0 border-b px-6 py-4">
          <DialogTitle className="flex items-center gap-2 text-base">
            <FileSpreadsheet className="h-4 w-4" />
            {t("imports.preview")}
          </DialogTitle>
          <DialogDescription className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span>{file?.name ?? t("imports.title")}</span>
            {preview ? (
              <>
                <span>{preview.encoding}</span>
                <span>&quot;{preview.delimiter}&quot;</span>
                <span>
                  {t("imports.previewRows", {
                    shown: preview.sample_rows.length,
                    total: preview.quality_report.total_rows,
                  })}
                </span>
              </>
            ) : null}
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          {previewPending ? (
            <div className="flex min-h-48 items-center justify-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              {t("common.loading")}
            </div>
          ) : null}

          {previewError ? <InlineError message={(previewError as Error).message} /> : null}

          {preview ? (
            <div className="space-y-5">
              <div
                className={
                  preview.detected_source
                    ? "grid gap-5"
                    : "grid gap-5 lg:grid-cols-[minmax(340px,420px)_1fr]"
                }
              >
                <div className="space-y-4">
                  <ImportSummaryHeader preview={preview} />
                  <ImportQualityPanel report={preview.quality_report} />
                </div>
                {!preview.detected_source ? (
                  <ColumnMappingPanel
                    preview={preview}
                    mapping={mapping}
                    customWarnings={customWarnings}
                    qualityPending={qualityPending}
                    qualityError={qualityError}
                    onMappingChange={onMappingChange}
                  />
                ) : null}
              </div>
              <PreviewRowsTable preview={preview} />
            </div>
          ) : null}

          {uploadError ? (
            <div className="mt-4">
              <InlineError
                message={`${t("imports.error")}: ${(uploadError as Error).message}`}
              />
            </div>
          ) : null}

          {uploadData ? (
            <div className="mt-4">
              <SuccessBox summary={uploadData} />
            </div>
          ) : null}
        </div>

        <DialogFooter className="grid shrink-0 gap-3 border-t bg-muted/20 px-6 py-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
          <label className="flex min-w-0 cursor-pointer select-none items-start gap-2.5 text-sm text-muted-foreground transition-colors hover:text-foreground">
            <Checkbox
              id="skip-categories-checkbox"
              checked={skipCategories}
              onCheckedChange={(checked) => onSkipCategoriesChange(checked === true)}
              disabled={busy}
              className="mt-1"
            />
            <span className="grid min-w-0 gap-1">
              <span className="text-sm font-semibold leading-none text-foreground">
                {t("imports.skipCategories")}
              </span>
              <span className="max-h-9 overflow-hidden text-xs leading-snug text-muted-foreground">
                {t("imports.skipCategoriesHelp")}
              </span>
            </span>
          </label>

          <Button onClick={onCommit} disabled={!canCommit} className="min-w-32 sm:justify-self-end">
            {busy ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Upload className="mr-2 h-4 w-4" />
            )}
            {t("imports.upload")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ImportSummaryHeader({ preview }: { preview: ImportPreview }) {
  const { t } = useT();
  return (
    <div className="rounded-md border bg-muted/20 p-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {preview.detected_source ? (
          <>
            <span className="text-muted-foreground">{t("imports.detectedSource")}:</span>
            <Badge>{preview.detected_source}</Badge>
          </>
        ) : (
          <span className="text-muted-foreground">{t("imports.detectedNone")}</span>
        )}
      </div>
    </div>
  );
}

function ColumnMappingPanel({
  preview,
  mapping,
  customWarnings,
  qualityPending,
  qualityError,
  onMappingChange,
}: {
  preview: ImportPreview;
  mapping: Record<FieldKey, string>;
  customWarnings: string[];
  qualityPending: boolean;
  qualityError: unknown;
  onMappingChange: (key: FieldKey, value: string) => void;
}) {
  const { t } = useT();
  return (
    <div className="space-y-3 rounded-md border p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">{t("imports.columnMap.title")}</h3>
          <p className="text-xs text-muted-foreground">{t("imports.columnMap.help")}</p>
        </div>
        {qualityPending ? (
          <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
        ) : null}
      </div>

      <TooltipProvider delayDuration={150}>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {fieldSpecsFromPreview(preview).map((spec) => {
            const { key, required, recommended } = spec;
            const labelKey: TranslationKey = `imports.field.${key}` as TranslationKey;
            const hint = t(fieldHintKey(key));
            return (
              <label key={key} className="grid gap-1 text-sm">
                <span className="flex items-center gap-1.5 font-medium">
                  <span>
                    {t(labelKey)}
                    {required ? (
                      <span className="text-destructive" aria-label={t("imports.required")}>
                        {" "}
                        *
                      </span>
                    ) : null}
                  </span>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <HelpCircle className="h-3.5 w-3.5 cursor-help text-muted-foreground" />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-64">
                      <p>{hint}</p>
                      {!required && recommended ? (
                        <p className="mt-1 text-muted-foreground">
                          {t("imports.recommended")}
                        </p>
                      ) : null}
                    </TooltipContent>
                  </Tooltip>
                </span>
                <Select
                  value={mapping[key] || "none"}
                  onValueChange={(value) => onMappingChange(key, value)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">{t("imports.fieldNone")}</SelectItem>
                    {preview.headers.map((header) => (
                      <SelectItem key={header} value={header}>
                        {header}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </label>
            );
          })}
        </div>
      </TooltipProvider>

      {customWarnings.length > 0 ? (
        <div className="space-y-1 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-800 dark:text-amber-300">
          {customWarnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </div>
      ) : null}

      {qualityError ? <InlineError message={(qualityError as Error).message} /> : null}
    </div>
  );
}

function PreviewRowsTable({ preview }: { preview: ImportPreview }) {
  const { t } = useT();
  const pageSize = 10;
  const [page, setPage] = useState(1);
  const pageCount = Math.max(1, Math.ceil(preview.sample_rows.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const visibleRows = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return preview.sample_rows.slice(start, start + pageSize);
  }, [currentPage, preview.sample_rows]);

  return (
    <section className="min-w-0 space-y-3 rounded-md border p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-semibold">{t("imports.rowsPreview.title")}</h3>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="h-7 w-7"
            disabled={currentPage <= 1}
            onClick={() => setPage((value) => Math.max(1, value - 1))}
            aria-label={t("common.previous")}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="min-w-20 text-center tabular-nums">
            {t("imports.rowsPreview.page", {
              page: currentPage,
              pages: pageCount,
            })}
          </span>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="h-7 w-7"
            disabled={currentPage >= pageCount}
            onClick={() => setPage((value) => Math.min(pageCount, value + 1))}
            aria-label={t("common.next")}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <div className="max-h-[56vh] overflow-x-scroll overflow-y-auto rounded-md border">
        <table className="min-w-full caption-bottom text-sm">
          <thead className="sticky top-0 z-10 bg-background shadow-sm">
            <tr className="border-b">
              {preview.headers.map((header) => (
                <th
                  key={header}
                  className="h-10 whitespace-nowrap px-3 text-left align-middle font-medium text-muted-foreground"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, index) => (
              <tr
                key={`${currentPage}:${index}`}
                className="border-b transition-colors last:border-0 hover:bg-muted/50"
              >
                {preview.headers.map((header) => (
                  <td
                    key={header}
                    className="max-w-64 whitespace-nowrap p-3 align-middle text-xs"
                    title={row[header] ?? ""}
                  >
                    <span className="block truncate">{row[header] ?? ""}</span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function InlineError({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
      <AlertCircle className="h-4 w-4 shrink-0" />
      <span>{message}</span>
    </div>
  );
}
