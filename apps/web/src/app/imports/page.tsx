"use client";

import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, FileSpreadsheet, Loader2 } from "lucide-react";
import {
  api,
  type ImportPreview,
} from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/page-header";
import { toast } from "sonner";
import { useT } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";
import { Dropzone } from "./_components/dropzone";
import { ImportPreviewDialog } from "./_components/import-preview-dialog";
import { ImportsHistory } from "./_components/imports-history";
import {
  LOGICAL_FIELDS,
  type FieldKey,
} from "./_lib/import-fields";

export default function ImportsPage() {
  const { t } = useT();
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const latestMappingPreviewKey = useRef<string | null>(null);
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

  const mappingPreviewMut = useMutation({
    mutationFn: (args: {
      file: File;
      columnMap: Record<string, string>;
      mappingKey: string;
    }) =>
      api.previewImport(args.file, {
        source: "generic",
        columnMap: args.columnMap,
      }),
    onSuccess: (p, args) => {
      if (latestMappingPreviewKey.current === args.mappingKey) {
        setPreview(p);
      }
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
    setPreviewOpen(!!f);
    latestMappingPreviewKey.current = null;
    setMapping({} as Record<FieldKey, string>);
    setSkipCategories(false);
    uploadMut.reset();
    mappingPreviewMut.reset();
    if (f) previewMut.mutate(f);
  };

  const onCommit = () => {
    if (!file) return;
    setPreviewOpen(false);
    if (preview?.detected_source) {
      uploadMut.mutate({
        file,
        source: preview.detected_source,
        columnMap: null,
        skipCategories,
      });
    } else {
      const cleaned = cleanImportMapping(mapping);
      uploadMut.mutate({
        file,
        source: "generic",
        columnMap: cleaned,
        skipCategories,
      });
    }
  };

  const updateMapping = (key: FieldKey, value: string) => {
    const next = {
      ...mapping,
      [key]: value === "none" ? "" : value,
    };
    setMapping(next);
    refreshGenericQuality(next);
  };

  const refreshGenericQuality = (nextMapping: Record<FieldKey, string>) => {
    if (!file || preview?.detected_source) return;
    const cleaned = cleanImportMapping(nextMapping);
    if (!cleaned.date || !cleaned.amount) {
      latestMappingPreviewKey.current = null;
      return;
    }
    const mappingKey = JSON.stringify(cleaned);
    latestMappingPreviewKey.current = mappingKey;
    mappingPreviewMut.mutate({ file, columnMap: cleaned, mappingKey });
  };

  const requiredOk = !!mapping.date && !!mapping.amount && !!mapping.merchant;
  const canCommit =
    !!file &&
    !uploadMut.isPending &&
    !mappingPreviewMut.isPending &&
    !mappingPreviewMut.error &&
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

      {(previewMut.isPending || previewMut.error || preview) && (
        <Card>
          <CardContent className="flex flex-col gap-3 pt-6 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex min-w-0 items-center gap-3">
              {previewMut.isPending ? (
                <Loader2 className="h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
              ) : previewMut.error ? (
                <AlertCircle className="h-4 w-4 shrink-0 text-destructive" />
              ) : (
                <FileSpreadsheet className="h-4 w-4 shrink-0 text-muted-foreground" />
              )}
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">
                  {file?.name ?? t("imports.preview")}
                </p>
                <p className="text-xs text-muted-foreground">
                  {previewMut.isPending
                    ? t("common.loading")
                    : previewMut.error
                      ? (previewMut.error as Error).message
                      : t("imports.previewReady", {
                          rows: preview?.quality_report.total_rows ?? 0,
                        })}
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              onClick={() => setPreviewOpen(true)}
              disabled={!preview && !previewMut.error}
            >
              {t("imports.openPreview")}
            </Button>
          </CardContent>
        </Card>
      )}

      <ImportPreviewDialog
        open={previewOpen}
        onOpenChange={setPreviewOpen}
        file={file}
        preview={preview}
        mapping={mapping}
        skipCategories={skipCategories}
        previewPending={previewMut.isPending}
        previewError={previewMut.error}
        qualityPending={mappingPreviewMut.isPending}
        qualityError={mappingPreviewMut.error}
        uploadPending={uploadMut.isPending}
        uploadError={uploadMut.error}
        uploadData={uploadMut.data}
        canCommit={canCommit}
        onMappingChange={updateMapping}
        onSkipCategoriesChange={setSkipCategories}
        onCommit={onCommit}
      />

      <ImportsHistory />
    </div>
  );
}

function cleanImportMapping(mapping: Record<FieldKey, string>): Record<string, string> {
  const cleaned: Record<string, string> = {};
  for (const [key, value] of Object.entries(mapping)) {
    if (value) cleaned[key] = value;
  }
  return cleaned;
}
