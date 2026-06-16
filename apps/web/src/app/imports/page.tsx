"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Upload,
  FileSpreadsheet,
  AlertCircle,
  CheckCircle2,
  HelpCircle,
  Loader2,
  Trash2,
  History,
  Receipt,
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
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { PageHeader } from "@/components/page-header";
import { useConfirm } from "@/components/confirm-dialog";
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
import { transactionsHref } from "@/lib/transaction-links";

const LOGICAL_FIELDS = [
  { key: "date", required: true, recommended: false, description: "" },
  { key: "amount", required: true, recommended: false, description: "" },
  { key: "currency", required: false, recommended: false, description: "" },
  { key: "merchant", required: false, recommended: true, description: "" },
  { key: "title", required: false, recommended: true, description: "" },
  { key: "category", required: false, recommended: false, description: "" },
  { key: "external_id", required: false, recommended: false, description: "" },
] as const;

type FieldKey = (typeof LOGICAL_FIELDS)[number]["key"];
type FieldSpec = {
  key: FieldKey;
  required: boolean;
  recommended: boolean;
  description: string;
};

const LOGICAL_FIELD_KEYS = new Set<string>(LOGICAL_FIELDS.map((field) => field.key));

const fieldSpecsFromPreview = (preview: ImportPreview | null): FieldSpec[] => {
  if (!preview?.field_specs?.length) return [...LOGICAL_FIELDS];
  return preview.field_specs
    .filter((spec) => LOGICAL_FIELD_KEYS.has(spec.key))
    .map((spec) => ({
      key: spec.key as FieldKey,
      required: spec.required,
      recommended: spec.recommended,
      description: spec.description,
    }));
};

const buildCustomWarnings = (
  mapping: Record<FieldKey, string>,
  t: (key: TranslationKey) => string,
) => {
  const warnings: string[] = [];
  if (!mapping.merchant && !mapping.title) {
    warnings.push(t("imports.warning.merchantOrTitle"));
  }
  if (!mapping.currency) {
    warnings.push(t("imports.warning.currencyDefault"));
  }
  if (!mapping.external_id) {
    warnings.push(t("imports.warning.externalId"));
  }
  return Array.from(new Set(warnings));
};

const fieldHintKey = (key: FieldKey): TranslationKey =>
  `imports.fieldHint.${key}` as TranslationKey;

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
      toast.success(t("toast.imported"));
    },
    onError: () => toast.error(t("toast.error")),
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
  const customWarnings = preview
    ? buildCustomWarnings(mapping, t)
    : [];
  const canCommit =
    !!file &&
    !uploadMut.isPending &&
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
        accept=".csv,.tsv,.txt,text/csv,text/plain,text/tab-separated-values"
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
  const confirm = useConfirm();
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
      toast.success(t("toast.deleted"));
    },
    onError: () => toast.error(t("toast.error")),
  });

  const onDelete = async (row: ImportHistoryRow) => {
    const ok = await confirm({
      title: t("imports.history.deleteConfirm", {
        filename: row.filename,
        n: row.inserted,
      }),
      destructive: true,
    });
    if (ok) deleteMut.mutate(row.id);
  };
  const columns: DataTableColumn<ImportHistoryRow>[] = [
    {
      id: "created_at",
      header: t("imports.history.created"),
      sortValue: (row) => new Date(row.created_at).getTime(),
      className: "text-xs whitespace-nowrap text-muted-foreground",
      cell: (row) => new Date(row.created_at).toLocaleString(),
    },
    {
      id: "filename",
      header: t("imports.history.filename"),
      sortValue: (row) => row.filename,
      className: "font-medium",
      cell: (row) => row.filename,
    },
    {
      id: "source",
      header: t("imports.history.source"),
      sortValue: (row) => row.source,
      cell: (row) => <Badge variant="outline">{row.source}</Badge>,
    },
    {
      id: "total_rows",
      header: t("imports.history.totalRows"),
      align: "right",
      className: "tabular-nums",
      sortValue: (row) => row.total_rows,
      cell: (row) => row.total_rows,
    },
    {
      id: "inserted",
      header: t("imports.history.inserted"),
      align: "right",
      className: "tabular-nums text-positive",
      sortValue: (row) => row.inserted,
      cell: (row) => row.inserted,
    },
    {
      id: "duplicates",
      header: t("imports.history.duplicates"),
      align: "right",
      className: "tabular-nums text-muted-foreground",
      sortValue: (row) => row.duplicates,
      cell: (row) => row.duplicates,
    },
    {
      id: "actions",
      header: "",
      align: "right",
      headerClassName: "w-24",
      className: "w-24",
      cell: (row) => (
        <div className="flex justify-end gap-1">
          <Button
            size="icon"
            variant="ghost"
            asChild
            aria-label={t("imports.history.openTransactions")}
          >
            <Link href={transactionsHref({ import_id: row.id })}>
              <Receipt className="h-4 w-4" />
            </Link>
          </Button>
          <Button
            size="icon"
            variant="ghost"
            onClick={() => onDelete(row)}
            disabled={deleteMut.isPending}
            aria-label={t("common.delete")}
          >
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <History className="h-4 w-4" /> {t("imports.history.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <DataTable
          columns={columns}
          data={imports}
          rowKey={(row) => row.id}
          isLoading={isLoading}
          emptyTitle={t("imports.history.empty")}
          initialSort={{ id: "created_at", dir: "desc" }}
          className="rounded-none border-0"
        />
      </CardContent>
    </Card>
  );
}
