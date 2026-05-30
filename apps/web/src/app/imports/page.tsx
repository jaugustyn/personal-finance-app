"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Upload,
  FileSpreadsheet,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Trash2,
  History,
} from "lucide-react";
import {
  api,
  type ImportPreview,
  type ImportSummary,
  type ImportHistoryRow,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useT, type TranslationKey } from "@/lib/i18n";

const LOGICAL_FIELDS = [
  { key: "date", required: true },
  { key: "amount", required: true },
  { key: "currency", required: false },
  { key: "merchant", required: false },
  { key: "title", required: false },
  { key: "category", required: false },
  { key: "external_id", required: false },
] as const;

type FieldKey = (typeof LOGICAL_FIELDS)[number]["key"];

export default function ImportsPage() {
  const { t } = useT();
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [mapping, setMapping] = useState<Record<FieldKey, string>>(
    {} as Record<FieldKey, string>,
  );

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
    }) =>
      api.uploadImport(args.file, {
        source: args.source,
        columnMap: args.columnMap,
      }),
    onSuccess: () => {
      qc.invalidateQueries();
    },
  });

  const onChooseFile = (f: File | null) => {
    setFile(f);
    setPreview(null);
    setMapping({} as Record<FieldKey, string>);
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
      });
    } else {
      const cleaned: Record<string, string> = {};
      for (const [k, v] of Object.entries(mapping)) {
        if (v) cleaned[k] = v;
      }
      uploadMut.mutate({ file, source: "generic", columnMap: cleaned });
    }
  };

  const requiredOk = !!mapping.date && !!mapping.amount;
  const canCommit =
    !!file &&
    !uploadMut.isPending &&
    (preview?.detected_source ? true : requiredOk);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {t("imports.title")}
        </h1>
      </div>

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
                <div className="grid gap-3 sm:grid-cols-2">
                  {LOGICAL_FIELDS.map(({ key, required }) => {
                    const labelKey: TranslationKey =
                      `imports.field.${key}` as TranslationKey;
                    return (
                      <label key={key} className="flex flex-col gap-1 text-sm">
                        <span className="font-medium">
                          {t(labelKey)}
                          {required && (
                            <span className="text-destructive"> *</span>
                          )}
                        </span>
                        <select
                          value={mapping[key] ?? ""}
                          onChange={(e) =>
                            setMapping((m) => ({ ...m, [key]: e.target.value }))
                          }
                          className="h-9 rounded-md border border-input bg-transparent px-2 text-sm"
                        >
                          <option value="">{t("imports.fieldNone")}</option>
                          {preview.headers.map((h) => (
                            <option key={h} value={h}>
                              {h}
                            </option>
                          ))}
                        </select>
                      </label>
                    );
                  })}
                </div>
              </div>
            )}

            {uploadMut.error && (
              <div className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
                <AlertCircle className="h-4 w-4" />
                {t("imports.error")}: {(uploadMut.error as Error).message}
              </div>
            )}

            {uploadMut.data && <SuccessBox summary={uploadMut.data} />}

            <div className="flex justify-end">
              <Button onClick={onCommit} disabled={!canCommit}>
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

function Dropzone({
  onFile,
  label,
  disabled,
}: {
  onFile: (f: File | null) => void;
  label: string;
  disabled?: boolean;
}) {
  const [hover, setHover] = useState(false);
  return (
    <label
      onDragOver={(e) => {
        e.preventDefault();
        setHover(true);
      }}
      onDragLeave={() => setHover(false)}
      onDrop={(e) => {
        e.preventDefault();
        setHover(false);
        const f = e.dataTransfer.files?.[0];
        if (f) onFile(f);
      }}
      className={`flex h-32 cursor-pointer flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed text-sm transition-colors ${
        hover ? "border-primary bg-primary/5" : "border-muted-foreground/30"
      } ${disabled ? "pointer-events-none opacity-50" : ""}`}
    >
      <Upload className="h-6 w-6 text-muted-foreground" />
      <span className="text-muted-foreground">{label}</span>
      <input
        type="file"
        accept=".csv,text/csv"
        className="hidden"
        onChange={(e) => onFile(e.target.files?.[0] ?? null)}
      />
    </label>
  );
}

function SuccessBox({ summary }: { summary: ImportSummary }) {
  const { t } = useT();
  return (
    <div className="flex items-center gap-2 rounded-md border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm text-emerald-700 dark:text-emerald-400">
      <CheckCircle2 className="h-4 w-4" />
      {t("imports.success", {
        inserted: summary.inserted,
        duplicates: summary.duplicates,
      })}
    </div>
  );
}

const IMPORTS_QUERY_KEY = ["imports", "history"] as const;

function ImportsHistory() {
  const { t } = useT();
  const qc = useQueryClient();
  const { data: imports = [], isLoading } = useQuery<ImportHistoryRow[]>({
    queryKey: IMPORTS_QUERY_KEY,
    queryFn: () => api.listImports(),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => api.deleteImport(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: IMPORTS_QUERY_KEY });
      qc.invalidateQueries({ queryKey: ["transactions"] });
      qc.invalidateQueries({ queryKey: ["overview"] });
      qc.invalidateQueries({ queryKey: ["byCategory"] });
    },
  });

  const onDelete = (row: ImportHistoryRow) => {
    const ok = window.confirm(
      t("imports.history.deleteConfirm", {
        filename: row.filename,
        n: row.inserted,
      }),
    );
    if (ok) deleteMut.mutate(row.id);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <History className="h-4 w-4" /> {t("imports.history.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <div className="flex h-24 items-center justify-center text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : imports.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted-foreground">
            {t("imports.history.empty")}
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("imports.history.created")}</TableHead>
                <TableHead>{t("imports.history.filename")}</TableHead>
                <TableHead>{t("imports.history.source")}</TableHead>
                <TableHead className="text-right">
                  {t("imports.history.totalRows")}
                </TableHead>
                <TableHead className="text-right">
                  {t("imports.history.inserted")}
                </TableHead>
                <TableHead className="text-right">
                  {t("imports.history.duplicates")}
                </TableHead>
                <TableHead className="w-12" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {imports.map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="text-muted-foreground text-xs whitespace-nowrap">
                    {new Date(row.created_at).toLocaleString()}
                  </TableCell>
                  <TableCell className="font-medium">{row.filename}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{row.source}</Badge>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {row.total_rows}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-emerald-600 dark:text-emerald-400">
                    {row.inserted}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-muted-foreground">
                    {row.duplicates}
                  </TableCell>
                  <TableCell>
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => onDelete(row)}
                      disabled={deleteMut.isPending}
                      aria-label={t("common.delete")}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
