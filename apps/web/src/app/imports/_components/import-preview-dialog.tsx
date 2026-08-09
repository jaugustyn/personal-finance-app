"use client";

import { type ReactNode, useState } from "react";
import {
  AlertCircle,
  ChevronDown,
  Loader2,
  Upload,
} from "lucide-react";
import type { ImportPreview } from "@/lib/api";
import { AccountSelect } from "@/components/account-select";
import { useT, type TranslationKey } from "@/lib/i18n";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { TablePagination } from "@/components/table-pagination";
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
import {
  buildCustomWarnings,
  fieldHintKey,
  fieldSpecsFromPreview,
  LOGICAL_FIELDS,
  type FieldKey,
} from "../_lib/import-fields";

export function ImportPreviewDialog({
  open,
  onOpenChange,
  file,
  preview,
  mapping,
  accountId,
  skipCategories,
  previewPending,
  previewError,
  qualityPending,
  qualityError,
  uploadPending,
  uploadError,
  canCommit,
  onMappingChange,
  onAccountChange,
  onSkipCategoriesChange,
  onCommit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  file: File | null;
  preview: ImportPreview | null;
  mapping: Record<FieldKey, string>;
  accountId: number | null;
  skipCategories: boolean;
  previewPending: boolean;
  previewError: unknown;
  qualityPending: boolean;
  qualityError: unknown;
  uploadPending: boolean;
  uploadError: unknown;
  canCommit: boolean;
  onMappingChange: (key: FieldKey, value: string) => void;
  onAccountChange: (accountId: number) => void;
  onSkipCategoriesChange: (checked: boolean) => void;
  onCommit: () => void;
}) {
  const { t } = useT();
  const customWarnings = preview ? buildCustomWarnings(mapping, t) : [];
  const busy = previewPending || qualityPending || uploadPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[90vh] w-[calc(100vw-1.5rem)] max-w-6xl flex-col gap-0 overflow-hidden p-0">
        <DialogHeader className="shrink-0 border-b px-6 py-4">
          <DialogTitle>{t("imports.reviewTitle")}</DialogTitle>
          <DialogDescription className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="max-w-xl truncate">
              {file?.name ?? t("imports.title")}
            </span>
            {preview ? (
              <>
                <span aria-hidden="true">·</span>
                <span>
                  {t("imports.fileRows", {
                    rows: preview.quality_report.total_rows,
                  })}
                </span>
                <Badge variant="outline">
                  {preview.detected_source ?? t("imports.customMapping")}
                </Badge>
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
            <div className="overflow-hidden rounded-lg border">
              <div className="grid gap-5 p-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:items-start">
                <section className="grid gap-2">
                  <Label htmlFor="import-account">{t("imports.account")}</Label>
                  <AccountSelect
                    id="import-account"
                    value={accountId}
                    onChange={onAccountChange}
                    disabled={busy}
                  />
                </section>
                <ImportQualityPanel report={preview.quality_report} />
              </div>

              {!preview.detected_source ? (
                <div className="border-t px-4 py-3">
                  <ColumnMappingSection
                    preview={preview}
                    mapping={mapping}
                    customWarnings={customWarnings}
                    qualityPending={qualityPending}
                    qualityError={qualityError}
                    onMappingChange={onMappingChange}
                  />
                </div>
              ) : null}

              <div className="border-t px-4 py-3">
                <PreviewRowsSection preview={preview} mapping={mapping} />
              </div>
            </div>
          ) : null}

          {uploadError ? (
            <div className="mt-4">
              <InlineError
                message={`${t("imports.error")}: ${(uploadError as Error).message}`}
              />
            </div>
          ) : null}

        </div>

        <DialogFooter className="grid shrink-0 gap-4 border-t bg-muted/20 px-6 py-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
          <TooltipProvider delayDuration={150}>
            <label className="flex w-fit cursor-pointer select-none items-center gap-2.5 text-sm font-medium">
              <Checkbox
                id="skip-categories-checkbox"
                checked={skipCategories}
                onCheckedChange={(value) =>
                  onSkipCategoriesChange(value === true)
                }
                disabled={busy}
              />
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="cursor-help">
                    {t("imports.skipCategories")}
                  </span>
                </TooltipTrigger>
                <TooltipContent className="max-w-80">
                  {t("imports.skipCategoriesHelp")}
                </TooltipContent>
              </Tooltip>
            </label>
          </TooltipProvider>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={busy}
            >
              {t("common.cancel")}
            </Button>
            <Button onClick={onCommit} disabled={!canCommit} className="min-w-32">
              {busy ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Upload className="mr-2 h-4 w-4" />
              )}
              {t("imports.upload")}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ColumnMappingSection({
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
  const fieldSpecs = fieldSpecsFromPreview(preview);
  const requiredComplete = fieldSpecs
    .filter((spec) => spec.required)
    .every((spec) => Boolean(mapping[spec.key]));

  return (
    <DisclosureSection
      title={t("imports.columnMap.title")}
      summary={t(
        requiredComplete
          ? "imports.columnMap.ready"
          : "imports.columnMap.incomplete",
      )}
      defaultOpen={!requiredComplete || Boolean(qualityError)}
    >
      <div className="space-y-3">
        {qualityPending ? (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            {t("common.loading")}
          </div>
        ) : null}

        <TooltipProvider delayDuration={150}>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {fieldSpecs.map((spec) => {
              const { key, required, recommended } = spec;
              const labelKey: TranslationKey = `imports.field.${key}` as TranslationKey;
              const hint = t(fieldHintKey(key));
              return (
                <label key={key} className="grid gap-1.5 text-sm">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="w-fit cursor-help font-medium">
                        {t(labelKey)}
                        {required ? (
                          <span
                            className="text-destructive"
                            aria-label={t("imports.required")}
                          >
                            {" "}*
                          </span>
                        ) : null}
                      </span>
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
    </DisclosureSection>
  );
}

type PreviewColumn = {
  key: string;
  sourceHeader: string;
  label: string;
  mapped: boolean;
};

function PreviewRowsSection({
  preview,
  mapping,
}: {
  preview: ImportPreview;
  mapping: Record<FieldKey, string>;
}) {
  const { t } = useT();
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(5);
  const columns = buildPreviewColumns(preview, mapping, t);
  const maxPage = Math.max(
    0,
    Math.ceil(preview.sample_rows.length / pageSize) - 1,
  );
  const currentPage = Math.min(page, maxPage);
  const pageStart = currentPage * pageSize;
  const visibleRows = preview.sample_rows.slice(pageStart, pageStart + pageSize);

  return (
    <DisclosureSection
      title={t("imports.rowsPreview.title")}
      summary={t("imports.previewRows", {
        shown: preview.sample_rows.length,
        total: preview.quality_report.total_rows,
      })}
      defaultOpen
    >
      <div className="overflow-hidden rounded-md border">
        <div className="overflow-x-auto">
          <table className="min-w-full caption-bottom text-sm">
            <thead className="bg-muted/30">
              <tr className="border-b">
                {columns.map((column) => (
                  <th
                    key={column.key}
                    className="h-12 whitespace-nowrap px-3 text-left align-middle font-medium text-muted-foreground"
                  >
                    <span className="flex min-h-8 flex-col justify-center">
                      <span className={column.mapped ? "text-foreground" : undefined}>
                        {column.label}
                      </span>
                      {column.mapped ? (
                        <span className="text-[11px] font-normal text-muted-foreground">
                          {column.sourceHeader}
                        </span>
                      ) : null}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((row, index) => (
                <tr
                  key={`${currentPage}:${index}`}
                  className="border-b transition-colors last:border-0 hover:bg-muted/30"
                >
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className="max-w-64 whitespace-nowrap p-3 align-middle text-xs"
                      title={row[column.sourceHeader] ?? ""}
                    >
                      <span className="block truncate">
                        {row[column.sourceHeader] ?? ""}
                      </span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <TablePagination
          page={currentPage}
          pageSize={pageSize}
          currentCount={visibleRows.length}
          total={preview.sample_rows.length}
          pageSizeOptions={[5, 10, 25]}
          onPageChange={setPage}
          onPageSizeChange={(nextPageSize) => {
            setPageSize(nextPageSize);
            setPage(0);
          }}
        />
      </div>
    </DisclosureSection>
  );
}

function buildPreviewColumns(
  preview: ImportPreview,
  mapping: Record<FieldKey, string>,
  t: (key: TranslationKey) => string,
): PreviewColumn[] {
  const mappedHeaders = new Set<string>();
  const mappedColumns: PreviewColumn[] = [];

  for (const field of LOGICAL_FIELDS) {
    const sourceHeader = mapping[field.key];
    if (
      !sourceHeader ||
      !preview.headers.includes(sourceHeader) ||
      mappedHeaders.has(sourceHeader)
    ) {
      continue;
    }
    mappedHeaders.add(sourceHeader);
    mappedColumns.push({
      key: `mapped:${field.key}:${sourceHeader}`,
      sourceHeader,
      label: t(`imports.field.${field.key}` as TranslationKey),
      mapped: true,
    });
  }

  const sourceColumns = preview.headers
    .filter((header) => !mappedHeaders.has(header))
    .map((header) => ({
      key: `source:${header}`,
      sourceHeader: header,
      label: header,
      mapped: false,
    }));

  return [...mappedColumns, ...sourceColumns];
}

function DisclosureSection({
  title,
  summary,
  defaultOpen = false,
  children,
}: {
  title: string;
  summary: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [expanded, setExpanded] = useState(defaultOpen);
  return (
    <section>
      <button
        type="button"
        className="flex w-full items-center justify-between gap-4 py-1.5 text-left transition-colors hover:text-foreground"
        aria-expanded={expanded}
        onClick={() => setExpanded((current) => !current)}
      >
        <span className="min-w-0">
          <span className="block text-sm font-semibold">{title}</span>
          <span className="block truncate text-xs text-muted-foreground">
            {summary}
          </span>
        </span>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${expanded ? "rotate-180" : ""}`}
        />
      </button>
      {expanded ? <div className="pt-3">{children}</div> : null}
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
