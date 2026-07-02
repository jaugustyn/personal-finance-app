"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Upload,
  FileSpreadsheet,
  AlertCircle,
  HelpCircle,
  Loader2,
} from "lucide-react";
import {
  api,
  type ImportPreview,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/page-header";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { toast } from "sonner";
import { useT, type TranslationKey } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";
import { Dropzone } from "./_components/dropzone";
import { ImportQualityPanel } from "./_components/import-quality-panel";
import { ImportsHistory } from "./_components/imports-history";
import { SuccessBox } from "./_components/success-box";
import {
  buildCustomWarnings,
  fieldHintKey,
  fieldSpecsFromPreview,
  LOGICAL_FIELDS,
  type FieldKey,
} from "./_lib/import-fields";

export default function ImportsPage() {
  const { t } = useT();
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [mapping, setMapping] = useState<Record<FieldKey, string>>(
    {} as Record<FieldKey, string>,
  );
  const [skipCategories, setSkipCategories] = useState(false);

  const previewMut = useMutation({
    mutationFn: (f: File) => api.previewImport(f),
    onSuccess: (p) => {
      setPreview(p);
      // Seed mapping from auto-detection.
      const seeded = {} as Record<FieldKey, string>;
      for (const { key } of LOGICAL_FIELDS) {
        const v = p.detected_mapping[key];
        if (v) seeded[key] = v;
      }
      setMapping(seeded);
    },
  });

  const uploadMut = useMutation({
    mutationFn: (args: {
      file: File;
      source: string | null;
      columnMap: Record<string, string> | null;
      skipCategories?: boolean;
    }) =>
      api.uploadImport(args.file, {
        source: args.source,
        columnMap: args.columnMap,
        skipCategories: args.skipCategories,
      }),
    onSuccess: () => {
      qc.invalidateQueries();
      toast.success(t("toast.imported"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const onChooseFile = (f: File | null) => {
    setFile(f);
    setPreview(null);
    setMapping({} as Record<FieldKey, string>);
    setSkipCategories(false);
    uploadMut.reset();
    if (f) previewMut.mutate(f);
  };

  const onCommit = () => {
    if (!file) return;
    if (preview?.detected_source) {
      uploadMut.mutate({
        file,
        source: preview.detected_source,
        columnMap: null,
        skipCategories,
      });
    } else {
      const cleaned: Record<string, string> = {};
      for (const [k, v] of Object.entries(mapping)) {
        if (v) cleaned[k] = v;
      }
      uploadMut.mutate({
        file,
        source: "generic",
        columnMap: cleaned,
        skipCategories,
      });
    }
  };

  const requiredOk = !!mapping.date && !!mapping.amount;
  const customWarnings = preview
    ? buildCustomWarnings(mapping, t)
    : [];
  const canCommit =
    !!file &&
    !uploadMut.isPending &&
    (preview?.quality_report.blocking_issues ?? 0) === 0 &&
    (preview?.detected_source ? true : requiredOk);

  return (
    <div className="space-y-6">
      <PageHeader title={t("imports.title")} />

      <Card>
        <CardContent className="pt-6">
          <Dropzone
            onFile={onChooseFile}
            label={file ? file.name : t("imports.dropzone")}
            disabled={previewMut.isPending || uploadMut.isPending}
          />
        </CardContent>
      </Card>

      {previewMut.isPending && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> {t("common.loading")}
        </div>
      )}

      {previewMut.error && (
        <div className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" />
          {(previewMut.error as Error).message}
        </div>
      )}

      {preview && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FileSpreadsheet className="h-4 w-4" /> {t("imports.preview")}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-2 text-sm">
              {preview.detected_source ? (
                <>
                  <span className="text-muted-foreground">
                    {t("imports.detectedSource")}:
                  </span>
                  <Badge>{preview.detected_source}</Badge>
                </>
              ) : (
                <span className="text-muted-foreground">
                  {t("imports.detectedNone")}
                </span>
              )}
              <span className="ml-auto text-xs text-muted-foreground">
                {preview.encoding} · &quot;{preview.delimiter}&quot;
              </span>
            </div>

            <ImportQualityPanel report={preview.quality_report} />

            <div className="overflow-x-auto rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    {preview.headers.map((h) => (
                      <TableHead key={h}>{h}</TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {preview.sample_rows.map((row, i) => (
                    <TableRow key={i}>
                      {preview.headers.map((h) => (
                        <TableCell key={h} className="text-xs">
                          {row[h] ?? ""}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {!preview.detected_source && (
              <div className="space-y-3">
                <div>
                  <h3 className="text-sm font-semibold">
                    {t("imports.columnMap.title")}
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    {t("imports.columnMap.help")}
                  </p>
                </div>
                <TooltipProvider delayDuration={150}>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {fieldSpecsFromPreview(preview).map((spec) => {
                      const { key, required, recommended } = spec;
                      const labelKey: TranslationKey =
                        `imports.field.${key}` as TranslationKey;
                      const hint = t(fieldHintKey(key));
                      return (
                        <label key={key} className="flex flex-col gap-1 text-sm">
                          <span className="flex items-center gap-1.5 font-medium">
                            <span>
                              {t(labelKey)}
                              {required && (
                                <span
                                  className="text-destructive"
                                  aria-label={t("imports.required")}
                                >
                                  {" "}
                                  *
                                </span>
                              )}
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
                            onValueChange={(v) =>
                              setMapping((m) => ({
                                ...m,
                                [key]: v === "none" ? "" : v,
                              }))
                            }
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="none">
                                {t("imports.fieldNone")}
                              </SelectItem>
                              {preview.headers.map((h) => (
                                <SelectItem key={h} value={h}>
                                  {h}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </label>
                      );
                    })}
                  </div>
                </TooltipProvider>
                {customWarnings.length > 0 && (
                  <div className="space-y-1 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-800 dark:text-amber-300">
                    {customWarnings.map((warning) => (
                      <p key={warning}>{warning}</p>
                    ))}
                  </div>
                )}
              </div>
            )}

            {uploadMut.error && (
              <div className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
                <AlertCircle className="h-4 w-4" />
                {t("imports.error")}: {(uploadMut.error as Error).message}
              </div>
            )}

            {uploadMut.data && <SuccessBox summary={uploadMut.data} />}

            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-t pt-4">
              <label className="flex items-start gap-2.5 text-sm cursor-pointer select-none text-muted-foreground hover:text-foreground transition-colors max-w-xl">
                <Checkbox
                  id="skip-categories-checkbox"
                  checked={skipCategories}
                  onCheckedChange={(c) => setSkipCategories(c === true)}
                  disabled={uploadMut.isPending}
                  className="mt-1"
                />
                <div className="grid gap-1">
                  <span className="font-semibold text-foreground text-sm leading-none">
                    {t("imports.skipCategories")}
                  </span>
                  <span className="text-xs text-muted-foreground leading-normal">
                    {t("imports.skipCategoriesHelp")}
                  </span>
                </div>
              </label>

              <Button onClick={onCommit} disabled={!canCommit} className="sm:self-end">
                {uploadMut.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Upload className="mr-2 h-4 w-4" />
                )}
                {t("imports.upload")}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <ImportsHistory />
    </div>
  );
}
