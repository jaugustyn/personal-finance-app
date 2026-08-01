"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, FileSpreadsheet, Landmark, Loader2 } from "lucide-react";
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
import { invalidateImportData, queryKeys } from "@/lib/query-keys";
import { Dropzone } from "./_components/dropzone";
import { ImportPreviewDialog } from "./_components/import-preview-dialog";
import { ImportsHistory } from "./_components/imports-history";
import { SuccessBox } from "./_components/success-box";
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
  const preferredAccountId = useRef<number | null>(null);
  const [mapping, setMapping] = useState<Record<FieldKey, string>>(
    {} as Record<FieldKey, string>,
  );
  const [skipCategories, setSkipCategories] = useState(false);
  const [accountId, setAccountId] = useState<number | null>(null);
  const accountsQuery = useQuery({
    queryKey: queryKeys.accounts.list(),
    queryFn: () => api.accounts(),
  });
  const selectedAccount = accountsQuery.data?.find(
    (account) => account.id === accountId,
  );

  /* eslint-disable react-hooks/set-state-in-effect -- initialize the import context from the client URL after hydration */
  useEffect(() => {
    const nextAccountId = parsePositiveId(
      new URLSearchParams(window.location.search).get("account_id"),
    );
    preferredAccountId.current = nextAccountId;
    setAccountId(nextAccountId);
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

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
      const nextAccountId =
        preferredAccountId.current ?? p.suggested_account_id;
      if (nextAccountId !== null) {
        preferredAccountId.current = nextAccountId;
        setAccountId(nextAccountId);
      }
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const qualityPreviewMut = useMutation({
    mutationFn: (args: {
      file: File;
      source: string;
      columnMap: Record<string, string> | null;
      accountId: number;
      previewKey: string;
    }) =>
      api.previewImport(args.file, {
        source: args.source,
        columnMap: args.columnMap,
        accountId: args.accountId,
      }),
    onSuccess: (p, args) => {
      if (latestMappingPreviewKey.current === args.previewKey) {
        setPreview(p);
      }
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const uploadMut = useMutation({
    mutationFn: (args: {
      file: File;
      source: string | null;
      columnMap: Record<string, string> | null;
      skipCategories?: boolean;
      accountId: number;
    }) =>
      api.uploadImport(args.file, {
        source: args.source,
        columnMap: args.columnMap,
        skipCategories: args.skipCategories,
        accountId: args.accountId,
      }),
    onSuccess: () => {
      void invalidateImportData(qc);
      setFile(null);
      setPreview(null);
      latestMappingPreviewKey.current = null;
      setMapping({} as Record<FieldKey, string>);
      setSkipCategories(false);
      qualityPreviewMut.reset();
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
    setAccountId(preferredAccountId.current);
    uploadMut.reset();
    qualityPreviewMut.reset();
    if (f) previewMut.mutate(f);
  };

  const onCommit = () => {
    if (!file || accountId === null) return;
    setPreviewOpen(false);
    if (preview?.detected_source) {
      uploadMut.mutate({
        file,
        source: preview.detected_source,
        columnMap: null,
        skipCategories,
        accountId,
      });
    } else {
      const cleaned = cleanImportMapping(mapping);
      uploadMut.mutate({
        file,
        source: "generic",
        columnMap: cleaned,
        skipCategories,
        accountId,
      });
    }
  };

  const updateMapping = (key: FieldKey, value: string) => {
    const next = {
      ...mapping,
      [key]: value === "none" ? "" : value,
    };
    setMapping(next);
    runAccountAwarePreview(accountId, next, preview);
  };

  function runAccountAwarePreview(
    nextAccountId: number | null,
    nextMapping: Record<FieldKey, string>,
    currentPreview: ImportPreview | null,
  ) {
    if (!file || nextAccountId === null || !currentPreview) return;
    const cleaned = cleanImportMapping(nextMapping);
    const source = currentPreview.detected_source ?? "generic";
    if (source === "generic" && (!cleaned.date || !cleaned.amount)) {
      latestMappingPreviewKey.current = null;
      return;
    }
    const columnMap = source === "generic" ? cleaned : null;
    const previewKey = JSON.stringify({ source, columnMap, accountId: nextAccountId });
    latestMappingPreviewKey.current = previewKey;
    qualityPreviewMut.mutate({
      file,
      source,
      columnMap,
      accountId: nextAccountId,
      previewKey,
    });
  }

  useEffect(() => {
    if (
      accountId !== null &&
      preview !== null &&
      preview.account_id !== accountId
    ) {
      runAccountAwarePreview(accountId, mapping, preview);
    }
    // The selected account and preview identity define when revalidation is needed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId, file, preview?.account_id]);

  const requiredOk = !!mapping.date && !!mapping.amount && !!mapping.merchant;
  const canCommit =
    !!file &&
    !uploadMut.isPending &&
    accountId !== null &&
    preview?.account_id === accountId &&
    !qualityPreviewMut.isPending &&
    !qualityPreviewMut.error &&
    (preview?.quality_report.blocking_issues ?? 0) === 0 &&
    (preview?.detected_source ? true : requiredOk);
  const showPreviewStatus =
    previewMut.isPending || Boolean(previewMut.error) || Boolean(preview);
  const showStatusPanel = showPreviewStatus || Boolean(uploadMut.data);

  return (
    <div className="space-y-5">
      <PageHeader title={t("imports.title")} />

      <Card>
        <CardContent className="pt-6">
          {selectedAccount ? (
            <div className="mb-4 flex items-center gap-2 text-sm">
              <Landmark className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">
                {t("imports.selectedAccount")}:
              </span>
              <span className="font-medium">{selectedAccount.name}</span>
            </div>
          ) : null}
          <div
            className={
              showStatusPanel
                ? "grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(22rem,1fr)]"
                : undefined
            }
          >
            <Dropzone
              key={uploadMut.data?.import_id ?? "empty"}
              onFile={onChooseFile}
              label={
                uploadMut.isPending
                  ? t("imports.uploading")
                  : file
                    ? t("imports.replaceFile")
                    : t("imports.dropzone")
              }
              disabled={previewMut.isPending || uploadMut.isPending}
            />

            {uploadMut.data ? (
              <SuccessBox summary={uploadMut.data} />
            ) : showPreviewStatus ? (
              <div className="flex min-h-32 min-w-0 flex-col justify-between rounded-md border bg-muted/15 p-4">
                <div className="flex min-w-0 items-start gap-3">
                  {previewMut.isPending || uploadMut.isPending ? (
                    <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
                  ) : previewMut.error ? (
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
                  ) : (
                    <FileSpreadsheet className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                  )}
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">
                      {file?.name ?? t("imports.preview")}
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {uploadMut.isPending
                        ? t("imports.uploading")
                        : previewMut.isPending
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
                  size="sm"
                  className="self-end"
                  onClick={() => setPreviewOpen(true)}
                  disabled={
                    uploadMut.isPending || (!preview && !previewMut.error)
                  }
                >
                  {t("imports.openPreview")}
                </Button>
              </div>
            ) : null}
          </div>
        </CardContent>
      </Card>

      <ImportPreviewDialog
        open={previewOpen}
        onOpenChange={setPreviewOpen}
        file={file}
        preview={preview}
        mapping={mapping}
        accountId={accountId}
        skipCategories={skipCategories}
        previewPending={previewMut.isPending}
        previewError={previewMut.error}
        qualityPending={qualityPreviewMut.isPending}
        qualityError={qualityPreviewMut.error}
        uploadPending={uploadMut.isPending}
        uploadError={uploadMut.error}
        canCommit={canCommit}
        onMappingChange={updateMapping}
        onAccountChange={(nextAccountId) => {
          preferredAccountId.current = nextAccountId;
          setAccountId(nextAccountId);
        }}
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

function parsePositiveId(value: string | null): number | null {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
}
